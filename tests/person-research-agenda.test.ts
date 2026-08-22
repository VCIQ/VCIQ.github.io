import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizePersonResearchAgenda,
  normalizePersonResearchTask,
} from "../lib/person-research-agenda";

test("active research task normalization rejects unsupported state and unsafe evidence URLs", () => {
  const task = normalizePersonResearchTask({
    id: "task-1",
    taskType: "viewpoint_verification",
    priority: "P0",
    target: "世界模型",
    question: "是否真的发生观点转向？",
    objective: "回到原始上下文核验。",
    preferredEvidence: ["原始视频"],
    searchQueries: ["测试人物 世界模型"],
    successCriteria: "必须有一手上下文。",
    evidenceBasis: [{
      title: "unsafe",
      url: "javascript:alert(1)",
      source: "bad",
      date: "2026-08-01",
    }],
    candidateEvidence: [{
      title: "safe",
      url: "https://example.com/source",
      source: "Example",
      sourceLevel: "媒体报道",
      date: "2026-08-01",
    }],
    status: "candidate_found",
  });
  assert.ok(task);
  assert.equal(task.evidenceBasis.length, 0);
  assert.equal(task.candidateEvidence.length, 1);

  assert.equal(normalizePersonResearchTask({
    ...task,
    status: "verified-by-model",
  }), null);
});

test("agenda derives open counts from normalized task status instead of trusting payload counters", () => {
  const agenda = normalizePersonResearchAgenda({
    schemaVersion: 1,
    generatedAt: "2026-08-22T00:00:00Z",
    taskCount: 999,
    openTaskCount: 999,
    people: {
      "test-person": {
        personName: "测试人物",
        openCount: 999,
        tasks: [
          {
            id: "task-open",
            taskType: "first_party_evidence",
            priority: "P0",
            target: "世界模型",
            question: "能否找到本人一手材料？",
            objective: "补证据。",
            preferredEvidence: ["本人论文"],
            searchQueries: ["测试人物 世界模型"],
            successCriteria: "新增一条一手材料。",
            evidenceBasis: [],
            candidateEvidence: [],
            status: "open",
          },
          {
            id: "task-supported",
            taskType: "execution_verification",
            priority: "P1",
            target: "Example Labs · Atlas",
            question: "公司是否有独立执行证据？",
            objective: "区分人物表达和组织执行。",
            preferredEvidence: ["官方公告"],
            searchQueries: [],
            successCriteria: "官方来源直接命中组织和产品。",
            evidenceBasis: [],
            candidateEvidence: [],
            status: "supported",
          },
        ],
      },
    },
  });
  assert.equal(agenda.taskCount, 2);
  assert.equal(agenda.openTaskCount, 1);
  assert.equal(agenda.people["test-person"].openCount, 1);
});
