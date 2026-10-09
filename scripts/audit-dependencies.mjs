#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const BRACE_EXPANSION_ADVISORY = "GHSA-MH99-V99M-4GVG";
// GHSA-VFJ7-8CJW-P6XM has no upstream patched npm release as of 2026-10-09.
// Bound the exception to the exact, dev-only micromatch -> braces path below.
const BRACES_DEV_ADVISORY = "GHSA-VFJ7-8CJW-P6XM";
const IMAGE_SIZE_DEV_ADVISORIES = new Set([
  "GHSA-W3RX-R6R6-PGPR",
  "GHSA-5P2G-FCMC-QVQQ",
]);
const ALLOWED_DEV_ADVISORIES = new Set([
  BRACE_EXPANSION_ADVISORY,
  BRACES_DEV_ADVISORY,
  ...IMAGE_SIZE_DEV_ADVISORIES,
]);
const SAFE_BRACE_EXPANSION_BACKPORTS = new Set([
  "1.1.16",
  "2.1.2",
  "3.0.2",
  "5.0.8",
]);
const EXPECTED_IMAGE_SIZE_DEV_VERSION = "2.0.2";
const EXPECTED_VINEXT_VERSION = "0.0.50";

function runAudit(args) {
  const result = spawnSync("npm", ["audit", "--json", ...args], {
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
  });
  let payload;
  try {
    payload = JSON.parse(result.stdout || "{}");
  } catch (error) {
    console.error(result.stdout);
    console.error(result.stderr);
    throw new Error(`npm audit did not return valid JSON: ${error.message}`);
  }
  return { result, payload };
}

function advisoryId(entry) {
  if (!entry || typeof entry !== "object") return "";
  const url = String(entry.url || "");
  const match = url.match(/GHSA-[a-z0-9-]+/i);
  return match ? match[0].toUpperCase() : "";
}

function directAdvisories(payload) {
  const advisories = [];
  for (const [packageName, detail] of Object.entries(payload.vulnerabilities || {})) {
    for (const via of detail.via || []) {
      if (via && typeof via === "object") {
        advisories.push({ packageName, id: advisoryId(via), via });
      }
    }
  }
  return advisories;
}

function loadLock() {
  return JSON.parse(readFileSync("package-lock.json", "utf8"));
}

function validateBraceExpansionBackports(lock = loadLock()) {
  const installed = [];
  for (const [path, detail] of Object.entries(lock.packages || {})) {
    if (
      path === "node_modules/brace-expansion" ||
      path.endsWith("/node_modules/brace-expansion")
    ) {
      installed.push({ path, version: String(detail.version || "") });
    }
  }
  if (installed.length === 0) {
    throw new Error(
      "package-lock.json contains no brace-expansion installation to validate",
    );
  }
  const unsafe = installed.filter(
    ({ version }) => !SAFE_BRACE_EXPANSION_BACKPORTS.has(version),
  );
  if (unsafe.length > 0) {
    throw new Error(
      `unsafe brace-expansion versions in lockfile: ${JSON.stringify(unsafe)}`,
    );
  }
  console.log(
    `Validated official brace-expansion maintenance releases: ${installed
      .map(({ version }) => version)
      .join(", ")}`,
  );
}

