import { readFileSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const OUT = path.join(ROOT, "out");
const INDEX = path.join(OUT, "index.html");

const MAX_SINGLE_SCRIPT_BYTES = Number(
  process.env.HOMEPAGE_MAX_SCRIPT_BYTES ?? 250_000,
);
const MAX_TOTAL_SCRIPT_BYTES = Number(
  process.env.HOMEPAGE_MAX_TOTAL_SCRIPT_BYTES ?? 800_000,
);
const MAX_HTML_BYTES = Number(
  process.env.HOMEPAGE_MAX_HTML_BYTES ?? 250_000,
);
const MAX_HTML_ELEMENTS = Number(
  process.env.HOMEPAGE_MAX_HTML_ELEMENTS ?? 1_200,
);
const MAX_INITIAL_EVENT_ROWS = Number(
  process.env.HOMEPAGE_MAX_INITIAL_EVENT_ROWS ?? 24,
);

function fail(message) {
  console.error(`HOMEPAGE_PERFORMANCE_BUDGET_ERROR: ${message}`);
  process.exitCode = 1;
}

const html = readFileSync(INDEX, "utf8");
const htmlBytes = statSync(INDEX).size;
const htmlElements = (html.match(/<[a-z][^>]*>/gi) ?? []).length;
const initialEventRows = (html.match(/class=["'][^"']*\bevent-row\b/gi) ?? []).length;
const sources = [
  ...new Set(
    [...html.matchAll(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>/gi)]
      .map((match) => match[1])
      .filter((source) => source.startsWith("/")),
  ),
];

if (!sources.length) {
  fail("homepage contains no local script assets");
} else {
  const assets = sources.map((source) => {
    const relative = source.replace(/^\/+/, "");
    const file = path.join(OUT, relative);
    return { source, bytes: statSync(file).size };
  });
  const totalBytes = assets.reduce((sum, asset) => sum + asset.bytes, 0);
  const largest = [...assets].sort((left, right) => right.bytes - left.bytes)[0];

  console.log(
    JSON.stringify(
      {
        scriptCount: assets.length,
        totalBytes,
        maxSingleBytes: largest?.bytes ?? 0,
        largestScript: largest?.source ?? "",
        htmlBytes,
        htmlElements,
        initialEventRows,
        budgets: {
          maxSingleBytes: MAX_SINGLE_SCRIPT_BYTES,
          maxTotalBytes: MAX_TOTAL_SCRIPT_BYTES,
          maxHtmlBytes: MAX_HTML_BYTES,
          maxHtmlElements: MAX_HTML_ELEMENTS,
          maxInitialEventRows: MAX_INITIAL_EVENT_ROWS,
        },
      },
      null,
      2,
    ),
  );

  if ((largest?.bytes ?? 0) > MAX_SINGLE_SCRIPT_BYTES) {
    fail(
      `largest homepage script is ${largest.bytes} bytes (${largest.source}); budget is ${MAX_SINGLE_SCRIPT_BYTES}`,
    );
  }
  if (totalBytes > MAX_TOTAL_SCRIPT_BYTES) {
    fail(`homepage scripts total ${totalBytes} bytes; budget is ${MAX_TOTAL_SCRIPT_BYTES}`);
  }
  if (htmlBytes > MAX_HTML_BYTES) {
    fail(`homepage HTML is ${htmlBytes} bytes; budget is ${MAX_HTML_BYTES}`);
  }
  if (htmlElements > MAX_HTML_ELEMENTS) {
    fail(`homepage has ${htmlElements} HTML elements; budget is ${MAX_HTML_ELEMENTS}`);
  }
  if (initialEventRows > MAX_INITIAL_EVENT_ROWS) {
    fail(
      `homepage renders ${initialEventRows} initial event rows; budget is ${MAX_INITIAL_EVENT_ROWS}`,
    );
  }
}
