import { genAI, CHAT_MODEL } from './base.agent';
import { AnalysisResult, Finding } from '../types';

/**
 * Performance Agent
 * Specialized in identifying performance bottlenecks, inefficient algorithms, and resource leaks.
 */
export const analyzePerformance = async (diff: string): Promise<string> => {
    try {
        const model = genAI.getGenerativeModel({
            model: CHAT_MODEL,
            systemInstruction: `You are a Senior Performance Engineer. Your role is to analyze code diffs for performance issues.
            Focus on:
            1. Time Complexity (Big O) - identify O(n^2) or worse loops where unnecessary.
            2. Memory Management - identify potential leaks or heavy allocations.
            3. Resource Utilization - inefficient database queries, API calls, or I/O.
            4. Web Performance - unnecessary re-renders, large asset loads, etc.
            
            Format your response in sleek, professional Markdown.
            - Start with a high-level summary.
            - List findings with severity (Low, Medium, High, Critical).
            - Provide optimized code examples where applicable.
            - If no issues are found, reply with: "🚀 **Performance looks highly optimized. LGTM!**"`,
        });

        const prompt = `Analyze this code diff for performance improvements:\n\n${diff}`;
        const result = await model.generateContent(prompt);
        return result.response.text();
    } catch (error) {
        console.error('[Performance Agent] Error:', error);
        return '⚠️ *Performance analysis failed.*';
    }
};

/**
 * Returns a structured AnalysisResult (Future use)
 */
export const analyzePerformanceStructured = async (diff: string): Promise<AnalysisResult> => {
    // This is a placeholder for when we want to fully move to structured types
    const text = await analyzePerformance(diff);
    return {
        agentName: "Performance Specialist",
        findings: [], // Would parse findings here if needed
        summary: text
    };
};
