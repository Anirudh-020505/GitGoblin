# GitGoblin learning notes: workers, concurrency, and migrations

Everything here is grounded in this repo's code and in measurements taken on this machine. Example data is labelled as such.

---

## 1. The big picture: three layers

```
 POSTGRES (jobs table)    = the to-do list, shared by everyone
        ▲ claim / complete
 WORKER PROCESS           = one running Python program (python -m gitgoblin.worker)
   └── EVENT LOOP         = its juggler
         ├── slot 0 (task) = one hand holding one to-do item
         ├── slot 1 (task)
         ├── slot 2 (task)
         └── slot 3 (task)
```

- **Postgres does not run anything.** It only stores jobs.
- **The worker is Python.** asyncio is the technique it uses to juggle several jobs.

---

## 2. Before vs after (PR #1)

```
 BEFORE (master)                            NOW (PR #1)
 web process                                web process
   webhook → whole review inline              webhook → INSERT job → 202 (~25 ms)
   GitHub hangs up at 10 s ✗                worker process (separate)
   restart = review lost ✗                    4 slots pull jobs from Postgres
   unlimited reviews at once                  restart = jobs still in Postgres ✓
```

asyncio was already there (FastAPI/uvicorn run on an event loop). What changed: **where** the review runs (a separate worker), **how many** run at once (4), and **durability** (Postgres).

Measured on the old path (your Mac → GitHub): token exchange 1,557 ms + fetch diff 1,273 ms ≈ **2.8 s before the LLM is even called**.
Measured on the new path: HMAC 0.04 ms, parse 0.05 ms, DB transaction 4–23 ms → **~25 ms per webhook**.

---

## 3. Process vs thread vs task

```
 OS
 └── PROCESS  (own memory, own PID)            ← "worker"
     └── OS THREAD  (OS can switch it anytime)
         └── EVENT LOOP
             └── TASKS  (switch only at `await`) ← "slots"
```

| | Who switches between them | When | Cost (measured here) |
|---|---|---|---|
| Process | OS | anytime | ~67 MB (our idle worker container) |
| OS thread | OS | anytime | 1,000 threads ≈ +33.9 MB (~34 KB each) |
| asyncio task | our event loop | only at `await` | 10,000 tasks ≈ +7.7 MB (~0.8 KB each), still **1** OS thread |

- **Tasks are not threads.** A task is just a paused function call (its local variables + where it stopped).
- **Workers are processes.** Slots are tasks.
- Checked: `WORKER_CONCURRENCY=1` → 2 OS threads, `=8` → 5 OS threads. Threads ≠ slots (the extras are asyncio helper threads, most likely for DNS lookups).

---

## 4. The event loop

```
 while True:
     pick a task that is ready
     run it until it hits an `await`   ← it gives up control here
     park it until its network reply arrives
```

Only **one** task runs Python code at a time, so one event loop uses **one CPU core**. That's fine for us: our tasks spend almost all their time waiting on GitHub and the LLM, and the waiting happens on *their* machines.

**How it knows a reply arrived:** it gives the operating system the list of open network connections and says "wake me when any of these has data" (kqueue on macOS, epoll on Linux).

---

## 5. `async` vs `await`

- **`async`** goes on a function **definition**. It means "this function is allowed to pause".
- **`await`** goes on a **call**. It means "pause here until the result arrives, and let others run meanwhile".

```python
async def review(pr):               # async → this function CAN pause
    diff = await get_diff(pr)       # await → pause HERE (~1.3 s), others run
    text = await ask_llm(diff)      # await → pause HERE (~3 s), others run
    await post_comment(pr, text)
```

Demo output: calling without `await`:
```
1) call without await:  got: coroutine        ← nothing ran
2) call with await:     fetching diff...  got: 'diff text'
RuntimeWarning: coroutine 'fetch_diff' was never awaited
```

| Situation | Result |
|---|---|
| `async def` with `await` inside | ✅ pauses at each `await`; other slots run |
| `await` inside a normal `def` | ❌ `SyntaxError` |
| Calling an `async def` without `await` | ❌ nothing runs; "never awaited" warning |
| `async def` with no `await` | never pauses, so never lets others run |
| Blocking call in `async def` (`time.sleep`, `requests.get`, a CPU loop) | ❌ freezes **every** slot |

