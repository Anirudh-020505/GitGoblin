// src/controllers/webhook.controller.ts
// Note: We intentionally do NOT use @octokit/webhooks here because it is ESM-only
// and incompatible with our CommonJS build. Signature verification is already handled
// by the verifyGithubSignature middleware in index.ts, so we just route events manually.

import { Request, Response } from "express";
import { processPullRequestReview } from "../services/review.service";
import { processInteractiveChat } from "../services/chat.service";
import { WebhookContext } from "../types";

export const handleGithubWebhook = async (req: Request, res: Response): Promise<void> => {
    // Signature already verified by middleware — safe to trust payload
    const event = req.headers["x-github-event"] as string;
    const payload = req.body;

    // Respond to GitHub immediately so we never hit a webhook timeout.
    // The async AI + GitHub API work continues after this line.
    res.status(200).send("Event Received & Verified");

    try {
        // --- PR Review Workflow ---
        if (event === "pull_request" &&
            (payload.action === "opened" || payload.action === "synchronize")) {

            const context: WebhookContext = {
                installationId: payload.installation?.id || 0,
                repository: {
                    owner: payload.repository.owner.login,
                    name: payload.repository.name,
                },
                pullRequest: {
                    number: payload.pull_request.number,
                    title: payload.pull_request.title,
                }
            };
            console.log(`\n[gitGoblin] PR #${context.pullRequest.number} opened/synced in ${context.repository.name}`);
            await processPullRequestReview(context);
        }

        // --- Chat Workflow: Comments on Issues/PRs ---
        if (event === "issue_comment" && payload.action === "created") {
            // Ignore bot comments to prevent feedback loops
            if (payload.comment.user?.type === "Bot") return;

            const body: string = payload.comment.body || "";
            if (!body.toLowerCase().includes("@gitgoblin")) return;

            const context: WebhookContext = {
                installationId: payload.installation?.id || 0,
                repository: {
                    owner: payload.repository.owner.login,
                    name: payload.repository.name,
                },
                pullRequest: {
                    number: payload.issue.number, // works for both issues and PRs
                }
            };

            console.log(`\n[gitGoblin] Chat triggered on Issue/PR #${context.pullRequest.number} in ${context.repository.name}`);
            await processInteractiveChat(context, body);
        }

        // --- Chat Workflow: Mention in new Issue body ---
        if (event === "issues" && payload.action === "opened") {
            const body: string = payload.issue.body || "";
            if (!body.toLowerCase().includes("@gitgoblin")) return;

            const context: WebhookContext = {
                installationId: payload.installation?.id || 0,
                repository: {
                    owner: payload.repository.owner.login,
                    name: payload.repository.name,
                },
                pullRequest: {
                    number: payload.issue.number,
                }
            };

            console.log(`\n[gitGoblin] Chat triggered in new Issue #${context.pullRequest.number} in ${context.repository.name}`);
            await processInteractiveChat(context, body);
        }

    } catch (error) {
        console.error("[gitGoblin] Webhook processing error:", error);
    }
};
