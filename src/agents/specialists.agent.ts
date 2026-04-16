// src/agents/specialists.agent.ts

import { analyzeSecurity } from './security.agent';
import { analyzePerformance } from './performance.agent';

/**
 * Legacy wrapper for the Security Agent.
 * Delegates to the specialized security agent.
 */
export const runSecurityAgent = async (diff: string): Promise<string> => {
    return analyzeSecurity(diff);
};

/**
 * Legacy wrapper for the Performance Agent.
 * Delegates to the specialized performance agent.
 */
export const runPerformanceAgent = async (diff: string): Promise<string> => {
    return analyzePerformance(diff);
};

// You can add more specialists here in the future