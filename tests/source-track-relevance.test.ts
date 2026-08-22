import assert from "node:assert/strict";
import test from "node:test";
import {
  classifySourceTrackProfile,
  sourceTrackWeightForEvidence,
} from "../lib/source-track-relevance";

test("broad source-track pairs with persistent weak evidence are severe", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 50,
      sourceTrackCount: 4,
      pairCount: 43,
      weakEvidenceCount: 37,
      directEvidenceCount: 5,
      observedDayCount: 5,
      observationSpanDays: 10,
    }),
    "severe",
  );
});

test("mixed broad source-track pairs are moderate after multi-day observation", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 21,
      sourceTrackCount: 3,
      pairCount: 19,
      weakEvidenceCount: 12,
      directEvidenceCount: 5,
      observedDayCount: 3,
      observationSpanDays: 7,
    }),
    "moderate",
  );
});

test("small samples never trigger automatic source-track penalties", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 50,
      sourceTrackCount: 4,
      pairCount: 5,
      weakEvidenceCount: 5,
      directEvidenceCount: 0,
      observedDayCount: 4,
      observationSpanDays: 10,
    }),
    "insufficient",
  );
});

test("noisy profiles remain provisional until evidence persists across observation days", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 50,
      sourceTrackCount: 4,
      pairCount: 12,
      weakEvidenceCount: 10,
      directEvidenceCount: 1,
      observedDayCount: 1,
      observationSpanDays: 0,
    }),
    "provisional",
  );
  assert.deepEqual(
    sourceTrackWeightForEvidence({
      profileStatus: "provisional",
      contentStatus: "weak-evidence",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
    }),
    { status: "provisional", weight: 1 },
  );
});

test("severe signal degrades only to moderate while temporal evidence is still maturing", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 50,
      sourceTrackCount: 4,
      pairCount: 12,
      weakEvidenceCount: 10,
      directEvidenceCount: 1,
      observedDayCount: 2,
      observationSpanDays: 4,
    }),
    "moderate",
  );
});

test("priority topic and crawler-usable evidence bypass a severe source-track profile", () => {
  assert.deepEqual(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "priority-topic",
      priorityTopic: true,
      primaryEvidence: false,
      companyEvidence: false,
    }),
    { status: "bypass-strong-evidence", weight: 1 },
  );
  assert.deepEqual(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "usable",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
    }),
    { status: "bypass-strong-evidence", weight: 1 },
  );
});

test("official company and human-reviewed evidence bypass source-track penalties", () => {
  assert.equal(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "weak-evidence",
      priorityTopic: false,
      primaryEvidence: true,
      companyEvidence: false,
    }).weight,
    1,
  );
  assert.equal(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "weak-evidence",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: true,
    }).weight,
    1,
  );
  assert.equal(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "weak-evidence",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
      canonicalReviewed: true,
    }).weight,
    1,
  );
});

test("only weak or partial events receive the empirical source-track multiplier", () => {
  assert.deepEqual(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "weak-evidence",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
    }),
    { status: "severe-downweight", weight: 0.5 },
  );
  assert.deepEqual(
    sourceTrackWeightForEvidence({
      profileStatus: "moderate",
      contentStatus: "partial-evidence",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
    }),
    { status: "moderate-downweight", weight: 0.75 },
  );
  assert.equal(
    sourceTrackWeightForEvidence({
      profileStatus: "severe",
      contentStatus: "unassessed",
      priorityTopic: false,
      primaryEvidence: false,
      companyEvidence: false,
    }).weight,
    1,
  );
});
