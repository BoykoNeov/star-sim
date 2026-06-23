// Composition panel (STAR_SIM_SPEC.md §5.4). Two views over the same EEP axis,
// switched by setMode():
//
//  * "bulk"  — X=H, Y=He, Z=metals as stacked-area bands (the default). Core on
//              top (where the drama is), surface below.
//  * "cno"   — the Phase 4 per-element detail: thirteen element mass fractions as
//              lines — C, N, O, Ne, Na, Mg, Al, Si, P, S, Ca, Ti, Fe (the id stays
//              "cno" — it began as the CNO trio). Core and surface get INDEPENDENT
//              y-scales on purpose: during core-He burning the core's C/O climb to
//              tens of percent while the surface stays ~1%, so a shared scale would
//              flatten the surface first-dredge-up signature (N up, C down) — the
//              actual teaching moment — into nothing. The α / odd-Z / iron-peak
//              tracers are near-flat: Fe in particular just marks the input [Fe/H], a
//              steady backdrop that makes the CNO motion legible. (Na is enriched ~1.4x
//              by Ne-Na-cycle dredge-up in intermediate-mass giants, but at ~3e-5 of
//              mass it's a sub-pixel wiggle against O's ~7e-3 on the shared scale.)
//
// Why EEP and not linear age on the x-axis (§6): the teaching payoffs — core H→He
// near TAMS, and the dredge-up on the lower RGB — are slivers on a linear-age
// axis (the MS eats ~90% of the width). On an EEP axis the phases are evenly
// spaced and you can actually watch them.
//
// A consumer of StellarState ONLY (§3): it reads X/Y/Z, the metals_surf/core
// dicts, and eep off the track and marker, and knows nothing about where they
// came from. setTrack() takes the list from /track; update() moves the marker
// from /state; setMode() flips the view. Same split as hr.js.

import { fitCanvas } from "./canvas.js";

const PAD_L = 30, PAD_R = 10, PAD_T = 16, PAD_B = 26;
const GAP = 22;   // vertical gap between the core and surface sub-charts