**One line:** `async` marks *who* can pause; `await` marks *where* they pause.

---

## 6. One thread, many users

Demo: two users' reviews print the **same PID and the same thread**:
```
 0.0s  alice PR#12  get token  [pid=43567 thread=8720]  → await (pause)
 0.0s  bob   PR#7   get token  [pid=43567 thread=8720]  → await (pause)
 1.5s  alice PR#12  fetch diff [pid=43567 thread=8720]  → await (pause)
 1.5s  bob   PR#7   fetch diff [pid=43567 thread=8720]  → await (pause)
 2.8s  alice PR#12  ask LLM    [pid=43567 thread=8720]  → await (pause)
 2.8s  bob   PR#7   ask LLM    [pid=43567 thread=8720]  → await (pause)
 5.8s  alice PR#12  posted     [pid=43567 thread=8720]
 5.8s  bob   PR#7   posted     [pid=43567 thread=8720]
```
One after the other: **11.6 s**. Overlapping with `await`: **5.8 s**. Nothing got faster; the two waits overlapped.

**Analogy:** one waiter (the thread) serves many tables (reviews). The kitchen (GitHub, the LLM) cooks elsewhere, so the waiter never stands at the kitchen door.

| | Gets its own… | Count |
|---|---|---|
| Worker program | process | **1**, for everyone |
| Event loop | thread | **1** |
| Each job (PR review or chat reply) | task (runs in a slot) | up to **4 at a time** |
| Alice, Bob, Carol… | **nothing**; their jobs wait in the queue | — |

---

## 7. What a slot holds

**One slot = one whole job** (one PR event, from start to finish). A PR is never split across slots.

- Inside one job, steps run **in order**: token → diff → LLM → post. The two specialists are the exception: they run together via `asyncio.gather` in `review.py`.
- Across slots, different jobs **overlap** their waiting.

Example (example data): 3 users push at once.

| Job | Who | PR | Slot |
|---|---|---|---|
| 1 | alice | #12 | 0 |
| 2 | bob | #7 | 1 |
| 3 | alice | #13 | 2 |
| 4 | carol | #3 | 3 |
| 5 | bob | #8 | waits |
| 6 | carol | #4 | waits |

Slots are first-come, first-served and owned by nobody.

⚠️ **Known gaps:** two pushes to the *same* PR create two jobs that can run in two slots at once and post two reviews. One person pushing many commits can also fill the queue ahead of others.

---

## 8. Database connections

```
 worker process
 └── connection POOL (SQLAlchemy default: 5, can grow to 15)
      slot: borrow ─ claim (ms) ─ return … review runs, holds NO connection …
            borrow ─ heartbeat ─ return … borrow ─ complete ─ return
```
- One pool per process (web has its own).
- Nothing per user or per PR.
- During the slow GitHub/LLM waits a slot holds **zero** connections.

---

## 9. When slots stop helping: CPU work

Demo: one slot runs 2 s of CPU work with no `await`:
```
 0.0s alice's slot: still alive
 0.1s bob: start parsing huge diff on the CPU
        ← alice gets NOTHING for 2 seconds
 2.1s bob: done parsing
 2.1s alice's slot: still alive
```

More **processes** fix this: each one has its own event loop on its own core, so a blocked loop freezes only its own slots.

```
 total reviews at once = processes × slots
 WORKER_CONCURRENCY=8                → 1 × 8 = 8   (cheap; still 1 core)
 docker compose up --scale worker=3  → 3 × 4 = 12  (isolation, multiple cores)
```

---

## 10. Capacity: what limits reviews

| Layer | Limit | Reviews it allows |
|---|---|---|
| Our worker | 1 process × 4 slots | 4 at once (hard cap) |
| GLM model | 2 calls per review; plan concurrency not published | unknown, **likely the real bottleneck** |
| GitHub: hourly quota | 5,000 requests/hour per installation | ~2,500 reviews/hour |
| GitHub: content creation | 80/min, 500/hour | ≤ 500 reviews + replies per hour |
| Postgres, web intake | — | not a constraint |

