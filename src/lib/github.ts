import { Octokit } from "octokit";
import dotenv from "dotenv"

dotenv.config();

// single instance of Octokit to use everywhere 
export const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN,
});

// Git diff function 
export async function getPRDiff(owner: string, repo: string, pullNumber: number) {
  try {
    const { data } = await octokit.rest.pulls.get({
      owner,
      repo,
      pull_number: pullNumber,
      mediaType: {
        format: "diff", // This tells GitHub we want the code changes, not just metadata
      },
    });
    return data as unknown as string;
  } catch (error) {
    console.error("Error fetching PR diff:", error);
    throw error;
  }
}
