// src/services/chat.service.ts

import { WebhookContext } from '../types';
import { getAuthenticatedOctokit, postIssueComment } from './github.service';
import { generateChatReply } from '../agents/base.agent'; 

/**
 * Processes mentions (@GitGoblin) in PR comments, fetches history, and replies.
 */
export const processInteractiveChat = async (context: WebhookContext, userComment: string): Promise<void> => {
  try {
    console.log(`[Chat Service] Initiating Gemini chat workflow for PR #${context.pullRequest.number}`);

    const octokit = await getAuthenticatedOctokit(context.installationId);

    const { data: comments } = await octokit.rest.issues.listComments({
      owner: context.repository.owner,
      repo: context.repository.name,
      issue_number: context.pullRequest.number,
      per_page: 10,
    });

    const formattedHistory = comments.map(c => ({
      role: c.user?.login?.includes('gitgoblin') ? 'model' : 'user',
      content: c.body || '',
    }));

    const cleanPrompt = userComment.replace(/@gitgoblin(-dev)?(\[bot\])?/gi, '').trim();

    // 5. Generate the AI Response
    // (Make sure your base.agent.ts accepts 'model' in its parameter types if you update this!)
    const aiReply = await generateChatReply(cleanPrompt, formattedHistory as any);

    await postIssueComment(
      octokit, 
      context.repository.owner, 
      context.repository.name, 
      context.pullRequest.number, 
      aiReply
    );

    console.log(`[Chat Service] Successfully replied to PR #${context.pullRequest.number}`);

  } catch (error) {
    console.error(`[Chat Service] Error processing chat for PR #${context.pullRequest.number}:`, error);
  }
};