# Pixel renderer integration contract

The standalone module owns presentation only. It does not call the server,
advance an episode, mutate a snapshot, or alter the running `:8766` process.
Serve `tools/pixel_renderer.js` at `/pixel_renderer.js` and
`tools/pixel_renderer.css` at `/pixel_renderer.css`, then include them in the
playground page. Place a canvas and optional inspector in a
`.csim-pixel-layout` container. Keep the canvas at the CSS controlled height
(220 px at desktop widths); the renderer sizes its backing store to that
rectangle and redraws on demand.
The renderer also observes CSS rectangle changes and repaints the most recent
snapshot after a late stylesheet or responsive layout change.

```html
<link rel="stylesheet" href="/pixel_renderer.css">
<div class="csim-pixel-layout">
  <canvas id="pixel-scene" class="csim-pixel-canvas" tabindex="0"
          aria-label="Shared field and selectable cell instances"></canvas>
  <div id="pixel-inspector" class="csim-pixel-inspector" aria-live="polite"></div>
</div>
<script src="/pixel_renderer.js"></script>
```

Use the complete `/api/state` snapshot for the `state` argument. The renderer
also accepts a bare episode observation for a static view. It infers uptake,
ligand, arena, and NF-κB observations; `state.mode` takes priority. It supports
one to five cell identities and the `cellsim_v2.nfkb_episode.NfkbEpisode`
`field`, `cells`, and `time_min` structure, including the seeded wrapper's
`response_variant_id` and accepted-step `info.variability.seed`.

```js
const scene = document.getElementById("pixel-scene");
const panel = document.getElementById("pixel-inspector");
let selectedCellId = null;

function updatePixel(state, observedOverlay, simulationBand) {
  const options = {
    selectedCellId,
    overlayCondition: observedOverlay?.condition,
    switchTimesMin: observedOverlay?.switch_times_min,
    simulationBand,
  };
  CsimPixelRenderer.render(scene, state, options);
  CsimPixelRenderer.renderInspector(panel, state, selectedCellId);
}

scene.addEventListener("click", event => {
  selectedCellId = CsimPixelRenderer.pickCell(scene, event, state);
  updatePixel(state, observedOverlay, simulationBand);
});
window.addEventListener("resize", () => updatePixel(state, observedOverlay, simulationBand));
```

Call `updatePixel` after reset, step, replay, selected observed condition change,
and resize. `render` returns `{mode,width,height,cellHitboxes,selectedCellId,
latestStatus}`. `pickCell` returns a cell ID or `null`. `inspectCell(state,id)`
returns a data object without DOM operations; `renderInspector` creates safe
text nodes and returns the same model. Keyboard selection can cycle IDs from
`state.observation.cells` when the focused canvas receives Enter or Space.

`options.overlayCondition` accepts a condition from
`runs/nfkb_metadata_20260926_01/demo_overlay.json`: `observed.mean`,
`observed.p10/p50/p90`, `model_prediction`, and `ligand_sequence` are used
only for display labels, the observed row-dispersion strip, and switch codes.
Pass the artifact's `switch_times_min` as `options.switchTimesMin`.
`options.simulationBand` is a separate explicit `{p10,p50,p90}` object
computed from a **declared** synthetic replicate aggregation. The renderer
does not derive a simulation band from cell trajectories or claim that measured
row dispersion calibrates an intrinsic stochastic law. Optional
`options.switches` can instead provide `[{time_min,code}]`. Seed and replicate
badges use `state.seed`, `state.configuration.seed`, `state.replicate_id`, or
accepted transition metadata when present.

The inspector displays paired transfer amounts and before/after values from
the latest timeline event. Rejected intervals show retained state and no
transfer arrow. Accepted per-cell traces are taken from accepted timeline
observations; they are illustrative proxy states, not observed p65 traces.
Observed p65, empirical fitted prediction, and synthetic reporter proxy stay
separate in labels. The OSS receipt is the primary execution evidence in the
inspector when `oss_atom_id` exists; an optional Engine ID is shown only when
present. Neither receipt is a biological validation claim.

For the compact playground layout, serve `tools/playground_pixel_theme.css`
at `/playground_pixel_theme.css` and include it after the base and renderer
stylesheets. It turns the three setup/advance/export sections into a horizontal
control grid and keeps the pixel scene before the numeric cards.

Run `node tools/pixel_renderer_smoke.mjs` for the isolated API smoke and
`node tools/pixel_evidence_charts_smoke.mjs` for the preserved-artifact plots.
For manual inspection, serve the checkout root on an unused local port (for
example `python -m http.server 8767 --bind 127.0.0.1`) and open
`/tools/pixel_renderer_preview.html`. The scene controls are synthetic UI
fixtures. The two smooth plots load read-only JSON from the preserved observed
overlay and seeded episode, condition 2. The observed plot shows source-row
p10/p50/p90, mean and frozen empirical fit; the synthetic plot shows individual
reporter-proxy trajectories, pooled pointwise p10/p50/p90 and its deterministic
baseline on a separate vertical scale. `pixel_evidence_charts.js` checks
condition, split, source-matrix hash, sequence key and time grids before
displaying a paired view. Preserved seeded cohorts exist for 1, 3 and 5
cells; 2 and 4 report their absence. The preview does not call `:8766`.
