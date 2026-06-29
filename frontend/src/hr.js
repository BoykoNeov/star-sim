// HR diagram (STAR_SIM_SPEC.md §5): log L vs log Teff, Teff axis REVERSED (hot on
// the left). Draws the full evolutionary track for the chosen (mass, [Fe/H]) with
// a marker at the current age — setTrack() takes the list from /track, update()
// moves the marker from /state (same split the composition panel uses).

import { teffToCSS } from "./color.js";
import { fitCanvas } from "./canvas.js";

// Plot bounds (log10): covers cool red dwarfs to hot O stars, and ~1e-4..1e6 L.
const LOGT_MIN = 3.4;   // ~2500 K  (right edge, cool)
const LOGT_MAX = 4.7;   // ~50000 K (left edge, hot)
const LOGL_MIN = -4;
const LOGL_MAX = 6;
// Wider bounds for the WHITE-DWARF ENDGAME view (the smoldering-cinder gateway): the
// cooling track runs from the cool-giant corner up to a ~100–400 kK central star
// (log T ≈ 5.0–5.6) and all the way down to a cold cinder at logL ≈ −5.3. The normal
// bounds would clip both the hot central star (off the left) and the faded WD (off the
// bottom), so endgame mode swaps in these. setEndgame()/clearEndgame() toggle them.
const LOGT_MIN_EG = 3.35;
const LOGT_MAX_EG = 5.7;    // ~500 kK — fits the hottest central stars (394 kK at 6.5 M☉)
const LOGL_MIN_EG = -5.6;
const LOGL_MAX_EG = 4.5;
// Wider bounds for the WOLF–RAYET ENDGAME view: a WR star is the stripped, blazing core
// of a massive star — far HOTTER (the stripped surface climbs to ~250 kK, log T ≈ 5.4)
// and far MORE LUMINOUS (log L ≈ 5.6–6.8; the 300 M☉ onset peaks at log L 6.80) than a
// white dwarf, so the WD endgame's faint-L ceiling (4.5) would clip the whole WR track
// off the top. The cool side stays open enough to show the immediate-pre-WR giant in the
// faint living-track context (the cool CHeB excursion reaches log T ≈ 3.9).
const LOGT_MIN_WR = 3.6;    // ~4 kK   (right edge, shows the cool pre-WR giant for context)
const LOGT_MAX_WR = 5.5;    // ~316 kK (left edge, fits the hottest stripped WO core)
const LOGL_MIN_WR = 4.3;
const LOGL_MAX_WR = 7.0;    // headroom above the 300 M☉ onset (log L 6.80)
// Per-mode gridline values (Teff in log10 K, L in log10 L☉) — the endgame views need
// hotter Teff and (WD) fainter / (WR) brighter L ticks than the living view.
const GRID_T = [4.5, 4.0, 3.7, 3.5];
const GRID_L = [-3, 0, 3, 6];
const GRID_T_EG = [5.5, 5.0, 4.5, 4.0, 3.5];
const GRID_L_EG = [-5, -2, 1, 4];
const GRID_T_WR = [5.4, 5.0, 4.5, 4.0];
const GRID_L_WR = [5, 6, 7];
// Asymmetric left pad: the y-axis needs two lanes side by side — the rotated
// "L / L☉" title in the far-left lane, the 1e-3..1e6 tick numbers in the lane
// just inside it — so they stop overlapping. Top/right/bottom stay at PAD.
const PAD = 30;
const PAD_L = 50;

// --- Variable-star zones for the optional overlay (setOverlay) ----------------
// SCHEMATIC on purpose: these are illustrative CLASS POSITIONS on the HR diagram,
// not a metallicity-calibrated instability strip — the panel help + legend say so,
// in keeping with the project's honesty rule (label what the data backs). They map
// "where on the HR diagram do stars of each variable class sit," NOT a claim that
// the currently-selected star is variable (the marker just happens to fall in or
// out of a zone). Drawn behind the track so the live star stays legible on top.
//
// The classical instability strip (one band, driven by the κ-mechanism in the He II
// partial-ionization zone) is crossed by δ Scuti, RR Lyrae and Cepheids at rising
// luminosity. Its edges genuinely CURVE (steeper near the main sequence, shallower
// at Cepheid luminosities), so it's given as piecewise-linear (logL, Teff_blue,
// Teff_red) control points rather than one straight line — that lets each class
// land near its real temperature instead of forcing RR Lyrae ~500 K off.
const STRIP = [
  // logL,  blue/hot(K), red/cool(K)
  [0.3, 8700, 7100],
  [1.0, 8400, 6900],
  [1.7, 7500, 6100],   // RR Lyrae sit here, on the horizontal branch
  [2.5, 7000, 5600],
  [4.0, 6500, 5100],
  [5.3, 6000, 4700],   // luminous classical Cepheids
];
// Two other variable classes, as simple (logL, Teff_K) corner polygons:
// LBV/S Dor near the empirical upper-luminosity (Humphreys–Davidson) limit, and the
// cool luminous Miras / long-period variables on the AGB.
const LBV_ZONE = [[5.3, 28000], [5.3, 8500], [5.95, 12000], [5.95, 28000]];
const MIRA_ZONE = [[2.8, 3800], [2.8, 2700], [4.4, 2700], [4.4, 4000]];
// Labels: [text, logL, Teff_K, color] placed near each zone's center.
const STRIP_GOLD = "#ffd98a", LBV_BLUE = "#a9c6ff", MIRA_RED = "#ff9d9d";
const ZONE_LABELS = [
  ["δ Scuti", 0.8, 7600, STRIP_GOLD],
  ["RR Lyrae", 1.7, 6700, STRIP_GOLD],
  ["Cepheids", 4.0, 5650, STRIP_GOLD],
  ["LBV / S Dor", 5.6, 15000, LBV_BLUE],
  ["Miras / LPV", 3.6, 3150, MIRA_RED],
];

