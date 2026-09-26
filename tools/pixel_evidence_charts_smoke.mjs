// Run: node tools/pixel_evidence_charts_smoke.mjs
// Exercises the read-only chart contract against preserved local artifacts.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";

const sandbox = {window: {devicePixelRatio: 1}};
runInNewContext(readFileSync(new URL("./pixel_evidence_charts.js", import.meta.url), "utf8"), sandbox);
const evidence = sandbox.window.CsimPixelEvidence;
const overlay = JSON.parse(readFileSync(new URL("../runs/nfkb_metadata_20260926_01/demo_overlay.json", import.meta.url)));
const seeded = JSON.parse(readFileSync(new URL("../runs/seeded_nfkb_demo_20260926_01/results.json", import.meta.url)));
let checks = 0;

const three = evidence.summarize(overlay, seeded, 3, 2);
assert.equal(three.observed.time.length, 83);
assert.equal(three.observed.rowCount, 76);
assert.equal(three.observed.split, "evaluation");
assert.equal(three.simulated.trajectoryCount, 12);
assert.equal(three.simulated.seeds.join(","), "7,17,29,43");
assert.equal(three.simulated.time.length, three.observed.time.length);
assert.ok(three.simulated.low.every((x, i) =>
  x <= three.simulated.median[i] && three.simulated.median[i] <= three.simulated.high[i]));
checks++;

for (const count of [1, 5]) {
  const result = evidence.summarize(overlay, seeded, count, 2);
  assert.equal(result.simulated.trajectoryCount, count * 4);
  assert.equal(result.observed.conditionId, 2);
  checks++;
}
for (const count of [2, 4]) {
  const result = evidence.summarize(overlay, seeded, count, 2);
  assert.equal(result.simulated, null);
  assert.match(result.reason, /No preserved seeded cohort/);
  checks++;
}
assert.throws(() => evidence.summarize(overlay, seeded, 3, 1), /identities do not match/);
checks++;
const wrongSource = structuredClone(seeded);
wrongSource.observed_schedule.source_matrix_sha256 = "different-source";
assert.throws(() => evidence.summarize(overlay, wrongSource, 3, 2), /source or schedule identities/);
checks++;

const calls = [];
const ctx = new Proxy({}, {get(target, key) {
  return key in target ? target[key] : (...args) => calls.push([key, args]);
}, set(target, key, value) {target[key] = value; return true;}});
const canvas = {width: 0, height: 0, getBoundingClientRect: () => ({width: 510, height: 177}),
  getContext: () => ctx};
evidence.renderChart(canvas, three.observed, "observed");
assert.equal(canvas.width, 510);
assert.equal(canvas.height, 177);
assert.ok(calls.some(([method]) => method === "fill"), "observed dispersion band is drawn");
checks++;
calls.length = 0;
evidence.renderChart(canvas, three.simulated, "simulated");
assert.ok(calls.some(([method]) => method === "lineTo"), "seeded cell trajectories are drawn");
checks++;
calls.length = 0;
evidence.renderChart(canvas, null, "simulated");
assert.ok(calls.some(([method, args]) => method === "fillText" &&
  String(args[0]).includes("No matched preserved cohort")));
checks++;

console.log(`pixel evidence charts smoke: ${checks} checks passed; condition 2 observed rows, seeded 1/3/5 cohorts, missing 2/4 cohorts, condition mismatch, chart draw`);
