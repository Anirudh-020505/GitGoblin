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


### Core Webhook Logic
The following optimized handler ensures the agent does not time out on Vercel while processing AI requests:

```typescript
// src/controllers/webhook.controller.ts

export const handleGithubWebhook = async (req: Request, res: Response) => {
    const event = req.headers["x-github-event"];
    const payload = req.body;

    try {
        // --- 1. CHAT WORKFLOW ---
        if (event === "issue_comment" && payload.action === "created") {
            const body = payload.comment.body.toLowerCase();
            
            // Trigger only if mentioned to save API tokens
            if (body.includes("@gitgoblin-dev")) {
                const context = {
                    installationId: payload.installation.id,
                    repo: payload.repository.name,
                    owner: payload.repository.owner.login
                };

                /* CRITICAL: We MUST await the AI service here.
                   In Vercel, if we send res.status(200) before this await,
                   the function context is destroyed and the AI process terminates.
                */
                await processInteractiveChat(context, body);
            }
        }

        // --- 2. FINAL RESPONSE ---
        // Acknowledge GitHub only AFTER AI work is completed or skipped
        res.status(200).send("Processed");

    } catch (error) {
        // Structured logging for Vercel Observability
        console.error("[GitGoblin-Error]:", error);
        res.status(500).send("Internal Error");
    }
};