Example: if one review takes 60 s, then 4 slots = 240 reviews/hour, and 20 simultaneous pushes finish in 5 batches (about 5 min).

---

## 11. Other stacks, compared

| Stack | "4 at once" means | Uses all cores in one process? |
|---|---|---|
| **Ours** (asyncio) | 4 tasks, 1 thread, 1 process | no; add processes |
| **Go** | 4 goroutines, scheduled across all cores | yes |
| **Celery** (default `prefork`) | 4 **child processes** (default count = number of CPU cores, prefetch 4 each) | n/a (it's already processes) |
| **RabbitMQ** | Not a worker: a broker server that pushes messages to consumers | n/a |

Things to remember about Celery: the message is acknowledged **before** the task runs by default (`task_acks_late` is off), so a crash loses the task unless you opt in. Publishing to a broker plus writing to the DB is a **dual write**; our Postgres queue avoids that because both happen in one transaction.

**Go vs Python for GitGoblin:** our work is mostly *waiting* (GitHub, LLM), and both languages wait equally well. The cost is dominated by LLM tokens. Go wins for CPU-heavy work or very high throughput; Python wins on the AI ecosystem (SDKs, Pydantic structured output, evals, DSPy/GEPA, Harness²). Correction to a common belief: Python is **not** limited to one process. Run more workers.

---

## 12. Alembic and `env.py`

### 12.1 Four similar names, four different things

| File | What it is | Who reads it |
|---|---|---|
| `.env` | Your secrets (`DATABASE_URL=…`, `LLM_API_KEY=…`) | `gitgoblin/settings.py` (pydantic-settings) |
| `.env.example` | Template listing every key, no secrets, committed | You, when setting up |
| `gitgoblin/settings.py` | Typed config classes that read env vars and `.env` | The app, the worker, **and env.py** |
| `gitgoblin/db/migrations/env.py` | Alembic's **migration environment** script. **Not** related to `.env` by name | Alembic, on every `alembic …` command |

"env" in `env.py` means *the environment migrations run in* (which DB, which tables, which driver), not environment variables.

### 12.2 What Alembic is: git for your database schema

| Git | Alembic |
|---|---|
| commit | a migration file in `gitgoblin/db/migrations/versions/` |
| commit hash | revision id, e.g. `a35533ff65a0` |
| `HEAD` | the `alembic_version` table inside Postgres |
| `git checkout` | `alembic upgrade head` / `alembic downgrade -1` |

Real value right now:
```
$ uv run alembic current
a35533ff65a0 (head)
```

### 12.3 Why env.py must exist

Alembic is generic. Out of the box it does **not** know:

1. **Which database** to connect to (our `DATABASE_URL`)
2. **What our tables should look like** (`Base.metadata` from `gitgoblin/db/models.py`)
3. **How to connect** (we use the async `asyncpg` driver; migrations themselves are plain synchronous functions)

`env.py` is the adapter where we answer those questions. Alembic runs it on **every** command.

```
 alembic upgrade head
   │ reads pyproject.toml [tool.alembic] → script_location, prepend_sys_path
   ▼
 env.py runs
   ├─ import Base.metadata          (what tables SHOULD look like)
   ├─ read DATABASE_URL via settings (WHERE the database is)
   ├─ open async engine, NullPool    (HOW to connect, one-shot)
   └─ hand the connection to Alembic
   ▼
 Alembic: alembic_version says a35533ff65a0?  → run newer versions/*.py upgrade()
                                              → update alembic_version
```

### 12.4 Our env.py, line by line

| Lines | Code | Why |
|---|---|---|
| 12 | `from gitgoblin.db.models import Base` | The table definitions autogenerate compares against |
| 13 | `from gitgoblin.settings import database_settings` | Same `DATABASE_URL` the app uses, so migrations can't target a different DB |
| 18 | `target_metadata = Base.metadata` | Without it, `--autogenerate` sees "no tables wanted" and writes empty migrations |
| 21–30 | `run_migrations_offline()` | `alembic upgrade head --sql` prints SQL instead of running it (useful for review/DBAs) |
| 33–36 | `do_run_migrations(connection)` | The actual run: a *synchronous* function, because Alembic's migration API is sync |
| 39–44 | `run_migrations_online()` | Opens an **async** engine (asyncpg), then `connection.run_sync(...)` runs the sync function on it. `NullPool` because a one-shot command shouldn't keep connections open |
| 47–50 | `if context.is_offline_mode(): … else: asyncio.run(...)` | Chooses print-SQL mode vs run-against-DB mode |

### 12.5 The two commands you'll use, with real output

**Apply migrations:** `uv run alembic upgrade head`

**See what would run (offline mode, lines 21–30):**
```sql
BEGIN;
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, ...);
CREATE TABLE webhook_deliveries (delivery_id TEXT NOT NULL, ... PRIMARY KEY (delivery_id));
CREATE TABLE jobs (id BIGSERIAL NOT NULL, kind TEXT NOT NULL, ...
    CONSTRAINT ck_jobs_status CHECK (status IN ('queued', 'running', 'done', 'failed')), ...);
CREATE INDEX ix_jobs_claimable ON jobs (run_after) WHERE status IN ('queued', 'running');
INSERT INTO alembic_version (version_num) VALUES ('a35533ff65a0');
COMMIT;
```

**Change the schema:**
```
 1. edit gitgoblin/db/models.py          (e.g. add a column)
 2. uv run alembic revision --autogenerate -m "add column x"
      env.py → compares Base.metadata (wanted) vs live DB (actual) → writes the diff
 3. READ the generated file in versions/  (autogenerate can miss renames)
 4. uv run alembic upgrade head
 5. uv run alembic check                  → "No new upgrade operations detected."
```

### 12.6 A bug we actually hit

`env.py` imports `gitgoblin`. That relies on the editable install (`_editable_impl_gitgoblin.pth` in `.venv`). The repo sits on an **iCloud-synced Desktop**, where `.venv` files get macOS's `hidden` flag, and Python 3.12 **skips hidden `.pth` files**. Result:
```
ModuleNotFoundError: No module named 'gitgoblin'
```
Fix (commit `a0f554f`): `prepend_sys_path = ["."]` under `[tool.alembic]` puts the repo root on the import path for Alembic regardless. Verified with the `.pth` deliberately hidden: `alembic current` → `a35533ff65a0 (head)`.

Still affected: other scripts run by path (e.g. `uv run python scripts/test_agents.py`) when the flag comes back. Durable fix: keep the project (or its `.venv`) outside iCloud-synced folders.

---

## 13. Glossary

| Term | Meaning |
|---|---|
| **Process** | One running program with its own PID and memory |
| **Thread** | A line of execution inside a process; the OS can switch it anytime |
| **asyncio task / coroutine** | A paused function call that resumes after an `await`; very cheap |
| **Event loop** | The loop that runs ready tasks until they `await` |
| **Slot** | One of `WORKER_CONCURRENCY` tasks in the worker, each running one job at a time |
| **Job** | One row in `jobs`: a unit of work (review a PR, reply to a mention) |
| **SKIP LOCKED** | Postgres: skip rows another transaction has locked, so workers never share a job |
| **Lease** | `locked_until`: a worker owns a job until then; if it dies, the job is reclaimable |
| **Heartbeat** | The worker extending its lease every 30 s while a job runs |
| **Fencing token** | `attempts` must still match on every write, so a stale worker can't overwrite the new owner |
| **Backoff + jitter** | Retry after 30 s, 60 s, 120 s… plus a random 0–10% |
| **Idempotent** | Doing it twice has the same effect as once |
| **Dual write** | Writing to two systems (DB + broker) that can't commit together |
| **Migration** | A versioned script that changes the database schema |
| **`env.py`** | Alembic's script that tells it which DB, which tables, and how to connect |
| **Autogenerate** | Alembic comparing models vs the live DB and writing the migration for you |
