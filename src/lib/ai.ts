import OpenAI from "openai";
import dotenv from "dotenv";

dotenv.config();

// Initiaslise the OpenAI Client
const openai = new OpenAI();


export async function analyzeCodeDiff(diff: string): Promise<string> {
    try {
        const response = await openai.chat.completions.create({
            model: "gpt-4o",
            temperature: 0.2, 
            messages: [
                {
                    //System Prompt
                    role: "system",
                    content: `You are gitGoblin, an elite, ruthless, but helpful Senior AI Code Reviewer.
                    You will be provided with a Git Diff. 
                    Your job is to:
                    1. Identify logical bugs, security flaws (like hardcoded secrets), and performance issues.
                    2. Ignore minor formatting issues.
                    3. Provide your review in clean Markdown format.
                    4. Keep it concise. If the code is perfect, just say "LGTM! (Looks Good To Me) 🚀".`
                },
                {
                    //User Prompt
                    role: "user",
                    content: `Here is the Git Diff to review:\n\n${diff}`
                }
            ],
        });
        return response.choices[0].message.content || "Review failed. No output generated.";
        
    } catch (error) {
        console.error("Error communicating with OpenAI:", error);
        throw new Error("AI Analysis Failed");
    }
}