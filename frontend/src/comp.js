// Composition panel (STAR_SIM_SPEC.md §5.4). Two views over the same EEP axis,
// switched by setMode():
//
//  * "bulk"  — X=H, Y=He, Z=metals as stacked-area bands (the default). Core on
//              top (where the drama is), surface below.
//  * "cno"   — the Phase 4 per-element detail: fourteen element mass fractions as
//              lines — Li, C, N, O, Ne, Na, Mg, Al, Si, P, S, Ca, Ti, Fe (the id
//              stays "cno" — it began as the CNO trio). Core and surface get
//              INDEPENDENT y-scales on purpose: during core-He burning the core's
//              C/O climb to tens of percent while the surface stays ~1%, so a shared
//              scale would flatten the surface first-dredge-up signature (N up, C
//              down) — the actual teaching moment — into nothing. The α / odd-Z /
//              iron-peak tracers are near-flat: Fe in particular just marks the input
//              [Fe/H], a steady backdrop that makes the CNO motion legible.
//
//              This view has a linear/log scale toggle (setScale). On LINEAR the big
//              elements (O, C, N…) and their dredge-up are read directly; but lithium
//              (~1e-10 of mass) and sodium (~3e-5) are sub-pixel floor-huggers against
//              O's ~7e-3 — invisible. On LOG every element spans real decades, so Li's
//              dramatic surface depletion (it burns as the convective envelope deepens,
//              plunging ~2400x by the RGB tip) and Na's Ne-Na-cycle enrichment (~1.4x)
//              actually show. Li's plunge runs off the bottom of the log axis once it
//              burns to ~0 — that "off the bottom" read is the payoff, not a gap.
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
// above and from each other. Li is a vivid flame-test crimson, deliberately loud:
// it's the star of the log view (the depletion plunge is the payoff), so it must
// pop against the warm-side cluster (Na yellow / Al silver / P orchid) where it
// lives. Fe is a steel-grey iron mnemonic (and the inert tracer that just marks the
// input [Fe/H]); CNO keep their Phase-4 hues; the α / odd-Z / iron-peak tracers
// fill the remaining hue gaps (violet/chartreuse/red/cyan, plus a sodium-D yellow,
// aluminium silver and phosphorus orchid). Li/Na/Al/P are tiny floor-huggers (Li
// ~1e-10, the rest ~1e-5 of mass) — on the linear scale they cluster on the axis,
// so they need only differ from each other and from Fe/Ca/Ti.
const ELEM_COL = {
  Li: "#ff2d6f",                                // lithium crimson (flame-test red)
  C: "#ff9f43", N: "#26de81", O: "#54a0ff",     // the CNO trio (orange/green/blue)
  Ne: "#ff6b9d", Na: "#ffe14d",                 // neon rose / sodium D-line yellow
  Mg: "#feca57", Al: "#cdd6e0",                 // magnesium amber / aluminium silver
  Si: "#a55eea", P: "#c77dff",                  // silicon violet / phosphorus orchid
  S: "#c4e538", Ca: "#ee5253", Ti: "#00d2d3",   // sulfur lime / calcium red / titanium cyan
  Fe: "#a4b0be",                                // iron grey
};
// Atomic-number order, so the legend reads Li→Fe left to right.
const ELEMS = ["Li", "C", "N", "O", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Ca", "Ti", "Fe"];

export function createComp(canvas, cssW = 300, cssH = 280) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  const { ctx, W, H } = fitCanvas(canvas, cssW, cssH);

  let track = null;    // array of StellarState (age-independent, set per mass/feh)
  let marker = null;   // current StellarState (moves as age scrubs)
  let mode = "bulk";   // "bulk" (X/Y/Z bands) | "cno" (per-element lines)
  let scale = "lin";   // "lin" | "log" — per-element y-axis (log reveals Li/Na)

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }
  function setMode(m) { mode = m === "cno" ? "cno" : "bulk"; draw(); }
  function setScale(s) { scale = s === "log" ? "log" : "lin"; draw(); }

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

  // -- per-element view: element mass-fraction lines, core & surface independently
  // scaled, linear or log (the log toggle is what makes the trace elements visible).
  function drawCno() {
    const { e0, e1, xOf, chartH, coreTop, surfTop } = layout();
    region(coreTop, chartH, xOf, "core", (s) => s.metals_core);
    region(surfTop, chartH, xOf, "surface", (s) => s.metals_surf);
    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // One sub-chart of per-element lines, scaled to ITS OWN range (the core/surface
  // decoupling that keeps the surface dredge-up visible against the huge core). The
  // active scale ("lin"|"log") sets the value→y map: linear reads the big elements
  // and their dredge-up directly; log opens up the ~10 decades the trace elements
  // (Li, Na…) live in, so Li's depletion plunge and Na's enrichment finally show.
  function region(top, h, xOf, label, pick) {
    // Range over every element & row in this sub-chart (core or surface).
    let max = 0, minPos = Infinity;
    for (const s of track)
      for (const el of ELEMS) {
        const v = pick(s)?.[el] ?? 0;
        if (v > max) max = v;
        if (v > 0 && v < minPos) minPos = v;
      }
    if (!(max > 0)) max = 1;

    // Build the value→y map and the two axis-cap labels for the active scale.
    let yOf, topLabel, botLabel, dec = null;
    if (scale === "log") {
      // Decade-rounded window, span capped to [MINDEC, MAXDEC] decades so a single
      // ~1e-16 core-Li sample can't stretch the axis to 15 decades, and a near-flat
      // region isn't absurdly zoomed. Values at/below the floor — Li once it burns to
      // exactly 0 — clamp to the bottom, so the plunge reads as "off the bottom", not
      // a NaN gap. THIS is what makes Li visible: its 1e-10 fraction is sub-pixel on a
      // linear axis but spans real decades here.
      const MAXDEC = 10, MINDEC = 4;
      const hiE = Math.ceil(Math.log10(max));
      let loE = isFinite(minPos) ? Math.floor(Math.log10(minPos)) : hiE - MINDEC;
      loE = Math.max(hiE - MAXDEC, Math.min(loE, hiE - MINDEC));
      const span = hiE - loE;
      dec = { hiE, loE, span };
      yOf = (v) => {
        if (!(v > 0)) return top + h;                  // zero / negative → axis bottom
        const f = (Math.log10(v) - loE) / span;        // 0 at bottom decade, 1 at top
        return top + h - Math.max(0, Math.min(1, f)) * h;
      };
      topLabel = fmtExp(hiE);
      botLabel = fmtExp(loE);
    } else {
      yOf = (v) => top + h - (v / max) * h;
      topLabel = fmtFrac(max);
      botLabel = "0";
    }

    // faint decade gridlines in log mode, so the eye can read the orders of magnitude
    if (dec) {
      ctx.strokeStyle = "rgba(138,147,166,0.12)"; ctx.lineWidth = 1;
      for (let e = dec.loE + 1; e < dec.hiE; e++) {
        const y = top + h - ((e - dec.loE) / dec.span) * h;
        ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
      }
    }

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
    // y ticks: the cap at top, the floor at bottom. Linear: the max IS the lesson
    // (core ~0.6 vs surface ~0.008), 0 at bottom. Log: the bracketing decades.
    ctx.fillStyle = "#8a93a6"; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(topLabel, PAD_L - 3, top + 9);
    ctx.fillText(botLabel, PAD_L - 3, top + h);
    ctx.textAlign = "left";
  }

  // Format a mass fraction compactly for the y-axis cap: 0.60, 0.008, 2.3e-4.
  function fmtFrac(v) {
    if (v >= 0.1) return v.toFixed(2);
    if (v >= 0.001) return v.toFixed(3);
    return v.toExponential(1);
  }

  // Power-of-ten axis cap for the log scale: exponent e → "1e-2".
  function fmtExp(e) { return `1e${e}`; }

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

  return { setTrack, update, setMode, setScale };
}
