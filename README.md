# GitGoblin-Dev
## Autonomous Agentic AI for Production-Grade Code Reviews

GitGoblin is an event-driven Agentic AI GitHub App designed to automate the pull request review cycle. Built with Gemini 3.1 Flash Lite, it moves beyond simple static analysis to provide deep, context-aware reasoning on logic, security, and performance.

---

### Key Features
* **Autonomous Auditing:** Automatically triggers on pull_request events to analyze diffs before human review.
* **Security-First Reasoning:** Identifies vulnerabilities such as SQL injection, exposed secrets, and improper error handling.
* **Interactive Chat:** Tag @gitgoblin-dev in any comment to initiate a Collaborative Debugging session.
* **Serverless-Optimized:** Custom-engineered non-blocking loops to handle high-latency AI inference within Vercel's 10-second execution window.

---

### Tech Stack
* **Engine:** Gemini 3.1 Flash Lite (Inference)
* **Runtime:** Node.js and TypeScript
* **Backend:** Express (Event-Driven Architecture)
* **Integration:** Octokit SDK and GitHub Webhooks
* **Deployment:** Vercel (Serverless Functions)

---

### Agentic Architecture
GitGoblin operates on a Perception-Reasoning-Action loop:
1. **Perception:** Captures repository state via HMAC-verified Webhook payloads.
2. **Reasoning:** Injects PR diffs into a Chain-of-Thought pipeline using Gemini 3.1 Flash Lite.
3. **Action:** Executes line-level comments and approvals via the GitHub REST API.

---



