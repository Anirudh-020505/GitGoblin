"""Run both specialists against a sample diff. Usage: `uv run python scripts/test_agents.py`"""

import asyncio

from gitgoblin.agents.specialists import PERFORMANCE, SECURITY

SAMPLE_DIFF = """diff --git a/src/index.ts b/src/index.ts
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
"""


async def main() -> None:
    for specialist in (SECURITY, PERFORMANCE):
        print(f"--- {specialist.name} ---")
        print(await specialist.review(SAMPLE_DIFF))
        print()


if __name__ == "__main__":
    asyncio.run(main())
