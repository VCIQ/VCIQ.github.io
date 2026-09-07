import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../components/site-header.tsx", import.meta.url), "utf8");
const responsive = readFileSync(new URL("../app/header-responsive.css", import.meta.url), "utf8");

test("tracking admin remains a direct desktop utility and mobile menu destination", () => {
  assert.match(source, /const TRACKING_ADMIN_URL = "https:\/\/vciq-tracking-console\.pages\.dev\/";/);
  assert.match(
    source,
    /<a\s+className="icon-button desktop-utility-action"\s+href=\{TRACKING_ADMIN_URL\}\s+aria-label="追踪管理台"\s+title="追踪管理台"/,
  );
  assert.match(
    source,
    /<a\s+className="mobile-nav-utility"\s+href=\{TRACKING_ADMIN_URL\}[\s\S]*?>[\s\S]*?追踪管理台[\s\S]*?<\/a>/,
  );
  assert.doesNotMatch(source, /href="\/tracking"[^>]*>\s*<Settings/);
});

test("mobile header moves secondary utilities into the expanded menu", () => {
  assert.match(
    source,
    /<Link className="mobile-nav-utility" href="\/search" onClick=\{\(\) => setOpen\(false\)\}>/,
  );
  assert.match(
    responsive,
    /@media \(max-width: 900px\)[\s\S]*?\.desktop-utility-action\s*\{[\s\S]*?display:\s*none !important;/,
  );
  assert.match(
    responsive,
    /\.main-nav\.is-open \.mobile-nav-utility\s*\{[\s\S]*?display:\s*flex !important;/,
  );
});