export function createHR(canvas, cssW = 300, cssH = 260) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  // W/H are `let` (not destructured const) so resize() can re-fit the canvas to
  // a new display size and the xOf/yOf closures below — which capture the W/H
  // *bindings* — pick up the new values on the next draw().
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));

  // Current plot bounds — swapped between the living-star and endgame views below.
  // xOf/yOf capture these `let` bindings, so a mode switch + redraw rescales the plot.
  let bT0 = LOGT_MIN, bT1 = LOGT_MAX, bL0 = LOGL_MIN, bL1 = LOGL_MAX;

  // Teff reversed: hot (high logT) on the LEFT.
  const xOf = (logT) =>
    PAD_L + (bT1 - logT) / (bT1 - bT0) * (W - PAD_L - PAD);
  const yOf = (logL) =>
    H - PAD - (logL - bL0) / (bL1 - bL0) * (H - 2 * PAD);

  function drawAxes() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#283149";
    ctx.fillStyle = "#8a93a6";
    ctx.font = "12px system-ui, sans-serif";
    ctx.lineWidth = 1;

    // frame
    ctx.strokeRect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);

    // Teff gridlines (label in kK), centered under each line.
    ctx.textAlign = "center";
    for (const logT of (endgameMode ? (endgameKind === "wr" ? GRID_T_WR : GRID_T_EG) : GRID_T)) {
      const x = xOf(logT);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, H - PAD); ctx.stroke();
      ctx.globalAlpha = 1;
      const kK = Math.round(10 ** logT / 100) / 10;
      ctx.fillText(`${kK}kK`, x, H - PAD + 15);
    }
    // L gridlines — tick numbers right-aligned in the lane just left of the
    // frame, so they never collide with the rotated axis title further left.
    ctx.textAlign = "right";
    for (const logL of (endgameMode ? (endgameKind === "wr" ? GRID_L_WR : GRID_L_EG) : GRID_L)) {
      const y = yOf(logL);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`1e${logL}`, PAD_L - 6, y + 4);
    }
    // axis titles
    ctx.textAlign = "center";
    ctx.fillText("Teff →  (hot left)", W / 2, H - 6);
    ctx.save();
    ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("L / L☉", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";   // reset for any later text draws
  }

  let track = null;        // array of StellarState (age-independent, set per mass/feh)
  let marker = null;       // current StellarState (moves as age scrubs)
  let showOverlay = false; // variable-star zones (off by default — opt-in view)
  let endgameMode = false; // endgame view: wide axes + the endgame track
  let endgameKind = "wd";  // "wd" (cooling track) | "wr" (stripping sub-track) — picks bounds/gridlines
  let endgameTrack = null; // the endgame StellarStates (the cooling / stripping sequence)
  let previewTrack = null; // LIVING-mode faint preview of where a WD-bound star is headed

  // Fill + dashed outline the current path with a zone's colors.
  function fillZone(fill, stroke) {
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1;
    ctx.strokeStyle = stroke;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Draw a simple (logL, Teff_K) corner polygon as a translucent zone.
  function drawPolyZone(corners, fill, stroke) {
    ctx.beginPath();
    corners.forEach(([logL, tK], i) => {
      const x = xOf(Math.log10(tK)), y = yOf(logL);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.closePath();
    fillZone(fill, stroke);
  }

  // The variable-star overlay: the classical instability strip (one filled band —
  // blue edge down the control points, then red edge back up) plus the LBV and Mira
  // zones, then the class labels on top. Clipped to the plot frame so nothing bleeds
  // past the axes.
  function drawOverlay() {
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();

    ctx.beginPath();
    STRIP.forEach(([logL, bK], i) => {
      const x = xOf(Math.log10(bK)), y = yOf(logL);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    for (let i = STRIP.length - 1; i >= 0; i--) {
      ctx.lineTo(xOf(Math.log10(STRIP[i][2])), yOf(STRIP[i][0]));
    }
    ctx.closePath();
    fillZone("rgba(255,206,107,0.12)", "rgba(255,206,107,0.5)");

    drawPolyZone(LBV_ZONE, "rgba(130,170,255,0.12)", "rgba(130,170,255,0.5)");
    drawPolyZone(MIRA_ZONE, "rgba(255,120,120,0.12)", "rgba(255,120,120,0.5)");

    ctx.font = "600 11px system-ui, sans-serif";
    ctx.textAlign = "center";
    for (const [text, logL, tK, color] of ZONE_LABELS) {
      ctx.fillStyle = color;
      ctx.fillText(text, xOf(Math.log10(tK)), yOf(logL));
    }
    ctx.textAlign = "left";
    ctx.restore();
  }

  function drawTrack() {
    if (!track || track.length < 2) return;
    ctx.beginPath();
    track.forEach((s, i) => {
      const x = xOf(Math.log10(s.Teff_K)), y = yOf(Math.log10(s.L_lsun));
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "rgba(231,236,245,0.45)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  // The endgame cooling track, colored segment-by-segment by the local Teff so the
  // sequence reads as a journey: cool-red giant → blazing blue-white central star →
  // fading through white/yellow/red to a cold cinder. Drawn over a faint copy of the
  // living track (kept for context — where the star came from).
  function drawEndgameTrack() {
    if (track && track.length > 1) {
      ctx.beginPath();
      track.forEach((s, i) => {
        const x = xOf(Math.log10(s.Teff_K)), y = yOf(Math.log10(s.L_lsun));
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.strokeStyle = "rgba(231,236,245,0.18)";
      ctx.lineWidth = 1.5; ctx.stroke();
    }
    if (!endgameTrack || endgameTrack.length < 2) return;
    ctx.lineWidth = 2;
    for (let i = 1; i < endgameTrack.length; i++) {
      const a = endgameTrack[i - 1], b = endgameTrack[i];
      ctx.beginPath();
      ctx.moveTo(xOf(Math.log10(a.Teff_K)), yOf(Math.log10(a.L_lsun)));
      ctx.lineTo(xOf(Math.log10(b.Teff_K)), yOf(Math.log10(b.L_lsun)));
      ctx.strokeStyle = teffToCSS((a.Teff_K + b.Teff_K) / 2);
      ctx.stroke();
    }
  }

  // A faint, dashed preview of the white-dwarf cooling track on the LIVING HR — "where
  // this star is headed" once its visible life ends (the mirror of the endgame view,
  // which keeps the living track faint for context). The cooling sequence runs far
  // hotter and fainter than the living-star axes, so it's CLIPPED to the plot frame:
  // only the in-bounds stretch shows (the post-AGB climb toward the hot upper-left and
  // the start of the cooling sweep), reading as a ghostly path leaving the bright track.
  // Set only for WD-ending stars (setEndgamePreview(null) for SN/WR), so it never
  // promises a remnant the star won't form.
  function drawPreviewEndgame() {
    if (!previewTrack || previewTrack.length < 2) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();
    ctx.beginPath();
    previewTrack.forEach((s, i) => {
      const x = xOf(Math.log10(s.Teff_K)), y = yOf(Math.log10(s.L_lsun));
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "rgba(231,236,245,0.22)";
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  function draw() {
    drawAxes();
    if (endgameMode) {
      drawEndgameTrack();
    } else {
      if (showOverlay) drawOverlay(); // behind the track, so the live star stays on top
      drawPreviewEndgame();           // ghostly "headed for the WD corner" path, clipped
      drawTrack();
    }
    if (!marker) return;
    const x = xOf(Math.log10(marker.Teff_K));
    const y = yOf(Math.log10(marker.L_lsun));
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = teffToCSS(marker.Teff_K);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#e7ecf5";
    ctx.stroke();
  }

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }
  function setOverlay(on) { showOverlay = !!on; draw(); }
  // The living-mode endgame preview — pass the WD cooling states, or null to clear it
  // (a star changed, or it doesn't end as a white dwarf). Drawn only in living mode.
  function setEndgamePreview(states) {
    previewTrack = states && states.length ? states : null;
    if (!endgameMode) draw();
  }

  // Enter/leave an endgame view. setEndgame(states, kind) swaps in the wide axes and the
  // endgame track; kind picks the bounds + gridlines — "wd" (cool→hot→faint cooling) vs
  // "wr" (hot, luminous stripped sub-track). clearEndgame() restores the living bounds.
  function setEndgame(states, kind = "wd") {
    endgameMode = true;
    endgameKind = kind === "wr" ? "wr" : "wd";
    endgameTrack = states && states.length ? states : null;
    if (endgameKind === "wr") {
      bT0 = LOGT_MIN_WR; bT1 = LOGT_MAX_WR; bL0 = LOGL_MIN_WR; bL1 = LOGL_MAX_WR;
    } else {
      bT0 = LOGT_MIN_EG; bT1 = LOGT_MAX_EG; bL0 = LOGL_MIN_EG; bL1 = LOGL_MAX_EG;
    }
    draw();
  }
  function clearEndgame() {
    endgameMode = false;
    endgameTrack = null;
    bT0 = LOGT_MIN; bT1 = LOGT_MAX; bL0 = LOGL_MIN; bL1 = LOGL_MAX;
    draw();
  }

  // Re-fit to a new display size (the responsive layout calls this when the
  // panel's width changes) and redraw from the retained track + marker.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

  return { setTrack, update, setOverlay, setEndgamePreview, setEndgame, clearEndgame, resize };
}
