import { Request, Response } from "express";
import { Webhooks } from "@octokit/webhooks";
import { processPullRequestReview } from "../services/review.service";
import { processInteractiveChat } from "../services/chat.service";
import { WebhookContext } from "../types";
import dotenv from "dotenv";

dotenv.config();

const webhooks = new Webhooks({
  secret: process.env.GITHUB_WEBHOOK_SECRET || "development_secret",
});

// PR Review Workflow
webhooks.on(["pull_request.opened", "pull_request.synchronize"], async ({ payload }) => {
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
    
    console.log(`\n[gitGoblin] Alert! PR #${context.pullRequest.number} opened/synced in ${context.repository.name}`);
    await processPullRequestReview(context);
});

// Chat Workflow (Comments)
webhooks.on(["issue_comment.created"], async ({ payload }) => {
    // Ignore bot comments
    if (payload.comment.user?.type === "Bot") return;

    // Check if the bot was mentioned
    const body = payload.comment.body;
    if (!body.toLowerCase().includes("@gitgoblin")) return;

    const context: WebhookContext = {
      installationId: payload.installation?.id || 0,
      repository: {
        owner: payload.repository.owner.login,
        name: payload.repository.name,
      },
      pullRequest: {
        number: payload.issue.number, // Works for both PRs and issues
      }
    };

    console.log(`\n[gitGoblin] Alert! Chat triggered on Issue/PR #${context.pullRequest.number} in ${context.repository.name}`);
    await processInteractiveChat(context, body);
});

// Chat Workflow (New Issues)
webhooks.on(["issues.opened"], async ({ payload }) => {
    // Check if the bot was mentioned in the issue description
    const body = payload.issue.body || "";
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

    console.log(`\n[gitGoblin] Alert! Chat triggered on New Issue #${context.pullRequest.number} in ${context.repository.name}`);
    await processInteractiveChat(context, body);
});

export const handleGithubWebhook = async (req: Request, res: Response) => {
    const id = req.headers["x-github-delivery"] as string;
    const name = req.headers["x-github-event"] as any;

    try {
        // Signature is already verified by verifyGithubSignature middleware.
        // Just forward the event to our octokit webhook handlers.
        await webhooks.receive({
            id,
            name,
            payload: req.body,
        });
        
        res.status(200).send("Event Received & Verified");
    } catch (error) {
        console.error("[gitGoblin] Webhook processing failed!", error);
        res.status(401).send("Unauthorized");
    }
};
