import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("homepage source count is labeled as a count, not as a clickable link", async () => {
  const source = await readFile(
    new URL("../components/event-quality-indicator.tsx", import.meta.url),
    "utf8",
  );

  assert.match(source, /可用来源 \{totalLinks\} 个/u);
  assert.match(source, /其他来源 \{additionalLinks\.length\} 个/u);
  assert.doesNotMatch(source, />\s*来源链接 \{totalLinks\}\s*</u);
  assert.match(source, /additionalLinks\.length > 0/u);
});
