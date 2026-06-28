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
//  * "light" — the fragile light elements Li, Be, F together, on a LOG scale (forced;
//              linear is useless when everything is ≤4e-7 of mass). The lesson is that
//              fragility tracks burning temperature: proton capture destroys Li (~2.5
//              MK) hardest as the RGB convective envelope deepens, Be (~3.5 MK) less,
//              while F survives this side of the AGB — the stable backdrop here, the
//              role Fe plays in the cno view. Boron is absent: MIST's only B isotope is
//              the radioactive b8 (~1e-83), not stable boron — so this is a Li/Be/F
//              panel, the achievable part of the requested "Be/B/F". A *panel*, not a
//              one-off element: Be/F would be invisible floor-huggers among the big
//              cno metals, so they get their own log view with Li (the bridge element).
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
import { teffToCSS } from "./color.js";

const PAD_L = 30, PAD_R = 10, PAD_T = 16, PAD_B = 26;
const GAP = 22;   // vertical gap between the core and surface sub-charts
const clamp01 = (x) => Math.max(0, Math.min(1, x));
// Honesty caption for the white-dwarf structure view (see drawWD): the C/O core and
// DA atmosphere are read from the model; the He buffer + all layer thicknesses are
// canonical and exaggerated to be visible (the simulator models no radial structure).
const WD_CAPTION =
  "Schematic cross-section. Composition is from the model (the C/O core and DA " +
  "atmosphere are real); the He buffer and all layer thicknesses are canonical, " +
  "exaggerated to be visible — no radial structure is modeled.";

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
  Li: "#ff2d6f", Be: "#2ee6c0",                 // lithium crimson / beryllium teal
  C: "#ff9f43", N: "#26de81", O: "#54a0ff",     // the CNO trio (orange/green/blue)
  F: "#cfe85a",                                 // fluorine yellow-green
  Ne: "#ff6b9d", Na: "#ffe14d",                 // neon rose / sodium D-line yellow
  Mg: "#feca57", Al: "#cdd6e0",                 // magnesium amber / aluminium silver
  Si: "#a55eea", P: "#c77dff",                  // silicon violet / phosphorus orchid
  S: "#c4e538", Ca: "#ee5253", Ti: "#00d2d3",   // sulfur lime / calcium red / titanium cyan
  Fe: "#a4b0be",                                // iron grey
};
// The per-element ("cno") detail view: fourteen metals in atomic-number order, legend
// reads Li→Fe left to right. (Be & F are NOT here — they're floor-huggers among the
// big metals; they get their own light-element view below, the whole "panel not a
// one-off element" point.)
const ELEMS = ["Li", "C", "N", "O", "Ne", "Na", "Mg", "Al", "Si", "P", "S", "Ca", "Ti", "Fe"];
// The "light" view: the fragile light elements that proton-capture burning destroys,
// shown together on a LOG scale (they're all ≤4e-7 of mass — flat on the axis in
// linear, so this view is log-only). The lesson is that fragility tracks burning
// temperature: Li (~2.5 MK) plunges hardest, Be (~3.5 MK) less, and F survives this
// side of the AGB (the stable backdrop, like Fe in the cno view). Boron is absent —
// MIST's only B isotope is the radioactive b8 (~1e-83), not stable boron.
const LIGHT_ELEMS = ["Li", "Be", "F"];

