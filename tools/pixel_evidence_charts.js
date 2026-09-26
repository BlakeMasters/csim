/* Read-only browser plots for the preserved local NF-kB artifacts.
 * Observed p65 and synthetic reporter use independent vertical axes. */
(function (root) {
  "use strict";
  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  const percentile = (sorted, p) => {
    const at = (sorted.length - 1) * p, lo = Math.floor(at), hi = Math.ceil(at);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (at - lo);
  };
  function summarize(overlay, seeded, cellCount, conditionId) {
    if (overlay?.status !== "pass" || seeded?.status !== "pass")
      throw new Error("Preserved observed and seeded artifacts must both have pass status");
    const condition = overlay.conditions?.find((c) => c.condition_id === conditionId);
    if (!condition || seeded.observed_schedule?.condition_id !== conditionId)
      throw new Error("Observed and seeded condition identities do not match");
    if (seeded.observed_schedule.sequence_key !== condition.sequence_key ||
        seeded.observed_schedule.split !== condition.split ||
        seeded.observed_schedule.source_matrix_sha256 !== overlay.source?.sha256)
      throw new Error("Observed and seeded source or schedule identities do not match");
    const obs = condition.observed, time = obs?.time_min;
    if (!Array.isArray(time) || time.length < 2 ||
        ![obs.p10, obs.p50, obs.p90, obs.mean, condition.model_prediction].every(
          (a) => Array.isArray(a) && a.length === time.length))
      throw new Error("Observed overlay lacks aligned time, dispersion, mean, or fit arrays");
    const observed = {
      time: time.slice(), low: obs.p10.slice(), median: obs.p50.slice(),
      high: obs.p90.slice(), mean: obs.mean.slice(), fit: condition.model_prediction.slice(),
      rowCount: condition.row_count, finiteCounts: obs.finite_count_by_time.slice(),
      split: condition.split, conditionId, switchTimes: overlay.switch_times_min.slice(),
      switchCodes: condition.ligand_sequence.slice(),
    };
    const cohort = seeded.cell_count_cases?.[String(cellCount)];
    if (!cohort) return {observed, simulated: null,
      reason: `No preserved seeded cohort for ${cellCount} cells. Choose 1, 3, or 5.`};
    const series = [], seeds = [];
    for (const replicate of cohort.replicates || []) {
      if (replicate.cell_count !== cellCount || replicate.curve?.length !== time.length)
        throw new Error("Seeded replicate shape does not match the selected cohort");
      if (!replicate.curve.every((row, i) => row.time_min === time[i]))
        throw new Error("Seeded and observed time grids differ");
      seeds.push(replicate.seed);
      const ids = Object.keys(replicate.curve[0].reporter_index_by_cell).sort();
      if (ids.length !== cellCount) throw new Error("Seeded cell count differs from declared cohort");
      for (const id of ids) {
        const values = replicate.curve.map((row) => row.reporter_index_by_cell?.[id]);
        if (!values.every(finite)) throw new Error("Nonfinite seeded reporter proxy");
        series.push({seed: replicate.seed, cellId: id, values});
      }
    }
    if (!series.length) throw new Error("Selected seeded cohort has no cell trajectories");
    const low = [], median = [], high = [];
    for (let i = 0; i < time.length; i++) {
      const sorted = series.map((s) => s.values[i]).sort((a, b) => a - b);
      low.push(percentile(sorted, .1));
      median.push(percentile(sorted, .5));
      high.push(percentile(sorted, .9));
    }
    const baselineCurve = cohort.baseline?.curve;
    const baseline = Array.isArray(baselineCurve) && baselineCurve.length === time.length ?
      baselineCurve.map((row, i) => {
        if (row.time_min !== time[i]) throw new Error("Baseline time grid differs");
        const values = Object.values(row.reporter_index_by_cell || {});
        if (!values.length || !values.every(finite)) throw new Error("Invalid baseline reporter proxy");
        return values.reduce((a, b) => a + b, 0) / values.length;
      }) : null;
    return {observed, simulated: {time: time.slice(), low, median, high, series,
      switchTimes: observed.switchTimes.slice(),
      baseline, seeds, cellCount, trajectoryCount: series.length,
      quantileMethod: "linear interpolation across pooled cell trajectories at each time"},
      reason: null};
  }
  function renderChart(canvas, data, kind) {
    if (!canvas || typeof canvas.getContext !== "function") throw new TypeError("Canvas required");
    const rect = canvas.getBoundingClientRect(), w = Math.max(250, Math.round(rect.width)),
      h = Math.max(130, Math.round(rect.height));
    const dpr = Math.max(1, Math.min(2, Math.round(root.devicePixelRatio || 1)));
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0c1b2b"; ctx.fillRect(0, 0, w, h);
    if (!data) {
      ctx.fillStyle = "#b7d1da"; ctx.font = "12px Consolas, monospace";
      ctx.fillText("No matched preserved cohort", 20, h / 2);
      return;
    }
    const left = 46, right = w - 13, top = 11, bottom = h - 25;
    const values = data.low.concat(data.high, data.median,
      kind === "observed" ? data.mean.concat(data.fit) :
        (data.baseline || []).concat(...data.series.map((s) => s.values)))
      .filter(finite);
    if (!values.length) return;
    let ymin = Math.min(...values), ymax = Math.max(...values);
    const pad = Math.max((ymax - ymin) * .07, 1e-6);
    ymin -= pad; ymax += pad;
    const start = data.time[0], end = data.time[data.time.length - 1];
    const x = (t) => left + (right - left) * (t - start) / (end - start);
    const y = (v) => bottom - (bottom - top) * (v - ymin) / (ymax - ymin);
    ctx.font = "10px Consolas, monospace"; ctx.textAlign = "right";
    for (let i = 0; i <= 3; i++) {
      const v = ymin + (ymax - ymin) * i / 3, yy = y(v);
      ctx.strokeStyle = "#294258"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(right, yy); ctx.stroke();
      ctx.fillStyle = "#adc6d2"; ctx.fillText(Number(v.toPrecision(2)).toString(), left - 5, yy + 3);
    }
    const switches = data.switchTimes || [];
    for (const t of switches) {
      if (t < start || t > end) continue;
      const xx = x(t);
      ctx.strokeStyle = "#694e31"; ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.moveTo(xx, top); ctx.lineTo(xx, bottom); ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.textAlign = "center";
    for (const t of [...new Set([start, ...switches, end])]) {
      if (t < start || t > end) continue;
      ctx.fillStyle = "#adc6d2"; ctx.fillText(String(t), x(t), h - 7);
    }
    function path(values, color, width, dash) {
      ctx.strokeStyle = color; ctx.lineWidth = width;
      ctx.setLineDash(dash || []); ctx.beginPath();
      let drawing = false;
      for (let i = 0; i < values.length; i++) {
        if (!finite(values[i])) { drawing = false; continue; }
        if (!drawing) {ctx.moveTo(x(data.time[i]), y(values[i])); drawing = true;}
        else ctx.lineTo(x(data.time[i]), y(values[i]));
      }
      ctx.stroke(); ctx.setLineDash([]);
    }
    if (kind === "simulated")
      for (const series of data.series) path(series.values, "#584d77", 1);
    const low = data.low, high = data.high;
    ctx.fillStyle = kind === "observed" ? "rgba(96,210,170,.23)" : "rgba(169,140,255,.25)";
    ctx.beginPath(); let started = false;
    for (let i = 0; i < low.length; i++) {
      if (!finite(low[i]) || !finite(high[i])) continue;
      if (!started) {ctx.moveTo(x(data.time[i]), y(high[i])); started = true;}
      else ctx.lineTo(x(data.time[i]), y(high[i]));
    }
    for (let i = low.length - 1; i >= 0; i--)
      if (finite(low[i]) && finite(high[i])) ctx.lineTo(x(data.time[i]), y(low[i]));
    if (started) {ctx.closePath(); ctx.fill();}
    path(data.median, kind === "observed" ? "#86e0bb" : "#bbabff", 2);
    if (kind === "observed") {
      path(data.mean, "#dff5f3", 1.5, [4, 3]);
      path(data.fit, "#ffd178", 2);
    } else if (data.baseline) path(data.baseline, "#69dfe5", 1.5, [4, 3]);
  }
  root.CsimPixelEvidence = Object.freeze({summarize, renderChart});
})(typeof window !== "undefined" ? window : globalThis);
