import { Octokit } from "octokit";
import dotenv from "dotenv";

dotenv.config();

if (!process.env.GITHUB_TOKEN) {
    throw new Error("CRITICAL: GITHUB_TOKEN is missing in .env file");
}

export const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});


export async function getPRDiff(owner: string, repo: string, pullNumber: number): Promise<string> {
  try {
    const response = await octokit.rest.pulls.get({
      owner,
      repo,
      pull_number: pullNumber,
      mediaType: {
        format: "diff", 
      },
    });

    return response.data as any; 
  } catch (error: any) {
    console.error(`Error fetching diff for PR #${pullNumber}:`, error.message);
    throw error;
  }
}

export async function postPRComment(owner: string, repo: string, pullNumber: number, body: string): Promise<void> {
    try {
        await octokit.rest.issues.createComment({
            owner,
            repo,
            issue_number: pullNumber, 
            body,                     
        });
        
        console.log(`[gitGoblin] Review posted to PR #${pullNumber}`);
    } catch (error: any) {
        console.error(`[GitHub Service] Failed to post comment:`, error.message);
        throw error;
    }
}