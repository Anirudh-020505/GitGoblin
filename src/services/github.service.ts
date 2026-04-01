// src/services/github.service.ts

import { Octokit } from '@octokit/rest';
import { createAppAuth } from '@octokit/auth-app';

/**
 * Generates an authenticated Octokit instance for a specific repository installation.
 * * INTERVIEW PREP NOTE: Why use App Auth instead of a PAT (Personal Access Token)?
 * PATs are tied to a single user account. If that user leaves the company, the bot breaks.
 * GitHub Apps are tied to the organization/repo, have granular permissions, and generate 
 * short-lived (1 hour) tokens, which is a massive security upgrade.
 * * @param installationId - The unique ID of the GitHub App installation on a specific repo.
 */
export const getAuthenticatedOctokit = async (installationId: number): Promise<Octokit> => {
  try {
    // We use the auth-app strategy which requires your App ID, Private Key, and Installation ID
    const octokit = new Octokit({
      authStrategy: createAppAuth,
      auth: {
        appId: process.env.GITHUB_APP_ID!,
        privateKey: process.env.GITHUB_PRIVATE_KEY!.replace(/\\n/g, '\n'), // Fixes multiline env variable issues
        installationId: installationId,
      },
    });

    return octokit;
  } catch (error) {
    console.error(`[GitHub Service] Failed to authenticate for installation ${installationId}:`, error);
    throw new Error('GitHub Authentication Failed');
  }
};

/**
 * Posts a comment back to a Pull Request or Issue.
 */
export const postIssueComment = async (
  octokit: Octokit,
  owner: string,
  repo: string,
  issueNumber: number,
  body: string
): Promise<void> => {
  try {
    await octokit.rest.issues.createComment({
      owner,
      repo,
      issue_number: issueNumber,
      body,
    });
  } catch (error) {
    console.error(`[GitHub Service] Failed to post comment on PR #${issueNumber}:`, error);
    throw error;
  }
};

/**
 * Posts a comment back to a Pull Request.
 */
export const postPRComment = postIssueComment;

/**
 * Fetches the raw diff of a Pull Request.
 */
export const getPRDiff = async (
  octokit: Octokit,
  owner: string,
  repo: string,
  pullNumber: number
): Promise<string> => {
  try {
    const response = await octokit.rest.pulls.get({
      owner,
      repo,
      pull_number: pullNumber,
      mediaType: {
        format: 'diff',
      },
    });
    return response.data as unknown as string;
  } catch (error) {
    console.error(`[GitHub Service] Failed to fetch PR diff for #${pullNumber}:`, error);
    throw error;
  }
};