function validateImageSizeDevIsolation(lock = loadLock()) {
  const packages = lock.packages || {};
  const imageSize = packages["node_modules/image-size"];
  const vinext = packages["node_modules/vinext"];
  if (!imageSize || !vinext) {
    throw new Error("expected vinext and image-size installations are absent");
  }
  if (
    String(imageSize.version || "") !== EXPECTED_IMAGE_SIZE_DEV_VERSION ||
    imageSize.dev !== true
  ) {
    throw new Error(
      `image-size advisory is only accepted for dev-only ${EXPECTED_IMAGE_SIZE_DEV_VERSION}; ` +
        `found ${JSON.stringify({ version: imageSize.version, dev: imageSize.dev })}`,
    );
  }
  if (
    String(vinext.version || "") !== EXPECTED_VINEXT_VERSION ||
    vinext.dev !== true ||
    String(vinext.dependencies?.["image-size"] || "") !==
      EXPECTED_IMAGE_SIZE_DEV_VERSION
  ) {
    throw new Error(
      `image-size advisory is only accepted through dev-only vinext ${EXPECTED_VINEXT_VERSION}`,
    );
  }

  const consumers = [];
  for (const [path, detail] of Object.entries(packages)) {
    if (detail?.dependencies?.["image-size"]) {
      consumers.push({
        path,
        version: String(detail.version || ""),
        range: String(detail.dependencies["image-size"] || ""),
        dev: detail.dev === true,
      });
    }
  }
  const unexpected = consumers.filter(
    ({ path, range, dev }) =>
      path !== "node_modules/vinext" ||
      range !== EXPECTED_IMAGE_SIZE_DEV_VERSION ||
      dev !== true,
  );
  if (unexpected.length > 0 || consumers.length !== 1) {
    throw new Error(
      `image-size advisory escaped the expected vinext-only dev boundary: ${JSON.stringify(
        consumers,
      )}`,
    );
  }

  const manifest = JSON.parse(readFileSync("package.json", "utf8"));
  if (
    manifest.dependencies?.["image-size"] ||
    manifest.devDependencies?.["image-size"]
  ) {
    throw new Error("image-size must remain transitive and may not become a direct dependency");
  }
  console.log(
    `Validated image-size ${EXPECTED_IMAGE_SIZE_DEV_VERSION} is isolated to dev-only ` +
      `vinext ${EXPECTED_VINEXT_VERSION}; production audit remains clean.`,
  );
}

function validateBracesDevIsolation(lock = loadLock()) {
  const packages = lock.packages || {};
  const installations = Object.entries(packages).filter(
    ([path]) => path === "node_modules/braces" || path.endsWith("/node_modules/braces"),
  );
  if (
    installations.length !== 1 ||
    installations[0][0] !== "node_modules/braces" ||
    installations[0][1].version !== "3.0.3" ||
    installations[0][1].dev !== true
  ) {
    throw new Error("braces advisory can only be accepted for the pinned dev-only 3.0.3 installation");
  }

  const consumers = Object.entries(packages).filter(
    ([, entry]) => entry?.dependencies?.braces || entry?.optionalDependencies?.braces,
  );
  if (
    consumers.length !== 1 ||
    consumers[0][0] !== "node_modules/micromatch" ||
    consumers[0][1].dev !== true ||
    consumers[0][1].version !== "4.0.8" ||
    consumers[0][1].dependencies?.braces !== "^3.0.3"
  ) {
    throw new Error("braces advisory escaped the approved dev-only micromatch dependency path");
  }

  const manifest = JSON.parse(readFileSync("package.json", "utf8"));
  if (manifest.dependencies?.braces || manifest.devDependencies?.braces) {
    throw new Error("braces must remain transitive, not a direct dependency");
  }

  console.log(
    "Validated unpatched braces 3.0.3 is restricted to dev-only micromatch 4.0.8; " +
      "production audit remains clean. Recheck when upstream publishes a fix.",
  );
}

const production = runAudit(["--omit=dev", "--audit-level=high"]);
if (production.result.status !== 0) {
  console.error(JSON.stringify(production.payload, null, 2));
  throw new Error("high or critical production dependency vulnerability detected");
}
console.log(
  "Production dependency audit passed with no high or critical vulnerabilities.",
);

const full = runAudit(["--audit-level=high"]);
if (full.result.status === 0) {
  console.log("Full dependency audit passed with no high or critical vulnerabilities.");
  process.exit(0);
}

const advisories = directAdvisories(full.payload);
const unapproved = advisories.filter(
  ({ id }) => !id || !ALLOWED_DEV_ADVISORIES.has(id),
);
if (unapproved.length > 0) {
  console.error(JSON.stringify(full.payload, null, 2));
  throw new Error(
    `unapproved high or critical development advisory detected: ${JSON.stringify(
      unapproved.map(({ packageName, id }) => ({ packageName, id })),
    )}`,
  );
}

const presentIds = new Set(advisories.map(({ id }) => id));
const lock = loadLock();
if (presentIds.has(BRACE_EXPANSION_ADVISORY)) {
  validateBraceExpansionBackports(lock);
}
if (presentIds.has(BRACES_DEV_ADVISORY)) {
  validateBracesDevIsolation(lock);
}
if ([...IMAGE_SIZE_DEV_ADVISORIES].some((id) => presentIds.has(id))) {
  validateImageSizeDevIsolation(lock);
}

console.log(
  "All remaining high-severity npm audit findings are explicitly bounded to " +
    "validated development-only dependency paths; any new advisory or dependency " +
    "path still fails closed.",
);
