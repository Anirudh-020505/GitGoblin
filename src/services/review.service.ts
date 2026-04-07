// src/services/review.service.ts

import { WebhookContext } from '../types';
import { getAuthenticatedOctokit, getPRDiff, postPRComment } from './github.service';
import { isNoiseFile } from '../utils/token.utils';
// We will build this file next!
import { runSecurityAgent, runPerformanceAgent } from '../agents/specialists.agent';

/**
 * Orchestrates the multi-agent review process for a new Pull Request.
 */
export const processPullRequestReview = async (context: WebhookContext): Promise<void> => {
  try {
    console.log(`[Review Service] Starting Multi-Agent Review for PR #${context.pullRequest.number}`);

    // 1. Authenticate & Fetch the raw diff from GitHub
    const octokit = await getAuthenticatedOctokit(context.installationId);
    const rawDiff = await getPRDiff(octokit, context.repository.owner, context.repository.name, context.pullRequest.number);

    // 2. Parse the Diff & Filter Noise
    // A standard git diff separates files with "diff --git". We split the string to get individual files.
    const fileDiffs = rawDiff.split('diff --git ').filter(Boolean);
    const cleanDiffs: string[] = [];

    for (const fileDiff of fileDiffs) {
      // Extract the filename from the first line of the diff chunk (e.g., "a/src/index.ts b/src/index.ts")
      const firstLine = fileDiff.split('\n')[0];
      const filename = firstLine.split(' b/')[1] || firstLine; 

      if (!isNoiseFile(filename)) {
        cleanDiffs.push(`diff --git ${fileDiff}`);
      }
    }

    const finalDiffToReview = cleanDiffs.join('\n');

    if (!finalDiffToReview.trim()) {
      console.log(`[Review Service] No reviewable files found in PR #${context.pullRequest.number}. Skipping AI.`);
      return;
    }

    // 3. THE MULTI-AGENT PARALLEL EXECUTION
    // * INTERVIEW PREP NOTE: Using Promise.all() here is crucial. 
    // Instead of waiting 10 seconds for Security, then 10 seconds for Performance, 
    // they both run concurrently. The total wait time is only as long as the slowest agent.
    console.log(`[Review Service] Dispatching diff to Specialist Agents...`);
    
    const [securityReview, performanceReview] = await Promise.all([
      runSecurityAgent(finalDiffToReview),
      runPerformanceAgent(finalDiffToReview)
    ]);

    // 4. Consolidate the Reports
    const consolidatedComment = `
## 👾 GitGoblin Multi-Agent Review

Thank you for the PR! Our specialist agents have analyzed the changes:

### 🛡️ Security Specialist
${securityReview}

### ⚡ Performance Specialist
${performanceReview}
    `.trim();

    // 5. Post the final consolidated review back to GitHub
    await postPRComment(
      octokit, 
      context.repository.owner, 
      context.repository.name, 
      context.pullRequest.number, 
      consolidatedComment
    );

    console.log(`[Review Service] Successfully posted consolidated review for PR #${context.pullRequest.number}`);

  } catch (error) {
    console.error(`[Review Service] Failed to process PR review:`, error);
  }
};