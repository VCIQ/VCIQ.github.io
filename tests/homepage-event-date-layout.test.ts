import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");
const guard = readFileSync(
  new URL("../components/homepage-event-date-guard.module.css", import.meta.url),
  "utf8",
);

test("homepage event date rail contains full ISO timestamps instead of overlapping titles", () => {
  assert.match(page, /dateGuardStyles\.root/);
  assert.match(guard, /:global\(\.event-date strong\)/);
  assert.match(guard, /width:\s*5ch/);
  assert.match(guard, /max-width:\s*5ch/);
  assert.match(guard, /overflow:\s*hidden/);
  assert.match(guard, /white-space:\s*nowrap/);
});
