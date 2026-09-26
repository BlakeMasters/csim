/* Csim pixel scene. Dependency-free presentation of accepted reference state.
 * Include after the playground page; see pixel_renderer_preview.html for the
 * integration contract and an isolated manual smoke. No simulation writes. */
(function (root) {
  "use strict";

  const COLORS = Object.freeze({
    bg: "#091625", panel: "#10273a", grid: "#214052", gridBright: "#2b5968",
    ink: "#effaff", muted: "#b7d1da", cyan: "#69dfe5", teal: "#76e2b8",
    violet: "#baa5ff", amber: "#ffd178", orange: "#ffab70", red: "#ff8e99",
    white: "#ffffff", dark: "#06121d", observed: "#8de4c9", fitted: "#ffd178",
    proxy: "#bbabff",
  });
  const STIMULUS = "synthetic_stimulus";
  const PAYLOAD = "generic_inhibitor_payload";
  const renderSessions = new WeakMap();

  function number(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }
  // Preserve invalid negative values in labels/inspection; only visual intensity is bounded.
  function positive(value) { return number(value, 0); }
  function fraction(value) { return Math.max(0, Math.min(1, number(value, 0))); }
  function format(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    if (n === 0) return "0";
    if (Math.abs(n) < 0.001 || Math.abs(n) >= 10000) return n.toExponential(2);
    return Number(n.toPrecision(3)).toString();
  }
  function text(ctx, value, x, y, color, size, weight, align) {
    ctx.font = `${weight || 600} ${size || 12}px system-ui, Segoe UI, sans-serif`;
    ctx.fillStyle = color || COLORS.ink;
    ctx.textAlign = align || "left";
    ctx.fillText(String(value), Math.round(x), Math.round(y));
  }
  function box(ctx, x, y, w, h, color) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }
  function line(ctx, x1, y1, x2, y2, color, width) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width || 2;
    ctx.beginPath();
    ctx.moveTo(Math.round(x1) + 0.5, Math.round(y1) + 0.5);
    ctx.lineTo(Math.round(x2) + 0.5, Math.round(y2) + 0.5);
    ctx.stroke();
  }
  function arrow(ctx, x1, y1, x2, y2, color, size) {
    line(ctx, x1, y1, x2, y2, color, 3);
    const dir = x2 >= x1 ? 1 : -1;
    box(ctx, x2 - (dir > 0 ? 0 : size), y2 - size / 2, size, size, color);
    box(ctx, x2 - dir * size, y2 - size, size, size * 2, color);
  }
  function hash(n) {
    let x = n | 0;
    x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
    x = Math.imul(x ^ (x >>> 16), 0x45d9f3b);
    return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
  }
  function modeOf(state, o) {
    if (state && typeof state.mode === "string") return state.mode;
    if (o && o.field && Array.isArray(o.cells)) return "nfkb";
    if (o && Array.isArray(o.cells)) return "arena";
    if (o && Object.hasOwn(o, "sender_amount_mol")) return "ligand";
    return "uptake";
  }
  function normalize(state) {
    const o = state && state.observation ? state.observation : (state || {});
    const mode = modeOf(state, o);
    let cells;
    if (mode === "nfkb") {
      cells = (o.cells || []).map((c) => ({
        id: String(c.cell_id), kind: "cell", amount: null, memory: null,
        payload: positive(c.payload_amount_mol), nuclear: fraction(c.nuclear_proxy),
        reporter: positive(c.reporter_index), feedback: positive(c.feedback),
        position: c.position_m || null, variantId: c.response_variant_id || null,
      }));
    } else if (mode === "arena") {
      cells = (o.cells || []).map((c) => ({
        id: String(c.cell_id), kind: "cell", amount: positive(c.amount_mol),
        memory: positive(c.memory), payload: null, nuclear: null,
        reporter: null, feedback: null, position: c.position_m || null, variantId: null,
      }));
    } else if (mode === "ligand") {
      cells = [
        {id: "sender", kind: "sender", amount: positive(o.sender_amount_mol), memory: null,
          payload: null, nuclear: null, reporter: null, feedback: null, position: null, variantId: null},
        {id: "receiver", kind: "receiver", amount: positive(o.receiver_amount_mol),
          memory: positive(o.receiver_memory), payload: null, nuclear: null,
          reporter: null, feedback: null, position: null, variantId: null},
      ];
    } else {
      cells = [{id: "cell_1", kind: "cell", amount: positive(o.cell_amount_mol),
        memory: positive(o.accepted_memory), payload: null, nuclear: null,
        reporter: null, feedback: null, position: null, variantId: null}];
    }
    const field = mode === "nfkb" ? {
      concentration: positive(o.field?.[STIMULUS]?.concentration_mol_m3),
      amount: positive(o.field?.[STIMULUS]?.amount_mol),
      payloadConcentration: positive(o.field?.[PAYLOAD]?.concentration_mol_m3),
      payloadAmount: positive(o.field?.[PAYLOAD]?.amount_mol),
    } : {
      concentration: positive(o.field_concentration_mol_m3 ?? o.local_concentration_mol_m3),
      amount: Object.hasOwn(o, "field_amount_mol") ? positive(o.field_amount_mol) : null,
      payloadConcentration: null, payloadAmount: null,
    };
    const timeline = Array.isArray(state?.timeline) ? state.timeline : [];
    const latest = timeline.length ? timeline[timeline.length - 1] : null;
    const time = mode === "nfkb" ? number(o.time_min, 0) : number(o.time_s, 0);
    const unit = mode === "nfkb" ? "min" : "s";
    const variation = state?.variability || o.variability || {};
    const seed = state?.seed ?? o.seed ?? state?.configuration?.seed ?? variation.seed ??
      latest?.transition?.info?.variability?.seed ?? null;
    const replicate = state?.replicate_id ?? o.replicate_id ??
      state?.configuration?.replicate_id ?? variation.replicate_id ?? null;
    const evidence = state?.last_record || state?.evidence || null;
    return {o, mode, cells: cells.slice(0, 5), field, timeline, latest, time, unit,
      configuration: state?.configuration || {}, acceptedSteps: number(state?.accepted_steps, 0),
      replay: state?.last_replay || null, seed, replicate, evidence};
  }
  function canvasSize(canvas) {
    const rect = canvas.getBoundingClientRect ? canvas.getBoundingClientRect() : null;
    return {width: Math.max(280, Math.round(number(rect?.width, canvas.clientWidth || canvas.width || 720))),
      height: Math.max(180, Math.round(number(rect?.height, canvas.clientHeight || canvas.height || 220))),
      rect};
  }
  function layout(canvas, normalized) {
    const {width: w, height: h} = canvasSize(canvas);
    const n = normalized.cells.length;
    const radius = Math.min(39, Math.max(23, (w - 62) / Math.max(1, n) / 3.1),
      Math.max(24, (h - 100) / 3));
    const side = Math.max(34, radius + 9);
    const usable = Math.max(0, w - 2 * side);
    const cy = Math.round(30 + (h - 112) * 0.5);
    const cells = normalized.cells.map((cell, i) => {
      const cx = n === 1 ? w / 2 : side + usable * i / (n - 1);
      return {id: cell.id, cx: Math.round(cx), cy, radius,
        x: Math.round(cx - radius - 9), y: Math.round(cy - radius - 9),
        width: Math.round((radius + 9) * 2), height: Math.round((radius + 9) * 2)};
    });
    return {width: w, height: h, cells};
  }
  function prepareCanvas(canvas, scene) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Csim pixel renderer requires a 2D canvas context");
    const dpr = Math.max(1, Math.min(2, Math.round(number(root.devicePixelRatio, 1))));
    const pxW = Math.round(scene.width * dpr), pxH = Math.round(scene.height * dpr);
    if (canvas.width !== pxW) canvas.width = pxW;
    if (canvas.height !== pxH) canvas.height = pxH;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    return ctx;
  }
  function drawField(ctx, n, scene, options) {
    const {width: w, height: h} = scene;
    box(ctx, 0, 0, w, h, COLORS.bg);
    box(ctx, 10, 32, w - 20, h - 100, COLORS.panel);
    const intensity = Math.max(0, n.field.concentration) /
      (Math.max(0, n.field.concentration) + 0.25);
    const payloadIntensity = n.field.payloadConcentration == null ? 0 :
      Math.max(0, n.field.payloadConcentration) /
        (Math.max(0, n.field.payloadConcentration) + 0.15);
    for (let y = 43; y < h - 79; y += 16) {
      for (let x = 22; x < w - 18; x += 18) {
        const seed = Math.floor(x * 17 + y * 29);
        if (hash(seed) < 0.18 + intensity * 0.35)
          box(ctx, x + 4 * hash(seed + 1), y + 4 * hash(seed + 2), 3, 3,
            hash(seed + 3) > 0.5 ? COLORS.gridBright : COLORS.grid);
        if (payloadIntensity > 0 && hash(seed + 7) < payloadIntensity * 0.14)
          box(ctx, x + 2, y + 2, 3, 3, COLORS.orange);
      }
    }
    for (let y = 43; y < h - 79; y += 24) {
      line(ctx, 11, y, w - 11, y, "#1b394a", 1);
    }
    box(ctx, 10, 32, w - 20, 2, "#3e8c92");
    if (n.field.concentration < 0 || (n.field.payloadConcentration != null &&
        n.field.payloadConcentration < 0)) box(ctx, 10, 32, w - 20, 3, COLORS.red);
    box(ctx, 10, h - 68, w - 20, 2, "#3e8c92");
    const compact = w < 720;
    text(ctx, n.mode === "nfkb" ? "SHARED FIELD · STIM" : "SHARED FIELD", 14, 22,
      COLORS.cyan, compact ? 10 : 12, 800);
    const concentration = `c ${format(n.field.concentration)} mol/m³`;
    text(ctx, concentration, compact ? w - 14 : w * 0.50, 22, COLORS.ink,
      compact ? 10 : 12, 700, compact ? "right" : "center");
    if (n.mode === "nfkb" && compact) {
      const observed = Array.isArray(options?.overlayCondition?.observed?.mean);
      const fitted = Array.isArray(options?.overlayCondition?.model_prediction);
      const start = w < 480 ? 146 : Math.round(w * 0.39);
      text(ctx, "OBS", start, 22, observed ? COLORS.observed : COLORS.muted, 9, 800);
      text(ctx, "FIT", start + 36, 22, fitted ? COLORS.fitted : COLORS.muted, 9, 800);
      text(ctx, "SYN", start + 72, 22, COLORS.proxy, 9, 800);
    }
    if (n.mode === "nfkb" && !compact)
      text(ctx, `PAYLOAD c ${format(n.field.payloadConcentration)} mol/m³`, w - 14,
        22, COLORS.orange, 11, 700, "right");
    text(ctx, n.latest?.kind === "accepted" ? "ACCEPTED · PAIRED AMOUNT" :
      "ONE VOXEL · DIAGRAM LAYOUT", 18, h - 74, COLORS.muted,
      compact ? 9 : 11, 500);
    if (n.seed != null) {
      const badge = compact ? `seed ${String(n.seed).slice(0, 12)}` :
        `SEEDED VARIABILITY · seed ${String(n.seed).slice(0, 16)}`;
      text(ctx, n.replicate == null ? badge :
        `${badge} · rep ${String(n.replicate).slice(0, 8)}`, w - 18, h - 74,
        COLORS.orange, compact ? 9 : 11, 750, "right");
    }
  }
  function drawCell(ctx, cell, hit, index, selected, small, seed) {
    const s = Math.max(4, Math.floor(hit.radius / 5));
    const x = Math.round(hit.cx - 4.5 * s), y = Math.round(hit.cy - 4.5 * s);
    const shell = [5, 7, 9, 9, 9, 9, 9, 7, 5];
    const hue = [COLORS.teal, COLORS.violet, COLORS.cyan, COLORS.amber, "#ff9fac"][index % 5];
    if (selected) {
      box(ctx, x - 5, y - 5, 9 * s + 10, 9 * s + 10, COLORS.white);
      box(ctx, x - 2, y - 2, 9 * s + 4, 9 * s + 4, COLORS.dark);
    }
    for (let row = 0; row < 9; row++) {
      const width = shell[row], inset = (9 - width) / 2;
      box(ctx, x + inset * s, y + row * s, width * s, s, COLORS.dark);
      box(ctx, x + inset * s + 2, y + row * s + 2,
        Math.max(0, width * s - 4), Math.max(0, s - 2), hue);
    }
    const mem = cell.memory == null ? cell.feedback : cell.memory;
    const visualMemory = Math.max(0, positive(mem));
    const memoryLevel = Math.min(5, Math.round(5 * (visualMemory / (visualMemory + 0.4))));
    for (let i = 0; i < memoryLevel; i++) box(ctx, x + s, y + (7 - i) * s, 3, 3, COLORS.white);
    // Nucleus brightness represents the bounded synthetic nuclear proxy.
    const nucleusFill = cell.nuclear == null ? COLORS.grid :
      (cell.nuclear > 0.55 ? COLORS.white : cell.nuclear > 0.18 ? COLORS.proxy : COLORS.grid);
    box(ctx, x + 3 * s, y + 3 * s, 3 * s, 3 * s, COLORS.dark);
    box(ctx, x + 3 * s + 2, y + 3 * s + 2, 3 * s - 4, 3 * s - 4, nucleusFill);
    if (cell.reporter != null) {
      const visualReporter = Math.max(0, positive(cell.reporter));
      const level = Math.min(4, Math.round(4 * visualReporter / (visualReporter + 0.35)));
      for (let i = 0; i < 4; i++)
        box(ctx, x + (3 + i) * s, y + 7 * s, Math.max(2, s - 2), 3,
          i < level ? COLORS.proxy : COLORS.grid);
    }
    if (cell.payload != null) {
      const dots = Math.min(4, Math.round(4 * cell.payload / (cell.payload + 0.01)));
      for (let i = 0; i < dots; i++) box(ctx, x + (6 + i % 2) * s,
        y + (2 + Math.floor(i / 2)) * s, 3, 3, COLORS.orange);
    }
    if (cell.kind === "sender") box(ctx, x + 7 * s, y + 4 * s, s, s, COLORS.amber);
    if (cell.kind === "receiver") box(ctx, x + s, y + 4 * s, s, s, COLORS.cyan);
    if (seed != null) {
      // Stable visual fingerprint only. The episode RNG, not this hash, owns dynamics.
      const key = `${seed}:${cell.id}`;
      let code = 0;
      for (let i = 0; i < key.length; i++) code = Math.imul(code ^ key.charCodeAt(i), 16777619);
      box(ctx, x + (2 + Math.abs(code % 2)) * s, y + 2 * s, 3, 3, COLORS.white);
      box(ctx, x + (5 + Math.abs((code >>> 4) % 2)) * s, y + 6 * s, 3, 3, COLORS.dark);
    }
    text(ctx, cell.id, hit.cx, y - 7, selected ? COLORS.white : COLORS.ink,
      small ? 10 : 12, 800, "center");
    const value = cell.payload != null ? `P ${format(cell.payload)}` :
      cell.memory != null ? `m ${format(cell.memory)}` : `a ${format(cell.amount)}`;
    text(ctx, value, hit.cx, y + 9 * s + 14, COLORS.ink,
      small ? 9 : 11, 650, "center");
  }
  function transferFor(n, id) {
    const event = n.latest;
    if (!event || event.kind !== "accepted") return 0;
    const info = event.transition?.info || {};
    if (n.mode === "arena") return positive(info.transfers_mol_by_cell?.[id]);
    if (n.mode === "nfkb") return positive(info.payload_transfers_mol_by_cell?.[id]);
    if (n.mode === "ligand") return id === "sender" ? positive(info.integrated_transfer_mol) : 0;
    return positive(info.integrated_transfer_mol);
  }
  function drawTransfers(ctx, n, scene) {
    if (n.latest?.kind !== "accepted") return;
    scene.cells.forEach((hit, i) => {
      const transfer = transferFor(n, hit.id);
      if (!(transfer > 0)) return;
      const secretion = n.mode === "ligand" && hit.id === "sender";
      const color = n.mode === "nfkb" ? COLORS.orange : COLORS.amber;
      const y = hit.cy + 1;
      if (secretion) arrow(ctx, hit.cx + hit.radius - 2, y,
        hit.cx + hit.radius + 20, y, color, 4);
      else arrow(ctx, hit.cx - hit.radius - 20, y,
        hit.cx - hit.radius + 1, y, color, 4);
    });
  }
  function switchesFor(n, options) {
    if (Array.isArray(options?.switches)) return options.switches.map((s) => ({
      time: number(s.time_min ?? s.time, NaN), code: s.code ?? s.stimulus_code ?? "",
    })).filter((s) => Number.isFinite(s.time));
    const condition = options?.overlayCondition;
    if (condition && Array.isArray(options?.switchTimesMin) &&
        Array.isArray(condition.ligand_sequence))
      return options.switchTimesMin.map((time, i) => ({
        time: number(time, NaN), code: condition.ligand_sequence[i] || "",
      })).filter((s) => Number.isFinite(s.time));
    return n.timeline.filter((e) => e.kind === "accepted" &&
      e.proposal?.stimulus_code != null).map((e) => ({
      time: number(e.before?.time_min, NaN), code: e.proposal.stimulus_code,
    })).filter((s) => Number.isFinite(s.time));
  }
  function drawRuler(ctx, n, scene, options) {
    const {width: w, height: h} = scene;
    const y = h - 12, x1 = 20, x2 = w - 20;
    const end = n.mode === "nfkb" ?
      Math.max(n.time, number(n.configuration.horizon_steps, 82) * number(n.configuration.step_min, 6), 1) :
      Math.max(n.time, n.time + number(n.o.remaining_steps, 0) *
        number(n.configuration.step_s, n.configuration.step_min || 1), 1);
    line(ctx, x1, y, x2, y, COLORS.gridBright, 3);
    const switches = n.mode === "nfkb" ? switchesFor(n, options) : [];
    switches.forEach((s) => {
      const x = x1 + (x2 - x1) * Math.max(0, Math.min(1, s.time / end));
      box(ctx, x - 1, y - 7, 3, 12, COLORS.amber);
      text(ctx, s.code, x + 3, y - 9, COLORS.amber, 10, 800);
    });
    const nowX = x1 + (x2 - x1) * Math.max(0, Math.min(1, n.time / end));
    box(ctx, nowX - 3, y - 4, 7, 9, COLORS.white);
    text(ctx, `t ${format(n.time)} ${n.unit}`, w - 17, h - 27, COLORS.ink,
      10, 700, "right");
    if (!switches.length)
      text(ctx, n.mode === "nfkb" ? `0–${format(end)} min` : "accepted time", 20,
        h - 27, COLORS.muted, 10, 600);
  }
  function drawSignalKeys(ctx, n, scene, options) {
    if (n.mode !== "nfkb") return;
    const w = scene.width, y = scene.height - 48;
    const condition = options?.overlayCondition || {};
    const observed = Array.isArray(condition.observed?.mean);
    const fitted = Array.isArray(condition.model_prediction);
    const labels = w < 720 ? [
      ["OBS p65", COLORS.observed, observed], ["FIT p65", COLORS.fitted, fitted],
      ["SYN proxy", COLORS.proxy, true],
    ] : [
      ["Observed normalized p65", COLORS.observed, observed],
      ["Empirical fitted prediction", COLORS.fitted, fitted],
      ["Synthetic reporter proxy", COLORS.proxy, true],
    ];
    const slot = (w - 34) / 3;
    labels.forEach(([label, color, available], i) => {
      const x = 17 + i * slot;
      box(ctx, x, y - 8, 6, 6, available ? color : COLORS.gridBright);
      text(ctx, label, x + 10, y - 1, available ? color : COLORS.muted,
        w < 720 ? 9 : 11, available ? 700 : 500);
    });
  }
  function band(source) {
    if (!source) return null;
    const candidate = source.percentiles || source.quantiles || source;
    const low = candidate.p10 || candidate.q10 || candidate.quantile_10 || candidate.lower;
    const median = candidate.p50 || candidate.q50 || candidate.median;
    const high = candidate.p90 || candidate.q90 || candidate.quantile_90 || candidate.upper;
    if (!Array.isArray(low) || !Array.isArray(median) || !Array.isArray(high) ||
        low.length < 2 || low.length !== median.length || low.length !== high.length)
      return null;
    return {low, median, high};
  }
  function drawBandRow(ctx, source, label, color, y, scene) {
    const data = band(source);
    if (!data) return false;
    const x1 = scene.width < 720 ? 129 : 206, x2 = scene.width - 18;
    const n = data.low.length;
    const valid = (v) => typeof v === "number" && Number.isFinite(v);
    const all = data.low.concat(data.median, data.high).filter(valid);
    if (!all.length) return false;
    const lo = Math.min(...all), hi = Math.max(...all), range = Math.max(hi - lo, 1e-9);
    box(ctx, x1, y - 10, x2 - x1, 12, "#142333");
    for (let i = 0; i < n; i++) {
      const low = data.low[i], mid = data.median[i], high = data.high[i];
      if (![low, mid, high].every(valid)) continue;
      const x = x1 + (x2 - x1) * i / (n - 1);
      const top = y - 9 + (hi - high) / range * 9;
      const bottom = y - 9 + (hi - low) / range * 9;
      box(ctx, x, top, 2, Math.max(2, bottom - top), color);
      box(ctx, x, y - 9 + (hi - mid) / range * 9, 2, 2, COLORS.white);
    }
    text(ctx, label, 18, y, color, scene.width < 720 ? 9 : 10, 700);
    return true;
  }
  function drawVariability(ctx, n, scene, options) {
    if (n.mode !== "nfkb") return false;
    const measured = options?.measuredBand || options?.overlayCondition?.observed;
    const simulated = options?.simulationBand || options?.illustrativeBand;
    const first = drawBandRow(ctx, measured,
      scene.width < 720 ? "OBS p65 10–90%" : "OBSERVED p65 rows · 10–90%", COLORS.observed,
      scene.height - 56, scene);
    const second = drawBandRow(ctx, simulated,
      scene.width < 720 ? "SIM 10–90%" : "ILLUSTRATIVE sim runs · 10–90%", COLORS.proxy,
      scene.height - 40, scene);
    if (first || second) {
      if (!first) text(ctx, "Observed dispersion unavailable", 18, scene.height - 56,
        COLORS.muted, 9, 600);
      if (!second) text(ctx, "Illustrative run spread unavailable", 18, scene.height - 40,
        COLORS.muted, 9, 600);
      return true;
    }
    return false;
  }
  function traceFor(n, cellId) {
    const values = [];
    n.timeline.forEach((e) => {
      if (e.kind !== "accepted") return;
      const c = observationCell(e.transition?.observation, n.mode, cellId);
      if (!c) return;
      const v = n.mode === "nfkb" ? c.reporter_index : n.mode === "arena" ? c.memory :
        n.mode === "ligand" ? (cellId === "receiver" ? c.receiver_memory : c.sender_amount_mol) :
        c.accepted_memory;
      if (Number.isFinite(Number(v))) values.push(Number(v));
    });
    return values;
  }
  function drawTraces(ctx, n, scene) {
    if (scene.height < 245) return;
    const base = scene.height - 85;
    scene.cells.forEach((hit) => {
      const values = traceFor(n, hit.id);
      if (values.length < 2) return;
      const lo = Math.min(...values), hi = Math.max(...values), range = Math.max(hi - lo, 1e-9);
      const left = hit.cx - Math.min(25, hit.radius), width = Math.min(50, hit.radius * 2);
      const color = n.mode === "nfkb" ? COLORS.proxy : COLORS.white;
      for (let i = 1; i < values.length; i++) {
        const x1 = left + width * (i - 1) / (values.length - 1);
        const x2 = left + width * i / (values.length - 1);
        line(ctx, x1, base - 9 * (values[i - 1] - lo) / range,
          x2, base - 9 * (values[i] - lo) / range, color, 2);
      }
    });
  }
  function drawStatus(ctx, n, scene) {
    const last = n.latest;
    if (last?.kind === "rejected") {
      box(ctx, 14, scene.height - 89, Math.min(scene.width - 28, 230), 20, "#682b3a");
      text(ctx, last.state_unchanged ? "REJECTED · state retained" : "REJECTED · check state",
        20, scene.height - 74, COLORS.white, 10, 800);
    } else if (n.replay) {
      const w = Math.min(scene.width - 28, 198);
      box(ctx, 14, scene.height - 89, w, 20,
        n.replay.equal ? "#1c6657" : "#682b3a");
      text(ctx, n.replay.equal ? "REPLAY MATCHED" : "REPLAY MISMATCH",
        20, scene.height - 74, COLORS.white, 10, 800);
    }
  }
  function paint(canvas, state, options) {
    if (!canvas || typeof canvas.getContext !== "function")
      throw new TypeError("render requires a canvas element");
    const n = normalize(state), scene = layout(canvas, n), ctx = prepareCanvas(canvas, scene);
    const selected = options?.selectedCellId || options?.selectedId || null;
    drawField(ctx, n, scene, options);
    drawTransfers(ctx, n, scene);
    n.cells.forEach((c, i) => drawCell(ctx, c, scene.cells[i], i,
      c.id === selected, scene.width < 540, n.seed));
    drawTraces(ctx, n, scene);
    drawStatus(ctx, n, scene);
    if (!drawVariability(ctx, n, scene, options)) drawSignalKeys(ctx, n, scene, options);
    drawRuler(ctx, n, scene, options);
    return {mode: n.mode, width: scene.width, height: scene.height,
      cellHitboxes: scene.cells.map((c) => ({...c})),
      selectedCellId: n.cells.some((c) => c.id === selected) ? selected : null,
      latestStatus: n.latest?.kind || "ready"};
  }
  function render(canvas, state, options) {
    const result = paint(canvas, state, options);
    let session = renderSessions.get(canvas);
    if (!session) {
      session = {state, options, width: result.width, height: result.height, observer: null};
      renderSessions.set(canvas, session);
      if (typeof root.ResizeObserver === "function") {
        session.observer = new root.ResizeObserver(() => {
          const size = canvasSize(canvas);
          if (size.width === session.width && size.height === session.height) return;
          // The page may apply its stylesheet after the first API snapshot.
          // Repaint the most recent state when that changes the CSS rectangle.
          const next = paint(canvas, session.state, session.options);
          session.width = next.width;
          session.height = next.height;
        });
        session.observer.observe(canvas);
      }
    }
    session.state = state;
    session.options = options;
    session.width = result.width;
    session.height = result.height;
    return result;
  }
  function pickCell(canvas, pointerEvent, state) {
    if (!canvas || !pointerEvent) return null;
    const scene = layout(canvas, normalize(state));
    const rect = canvas.getBoundingClientRect ? canvas.getBoundingClientRect() :
      {left: 0, top: 0, width: scene.width, height: scene.height};
    const x = Number.isFinite(pointerEvent.clientX) ? pointerEvent.clientX - rect.left :
      number(pointerEvent.offsetX, NaN);
    const y = Number.isFinite(pointerEvent.clientY) ? pointerEvent.clientY - rect.top :
      number(pointerEvent.offsetY, NaN);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return scene.cells.find((hit) => x >= hit.x && x <= hit.x + hit.width &&
      y >= hit.y && y <= hit.y + hit.height)?.id || null;
  }
  function observationCell(o, mode, id) {
    if (!o) return null;
    if (mode === "nfkb" || mode === "arena")
      return (o.cells || []).find((c) => c.cell_id === id) || null;
    if (mode === "ligand" && ["sender", "receiver"].includes(id)) return o;
    return mode === "uptake" && id === "cell_1" ? o : null;
  }
  function inspectCell(state, cellId) {
    const n = normalize(state);
    if (!n.cells.some((c) => c.id === cellId)) return null;
    const event = n.latest;
    const before = event?.before || null;
    const after = event?.kind === "accepted" ? event.transition?.observation : n.o;
    const prior = observationCell(before, n.mode, cellId);
    const current = observationCell(after, n.mode, cellId);
    const fields = n.mode === "nfkb" ? [
      ["Payload amount", "payload_amount_mol", "mol"],
      ["Nuclear proxy", "nuclear_proxy", "1"],
      ["Feedback proxy", "feedback", "1"],
      ["Reporter proxy", "reporter_index", "1"],
    ] : n.mode === "arena" ? [
      ["Cell amount", "amount_mol", "mol"], ["Response memory", "memory", "1"],
    ] : n.mode === "ligand" ? (cellId === "sender" ? [
      ["Sender amount", "sender_amount_mol", "mol"],
    ] : [
      ["Receiver amount", "receiver_amount_mol", "mol"],
      ["Response memory", "receiver_memory", "1"],
    ]) : [
      ["Cell amount", "cell_amount_mol", "mol"],
      ["Response memory", "accepted_memory", "1"],
    ];
    return {cellId, mode: n.mode, eventIndex: event?.index || null,
      status: event?.kind || "ready", stateUnchanged: event?.kind === "rejected" ?
        event.state_unchanged === true : null,
      timeBefore: before ? (n.mode === "nfkb" ? before.time_min : before.time_s) : null,
      timeAfter: n.mode === "nfkb" ? after?.time_min : after?.time_s,
      timeUnit: n.unit, transferMol: transferFor(n, cellId),
      transferDirection: n.mode === "ligand" && cellId === "sender" ?
        "cell → field" : n.mode === "ligand" ? "sensing only" : "field → cell",
      values: fields.map(([label, key, unit]) => ({label, unit,
        before: prior == null ? null : number(prior[key], null),
        after: current == null ? null : number(current[key], null),
      })),
      trace: traceFor(n, cellId), seed: n.seed, replicate: n.replicate,
      variantId: n.cells.find((c) => c.id === cellId)?.variantId || null,
      ossAtomId: n.evidence?.oss_atom_id || null,
      engineRunId: n.evidence?.engine_run_id || null,
      scope: n.mode === "nfkb" ?
        "Synthetic proxy. Observed p65 and fitted predictions are separate; row dispersion is not intrinsic noise." :
        "Synthetic reference state; values are not biological calibration.",
    };
  }
  function renderInspector(element, state, cellId) {
    if (!element || typeof element.replaceChildren !== "function")
      throw new TypeError("renderInspector requires an element");
    const model = inspectCell(state, cellId);
    const doc = element.ownerDocument || root.document;
    function el(tag, value, className) {
      const node = doc.createElement(tag);
      if (value != null) node.textContent = String(value);
      if (className) node.className = className;
      return node;
    }
    if (!model) {
      element.replaceChildren(el("p", "Select a cell in the scene to inspect accepted state.",
        "csim-inspector-empty"));
      return null;
    }
    const header = el("div", null, "csim-inspector-header");
    header.append(el("strong", model.cellId), el("span", model.status.toUpperCase(),
      `csim-inspector-status ${model.status}`));
    const table = el("table", null, "csim-inspector-table");
    const head = el("thead"), headRow = el("tr");
    ["State", "Before", "After"].forEach((label) => headRow.append(el("th", label)));
    head.append(headRow); table.append(head);
    const body = el("tbody");
    model.values.forEach((value) => {
      const row = el("tr");
      row.append(el("th", `${value.label} (${value.unit})`),
        el("td", value.before == null ? "—" : format(value.before)),
        el("td", value.after == null ? "—" : format(value.after)));
      body.append(row);
    });
    table.append(body);
    const transfer = model.status === "ready" ? "No accepted transfer yet." :
      model.status === "rejected" ? "Rejected interval: accepted cell state retained." :
      model.transferDirection === "sensing only" ?
      "Sensing samples the field without material transfer." :
      `${model.transferDirection}: ${format(model.transferMol)} mol in latest accepted interval.`;
    const note = el("p", transfer, "csim-inspector-transfer");
    const scope = el("p", model.scope, "csim-inspector-scope");
    const details = [];
    if (model.seed != null)
      details.push(el("p", `Seed ${model.seed}${model.replicate == null ? "" : ` · replicate ${model.replicate}`}`,
        "csim-inspector-seed"));
    if (model.variantId)
      details.push(el("p", `Cell variant: ${model.variantId}`, "csim-inspector-seed"));
    if (model.trace.length > 1)
      details.push(el("p", `Accepted ${model.cellId} trace (last ${Math.min(8, model.trace.length)}/${model.trace.length}): ${model.trace.slice(-8).map(format).join(" → ")}`,
        "csim-inspector-trace"));
    if (model.ossAtomId)
      details.push(el("p", `OSS receipt: ${model.ossAtomId}${model.engineRunId ?
        ` · optional Engine run: ${model.engineRunId}` : ""}`, "csim-inspector-evidence"));
    element.replaceChildren(header, table, note, ...details, scope);
    return model;
  }
  root.CsimPixelRenderer = Object.freeze({
    render, pickCell, inspectCell, renderInspector, version: "1.0.0",
  });
})(typeof window !== "undefined" ? window : globalThis);
