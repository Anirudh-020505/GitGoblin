/**
 * GitGoblin Types
 */

export interface PRContext {
    owner: string;
    repo: string;
    prNumber: number;
    title: string;
    description?: string;
}

export interface WebhookContext {
  installationId: number;
  repository: {
    owner: string;
    name: string;
  };
  pullRequest: {
    number: number;
    title?: string;
  };
}

export interface AnalysisResult {
    agentName: string;
    findings: Finding[];
    summary: string;
}

export interface Finding {
    type: "security" | "performance" | "logic" | "style";
    severity: "low" | "medium" | "high" | "critical";
    message: string;
    file?: string;
    line?: number;
}
