// HR diagram (STAR_SIM_SPEC.md §5): log L vs log Teff, Teff axis REVERSED (hot on
// the left). Draws the full evolutionary track for the chosen (mass, [Fe/H]) with
// a marker at the current age — setTrack() takes the list from /track, update()
// moves the marker from /state (same split the composition panel uses). The living
// track is painted segment-by-segment with the local Teff color (like the endgame
// track) so the line itself narrates the journey, split at the marker into a solid
// PAST and a dimmer FUTURE (so "how far along its life is this star" reads at a
// glance), the marker carries a soft glow in the star's own color, and faint
// O·B·A·F·G·K·M spectral-class bands anchor the reversed Teff axis along the top
// edge (living view only — MK classes don't apply to the WD/WR remnant regimes the
// endgame axes span). Dotted iso-radius diagonals (drawIsoRadius) underlie both the
// living and endgame views — constant-R lines from L = 4πR²σT⁴, the diagram's
// graph paper.

import { teffToCSS, teffToRGB } from "./color.js";
import { fitCanvas } from "./canvas.js";

// DEFAULT living-view plot bounds (log10): covers cool red dwarfs to hot O stars, and
// ~1e-4..1e6 L. This is the stable TEACHING frame — the Sun and ordinary stars are read
// against fixed axes here so you can compare stars at a glance. But massive stars clip:
// ≳60 M☉ reach log L > 6 (off the top) and ≳120 M☉ also exceed log T 4.7 (off the left).
// So the living frame is EXPANDED to enclose the current track whenever it crosses an
// edge (applyLivingBounds) — fixed for the common case, auto-fit only when a track demands
// it. The ENDGAME views (WD cooling, WR stripping) span a far wider, mass-dependent range
// (a WD fades to log L ≈ −5; a WR core blazes to ~316 kK / log L ≈ 7), so they FIT TIGHTLY
// to the actual endgame.states each time (setEndgame → fitBounds) — mirroring star.js
// applyWindScale, which fits the WR-3D extent to the frame for exactly this reason. Auto-
// fit GUARANTEES the track is framed regardless of progenitor mass/[Fe/H], which a fixed
// ceiling could not (item 6: a WR trail "so high up nothing is displayed").
const LOGT_MIN = 3.4;   // ~2500 K  (right edge, cool)
const LOGT_MAX = 4.7;   // ~50000 K (left edge, hot)
const LOGL_MIN = -4;
const LOGL_MAX = 6;
// Default living-view gridlines (Teff in log10 K, L in log10 L☉). Used as-is for the
// unexpanded frame; when the frame expands for a massive star — or in an auto-fit endgame
// view — the gridlines are regenerated from the live bounds (genTicks) so labels stay
// legible and on-frame. L ticks stay at INTEGER dex (labels are "1e<n>"); Teff ticks allow
// half-dex steps (labels are kK, so 3.5 → 3.2kK reads fine).
const GRID_T = [4.5, 4.0, 3.7, 3.5];
const GRID_L = [-3, 0, 3, 6];

// --- auto-fit axis helpers ----------------------------------------------------
// Nice gridline step (in log10 dex) for ~4 intervals across `span`. L uses integer dex
// only (its labels are "1e<n>"); Teff allows finer steps (its labels are kK).
function niceStepL(span) { const r = span / 4; return r <= 1 ? 1 : r <= 2 ? 2 : Math.ceil(r); }
function niceStepT(span) { const r = span / 5; for (const s of [0.25, 0.5, 1, 1.5, 2]) if (s >= r) return s; return Math.ceil(r); }
// Gridline values that are multiples of `step` lying inside [lo, hi].
function genTicks(lo, hi, step) {
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 100) / 100);
  return out;
}
// Padded log10 bounds enclosing every state across the given StellarState arrays. A small
// margin keeps the track off the frame edge; a floor pad handles near-flat tracks. Teff/L
// are read straight off the state (Teff_K, L_lsun) — the §3 consumer rule, no provider guts.
function fitBounds(...lists) {
  let t0 = Infinity, t1 = -Infinity, l0 = Infinity, l1 = -Infinity;
  for (const list of lists) for (const s of (list || [])) {
    const lt = Math.log10(s.Teff_K), ll = Math.log10(s.L_lsun);
    if (lt < t0) t0 = lt; if (lt > t1) t1 = lt;
    if (ll < l0) l0 = ll; if (ll > l1) l1 = ll;
  }
  const pT = Math.max(0.12, (t1 - t0) * 0.06), pL = Math.max(0.2, (l1 - l0) * 0.06);
  return { t0: t0 - pT, t1: t1 + pT, l0: l0 - pL, l1: l1 + pL };
}
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

// --- Spectral-class bands (living view) ----------------------------------------
// The textbook O·B·A·F·G·K·M anchor: each class is [letter, cool-edge Teff (K),
// letter-color Teff (K)]; its hot edge is the previous class's cool edge (O extends
// to the hot frame edge). Boundaries are the standard MK Teff cuts. The letter color
// is a representative mid-class Planck hue via teffToCSS, so the row itself runs
// blue-white → red and doubles as a legend for the reversed axis.
const SPECTRAL_CLASSES = [
  ["O", 30000, 40000],
  ["B", 10000, 17000],
  ["A", 7500, 8600],
  ["F", 6000, 6700],
  ["G", 5200, 5600],
  ["K", 3700, 4400],
  ["M", 2400, 3050],
];

