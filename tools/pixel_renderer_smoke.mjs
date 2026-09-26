// Run: node tools/pixel_renderer_smoke.mjs
// Checks the standalone presentation contract without browser dependencies.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";

const calls = [];
const context = new Proxy({}, {get(target, key) {
  if (key in target) return target[key];
  return (...args) => {calls.push([key, args]);};
}, set(target, key, value) {target[key] = value; return true;}});
const canvas = {width: 720, height: 220, clientWidth: 720, clientHeight: 220,
  getContext: () => context,
  getBoundingClientRect: () => ({left: 10, top: 20, width: 720, height: 220})};
let resizeCallback, observedCanvas;
const sandbox = {window: {devicePixelRatio: 1,
  ResizeObserver: class {
    constructor(callback) { resizeCallback = callback; }
    observe(target) { observedCanvas = target; }
  }}, console};
runInNewContext(readFileSync(new URL("./pixel_renderer.js", import.meta.url), "utf8"), sandbox);
const renderer = sandbox.window.CsimPixelRenderer;
assert.equal(typeof renderer.render, "function");
assert.equal(typeof renderer.pickCell, "function");
assert.equal(typeof renderer.inspectCell, "function");

function state(mode, count) {
  const s = {mode, configuration: {cell_count: count, step_min: 6, horizon_steps: 82},
    seed: 743, replicate_id: "R03", timeline: [], accepted_steps: 0};
  if (mode === "nfkb") s.observation = {time_min: 0, remaining_steps: 82,
    field: {synthetic_stimulus: {amount_mol: .125, concentration_mol_m3: 1},
      generic_inhibitor_payload: {amount_mol: .05, concentration_mol_m3: .4}},
    cells: Array.from({length: count}, (_, i) => ({cell_id: `cell_${i + 1}`,
      payload_amount_mol: 0, nuclear_proxy: .1 * i, feedback: .02 * i,
      reporter_index: .03 * i}))};
  else if (mode === "arena") s.observation = {time_s: 0, remaining_steps: 8,
    field_amount_mol: .1, field_concentration_mol_m3: .8,
    cells: Array.from({length: count}, (_, i) => ({cell_id: `cell_${i + 1}`,
      amount_mol: .01 * i, memory: .1 * i}))};
  else if (mode === "ligand") s.observation = {time_s: 0, remaining_steps: 8,
    field_concentration_mol_m3: .4, sender_amount_mol: .1,
    receiver_amount_mol: 0, receiver_memory: .2};
  else s.observation = {time_s: 0, remaining_steps: 8,
    local_concentration_mol_m3: .4, cell_amount_mol: .01, accepted_memory: .2};
  return s;
}
let checks = 0;
for (const [mode, count] of [["nfkb", 5], ["arena", 3], ["ligand", 2], ["uptake", 1]]) {
  const s = state(mode, count), snapshot = JSON.stringify(s);
  const rendered = renderer.render(canvas, s, {selectedCellId: mode === "ligand" ? "sender" : "cell_1",
    overlayCondition: {observed: {p10: [.1,.2], p50: [.2,.3], p90: [.3,.4]},
      model_prediction: [.25,.35], ligand_sequence: ["T","I","P","L"]},
    simulationBand: {p10: [.1,.15], p50: [.2,.25], p90: [.3,.35]},
    switchTimesMin: [0,120,240,360]});
  assert.equal(rendered.mode, mode);
  assert.equal(rendered.cellHitboxes.length, count);
  for (const cell of rendered.cellHitboxes) {
    const hit = renderer.pickCell(canvas, {clientX: cell.cx + 10, clientY: cell.cy + 20}, s);
    assert.equal(hit, cell.id);
  }
  assert.deepEqual(JSON.stringify(s), snapshot);
  checks++;
}
canvas.getBoundingClientRect = () => ({left: 10, top: 20, width: 560, height: 220});
const five = renderer.render(canvas, state("nfkb", 5));
for (let i = 1; i < five.cellHitboxes.length; i++)
  assert.ok(five.cellHitboxes[i - 1].x + five.cellHitboxes[i - 1].width <
    five.cellHitboxes[i].x, "five cell hitboxes remain distinct in compact scene");
checks++;
canvas.getBoundingClientRect = () => ({left: 10, top: 20, width: 720, height: 220});
const nf = state("nfkb", 3), before = structuredClone(nf.observation);
nf.observation.time_min = 6;
nf.observation.cells[1].payload_amount_mol = .003;
nf.observation.cells[1].nuclear_proxy = .42;
nf.timeline.push({index: 1, kind: "accepted", before, proposal: {stimulus_code: "T"},
  transition: {observation: structuredClone(nf.observation), info: {
    payload_transfers_mol_by_cell: {cell_1: 0, cell_2: .003, cell_3: 0}}}});
const inspected = renderer.inspectCell(nf, "cell_2");
assert.equal(inspected.values.find(v => v.label === "Payload amount").before, 0);
assert.equal(inspected.values.find(v => v.label === "Payload amount").after, .003);
assert.equal(inspected.transferMol, .003);
assert.equal(inspected.seed, 743);
checks++;
nf.timeline.push({index: 2, kind: "rejected", before: structuredClone(nf.observation),
  state_unchanged: true});
assert.equal(renderer.inspectCell(nf, "cell_2").stateUnchanged, true);
assert.equal(renderer.inspectCell(nf, "cell_2").transferMol, 0);
checks++;
assert.equal(renderer.pickCell(canvas, {clientX: -100, clientY: -100}, nf), null);
checks++;
const invalid = state("arena", 1);
invalid.observation.field_concentration_mol_m3 = -.2;
calls.length = 0;
renderer.render(canvas, invalid);
assert.ok(calls.some(([name, args]) => name === "fillText" &&
  String(args[0]).includes("-0.2")), "invalid negative concentration must remain visible");
checks++;
assert.ok(calls.some(([name]) => name === "fillRect"));
assert.equal(observedCanvas, canvas);
const lastState = state("nfkb", 3);
renderer.render(canvas, lastState);
canvas.getBoundingClientRect = () => ({left: 10, top: 20, width: 610, height: 190});
calls.length = 0;
resizeCallback();
assert.equal(canvas.width, 610, "CSS resize repaints backing store without a new state event");
assert.equal(canvas.height, 190);
assert.ok(calls.some(([name]) => name === "fillRect"), "CSS resize repaints scene");
checks++;
console.log(`pixel renderer smoke: ${checks} scenario/transition checks passed; 1–5 cells, click picking, bands, seed, accepted/rejected inspection, post-layout repaint`);
