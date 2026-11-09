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
* **Integration:** GitHub App (JWT → installation token) and HMAC-verified webhooks
* **Deployment:** Docker (Fly.io, Railway, or any VM)

---

### Agentic Architecture
GitGoblin operates on a Perception-Reasoning-Action loop:
1. **Perception:** Captures repository state via HMAC-verified webhook payloads.
2. **Reasoning:** Sends the filtered PR diff to specialist agents in parallel.
3. **Action:** Posts the consolidated review or chat reply through the GitHub REST API.

---

### Development
```bash
cp .env.example .env            # fill in GitHub App + LLM credentials
uv sync
uv run uvicorn gitgoblin.main:app --reload --port 8080
uv run python scripts/test_agents.py   # run specialists on a sample diff
```
Point the GitHub App webhook URL at `https://<host>/api/webhook` (use ngrok locally).

### Deployment
```bash
docker build -t gitgoblin .
docker run --env-file .env -p 8080:8080 gitgoblin
```
The container listens on `$PORT` (default 8080). Fly.io (`fly launch`) and Railway both build from the Dockerfile.

> The default `LLM_BASE_URL` is the GLM Coding Plan endpoint. Z.ai's usage policy restricts that plan to officially supported tools; for production use the pay-as-you-go endpoint `https://api.z.ai/api/paas/v4`.
