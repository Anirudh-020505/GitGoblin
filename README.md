# GitGoblin-Dev
## Autonomous Agentic AI for Production-Grade Code Reviews

GitGoblin is an event-driven Agentic AI GitHub App that automates the pull request review cycle. Specialist agents reason about security and performance in every diff, and developers can chat with it directly on the PR.

---

### Key Features
* **Autonomous Auditing:** Triggers on `pull_request` opened/synchronize events and reviews the diff before human review.
* **Multi-Agent Review:** Security and Performance specialists run concurrently; results are consolidated into one comment.
* **Interactive Chat:** Tag @gitgoblin-dev in any PR comment to start a collaborative debugging session.
* **Noise Filtering:** Lockfiles, binaries, and build output are stripped before inference.

---

### Tech Stack
* **Engine:** GLM (Z.ai) through any OpenAI-compatible endpoint
* **Runtime:** Python 3.12, FastAPI, httpx
* **Data & Queue:** PostgreSQL 17 via SQLAlchemy 2.0 (async) and Alembic; the `jobs` table is the job queue
* **Integration:** GitHub App (JWT → installation token) and HMAC-verified webhooks
* **Deployment:** Docker (Fly.io, Railway, or any VM); one image runs both the web and worker processes

---

### Architecture
```
GitHub ──webhook──► web (FastAPI)          ──202 in ms──► GitHub
                     │ one transaction: store delivery (dedupe) + insert job
                     ▼
                  Postgres  jobs table = queue
                     ▲ claim: FOR UPDATE SKIP LOCKED, 120s lease, heartbeat
                     │
                  worker ──► GitHub diff ──► specialist agents ──► PR comment
```
* **Fast acknowledgement:** GitHub expects a 2xx within 10 seconds, so the webhook only queues work.
* **Exactly-once effect:** GitHub's `X-GitHub-Delivery` id is a primary key; redeliveries are acknowledged and dropped.
* **Crash-safe:** a job held by a dead worker becomes claimable when its lease expires; a stale worker's late write is rejected.
* **Retries:** failures back off exponentially (30s, 60s, … capped at 15 min) and end as `failed` after 5 attempts, with the traceback in `jobs.last_error`.

---

### Development
```bash
cp .env.example .env                  # fill in GitHub App + LLM credentials
uv sync
docker compose up -d postgres         # Postgres on localhost:5433
uv run alembic upgrade head           # create/upgrade tables
uv run uvicorn gitgoblin.main:app --reload --port 8080   # web
uv run python -m gitgoblin.worker     # worker (second terminal)
uv run pytest                         # tests need the compose Postgres running
uv run python scripts/test_agents.py  # run specialists on a sample diff
```
Or run everything in containers: `docker compose up --build` (web on http://localhost:8000).

Point the GitHub App webhook URL at `https://<host>/api/webhook` (use ngrok locally).

**Schema changes:** edit `gitgoblin/db/models.py`, then
`uv run alembic revision --autogenerate -m "describe change"` and review the generated file before committing.

### Deployment
Build the Dockerfile and run two processes from the same image, both with the same environment:
* **web:** default command (`uvicorn` on `$PORT`, default 8080)
* **worker:** `python -m gitgoblin.worker`

Run `alembic upgrade head` before starting a new release (e.g. Fly's `release_command`).

> The default `LLM_BASE_URL` is the GLM Coding Plan endpoint. Z.ai's usage policy restricts that plan to officially supported tools; for production use the pay-as-you-go endpoint `https://api.z.ai/api/paas/v4`.
