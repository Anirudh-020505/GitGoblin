// src/controllers/webhook.controller.ts
import { Request, Response } from "express";
import { processPullRequestReview } from "../services/review.service";
import { processInteractiveChat } from "../services/chat.service";
import { WebhookContext } from "../types";

export const handleGithubWebhook = async (req: Request, res: Response): Promise<void> => {
    const event = req.headers["x-github-event"] as string;
    const payload = req.body;

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
            
            // We await here so Vercel doesn't kill the function early
            await processPullRequestReview(context);
        }

        // --- Chat Workflow ---
        if (event === "issue_comment" && payload.action === "created") {
            if (payload.comment.user?.type === "Bot") return;

            const body: string = payload.comment.body || "";
            
            // Use your exact handle to ensure the trigger is accurate
            if (!body.toLowerCase().includes("@gitgoblin-dev")) {
                res.status(200).send("No mention detected");
                return;
            };

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

            // CRITICAL: Function stays alive until processInteractiveChat finishes
            await processInteractiveChat(context, body);
        }

        // ONLY SEND THE RESPONSE AT THE VERY END
        res.status(200).send("Successfully processed by GitGoblin");

    } catch (error) {
        console.error("[gitGoblin] Webhook processing error:", error);
        // If it fails, we still need to send a response so GitHub doesn't keep retrying
        res.status(500).send("Internal processing error");
    }
};