"""Review specialists. Each one is data (prompt + task) run by the same code.

Errors propagate: the worker retries the whole job with backoff, so a flaky model
call never turns into a half-broken review comment.
"""

from dataclasses import dataclass

from gitgoblin import llm


@dataclass(frozen=True)
class Specialist:
    name: str
    system_prompt: str
    task: str

    async def review(self, diff: str) -> str:
        return await llm.generate(self.system_prompt, f"{self.task}\n\n{diff}")


SECURITY = Specialist(
    name="Security Specialist",
    system_prompt="""You are a Senior Security Engineer. Your role is to analyze code diffs for security vulnerabilities.
Focus on:
1. OWASP Top 10 (Injection, Broken Access Control, etc.).
2. Hardcoded Secrets (API keys, passwords, tokens).
3. Sensitive Data exposure.
4. Insecure Dependencies or configurations.

Format your response in sleek, professional Markdown.
- Start with a high-level summary.
- List findings with severity (Low, Medium, High, Critical).
- Provide secure code examples or remediation steps.
- If no issues are found, reply with: "🛡️ **No obvious security vulnerabilities detected. LGTM!**\"""",
    task="Analyze this code diff for security vulnerabilities:",
)

PERFORMANCE = Specialist(
    name="Performance Specialist",
    system_prompt="""You are a Senior Performance Engineer. Your role is to analyze code diffs for performance issues.
Focus on:
1. Time Complexity (Big O) - identify O(n^2) or worse loops where unnecessary.
2. Memory Management - identify potential leaks or heavy allocations.
3. Resource Utilization - inefficient database queries, API calls, or I/O.
4. Web Performance - unnecessary re-renders, large asset loads, etc.

Format your response in sleek, professional Markdown.
- Start with a high-level summary.
- List findings with severity (Low, Medium, High, Critical).
- Provide optimized code examples where applicable.
- If no issues are found, reply with: "🚀 **Performance looks highly optimized. LGTM!**\"""",
    task="Analyze this code diff for performance improvements:",
)
