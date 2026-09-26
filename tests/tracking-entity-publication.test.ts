import assert from "node:assert/strict";
import test from "node:test";

import rawInbox from "../config/tracking_capture_inbox.json";
import {
  normalizeTrackingCaptureInbox,
  type TrackingCaptureRecord,
} from "../lib/tracking-capture";
import {
  isPublishableTrackingCapture,
  publishedTrackingCaptureDescriptor,
} from "../lib/tracking-entity-publication";
import {
  normalizeTrackingResearchIdentity,
  trackingResearchEntities,
} from "../lib/tracking-entity-research";

function capture(
  overrides: Partial<TrackingCaptureRecord> = {},
): TrackingCaptureRecord {
  return {
    id: "capture-test",
    entityType: "company",
    canonicalName: "Example",
    rawSelection: "Example",
    aliases: [],
    trackSlugs: ["ai"],
    trackNames: ["AI / AGI"],
    source: {
      articleId: "article-test",
      title: "Example source",
      url: "https://example.com/source",
      summary: "",
      sourceName: "Example",
      channel: "technology",
      channelLabel: "新兴科技",
      eventType: "公司动态",
    },
    capturedAt: "2026-08-06T00:00:00Z",
    capturedBy: "VCIQ",
    status: "applied",
    appliedTo: ["ai:sampleCompanies"],
    reasons: [],
    note: "",
    ...overrides,
  };
}

function resolution(status: "resolved" | "review" | "rejected") {
  return {
    status,
    requestedType: "company" as const,
    entityType: status === "resolved" ? ("topic" as const) : ("person" as const),
    canonicalName: status === "resolved" ? "TypeScript" : "Matt",
    targetId: status === "resolved" ? "topic:typescript" : "",
    confidence: status === "resolved" ? ("verified" as const) : ("low" as const),
    source: "human-decision" as const,
    reason: "test",
    decisionKey: status === "resolved" ? "typescript" : "matt",
    reclassified: true,
  };
}

test("public capture eligibility requires a final resolved identity", () => {
  assert.equal(
    isPublishableTrackingCapture(capture()),
    false,
    "legacy applied records without a resolution must remain internal",
  );
  assert.equal(
    isPublishableTrackingCapture(capture({ resolution: resolution("resolved") })),
    true,
  );
  assert.equal(isPublishableTrackingCapture(capture({ status: "queued" })), false);
  assert.equal(isPublishableTrackingCapture(capture({ status: "dismissed" })), false);
  assert.equal(
    isPublishableTrackingCapture(capture({ resolution: resolution("review") })),
    false,
  );
  assert.equal(
    isPublishableTrackingCapture(capture({ resolution: resolution("rejected") })),
    false,
  );
});

test("public capture descriptor uses only the final resolved identity", () => {
  assert.deepEqual(
    publishedTrackingCaptureDescriptor(
      capture({
        entityType: "company",
        canonicalName: "TypeScript",
        resolution: resolution("resolved"),
      }),
    ),
    { entityType: "topic", canonicalName: "TypeScript" },
  );
  assert.equal(publishedTrackingCaptureDescriptor(capture()), undefined);
  assert.equal(
    publishedTrackingCaptureDescriptor(
      capture({ status: "queued", resolution: resolution("review") }),
    ),
    undefined,
  );
});

test("production applied records without a final identity stay out of the public graph", () => {
  const inbox = normalizeTrackingCaptureInbox(rawInbox);
  const applied = inbox.records.filter((record) => record.status === "applied");
  assert.ok(applied.length > 0, "expected at least one production applied record");

  for (const record of applied) {
    if (record.resolution?.status === "resolved") {
      assert.ok(
        publishedTrackingCaptureDescriptor(record),
        `${record.id} (${record.canonicalName}) has a resolved identity but is not publishable`,
      );
      continue;
    }

    assert.equal(
      isPublishableTrackingCapture(record),
      false,
      `${record.id} (${record.canonicalName}) must remain private until identity resolution is final`,
    );
    assert.equal(
      publishedTrackingCaptureDescriptor(record),
      undefined,
      `${record.id} (${record.canonicalName}) leaked an unresolved identity into the public graph`,
    );
  }
});

test("production review records never enter the public research entity graph", () => {
  const inbox = normalizeTrackingCaptureInbox(rawInbox);
  const reviewRecords = inbox.records.filter(
    (record) => record.resolution?.status === "review",
  );
  assert.ok(reviewRecords.length > 0, "expected at least one production review record");

  for (const record of reviewRecords) {
    assert.equal(isPublishableTrackingCapture(record), false, record.canonicalName);
    for (const entity of trackingResearchEntities) {
      assert.ok(
        entity.timeline.every(
          (item) => item.id !== record.id && !item.captureIds.includes(record.id),
        ),
        `${record.canonicalName} review evidence leaked into ${entity.id}`,
      );
    }
  }
});

test("production TypeScript, Matt and GitHub routes respect resolved identity", () => {
  const byName = (name: string) => {
    const key = normalizeTrackingResearchIdentity(name);
    return trackingResearchEntities.filter(
      (entity) => normalizeTrackingResearchIdentity(entity.name) === key,
    );
  };

  assert.deepEqual(
    [...new Set(byName("TypeScript").map((entity) => entity.entityType))],
    ["topic"],
  );
  assert.equal(byName("Matt").length, 0);
  assert.ok(
    byName("GitHub").some((entity) => entity.entityType === "company"),
    "GitHub must remain a public company entity",
  );
});
