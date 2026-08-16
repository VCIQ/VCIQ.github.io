import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";

 test("batch 2 new-track proposal passes taxonomy and discovery prechecks", () => {
  const result = spawnSync("python", ["tools/validate_new_track_proposal.py"], {
    cwd: process.cwd(),
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  const output = JSON.parse(result.stdout.trim());
  assert.equal(output.valid, true);
  assert.equal(output.exactProductionTermCollisions, 0);
  assert.deepEqual(output.proposedTracks, ["cyber-insurtech", "public-markets"]);
  assert.equal(output.generatedDiscoveryRoutes["cyber-insurtech"].length, 4);
  assert.equal(output.generatedDiscoveryRoutes["public-markets"].length, 4);
  assert.equal(output.listedCompanyGate.name, "恒锋信息");
  assert.equal(output.listedCompanyGate.market, "A股");
  assert.equal(output.listedCompanyGate.ticker, "300605");
  assert.equal(output.listedCompanyGate.alreadyRegistered, false);
});
