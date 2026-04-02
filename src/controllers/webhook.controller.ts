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

// Chat Workflow
webhooks.on(["issue_comment.created"], async ({ payload }) => {
    // Only respond to PR comments (issues also trigger this event, but we focus on PRs)
    if (!payload.issue.pull_request) return;
    
    // Ignore bot comments
    if (payload.comment.user?.type === "Bot") return;

    // Check if the bot was mentioned
    const body = payload.comment.body;
    if (!body.includes("@GitGoblin") && !body.includes("@gitgoblin")) return;

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

    console.log(`\n[gitGoblin] Alert! Chat triggered on PR #${context.pullRequest.number} in ${context.repository.name}`);
    await processInteractiveChat(context, body);
});

export const handleGithubWebhook = async (req: Request, res: Response) => {
    const signature = req.headers["x-hub-signature-256"] as string;
    const id = req.headers["x-github-delivery"] as string;
    const name = req.headers["x-github-event"] as any;

    try {
        await webhooks.verifyAndReceive({
            id,
            name,
            payload: JSON.stringify(req.body),
            signature: signature || "",
        });
        
        res.status(200).send("Event Received & Verified");
    } catch (error) {
        console.error("[gitGoblin] Webhook processing failed!", error);
        res.status(401).send("Unauthorized");
    }
};