export function createHR(canvas, cssW = 300, cssH = 260) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  // W/H are `let` (not destructured const) so resize() can re-fit the canvas to
  // a new display size and the xOf/yOf closures below — which capture the W/H
  // *bindings* — pick up the new values on the next draw().
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));

  // Current plot bounds + gridlines — recomputed by applyLivingBounds (living view) and
  // setEndgame (endgame views). xOf/yOf and drawAxes capture these `let` bindings, so a
  // recompute + redraw rescales the plot and relabels the axes.
  let bT0 = LOGT_MIN, bT1 = LOGT_MAX, bL0 = LOGL_MIN, bL1 = LOGL_MAX;
  let gridT = GRID_T, gridL = GRID_L;

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
    for (const logT of gridT) {
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
    for (const logL of gridL) {
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
  let endgameMode = false; // endgame view: auto-fit axes + the endgame track
  let endgameTrack = null; // the endgame StellarStates (the cooling / stripping sequence)
  let previewTrack = null; // LIVING-mode faint preview of where a WD-bound star is headed
  let companion = null;    // binary-stripped path (b): the un-stripped companion (accretor),
                           //   drawn as a SECOND marker so the Algol mass-ratio reversal is
                           //   visible (the donor blue-left + hotter, the companion cooler).
                           //   Only set in stripped-mode when "Show companion" is on.

  // --- path (b) Chunk 4b: the co-evolving POSYDON binary — BOTH markers move -----------
  // Unlike `companion` above (one static marker beside the living donor), this is a real
  // TIME SERIES: both stars trace their OWN track as system time scrubs, each with a
  // past/future split at the scrubbed step (the living-track idiom, doubled). `binaryIdx`
  // indexes star_1's array; star_2's array may be shorter after a merger truncation, so
  // its own index is clamped separately in drawBinary(). donor (star_1) / companion
  // (star_2) are fixed IDENTITIES — the reversal is the markers crossing, never a label
  // swap (the Chunk-1/Chunk-3 convention-mismatch class of bug).
  let binaryMode = false;
  let binaryStar1 = null;  // array of StellarState (star_1, the donor) across steps
  let binaryStar2 = null;  // array of StellarState (star_2, the companion) — may be shorter
  let binaryIdx = -1;
  // --- supernova mode: a DIFFERENT plot (the light curve), not the HR diagram ---------
  // The SN endgame repurposes this panel as the observable: bolometric L (log, erg/s) vs
  // TIME (LINEAR days since explosion). The linear-time x-axis is deliberate and load-
  // bearing — ⁵⁶Co decay is exponential, so log L is LINEAR in linear time, giving the
  // iconic STRAIGHT radioactive tail on which the Tier-1 slope (0.00975 mag/day) is
  // visually verifiable against SN 1987A's measured tail. A log-time x-axis would bend the
  // tail into a curve and the anchor would read as mush. So SN mode has its own coordinate
  // transforms (xSN/ySN) and its own draw path (drawSupernova), separate from the HR axes.
  let snMode = false;      // light-curve view (overrides endgameMode/living draw)
  let snModel = null;      // the served SupernovaModel (light_curve + scalars)
  let snObserved = null;   // the cited real-SN overlays (sn.js OBSERVED_SNE)
  let snTmax = 500;        // x-axis extent, days
  let snLlo = 40, snLhi = 43;   // y-axis extent, log10(L / erg s⁻¹)
  const LSUN_ERG_S = 3.828e33;  // erg/s — to put the photosphere L_lsun on the erg/s axis

  // --- thermal-pulse showcase (TPAGB): a DECOMPRESSED zoom of the He-shell-flash loops ---
  // The WD scrub deliberately crushes the ~600 chaotic TPAGB rows into 12% of the slider to
  // protect the dramatic ~100 kK central-star spike (see main.js WD_FP). This opt-in view is
  // the inverse: the TPAGB rows alone get the WHOLE panel — surface log L vs age-since-first-
  // pulse (kyr, LINEAR so the sawtooth reads as physical time) — so the 0.3–0.8 dex He-shell-
  // flash loops (a slow quiescent H-shell rise, a brief flash, then a deep dip) are actually
  // legible instead of a squashed sliver. Its own coordinate transforms (xTP/yTP) and draw
  // path (drawThermalPulses), scoped to just the TP slice, like snMode.
  let pulseMode = false;
  let pulseStates = null;                        // the TPAGB-only StellarState slice
  let pAge0 = 0, pAgeMaxKyr = 1, pLlo = 0, pLhi = 1;  // first-pulse age ref + axis extents

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

  // The spectral-class anchor row: ultra-faint vertical separators at the MK class
  // boundaries inside the frame, with each class letter in its own Planck hue sitting
  // just ABOVE the top frame line (the padding strip — inside the frame it would
  // collide with the overlay's LBV label and with luminous tracks). Bands whose
  // visible slice is too thin to hold a letter are skipped; on an expanded hot frame
  // (massive stars) the O band simply widens to the new edge.
  function drawClassBands() {
    const xL = PAD_L, xR = W - PAD;
    ctx.save();
    ctx.font = "600 10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.lineWidth = 1;
    let hotEdgeX = xL;   // O's hot edge = the frame edge, however far it expands
    for (const [letter, coolK, colorK] of SPECTRAL_CLASSES) {
      const x0 = Math.max(xL, hotEdgeX);
      const x1 = Math.min(xR, xOf(Math.log10(coolK)));
      hotEdgeX = x1;
      if (x1 - x0 < 9) continue;    // band off-frame or too thin at this zoom (a single
                                    // 10px letter needs ~7px — 9 keeps G alive at phone width)
      if (x1 < xR - 1) {            // cool-edge separator (skip when it IS the frame edge)
        ctx.strokeStyle = "rgba(138,147,166,0.13)";
        ctx.beginPath(); ctx.moveTo(x1, PAD); ctx.lineTo(x1, H - PAD); ctx.stroke();
      }
      ctx.fillStyle = teffToCSS(colorK);
      ctx.globalAlpha = 0.75;
      ctx.fillText(letter, (x0 + x1) / 2, PAD - 5);
      ctx.globalAlpha = 1;
    }
    ctx.restore();
  }

  // Iso-radius diagonals: on the (log Teff, log L) plane every constant radius is a
  // straight line — L/L☉ = (R/R☉)²·(Teff/T☉)⁴, i.e. logL = 2·logR + 4·(logT − logT☉).
  // Decade lines make the diagram's geometry legible: the giant branch running
  // up-RIGHT means SWELLING (bigger at the same Teff = brighter), the main sequence
  // hugs ~1 R☉ near the Sun, and in the endgame view the WD cooling track slides DOWN
  // a single iso-R line — constant radius, just fading and cooling (why a "dwarf").
  // The physics holds on any axes, so this draws in the living AND endgame views
  // (never the SN light curve — its x-axis is time). Dotted + very faint, behind
  // everything: graph paper, not data. T☉ = 5772 K (the IAU nominal value).
  const LOG_TSUN = Math.log10(5772);
  function drawIsoRadius() {
    const logLof = (logT, e) => 2 * e + 4 * (logT - LOG_TSUN);
    const tAt = (logL, e) => (logL - 2 * e) / 4 + LOG_TSUN;
    ctx.save();
    ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "left";
    for (let e = -3; e <= 4; e++) {          // 0.001 … 10000 R☉; off-frame decades skip
      // The visible sub-segment: clamp the line to the frame in BOTH axes. logL rises
      // with logT along a line, so the L-window maps back to a T-window directly.
      const tLo = Math.max(bT0, tAt(bL0, e));
      const tHi = Math.min(bT1, tAt(bL1, e));
      if (tHi - tLo < 0.02) continue;        // misses the frame (or a corner sliver)
      const x0 = xOf(tLo), y0 = yOf(logLof(tLo, e));   // cool / faint end (lower right)
      const x1 = xOf(tHi), y1 = yOf(logLof(tHi, e));   // hot / bright end (upper left)
      ctx.strokeStyle = "rgba(138,147,166,0.28)";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      ctx.setLineDash([]);
      // Label tucked along the line just inside its cool (lower-right) end, rotated to
      // the on-screen slope so it reads as part of the line. Skipped when the visible
      // segment is too short to hold it.
      const label = `${10 ** e} R☉`;
      const labelW = ctx.measureText(label).width;
      const len = Math.hypot(x1 - x0, y1 - y0);
      if (len < labelW + 18) continue;
      const ux = (x1 - x0) / len, uy = (y1 - y0) / len;   // unit vector toward the hot end
      const lx = x0 + ux * (labelW + 8), ly = y0 + uy * (labelW + 8);
      ctx.save();
      ctx.translate(lx, ly);
      ctx.rotate(Math.atan2(y0 - y1, x0 - x1));           // text runs hot→cool (down-right)
      ctx.fillStyle = "rgba(138,147,166,0.65)";
      ctx.fillText(label, 0, -3);
      ctx.restore();
    }
    ctx.restore();
  }

  // The marker's row index along `list` — the past/future split point. The marker IS
  // an element of the current track array in every scrub mode (live: refresh() picks
  // currentTrack[i], the same array setTrack received; WD/WR: refreshWD/WR pick
  // endgame.states[i], the same array setEndgame received), so indexOf is exact. The
  // age fallback covers any state that arrives from elsewhere: every scrub sequence
  // is age-monotone, so "last row not younger than the marker" is the right split.
  function splitIndex(list) {
    if (!marker || !list) return list ? list.length - 1 : -1;
    const idx = list.indexOf(marker);
    if (idx >= 0) return idx;
    let s = list.length - 1;
    for (let i = 0; i < list.length; i++)
      if (list[i].age_yr > marker.age_yr) { s = i - 1; break; }
    return s;
  }

  function drawTrack() {
    if (!track || track.length < 2) return;
    // Painted segment-by-segment with the local Teff color (the same idiom as the
    // endgame track below) so the polyline itself tells the story — blue-white on
    // the upper main sequence, deepening through gold to red up the giant branch —
    // and SPLIT at the marker: the traversed past draws solid, the future dimmer,
    // so the marker's place in the whole life is legible without touching the age
    // slider. (With no marker yet, everything draws as "past" for one frame.)
    const split = splitIndex(track);
    for (let i = 1; i < track.length; i++) {
      const a = track[i - 1], b = track[i];
      const past = i <= split;
      ctx.lineWidth = past ? 1.8 : 1.1;
      ctx.globalAlpha = past ? 0.9 : 0.3;
      ctx.beginPath();
      ctx.moveTo(xOf(Math.log10(a.Teff_K)), yOf(Math.log10(a.L_lsun)));
      ctx.lineTo(xOf(Math.log10(b.Teff_K)), yOf(Math.log10(b.L_lsun)));
      ctx.strokeStyle = teffToCSS((a.Teff_K + b.Teff_K) / 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
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
    // Same past/future split as the living track: the scrubbed-through part of the
    // cooling/stripping journey draws solid, what's still ahead dimmer.
    const split = splitIndex(endgameTrack);
    for (let i = 1; i < endgameTrack.length; i++) {
      const a = endgameTrack[i - 1], b = endgameTrack[i];
      const past = i <= split;
      ctx.lineWidth = past ? 2 : 1.3;
      ctx.globalAlpha = past ? 1 : 0.35;
      ctx.beginPath();
      ctx.moveTo(xOf(Math.log10(a.Teff_K)), yOf(Math.log10(a.L_lsun)));
      ctx.lineTo(xOf(Math.log10(b.Teff_K)), yOf(Math.log10(b.L_lsun)));
      ctx.strokeStyle = teffToCSS((a.Teff_K + b.Teff_K) / 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // A faint preview of where a WD-bound star is headed once its visible life ends, drawn on
  // the LIVING HR. Drawn SOLID and faint (not dashed) to MATCH the endgame view, which keeps
  // the living track solid-faint for context: the two views share one "faint grey = the part
  // of the story you're not focused on" treatment.
  //
  // The raw WD endgame states are NOT a clean line: they meander on the cool TPAGB (an upper-
  // right tangle the living track deliberately omits), then jump blueward to a hot exposed core
  // (off the left of the living frame), then sweep DOWN across the whole diagram as the WD cools.
  // Drawing all of it scrawls a confusing diagonal over the living view — exactly the "clipped,
  // and it is unclear what it is" complaint. The only cue we want here is DIRECTIONAL: "this star
  // heads off toward the hot WD regime." So we draw a single straight leader from the AGB tip
  // (previewTrack[0], = where the living track ends) to the HOTTEST state (the post-AGB knee),
  // which runs up-left and exits the frame toward the hot corner, with a "→ white dwarf" label on
  // it. The full cooling physics lives in the dedicated WD endgame view (the gateway button), not
  // here. Clipped to the plot frame as a backstop. Set only for WD-ending stars
  // (setEndgamePreview(null) for SN/WR), so it never promises a remnant the star won't form.
  function drawPreviewEndgame() {
    if (!previewTrack || previewTrack.length < 2) return;
    const p0 = previewTrack[0];
    let hot = p0;
    for (const s of previewTrack) if (s.Teff_K > hot.Teff_K) hot = s;
    if (hot === p0) return;   // no blueward leg to point at
    const x0 = xOf(Math.log10(p0.Teff_K)), y0 = yOf(Math.log10(p0.L_lsun));
    const x1 = xOf(Math.log10(hot.Teff_K)), y1 = yOf(Math.log10(hot.L_lsun));
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.strokeStyle = "rgba(231,236,245,0.30)";
    ctx.lineWidth = 1.4;
    ctx.stroke();
    // Label on the leader, near its midpoint, clamped inside the frame so it stays legible and
    // unclipped (the hot end is usually off-frame to the left).
    const lx = Math.max(PAD_L + 4, Math.min(W - PAD - 78, (x0 + x1) / 2 - 10));
    const ly = Math.max(PAD + 12, Math.min(H - PAD - 4, (y0 + y1) / 2 - 6));
    ctx.fillStyle = "rgba(231,236,245,0.6)";
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText("→ white dwarf", lx, ly);
    ctx.restore();
  }

  // --- supernova light-curve view (linear days x / log erg/s y) -----------------------
  const xSN = (day) => PAD_L + (day / snTmax) * (W - PAD_L - PAD);
  const ySN = (logL) => H - PAD - (logL - snLlo) / (snLhi - snLlo) * (H - 2 * PAD);

  // --- thermal-pulse view (linear kyr-since-first-pulse x / surface log L y) -----------
  const xTP = (ageYr) => PAD_L + ((ageYr - pAge0) / 1e3 / pAgeMaxKyr) * (W - PAD_L - PAD);
  const yTP = (logL) => H - PAD - (logL - pLlo) / (pLhi - pLlo) * (H - 2 * PAD);

  // The thermal-pulse showcase: surface log L vs LINEAR kyr since the first pulse, over just
  // the TPAGB slice. The polyline is Teff-colored + past/future-split at the marker (the same
  // idiom as the living/endgame tracks), so the He-shell-flash sawtooth reads as a journey.
  function drawThermalPulses() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#283149";
    ctx.fillStyle = "#8a93a6";
    ctx.font = "12px system-ui, sans-serif";
    ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);

    // x gridlines: age since first pulse (kyr), a nice round step for the span.
    ctx.textAlign = "center";
    const kStep = pAgeMaxKyr <= 20 ? 5 : pAgeMaxKyr <= 60 ? 10 : pAgeMaxKyr <= 150 ? 25 :
                  pAgeMaxKyr <= 400 ? 50 : pAgeMaxKyr <= 800 ? 100 : 250;
    for (let a = 0; a <= pAgeMaxKyr + 1e-6; a += kStep) {
      const x = xTP(pAge0 + a * 1e3);
      ctx.globalAlpha = 0.3;
      ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, H - PAD); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`${Math.round(a)}`, x, H - PAD + 15);
    }
    // y gridlines: surface log L / L☉.
    ctx.textAlign = "right";
    for (const ll of genTicks(pLlo, pLhi, niceStepL(pLhi - pLlo))) {
      const y = yTP(ll);
      ctx.globalAlpha = 0.3;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(ll.toFixed(1), PAD_L - 6, y + 4);
    }
    ctx.textAlign = "center";
    ctx.fillText("kyr since TPAGB onset", W / 2, H - 6);
    ctx.save();
    ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("surface log L / L☉", 0, 0);
    ctx.restore();

    if (pulseStates && pulseStates.length > 1) {
      const split = splitIndex(pulseStates);
      for (let i = 1; i < pulseStates.length; i++) {
        const a = pulseStates[i - 1], b = pulseStates[i];
        const past = i <= split;
        ctx.lineWidth = past ? 1.8 : 1.1;
        ctx.globalAlpha = past ? 0.9 : 0.3;
        ctx.beginPath();
        ctx.moveTo(xTP(a.age_yr), yTP(Math.log10(a.L_lsun)));
        ctx.lineTo(xTP(b.age_yr), yTP(Math.log10(b.L_lsun)));
        ctx.strokeStyle = teffToCSS((a.Teff_K + b.Teff_K) / 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    if (marker) {
      const ll = Math.max(pLlo, Math.min(pLhi, Math.log10(marker.L_lsun)));
      drawMarker(xTP(Math.max(pAge0, marker.age_yr)), yTP(ll), marker.Teff_K);
    }
  }

  // Draw a {t (days), L (erg/s)} polyline on the SN axes, clipped to the frame; L≤0 or an
  // off-bottom value clamps to the floor so a fading tail runs along the axis (no gap).
  function drawSNCurve(points, stroke, width, dash) {
    if (!points || points.length < 2) return;
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();
    ctx.beginPath();
    let started = false;
    for (const p of points) {
      if (p.t > snTmax + 1e-6) break;
      const ll = p.L > 0 ? Math.log10(p.L) : snLlo;
      const x = xSN(p.t), y = ySN(Math.max(snLlo, Math.min(snLhi, ll)));
      started ? ctx.lineTo(x, y) : (ctx.moveTo(x, y), started = true);
    }
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    if (dash) ctx.setLineDash(dash);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  }

  // The SN light-curve view: bolometric L (log erg/s) vs LINEAR days. The cited observed-SN
  // overlays draw faint behind; then the model's L_total (solid) and its radioactive ⁵⁶Co
  // component L_radio (dashed — the Tier-1 line, which should lie parallel to SN 1987A's
  // measured tail); then the marker at the scrubbed time.
  function drawSupernova() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#283149";
    ctx.fillStyle = "#8a93a6";
    ctx.font = "12px system-ui, sans-serif";
    ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);

    ctx.textAlign = "center";
    for (let d = 0; d <= snTmax + 1e-6; d += 100) {
      const x = xSN(d);
      ctx.globalAlpha = 0.3;
      ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, H - PAD); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`${d}`, x, H - PAD + 15);
    }
    ctx.textAlign = "right";
    for (const logL of genTicks(snLlo, snLhi, niceStepL(snLhi - snLlo))) {
      const y = ySN(logL);
      ctx.globalAlpha = 0.3;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`1e${logL}`, PAD_L - 6, y + 4);
    }
    ctx.textAlign = "center";
    ctx.fillText("days since explosion", W / 2, H - 6);
    ctx.save();
    ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("L (erg/s)", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";

    // The observed overlays draw faint behind; their labels go in the legend (drawn last),
    // NOT on the curves — an on-curve label lands on the light-curve path and gets obscured.
    if (snObserved) {
      for (const o of snObserved) drawSNCurve(o.points, o.color, 1.6, [5, 4]);
    }

    const lc = snModel && snModel.light_curve;
    if (lc) {
      const toPts = (arr) => arr.map((L, i) => ({ t: lc.time_days[i], L }));
      drawSNCurve(toPts(lc.L_radio_erg_s), "rgba(255,210,140,0.85)", 1.5, [3, 3]);
      drawSNCurve(toPts(lc.L_total_erg_s), "#e7ecf5", 2.2, null);
    }

    // A failed direct collapse has no bright explosion — its curve is a faint floor far below
    // the observed SNe overlays, which would read as a broken plot without a banner saying so.
    if (snModel && snModel.failed_sn) {
      ctx.textAlign = "center";
      // Auto-shrink each line to fit the canvas so the long banner doesn't clip at the panel
      // edge on narrow (phone-width) viewports; centered at W/2 with a small side margin.
      const avail = W - 12;
      const fitFont = (px, weight, text) => {
        let size = px;
        ctx.font = `${weight}${size}px system-ui, sans-serif`;
        const w = ctx.measureText(text).width;
        if (w > avail) size = Math.max(9, Math.floor(size * avail / w));
        ctx.font = `${weight}${size}px system-ui, sans-serif`;
      };
      const line1 = "Direct collapse — failed supernova: almost no light emitted";
      const line2 = "the star implodes to a black hole and winks out";
      ctx.fillStyle = "#b9aaff"; fitFont(12, "600 ", line1);
      ctx.fillText(line1, W / 2, PAD + 18);
      ctx.fillStyle = "#8a93a6"; fitFont(11, "", line2);
      ctx.fillText(line2, W / 2, PAD + 34);
      ctx.textAlign = "left";
    }

    drawSNLegend(!!lc, !!(snModel && snModel.failed_sn));

    if (marker) {
      const day = (marker.age_yr ?? 0) * 365.25;
      const L = (marker.L_lsun ?? 0) * LSUN_ERG_S;
      const ll = Math.max(snLlo, Math.min(snLhi, L > 0 ? Math.log10(L) : snLlo));
      drawMarker(xSN(Math.max(0, Math.min(snTmax, day))), ySN(ll), marker.Teff_K);
    }
  }

  // The SN light-curve legend — a compact keyed box in the TOP-RIGHT (clear of the plateau,
  // which sits upper-left, and the marker, which rides the curve). It names BOTH the model's
  // two lines (L_total solid, L_radio dashed — previously unlabeled) and the cited observed
  // overlays, so nothing is a mystery line and no label sits on the light-curve path. Shifts
  // below the failed-SN banner (top-centre) when it's shown.
  function drawSNLegend(hasModel, failed) {
    const rows = [];
    if (hasModel) {
      rows.push({ label: "This star (model)", color: "#e7ecf5", dash: null, w: 2.2 });
      rows.push({ label: "⁵⁶Co tail (model)", color: "rgba(255,210,140,0.95)", dash: [3, 3], w: 1.5 });
    }
    if (snObserved) for (const o of snObserved) rows.push({ label: o.label, color: o.color, dash: [5, 4], w: 1.6 });
    if (!rows.length) return;

    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    const sw = 20, gap = 6, rowH = 15;      // swatch length, swatch→text gap, row pitch
    let tw = 0;
    for (const r of rows) tw = Math.max(tw, ctx.measureText(r.label).width);
    const boxW = 6 + sw + gap + tw + 8;
    const boxH = rows.length * rowH + 8;
    const x0 = W - PAD - boxW;
    const y0 = PAD + (failed ? 42 : 8);     // clear the two-line failed banner at PAD+18/+34

    ctx.fillStyle = "rgba(20,24,38,0.78)";  // opaque-ish backing so lines behind don't muddle it
    ctx.fillRect(x0, y0, boxW, boxH);
    ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
    ctx.strokeRect(x0, y0, boxW, boxH);

    rows.forEach((r, i) => {
      const y = y0 + 8 + i * rowH + 3;
      ctx.strokeStyle = r.color; ctx.lineWidth = r.w;
      if (r.dash) ctx.setLineDash(r.dash);
      ctx.beginPath(); ctx.moveTo(x0 + 6, y); ctx.lineTo(x0 + 6 + sw, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#cfd6e4";
      ctx.fillText(r.label, x0 + 6 + sw + gap, y + 4);
    });
  }

  // Enter / refresh the SN light-curve view. Auto-fits the y-axis (log L) to enclose the
  // model's L_total + L_radio AND the observed overlays, and the x-axis to the longest run.
  // Re-called on an M_Ni refetch (the tail rescales) — re-fit each time, like setEndgame.
  function setSupernova(model, observed) {
    snMode = true;
    snModel = model || null;
    snObserved = observed && observed.length ? observed : null;
    let lo = Infinity, hi = -Infinity, tmax = 0;
    const consider = (L, t) => {
      if (L > 0) { const v = Math.log10(L); if (v < lo) lo = v; if (v > hi) hi = v; }
      if (t > tmax) tmax = t;
    };
    const lc = snModel && snModel.light_curve;
    if (lc) for (let i = 0; i < lc.time_days.length; i++) {
      consider(lc.L_total_erg_s[i], lc.time_days[i]);
      consider(lc.L_radio_erg_s[i], lc.time_days[i]);
    }
    if (snObserved) for (const o of snObserved) for (const p of o.points) consider(p.L, p.t);
    if (!isFinite(lo) || !isFinite(hi)) { lo = 40; hi = 43; }
    lo = Math.max(lo, hi - 4);   // don't let a deep tail stretch the axis to nothing
    snLlo = Math.floor(lo - 0.2);
    snLhi = Math.ceil(hi + 0.2);
    snTmax = Math.max(100, Math.ceil(tmax / 50) * 50);
    draw();
  }

  // The marker dot with a soft radial glow in the star's own color, so the live star
  // reads as the bright "you are here" point on its like-colored track. The glow is
  // clipped to the plot frame (a marker riding an axis edge must not bleed onto the
  // tick labels); the dot itself stays unclipped, as before.
  function drawMarker(x, y, teffK) {
    const [r, g, b] = teffToRGB(teffK).map((v) => Math.round(v * 255));
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();
    const glow = ctx.createRadialGradient(x, y, 2, x, y, 20);
    glow.addColorStop(0, `rgba(${r},${g},${b},0.55)`);
    glow.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.beginPath();
    ctx.arc(x, y, 20, 0, Math.PI * 2);
    ctx.fillStyle = glow;
    ctx.fill();
    ctx.restore();
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = teffToCSS(teffK);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#e7ecf5";
    ctx.stroke();
  }

  // A small text label pinned near a marker, clamped inside the frame (flips left if it
  // would overflow the right edge). A dark 0.6-px offset makes it legible over gridlines.
  function markerLabel(x, y, text, dyOff) {
    ctx.font = "10px system-ui, -apple-system, sans-serif";
    ctx.textBaseline = "middle";
    const w = ctx.measureText(text).width;
    let tx = x + 11;
    if (tx + w > W - PAD) tx = x - 11 - w;
    const ty = Math.max(PAD + 7, Math.min(H - PAD - 7, y + dyOff));
    ctx.fillStyle = "rgba(9,11,17,0.72)";
    ctx.fillText(text, tx + 0.6, ty + 0.6);
    ctx.fillStyle = "#e7ecf5";
    ctx.fillText(text, tx, ty);
  }

  // The binary-stripped path (b) second star: the companion (accretor) marker + a dotted
  // link to the donor, drawn UNDER the donor marker so the donor (the focus) stays on top.
  // The two dots directly show the Algol reversal — the hot stripped donor is blue-left,
  // the cooler companion sits to its right (and, at low mass, ABOVE it: the "optically
  // bright companion" that outshines the sub-luminous stripped star, Götberg 2018).
  function drawCompanion() {
    const dx = xOf(Math.log10(marker.Teff_K)), dy = yOf(Math.log10(marker.L_lsun));
    const cx = xOf(Math.log10(companion.Teff_K)), cy = yOf(Math.log10(companion.L_lsun));
    ctx.save();
    ctx.beginPath();
    ctx.rect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);
    ctx.clip();
    ctx.beginPath();                       // the binary link
    ctx.setLineDash([3, 3]);
    ctx.moveTo(dx, dy); ctx.lineTo(cx, cy);
    ctx.strokeStyle = "rgba(231,236,245,0.4)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.setLineDash([]);
    const [r, g, b] = teffToRGB(companion.Teff_K).map((v) => Math.round(v * 255));
    const glow = ctx.createRadialGradient(cx, cy, 1, cx, cy, 14);
    glow.addColorStop(0, `rgba(${r},${g},${b},0.45)`);
    glow.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.beginPath(); ctx.arc(cx, cy, 14, 0, Math.PI * 2); ctx.fillStyle = glow; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = teffToCSS(companion.Teff_K); ctx.fill();
    ctx.setLineDash([2, 2]);               // dashed ring distinguishes it from the donor's solid ring
    ctx.lineWidth = 1.5; ctx.strokeStyle = "#e7ecf5"; ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
    markerLabel(dx, dy, "stripped star", -12);
    markerLabel(cx, cy, "companion", 13);
  }

  // One star's trail for the binary-track view: Teff-coloured, past/future split at
  // `splitIdx` — the same segment-by-segment idiom as `drawTrack`/`drawEndgameTrack`,
  // parameterized so both star_1 and star_2 reuse it instead of forking the logic twice.
  function drawBinaryTrail(list, splitIdx) {
    if (!list || list.length < 2) return;
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1], b = list[i];
      const past = i <= splitIdx;
      ctx.lineWidth = past ? 2 : 1.2;
      ctx.globalAlpha = past ? 0.95 : 0.32;
      ctx.beginPath();
      ctx.moveTo(xOf(Math.log10(a.Teff_K)), yOf(Math.log10(a.L_lsun)));
      ctx.lineTo(xOf(Math.log10(b.Teff_K)), yOf(Math.log10(b.L_lsun)));
      ctx.strokeStyle = teffToCSS((a.Teff_K + b.Teff_K) / 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  // The co-evolving binary view (path (b) Chunk 4b): both stars' full tracks (faint
  // future, bold past) + both live markers, fixed-labeled by identity. `binaryStar2`
  // (and hence its own index) may run shorter than `binaryStar1` after a merger
  // truncation — clamp rather than assume the two arrays stay the same length.
  function drawBinary() {
    drawAxes();
    drawIsoRadius();
    const idx2 = binaryStar2 ? Math.min(binaryIdx, binaryStar2.length - 1) : -1;
    drawBinaryTrail(binaryStar1, binaryIdx);
    if (binaryStar2) drawBinaryTrail(binaryStar2, idx2);
    if (binaryStar1 && binaryIdx >= 0 && binaryIdx < binaryStar1.length) {
      const s1 = binaryStar1[binaryIdx];
      const x = xOf(Math.log10(s1.Teff_K)), y = yOf(Math.log10(s1.L_lsun));
      drawMarker(x, y, s1.Teff_K);
      markerLabel(x, y, "donor", -12);
    }
    if (binaryStar2 && idx2 >= 0) {
      const s2 = binaryStar2[idx2];
      const x = xOf(Math.log10(s2.Teff_K)), y = yOf(Math.log10(s2.L_lsun));
      drawMarker(x, y, s2.Teff_K);
      markerLabel(x, y, "companion", 13);
    }
  }

  // Enter the co-evolving binary view: both stars' full state arrays (star_1/star_2 across
  // every step of a `/binary_track` payload). Auto-fits BOTH tracks in full — unlike
  // setEndgame's marker-relative fit, the whole movie must stay in frame since the marker
  // will visit every point on both curves as the scrub plays.
  function setBinaryTrack(star1States, star2States) {
    binaryMode = true;
    binaryStar1 = star1States && star1States.length ? star1States : null;
    // star_2 can go null after a merger (never observed on the current bake, but the
    // type allows it) — truncate the companion's trail at the first null step rather
    // than filtering nulls out, which would shift later indices out of alignment with
    // star_1's array (index i must mean "the same step" in both arrays).
    const nullAt = star2States ? star2States.findIndex((s) => !s) : 0;
    binaryStar2 = star2States && (nullAt === -1 ? star2States : star2States.slice(0, nullAt));
    if (!binaryStar2 || !binaryStar2.length) binaryStar2 = null;
    const b = fitBounds(binaryStar1, binaryStar2);
    bT0 = b.t0; bT1 = b.t1; bL0 = b.l0; bL1 = b.l1;
    gridT = genTicks(bT0, bT1, niceStepT(bT1 - bT0));
    gridL = genTicks(bL0, bL1, niceStepL(bL1 - bL0));
    draw();
  }
  // Move both markers to step `i` (a pure pick, like the WD/WR endgame scrubs — no fetch).
  function updateBinaryIndex(i) {
    binaryIdx = i;
    draw();
  }
  function clearBinaryTrack() {
    binaryMode = false;
    binaryStar1 = null; binaryStar2 = null; binaryIdx = -1;
  }

  function draw() {
    if (pulseMode) { drawThermalPulses(); return; }
    if (snMode) { drawSupernova(); return; }
    if (binaryMode) { drawBinary(); return; }
    drawAxes();
    drawIsoRadius();                  // constant-R graph paper, under everything
    if (endgameMode) {
      drawEndgameTrack();
    } else {
      drawClassBands();               // the faint O·B·A·F·G·K·M anchor, behind everything
      if (showOverlay) drawOverlay(); // behind the track, so the live star stays on top
      drawPreviewEndgame();           // ghostly "headed for the WD corner" path, clipped
      drawTrack();
    }
    if (!marker) return;
    if (endgameMode && companion) drawCompanion();   // the binary companion, under the donor
    drawMarker(xOf(Math.log10(marker.Teff_K)), yOf(Math.log10(marker.L_lsun)), marker.Teff_K);
  }

  // Recompute the living frame from the current track. Each edge keeps the fixed teaching
  // default UNLESS the RAW track data actually crosses it — then that edge extends (with a
  // margin) to enclose the overflow. So the Sun and ordinary stars get the EXACT default
  // frame + hand-tuned gridlines (a stable comparison frame); only a genuinely off-scale
  // star (≳60 M☉ over the top, ≳120 M☉ past the hot-left, the coolest dwarfs past 2500 K)
  // moves an edge, and only an expanded axis regenerates its gridlines from the live bounds.
  // The margin is added solely on overflowing edges, so within-frame padding never trips it.
  function applyLivingBounds() {
    if (!track || !track.length) {
      bT0 = LOGT_MIN; bT1 = LOGT_MAX; bL0 = LOGL_MIN; bL1 = LOGL_MAX;
      gridT = GRID_T; gridL = GRID_L; return;
    }
    let rt0 = Infinity, rt1 = -Infinity, rl0 = Infinity, rl1 = -Infinity;
    for (const s of track) {
      const lt = Math.log10(s.Teff_K), ll = Math.log10(s.L_lsun);
      if (lt < rt0) rt0 = lt; if (lt > rt1) rt1 = lt;
      if (ll < rl0) rl0 = ll; if (ll > rl1) rl1 = ll;
    }
    const PT = 0.15, PL = 0.3;   // margin past an overflowing edge (room for the marker dot)
    bT0 = rt0 < LOGT_MIN ? rt0 - PT : LOGT_MIN;
    bT1 = rt1 > LOGT_MAX ? rt1 + PT : LOGT_MAX;
    bL0 = rl0 < LOGL_MIN ? rl0 - PL : LOGL_MIN;
    bL1 = rl1 > LOGL_MAX ? rl1 + PL : LOGL_MAX;
    const tExp = bT0 < LOGT_MIN - 1e-6 || bT1 > LOGT_MAX + 1e-6;
    const lExp = bL0 < LOGL_MIN - 1e-6 || bL1 > LOGL_MAX + 1e-6;
    gridT = tExp ? genTicks(bT0, bT1, niceStepT(bT1 - bT0)) : GRID_T;
    gridL = lExp ? genTicks(bL0, bL1, niceStepL(bL1 - bL0)) : GRID_L;
  }

  function setTrack(t) {
    track = t && t.length ? t : null;
    if (!endgameMode) applyLivingBounds();   // never clobber endgame bounds
    draw();
  }
  function update(state) { marker = state; draw(); }
  function setOverlay(on) { showOverlay = !!on; draw(); }
  // The living-mode endgame preview — pass the WD cooling states, or null to clear it
  // (a star changed, or it doesn't end as a white dwarf). Drawn only in living mode.
  function setEndgamePreview(states) {
    previewTrack = states && states.length ? states : null;
    if (!endgameMode) draw();
  }

  // Enter/leave an endgame view. setEndgame(states) AUTO-FITS the axes to the endgame
  // journey — fitting the wide, mass-dependent WD-cooling / WR-stripping track plus the
  // faint living context track drawn under it, so neither clips regardless of progenitor
  // mass/[Fe/H] (the item-6 fix: no fragile fixed ceiling). Gridlines regenerate from the
  // live bounds. `kind` ("wd"/"wr") is accepted for API symmetry but no longer needed for
  // framing — auto-fit is kind-agnostic. clearEndgame() restores the living bounds.
  function setEndgame(states, _kind = "wd") {
    endgameMode = true;
    endgameTrack = states && states.length ? states : null;
    const b = fitBounds(endgameTrack, track, companion ? [companion] : null);
    bT0 = b.t0; bT1 = b.t1; bL0 = b.l0; bL1 = b.l1;
    gridT = genTicks(bT0, bT1, niceStepT(bT1 - bT0));
    gridL = genTicks(bL0, bL1, niceStepL(bL1 - bL0));
    draw();
  }
  // Binary-stripped path (b): show/hide the companion (accretor) as a second marker.
  // Pass its StellarState, or null to hide it (back to path (a), the stripped star alone).
  // Re-fits the endgame bounds to enclose the companion too — at low progenitor mass it is
  // MORE luminous than the sub-luminous stripped donor, so it can sit above the donor and
  // would otherwise clip the top of the frame.
  function setCompanion(state) {
    companion = state || null;
    if (endgameMode) {
      const b = fitBounds(endgameTrack, track, companion ? [companion] : null);
      bT0 = b.t0; bT1 = b.t1; bL0 = b.l0; bL1 = b.l1;
      gridT = genTicks(bT0, bT1, niceStepT(bT1 - bT0));
      gridL = genTicks(bL0, bL1, niceStepL(bL1 - bL0));
    }
    draw();
  }
  // Enter/refresh the thermal-pulse showcase. Fits the y-axis to the TP slice's surface log L
  // range and the x-axis to its total span (kyr since the first pulse), both scoped to the TP
  // rows ONLY — this decompression IS the feature. Re-fittable (idempotent); the marker rides
  // via the usual update(). clearThermalPulses / clearEndgame drop back out.
  function setThermalPulses(states) {
    pulseMode = true;
    pulseStates = states && states.length ? states : null;
    if (pulseStates) {
      pAge0 = pulseStates[0].age_yr;
      let lo = Infinity, hi = -Infinity, tmax = 0;
      for (const s of pulseStates) {
        const ll = Math.log10(s.L_lsun);
        if (ll < lo) lo = ll; if (ll > hi) hi = ll;
        const kyr = (s.age_yr - pAge0) / 1e3; if (kyr > tmax) tmax = kyr;
      }
      pLlo = Math.floor((lo - 0.05) * 10) / 10;
      pLhi = Math.ceil((hi + 0.05) * 10) / 10;
      pAgeMaxKyr = Math.max(1, tmax * 1.02);   // a hair of right margin so the last pulse isn't on the frame
    }
    draw();
  }
  function clearThermalPulses() { pulseMode = false; pulseStates = null; draw(); }

  function clearEndgame() {
    endgameMode = false;
    endgameTrack = null;
    companion = null;                                    // drop the binary companion marker
    snMode = false; snModel = null; snObserved = null;   // also leave the SN light-curve view
    pulseMode = false; pulseStates = null;               // ...and the thermal-pulse showcase
    clearBinaryTrack();                                   // ...and the co-evolving binary view
    applyLivingBounds();   // restore the living frame (re-fit, in case a massive star is selected)
    draw();
  }

  // Re-fit to a new display size (the responsive layout calls this when the
  // panel's width changes) and redraw from the retained track + marker.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

  return { setTrack, update, setOverlay, setEndgamePreview, setEndgame, setCompanion, setSupernova, setThermalPulses, clearThermalPulses, clearEndgame, resize, setBinaryTrack, updateBinaryIndex, clearBinaryTrack };
}
