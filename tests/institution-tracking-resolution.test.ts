import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";
import { normalizeTrackingEntityResolution, resolveTrackingEntity } from "../lib/entity-resolution";

const names = ["CMC资本", "达晨财智", "中科创星", "高瓴投资", "联想之星", "元禾控股", "CPE源峰", "创新工场", "金浦投资", "鼎峰科创", "国投创新", "同创伟业", "美团龙珠", "中信金石", "鼎晖投资", "前海方舟", "国投创益", "Sinovation Ventures", "尚无核验的机构名字"];

test("Python and TypeScript agree on the audited investment institution identities", () => {
  const script = "import json,sys; from tools.entity_resolution import resolve_entity; print(json.dumps([resolve_entity('company',n).to_dict() for n in json.loads(sys.argv[1])],ensure_ascii=False))";
  const expected = JSON.parse(execFileSync("python3", ["-c", script, JSON.stringify(names)], { encoding: "utf8" }));
  names.forEach((name, index) => {
    const actual = resolveTrackingEntity({ requestedType: "company", name });
    for (const field of ["status", "entityType", "canonicalName", "targetId", "source"] as const) {
      assert.equal(actual[field], expected[index][field], `${name}: ${field}`);
    }
  });
});

test("stored institution resolutions retain the source instead of becoming unresolved", () => {
  const resolution = resolveTrackingEntity({ requestedType: "company", name: "创新工场" });
  assert.equal(normalizeTrackingEntityResolution(resolution)?.source, "institution-directory");
  assert.equal(resolution.targetId, "institution:创新工场");
});
