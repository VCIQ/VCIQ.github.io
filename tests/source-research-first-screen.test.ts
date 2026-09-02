import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync("app/sources/page.tsx", "utf8");
const operations = readFileSync("app/sources/source-operations-client.tsx", "utf8");
const styles = readFileSync("app/sources/page.module.css", "utf8");
const operationsStyles = readFileSync("app/sources/source-operations.module.css", "utf8");

test("source lifecycle methodology remains collapsed below the live decision dashboard", () => {
  assert.match(page, /<SourceOperationsClient/);
  assert.match(page, /<details className=\{styles\.lifecycle\}>/);
  assert.ok(
    page.indexOf("<SourceOperationsClient") < page.indexOf("<details className={styles.lifecycle}>")
  );
  assert.match(page, /Candidate → Tracked → Core/);
  assert.match(styles, /\.lifecycle summary[\s\S]*min-height:\s*54px/);
});

test("source cards expose compact coverage and readiness context", () => {
  assert.match(operations, /className=\{styles\.coverageTags\}/);
  assert.match(operations, /source\.sectors\.slice/);
  assert.match(operations, /source\.companies/);
  assert.match(operations, /source\.people/);
  assert.match(operations, /source\.keywords/);
  assert.match(operations, /CORE READINESS/);
  assert.match(operationsStyles, /\.coverageTags \{/);
  assert.match(operationsStyles, /\.sourceGrid \{/);
});