import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(
  new URL("../components/homepage-unified-inbox.module.css", import.meta.url),
  "utf8",
);

test("homepage event dates cannot wrap full ISO timestamps into the content column", () => {
  assert.match(
    css,
    /\.root :global\(\.event-date\)\s*\{[^}]*overflow:\s*hidden;/s,
  );
  assert.match(
    css,
    /\.root :global\(\.event-date strong\)\s*\{[^}]*width:\s*4\.6ch;[^}]*overflow:\s*hidden;[^}]*white-space:\s*nowrap;/s,
  );
  assert.match(
    css,
    /\.root :global\(\.event-date span\)\s*\{[^}]*white-space:\s*nowrap;/s,
  );
});
