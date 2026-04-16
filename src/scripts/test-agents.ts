// src/scripts/test-agents.ts

import { runSecurityAgent, runPerformanceAgent } from '../agents/specialists.agent';

const mockDiff = `
diff --git a/src/index.ts b/src/index.ts
index 1234567..89abcdef 100644
--- a/src/index.ts
+++ b/src/index.ts
@@ -1,5 +1,10 @@
-console.log("Hello World");
+const apiKey = "12345-ABCDE-67890-FGHIJ"; // Hardcoded secret
+
+for (let i = 0; i < 1000; i++) {
+    for (let j = 0; j < 1000; j++) {
+        console.log(i + j); // Inefficient O(n^2) loop
+    }
+}
`;

async function main() {
    console.log("--- Testing Security Agent ---");
    const securityResult = await runSecurityAgent(mockDiff);
    console.log(securityResult);

    console.log("\n--- Testing Performance Agent ---");
    const performanceResult = await runPerformanceAgent(mockDiff);
    console.log(performanceResult);
}

main().catch(console.error);
