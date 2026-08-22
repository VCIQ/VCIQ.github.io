import assert from "node:assert/strict";
import test from "node:test";
import { technologyTopicsForText } from "../lib/technology-topic-matching";
import { technologyTermMatchesText } from "../lib/technology-term-matching";
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

test("short ASCII technology terms require token boundaries", () => {
  assert.equal(technologyTermMatchesText("AI music startup", "SiC"), false);
  assert.equal(technologyTermMatchesText("A compact system with 96GB memory", "6G"), false);
  assert.equal(technologyTermMatchesText("forward-looking revenue guidance", "RWA"), false);
  assert.equal(technologyTermMatchesText("gantry automation system", "GaN"), false);

  assert.equal(technologyTermMatchesText("SiC power device", "SiC"), true);
  assert.equal(technologyTermMatchesText("6G network architecture", "6G"), true);
  assert.equal(technologyTermMatchesText("RWA tokenization platform", "RWA"), true);
  assert.equal(technologyTermMatchesText("GaN RF device", "GaN"), true);
});

test("four-character model brands still match attached version numbers", () => {
  assert.equal(technologyTermMatchesText("Qwen3.8-Max is released", "Qwen"), true);
  const names = technologyTopicsForText(["Qwen3.8-Max is released"]).map(
    (topic) => topic.name,
  );
  assert.ok(names.includes("大模型"));
});

test("ordinary prose cannot acquire acronym-driven technology topics", () => {
  const names = technologyTopicsForText([
    "A 96GB music workstation posts forward-looking guidance",
  ]).map((topic) => topic.name);

  assert.equal(names.includes("宽禁带半导体"), false);
  assert.equal(names.includes("6G"), false);
  assert.equal(names.includes("稳定币"), false);
});

test("entity topic matching uses the same acronym safety rules", () => {
  const names = technologyTopicsForEntity({
    name: "AI Music Workspace",
    aliases: [],
    summary: "A 96GB workstation for music creators with forward-looking revenue guidance.",
    reasons: [],
    notes: [],
    researchThesis: "",
    timeline: [],
  }).map((topic) => topic.name);

  assert.equal(names.includes("宽禁带半导体"), false);
  assert.equal(names.includes("6G"), false);
  assert.equal(names.includes("稳定币"), false);
});
