import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/favorites/page.tsx", import.meta.url), "utf8");
const css = await readFile(new URL("../app/favorites/favorites.css", import.meta.url), "utf8");
const marker = await readFile(new URL("../components/favorites-hydration-marker.tsx", import.meta.url), "utf8");

test("favorites critical controls are statically styled before client hydration", () => {
  assert.match(page, /import "\.\/favorites\.css"/);
  for (const selector of [
    ".favorites-safety",
    ".favorites-transfer-actions",
    ".favorites-file-input",
    ".favorites-preference-summary",
    ".favorite-intelligence-card",
    ".favorite-intelligence-link",
    ".favorite-card-actions",
    ".favorites-toast",
  ]) {
    assert.ok(css.includes(selector), `missing static selector ${selector}`);
  }
  assert.match(css, /\.favorites-file-input\s*\{[^}]*display:\s*none\s*!important/s);
});

test("favorites page performs a single cache-busting recovery when hydration stalls", () => {
  assert.match(page, /vciqFavoritesHydrated/);
  assert.match(page, /vciq:favorites:recovery-reload:v1/);
  assert.match(page, /_vciq_reload/);
  assert.match(page, /window\.setTimeout/);
  assert.match(page, /window\.location\.replace/);
  assert.match(page, /8000/);
});

test("successful favorites hydration clears recovery state and query noise", () => {
  assert.match(marker, /document\.documentElement\.dataset\[FAVORITES_HYDRATION_MARKER\] = "1"/);
  assert.match(marker, /sessionStorage\.removeItem\(FAVORITES_RECOVERY_SESSION_KEY\)/);
  assert.match(marker, /url\.searchParams\.delete\(FAVORITES_RECOVERY_QUERY\)/);
  assert.match(marker, /history\.replaceState/);
});
