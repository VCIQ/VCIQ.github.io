import assert from "node:assert/strict";
import test from "node:test";
import {
  technologyTopicDefinitions,
  technologyTopicsForEntity,
  technologyTopicsForTrack,
} from "../lib/technology-topics";

test("technology topic taxonomy keeps exactly 20 stable primary topics", () => {
  assert.equal(technologyTopicDefinitions.length, 20);
  assert.equal(
    new Set(technologyTopicDefinitions.map((topic) => topic.slug)).size,
    technologyTopicDefinitions.length,
  );
  assert.equal(
    new Set(technologyTopicDefinitions.map((topic) => topic.alertQuery)).size,
    technologyTopicDefinitions.length,
  );
  for (const topic of technologyTopicDefinitions) {
    assert.ok(topic.name.trim());
    assert.ok(topic.alertQuery.trim());
    assert.ok(topic.trackNames.length > 0);
    assert.ok(topic.matchTerms.length > 0);
    assert.equal(/\bOR\b/u.test(topic.alertQuery), false);
  }
});

test("robotics track resolves the intended technology topic layer", () => {
  const names = technologyTopicsForTrack({ name: "机器人", aliases: [] }).map(
    (topic) => topic.name,
  );
  assert.ok(names.includes("具身智能"));
  assert.ok(names.includes("人形机器人"));
  assert.ok(names.includes("自动驾驶"));
  assert.ok(names.includes("世界模型"));
});

test("technology entities are mapped from public evidence text instead of track membership alone", () => {
  const names = technologyTopicsForEntity({
    name: "DeepSeek-V4-Flash-Vision-Exp",
    aliases: ["V4-Flash-Vision-Exp"],
    summary: "面向多模态 AI Agent 的视觉语言模型升级。",
    reasons: [],
    notes: [],
    researchThesis: "",
    timeline: [],
  }).map((topic) => topic.name);

  assert.ok(names.includes("大模型"));
  assert.ok(names.includes("多模态模型"));
  assert.ok(names.includes("AI 智能体"));
});
