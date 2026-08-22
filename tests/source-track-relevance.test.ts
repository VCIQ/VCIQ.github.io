import assert from "node:assert/strict";
import test from "node:test";
import {
  classifySourceTrackProfile,
  sourceTrackWeightForEvidence,
} from "../lib/source-track-relevance";

test("broad source-track pairs with overwhelmingly weak evidence are severe", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 50,
      sourceTrackCount: 4,
      pairCount: 43,
      weakEvidenceCount: 37,
      directEvidenceCount: 5,
    }),
    "severe",
  );
});

test("mixed broad source-track pairs are moderate instead of globally blocked", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 21,
      sourceTrackCount: 3,
      pairCount: 19,
      weakEvidenceCount: 12,
      directEvidenceCount: 5,
    }),
    "moderate",
  );
});

test("small samples never trigger automatic source-track penalties", () => {
  assert.equal(
    classifySourceTrackProfile({
      sourceEventCount: 6,
      sourceTrackCount: 2,
      pairCount: 5,
      weakEvidenceCount: 5,
      directEvidenceCount: 0,
    }),
    "insufficient",
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