// Bulk band colors: H a cool blue, He a warm gold, metals a violet. Z is ~1.5%
// so its band is a thin sliver at the top — honest, not a rendering bug.
const COL = { X: "#5b8def", Y: "#ffce6b", Z: "#b083e0" };
// Per-element line colors — deliberately distinct from the bulk band palette
// above and from each other. Fe is a steel-grey iron mnemonic (and the inert
// tracer that just marks the input [Fe/H]); CNO keep their Phase-4 hues; the
// α / odd-Z / iron-peak tracers fill the remaining hue gaps (violet/chartreuse/
// red/cyan, plus a sodium-D yellow, aluminium silver and phosphorus orchid).
// Na/Al/P are tiny floor-huggers (~1e-5 of mass); they cluster at the bottom of
// each sub-chart, so they need only differ from each other and from Fe/Ca/Ti.
const ELEM_COL = {
  C: "#ff9f43", N: "#26de81", O: "#54a0ff",     // the CNO trio (orange/green/blue)
  Ne: "#ff6b9d", Na: "#ffe14d",                 // neon rose / sodium D-line yellow
  Mg: "#feca57", Al: "#cdd6e0",                 // magnesium amber / aluminium silver
  Si: "#a55eea", P: "#c77dff",                  // silicon violet / phosphorus orchid
  S: "#c4e538", Ca: "#ee5253", Ti: "#00d2d3",   // sulfur lime / calcium red / titanium cyan
  Fe: "#a4b0be",                                // iron grey
};
// Atomic-number order, so the legend reads C→Fe left to right.
const ELEMS = ["C", "N", "O", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Ca", "Ti", "Fe"];

export function createComp(canvas, cssW = 300, cssH = 280) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  const { ctx, W, H } = fitCanvas(canvas, cssW, cssH);

  let track = null;    // array of StellarState (age-independent, set per mass/feh)
  let marker = null;   // current StellarState (moves as age scrubs)
  let mode = "bulk";   // "bulk" (X/Y/Z bands) | "cno" (C/N/O lines)

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }
  function setMode(m) { mode = m === "cno" ? "cno" : "bulk"; draw(); }

  // Shared geometry both views build on: the EEP→x map and the two sub-chart
  // bands (core on top, surface below).
  function layout() {
    const e0 = track[0].eep;
    const e1 = track[track.length - 1].eep;
    const span = e1 - e0 || 1;
    const xOf = (eep) => PAD_L + (eep - e0) / span * (W - PAD_L - PAD_R);
    const chartH = (H - PAD_T - PAD_B - GAP) / 2;
    return { e0, e1, xOf, chartH, coreTop: PAD_T, surfTop: PAD_T + chartH + GAP };
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!track) return;
    mode === "cno" ? drawCno() : drawBulk();
  }

  // -- bulk view: stacked X/Y/Z bands ---------------------------------------
  function drawBulk() {
    const { e0, e1, xOf, chartH, coreTop, surfTop } = layout();

    // Fill one stacked band: cumulative-fraction boundaries lowFn..highFn, mapped
    // so fraction 0 sits at the chart's bottom and 1 at its top.
    function band(top, h, lowFn, highFn) {
      ctx.beginPath();
      track.forEach((s, i) => {
        const x = xOf(s.eep), y = top + h - highFn(s) * h;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      for (let i = track.length - 1; i >= 0; i--) {
        const s = track[i];
        ctx.lineTo(xOf(s.eep), top + h - lowFn(s) * h);
      }
      ctx.closePath();
      ctx.fill();
    }

    function stack(top, h, label, X, Y) {
      // bottom -> top: X (H), then Y (He), then Z (metals = remainder to 1).
      ctx.fillStyle = COL.X; band(top, h, () => 0, X);
      ctx.fillStyle = COL.Y; band(top, h, X, (s) => X(s) + Y(s));
      ctx.fillStyle = COL.Z; band(top, h, (s) => X(s) + Y(s), () => 1);

      ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
      ctx.strokeRect(PAD_L, top, W - PAD_L - PAD_R, h);

      labelPill(label, PAD_L + 4, top + 4);
      // y ticks: 1 at top, 0 at bottom.
      ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";
      ctx.fillText("1", 14, top + 9);
      ctx.fillText("0", 14, top + h);
    }

    stack(coreTop, chartH, "core", (s) => s.X_core, (s) => s.Y_core);
    stack(surfTop, chartH, "surface", (s) => s.X_surf, (s) => s.Y_surf);

    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // -- CNO view: C/N/O mass-fraction lines, core & surface independently scaled
  function drawCno() {
    const { e0, e1, xOf, chartH, coreTop, surfTop } = layout();
    region(coreTop, chartH, xOf, "core", (s) => s.metals_core);
    region(surfTop, chartH, xOf, "surface", (s) => s.metals_surf);
    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // One sub-chart of C/N/O lines, auto-scaled to ITS OWN max (the core/surface
  // decoupling that keeps the surface dredge-up visible against the huge core).
  function region(top, h, xOf, label, pick) {
    let max = 0;
    for (const s of track)
      for (const el of ELEMS) max = Math.max(max, pick(s)?.[el] ?? 0);
    if (!(max > 0)) max = 1;
    const yOf = (v) => top + h - (v / max) * h;

    ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, top, W - PAD_L - PAD_R, h);

    for (const el of ELEMS) {
      ctx.strokeStyle = ELEM_COL[el]; ctx.lineWidth = 1.6;
      ctx.beginPath();
      track.forEach((s, i) => {
        const x = xOf(s.eep), y = yOf(pick(s)?.[el] ?? 0);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    labelPill(label, PAD_L + 4, top + 4);
    // y ticks: the region max at top (the scale IS the lesson — core ~0.6 vs
    // surface ~0.008), 0 at bottom.
    ctx.fillStyle = "#8a93a6"; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(fmtFrac(max), PAD_L - 3, top + 9);
    ctx.fillText("0", PAD_L - 3, top + h);
    ctx.textAlign = "left";

  }

  // Format a mass fraction compactly for the y-axis cap: 0.60, 0.008, 2.3e-4.
  function fmtFrac(v) {
    if (v >= 0.1) return v.toFixed(2);
    if (v >= 0.001) return v.toFixed(3);
    return v.toExponential(1);
  }

  // A chart label drawn as bright text on a dark rounded pill, anchored at its
  // top-left (x, y), so it reads clearly over whichever band sits behind it.
  function labelPill(text, x, y) {
    ctx.font = "600 12px system-ui, sans-serif";
    const padX = 5, h = 16;
    const w = ctx.measureText(text).width + padX * 2;
    ctx.fillStyle = "rgba(8,10,18,0.80)";
    roundRect(x, y, w, h, 4); ctx.fill();
    ctx.fillStyle = "#f4f7fc";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + padX, y + h / 2 + 0.5);
    ctx.textBaseline = "alphabetic";
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // Faint full-height line wherever the phase label changes, labeled once at the
  // top — turns the EEP axis into a readable MS | RGB map (a teaching cue).
  function drawPhaseDividers(xOf) {
    ctx.font = "11px system-ui, sans-serif";
    let prev = null, lastLabelX = -1e9;
    for (const s of track) {
      if (s.phase === prev) continue;
      prev = s.phase;
      const x = xOf(s.eep);
      if (x > PAD_L + 1) {
        ctx.strokeStyle = "rgba(138,147,166,0.30)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      }
      if (x - lastLabelX > 42) {   // looser on the now-narrower axis so labels don't crowd
        ctx.fillStyle = "#8a93a6";
        ctx.fillText(s.phase, x + 3, PAD_T - 5);
        lastLabelX = x;
      }
    }
  }

  function drawMarker(xOf, e0, e1) {
    if (!marker) return;
    const eep = Math.min(Math.max(marker.eep, e0), e1);
    const x = xOf(eep);
    ctx.strokeStyle = "#e7ecf5"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
    // little caps so the marker reads as a marker, not a phase divider.
    ctx.fillStyle = "#e7ecf5";
    ctx.beginPath(); ctx.arc(x, PAD_T, 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x, H - PAD_B, 2.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawAxis() {
    ctx.fillStyle = "#8a93a6"; ctx.font = "12px system-ui, sans-serif";
    ctx.fillText("EEP →  (evolutionary phase)", W / 2 - 80, H - 8);
  }

  return { setTrack, update, setMode };
}
