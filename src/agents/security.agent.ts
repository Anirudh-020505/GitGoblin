import { genAI, CHAT_MODEL } from './base.agent';
import { AnalysisResult, Finding } from '../types';

/**
 * Security Agent
 * Specialized in identifying security vulnerabilities, hardcoded secrets, and OWASP risks.
 */
export const analyzeSecurity = async (diff: string): Promise<string> => {
    try {
        const model = genAI.getGenerativeModel({
            model: CHAT_MODEL,
            systemInstruction: `You are a Senior Security Engineer. Your role is to analyze code diffs for security vulnerabilities.
            Focus on:
            1. OWASP Top 10 (Injection, Broken Access Control, etc.).
            2. Hardcoded Secrets (API keys, passwords, tokens).
            3. Sensitive Data exposure.
            4. Insecure Dependencies or configurations.
            
            Format your response in sleek, professional Markdown.
            - Start with a high-level summary.
            - List findings with severity (Low, Medium, High, Critical).
            - Provide secure code examples or remediation steps.
            - If no issues are found, reply with: "🛡️ **No obvious security vulnerabilities detected. LGTM!**"`,
        });

        const prompt = `Analyze this code diff for security vulnerabilities:\n\n${diff}`;
        const result = await model.generateContent(prompt);
        return result.response.text();
    } catch (error) {
        console.error('[Security Agent] Error:', error);
        return '⚠️ *Security analysis failed.*';
    }
};

/**
 * Returns a structured AnalysisResult (Future use)
 */
export const analyzeSecurityStructured = async (diff: string): Promise<AnalysisResult> => {
    const text = await analyzeSecurity(diff);
    return {
        agentName: "Security Specialist",
        findings: [],
        summary: text
    };
};
