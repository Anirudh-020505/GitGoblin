// src/agents/specialists.agent.ts

import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';

dotenv.config();

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY!);
const MODEL_NAME = 'gemini-1.5-flash';


export const runSecurityAgent = async (diff: string): Promise<string> => {
  try {
    const model = genAI.getGenerativeModel({
      model: MODEL_NAME,
      systemInstruction: `You are an elite Application Security Engineer. Your sole job is to review code diffs for security vulnerabilities (e.g., SQL injection, XSS, exposed secrets, broken access control). 
      If you find security issues, list them clearly with code examples of how to fix them.
      If the code is secure and you find NO security issues, you MUST reply ONLY with: "✅ No obvious security vulnerabilities detected. LGTM!" Do not invent issues.`
    });

    const prompt = `Review the following code diff for security vulnerabilities:\n\n${diff}`;
    const result = await model.generateContent(prompt);
    
    return result.response.text();
  } catch (error) {
    console.error('[Security Agent] Execution failed:', error);
    return '⚠️ Security review failed to execute.';
  }
};


export const runPerformanceAgent = async (diff: string): Promise<string> => {
  try {
    const model = genAI.getGenerativeModel({
      model: MODEL_NAME,
      systemInstruction: `You are a strict Performance Optimization Engineer. Your sole job is to review code diffs for performance bottlenecks, memory leaks, inefficient loops, or poor Big O time complexity.
      If you find performance issues, explain why it is slow and provide optimized code.
      If the code is already highly optimized, you MUST reply ONLY with: "🚀 Performance looks highly optimized. LGTM!" Do not invent issues.`
    });

    const prompt = `Review the following code diff for performance issues:\n\n${diff}`;
    const result = await model.generateContent(prompt);
    
    return result.response.text();
  } catch (error) {
    console.error('[Performance Agent] Execution failed:', error);
    return '⚠️ Performance review failed to execute.';
  }
};