export function createComp(canvas, cssW = 300, cssH = 280) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  // W/H are `let` (not destructured const) so resize() can re-fit to a new
  // display size; layout()/region()/drawAxis() all read W/H at draw time, so
  // they pick up the new size on the next draw().
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));

  let track = null;    // array of StellarState (age-independent, set per mass/feh)
  let marker = null;   // current StellarState (moves as age scrubs)
  let mode = "bulk";   // "bulk" (X/Y/Z bands) | "cno" (14-element lines) | "light" (Li/Be/F)
  let scale = "lin";   // "lin" | "log" — the cno view's y-axis (log reveals Li/Na)
  let wd = false;      // white-dwarf endgame: replace the burning-abundance views with
                       // a layered structure cross-section (see drawWD)
  // Per-element visibility for the cno view (legend-click toggles). Session-only
  // (not persisted). Scoped to the cno view — the light view is only three lines.
  const hidden = new Set();

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }
  function setMode(m) { mode = (m === "cno" || m === "light") ? m : "bulk"; draw(); }
  // Enter/leave the white-dwarf endgame structure view (mirrors hr.setEndgame). It
  // swaps the burning-abundance views for the layered cross-section, driven by the
  // marker state alone (the EEP-vs-track machinery doesn't apply to a structure view).
  function setEndgame(states) { wd = true; track = states && states.length ? states : track; draw(); }
  function clearEndgame() { wd = false; draw(); }
  function setScale(s) { scale = s === "log" ? "log" : "lin"; draw(); }
  // Toggle one per-element line in the cno view on/off, returning its new
  // visibility. Hiding doesn't just declutter: region() autoscales over only the
  // elements it's handed, so hiding the abundant O/C/N rescales the axis to reveal
  // the trace elements (Na, Al, P…) at full height — that rescale IS the payoff.
  function toggleElem(el) {
    if (hidden.has(el)) hidden.delete(el); else hidden.add(el);
    draw();
    return !hidden.has(el);
  }
  // Re-fit to a new display size (responsive layout) and redraw from retained state.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

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
    if (wd) { drawWD(); return; }   // structure view drives off the marker, not the track
    if (!track) return;
    if (mode === "cno") drawCno();
    else if (mode === "light") drawLight();
    else drawBulk();
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

  // -- per-element view: fourteen element mass-fraction lines, core & surface
  // independently scaled, linear or log (the log toggle is what makes the trace
  // elements visible).
  function drawCno() {
    const { e0, e1, xOf, chartH, coreTop, surfTop } = layout();
    const useLog = scale === "log";
    // Only the elements still toggled on — region() ranges (autoscales) over
    // exactly this list, so the y-axis follows what's actually shown.
    const shown = ELEMS.filter((el) => !hidden.has(el));
    region(coreTop, chartH, xOf, "core", (s) => s.metals_core, shown, useLog);
    region(surfTop, chartH, xOf, "surface", (s) => s.metals_surf, shown, useLog);
    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // -- light-element view: the fragile light elements (Li, Be, F) on a LOG scale.
  // Same machinery as the cno view, but a different (tiny) element set and log forced
  // on — linear is useless here (everything is ≤4e-7 of mass). The payoff is watching
  // surface Li plunge and Be dip on the lower RGB while F holds steady (fragility
  // tracks burning temperature). Reuses region()'s log path, so the decade gridlines,
  // floor-clamping and independent core/surface scales all come for free.
  function drawLight() {
    const { e0, e1, xOf, chartH, coreTop, surfTop } = layout();
    region(coreTop, chartH, xOf, "core", (s) => s.metals_core, LIGHT_ELEMS, true);
    region(surfTop, chartH, xOf, "surface", (s) => s.metals_surf, LIGHT_ELEMS, true);
    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // -- white-dwarf structure view: a schematic layered cross-section -------------
  // The burning-abundance views are over once the star is a degenerate remnant, so in
  // the endgame the panel shows the white dwarf's ANATOMY instead: a C/O core under a
  // thin He buffer under a thin H (or He) atmosphere. What is honest here:
  //   * The C/O core composition (C:O) and the atmosphere type (DA pure-H vs DB He)
  //     are READ FROM THE MODEL each frame (data-driven) — for the loaded MIST grid
  //     every white dwarf comes out DA with a C/O core (the surface purifies to pure
  //     hydrogen by gravitational settling; the non-DA / He-core paths are kept as a
  //     minimal data-parameterized fallback, not authored artwork).
  //   * The He buffer and ALL layer thicknesses are CANONICAL and exaggerated to be
  //     visible — the simulator models no radial structure. The drawn envelope thins
  //     as log g rises (giant shedding its envelope → degenerate remnant with a thin
  //     skin), an evocative cue tied to the real log g, not a measured profile.
  //   * Crystallization is shown in the CORE (where the C/O lattice forms), never on
  //     the gaseous surface; its onset temperature rises with log g (denser remnants
  //     crystallize hotter — the Gaia crystallization sequence). Evocative, labeled.
  function drawWD() {
    const s = marker;
    if (!s) return;
    const PAD = 12;
    const coolCol = teffToCSS(s.Teff_K);

    // --- read the composition from the state (data-driven) ---
    const heCore = (s.Y_core ?? 0) > 0.5;          // He-core WD (very low mass) vs C/O
    const mc = s.metals_core || {};
    const cC = mc.C ?? 0, cO = mc.O ?? 0;
    const da = (s.X_surf ?? 0) >= (s.Y_surf ?? 0);  // DA (H atmosphere) vs DB (He)

    // --- schematic geometry, the envelope thinning with log g (real) ---
    const g = s.logg ?? 8;
    const t = clamp01((g - 0.5) / (8.7 - 0.5));     // 0 ≈ AGB giant, 1 ≈ cold remnant
    const coreFrac = 0.35 + 0.55 * t;               // tiny core+vast envelope → thin skin
    const envFrac = 1 - coreFrac;

    // --- crystallization: a core phenomenon, onset rising with log g ---
    // ~6.5 kK at log g 7.95 (0.54 M☉) up to ~13 kK at log g 8.7 (1.0 M☉). Only for a
    // genuinely degenerate remnant (log g ≳ 7) below its onset; grows from the centre.
    const onset = Math.max(4000, Math.min(20000, 6500 + 8700 * (g - 7.95)));
    let crystFrac = 0;
    if (g >= 7 && s.Teff_K < onset)
      crystFrac = Math.max(0, Math.min(0.9, ((onset - s.Teff_K) / onset) * 1.3));

    // --- layout: cross-section disk on the left, a label column on the right ---
    // The caption reserve is DYNAMIC — its wrapped line count grows as the canvas
    // narrows, so a fixed reserve would clip the last line on a phone-width panel.
    const titleH = 24, capLh = 11;
    ctx.font = "10px system-ui, sans-serif";
    const capH = wrapText(WD_CAPTION, PAD, 0, W - 2 * PAD, capLh, true) * capLh + 6;
    const top = PAD + titleH, bot = H - PAD - capH;
    const LW = Math.max(150, W * 0.42);             // label column width (text-fit)
    const diskAreaW = W - PAD - PAD - LW;
    const cx = PAD + diskAreaW / 2;
    const cy = (top + bot) / 2;
    const Rd = Math.max(24, Math.min(diskAreaW / 2 - 4, (bot - top) / 2 - 4));

    const COL_CORE = heCore ? "#ffce6b" : "#aeb9cf";   // He gold / C·O degenerate steel
    const COL_BUF = "#e0b85f";                          // He buffer (canonical)
    const COL_ATM = da ? "#5b8def" : "#ffce6b";         // H (DA) blue / He (DB) gold
    const COL_CRYST = "#e6eeff";                        // diamond/lattice tint

    const circle = (r) => { ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill(); };

    const rCore = Rd * coreFrac;
    const atmTh = Rd * envFrac * 0.30;
    const rBuf = Rd - atmTh;

    // soft cooling-color rim (the only place Teff tints the cross-section)
    ctx.save();
    ctx.shadowColor = coolCol; ctx.shadowBlur = 14;
    ctx.fillStyle = COL_ATM; circle(Rd);
    ctx.restore();
    ctx.fillStyle = COL_BUF; circle(rBuf);
    ctx.fillStyle = COL_CORE; circle(rCore);
    // subtle radial shading so the dense core reads as a sphere, not a flat disk
    const grd = ctx.createRadialGradient(cx - rCore * 0.3, cy - rCore * 0.3, rCore * 0.1, cx, cy, rCore);
    grd.addColorStop(0, "rgba(255,255,255,0.18)");
    grd.addColorStop(1, "rgba(0,0,0,0.22)");
    ctx.fillStyle = grd; circle(rCore);

    // crystallized inner region (area-proportional), with faint facet lines
    if (crystFrac > 0) {
      const rCr = rCore * Math.sqrt(crystFrac);
      ctx.fillStyle = COL_CRYST; circle(rCr);
      ctx.strokeStyle = "rgba(120,140,180,0.55)"; ctx.lineWidth = 1;
      ctx.save();
      ctx.beginPath(); ctx.arc(cx, cy, rCr, 0, Math.PI * 2); ctx.clip();
      for (let k = 0; k < 6; k++) {
        const a = (k / 6) * Math.PI;
        ctx.beginPath();
        ctx.moveTo(cx - Math.cos(a) * rCr, cy - Math.sin(a) * rCr);
        ctx.lineTo(cx + Math.cos(a) * rCr, cy + Math.sin(a) * rCr);
        ctx.stroke();
      }
      ctx.restore();
    }

    // thin separators between shells
    ctx.strokeStyle = "rgba(8,10,18,0.45)"; ctx.lineWidth = 1;
    for (const r of [Rd, rBuf, rCore]) {
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    }

    // --- title + type tag (type tinted by the cooling color) ---
    labelPill("white-dwarf structure", PAD, PAD);
    const tag = `${da ? "DA" : "DB"} · ${heCore ? "He core" : "C/O core"}`;
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.fillStyle = coolCol; ctx.textAlign = "right";
    ctx.fillText(tag, W - PAD, PAD + 12);
    ctx.textAlign = "left";

    // --- label column: one entry per layer, outer → inner. Sublines WRAP to the
    // column width (never truncate at the canvas edge — the phone-width failure the
    // first pass had), advancing the cursor by however many lines they take. ---
    const lx = W - PAD - LW + 2;
    const txtW = LW - 16;            // text width available after the swatch
    let ly = top + 4;
    const entry = (col, title, lines) => {
      ctx.fillStyle = col;
      ctx.fillRect(lx, ly + 2, 9, 9);
      ctx.fillStyle = "#e7ecf5"; ctx.font = "600 11px system-ui, sans-serif";
      ctx.fillText(title, lx + 14, ly + 10);
      ctx.fillStyle = "#9aa3b5"; ctx.font = "10px system-ui, sans-serif";
      let yy = ly + 22;
      for (const l of lines) yy += wrapText(l, lx + 14, yy, txtW, 12) * 12;
      ly = yy + 6;
    };
    const yFmt = (v) => ((v ?? 0) < 1e-4 ? "0" : fmtFrac(v));  // tidy the pure-H WD's Y≈0
    entry(COL_ATM,
      da ? "H atmosphere (DA)" : "He atmosphere (DB)",
      [`X ${fmtFrac(s.X_surf ?? 0)} · Y ${yFmt(s.Y_surf)}`, "~1e-4 M skin"]);
    if (da) entry(COL_BUF, "He buffer", ["~1e-2 M"]);
    entry(COL_CORE,
      heCore ? "He core" : "C/O core",
      heCore
        ? [`Y ${fmtFrac(s.Y_core ?? 0)}`, "degenerate · ~99% mass"]
        : [`C ${pct(cC)} · O ${pct(cO)}`, "degenerate · ~99% mass"]);
    if (crystFrac > 0)
      entry(COL_CRYST, "crystallizing core",
        [`~${Math.round(crystFrac * 100)}% solid`, "C/O lattice (evocative)"]);

    // --- honesty caption (wrapped; capH reserved its exact line count above) ---
    ctx.fillStyle = "#7e879a"; ctx.font = "10px system-ui, sans-serif";
    wrapText(WD_CAPTION, PAD, bot + 12, W - 2 * PAD, capLh);
  }

  // Format a mass fraction as a whole-ish percent for compact core labels.
  function pct(v) { return `${Math.round((v || 0) * 100)}%`; }

  // Minimal word-wrap for canvas text: draw `text` from (x,y) wrapping to maxW, and
  // return the number of lines used. With dry=true it measures only (no draw), so a
  // caller can reserve the right height before laying out — the panel must stay
  // width-robust (a phone-narrow canvas wraps more lines than a wide one). Assumes the
  // font is already set on ctx (measureText/​fillText both read it).
  function wrapText(text, x, y, maxW, lh, dry) {
    const words = text.split(" ");
    let line = "", n = 0;
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > maxW && line) {
        if (!dry) ctx.fillText(line, x, y);
        y += lh; n++; line = w;
      } else line = test;
    }
    if (line) { if (!dry) ctx.fillText(line, x, y); n++; }
    return n;
  }

  // One sub-chart of element lines for `elems`, scaled to ITS OWN range (the
  // core/surface decoupling that keeps the surface dredge-up visible against the huge
  // core). `useLog` sets the value→y map: linear reads the big elements and their
  // dredge-up directly; log opens up the ~10 decades the trace elements (Li, Be, Na…)
  // live in, so their depletion plunges and enrichments finally show.
  function region(top, h, xOf, label, pick, elems, useLog) {
    // Range over every element & row in this sub-chart (core or surface).
    let max = 0, minPos = Infinity;
    for (const s of track)
      for (const el of elems) {
        const v = pick(s)?.[el] ?? 0;
        if (v > max) max = v;
        if (v > 0 && v < minPos) minPos = v;
      }
    if (!(max > 0)) max = 1;

    // Build the value→y map and the two axis-cap labels for the active scale.
    let yOf, topLabel, botLabel, dec = null;
    if (useLog) {
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

    for (const el of elems) {
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

  return { setTrack, update, setMode, setScale, toggleElem, setEndgame, clearEndgame, resize };
}
