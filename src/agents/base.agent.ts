// src/agents/base.agent.ts

import { GoogleGenerativeAI } from '@google/generative-ai';
import dotenv from 'dotenv';

dotenv.config();

if (!process.env.GEMINI_API_KEY) {
  throw new Error("CRITICAL: GEMINI_API_KEY is missing in .env file");
}

// Initialize the Google Generative AI SDK
export const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// We use gemini-1.5-flash because it is extremely fast and cost-effective for chat.
// If you move to full repository analysis later, you would swap this to 'gemini-1.5-pro'
export const CHAT_MODEL = "gemini-3.1-flash-lite-preview";

/**
 * Generates a conversational reply for the @GitGoblin mentions using Google Gemini.
 */
export const generateChatReply = async (
  userPrompt: string,
  // Notice we keep 'assistant' here to avoid breaking the chat.service.ts,
  // but we will map it to Gemini's 'model' role internally.
  conversationHistory: { role: 'user' | 'assistant', content: string }[]
): Promise<string> => {
  try {
    // 1. Initialize the Model with System Instructions
    // Gemini allows us to set the persona directly on the model instance
    const model = genAI.getGenerativeModel({
      model: CHAT_MODEL,
      systemInstruction: `You are GitGoblin, an expert Senior Software Engineer and AI Code Reviewer. 
      You are helping a team review pull requests. Be concise, technically rigorous, 
      and encouraging. Format your responses in Markdown with clear code blocks. 
      Do not hallucinate code that isn't there.`
    });

    // 2. Format History for Gemini
    // Gemini uses 'model' instead of 'assistant', and wraps text in a 'parts' array.
    const geminiHistory = conversationHistory.map(msg => ({
      role: msg.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: msg.content }]
    }));


    const chat = model.startChat({
      history: geminiHistory,
      generationConfig: {
        temperature: 0.3,
      }
    });


    const result = await chat.sendMessage(userPrompt);

    return result.response.text();

  } catch (error: any) {
    console.error('[Gemini Service] Failed to generate chat reply:', error.message);
    return '⚠️ *GitGoblin encountered an internal error while consulting its Gemini brain. Please try again later.*';
  }
};