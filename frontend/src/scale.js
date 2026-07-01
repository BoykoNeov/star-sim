// True-size scale bar — "how big is THIS star, really?"
//
// The 3D star above it is LOG-COMPRESSED on purpose (star.js displayRadius): a red
// dwarf and a red supergiant render at almost the same on-screen size so both stay
// visible in one frame. That makes the 3D view deliberately NOT to scale — so a
// "N px = 1 R☉" ruler drawn against the rendered star would be a lie. This strip is
// the honest companion: it plots the star's TRUE radius on a single LOGARITHMIC
// length axis (solar radii) against fixed solar-system landmarks — the sizes of
// Earth, Jupiter and the Sun, and the ORBITS of the inner planets. The orbits are
// the payoff: a giant's radius isn't measured in Suns but in planetary orbits — an
// early-AGB giant's surface, placed at the Sun, would reach past Mercury toward Mars.
//
// A SIBLING to the §3 spine, like sed.js: it reads ONE number off the marker (the
// radius R_rsun) and redraws — no fetch, no backend. The "this star" marker is tinted
// with teffToCSS(Teff) so it always matches the 3D star and the HR dot. update(state)
// / resize(w,h) mirror the other 2D plot modules (fitCanvas + retained state).

import { fitCanvas } from "./canvas.js";
import { teffToCSS } from "./color.js";

const PAD_L = 14, PAD_R = 14;

// Axis: log10 of length in R_sun. From just below Earth's radius (~0.009) to just
// above Jupiter's orbit (~1119) — ~5.5 decades that bracket every star in the exposed
// window (M-dwarf ~0.1 R☉ → EAGB giant a few hundred R☉) and every landmark below.
const R_MIN = 0.004, R_MAX = 1500;
const LOG_LO = Math.log10(R_MIN), LOG_HI = Math.log10(R_MAX);

const RSUN_PER_AU = 215.032;   // 1 AU in solar radii

// Earth's and Jupiter's radii in R_sun — the small-end size references.
const EARTH_R = 0.009158, JUP_R = 0.10045;

// Body SIZES (radii), in R_sun — drawn as filled dots, labelled BELOW the axis.
const BODIES = [
  { r: EARTH_R, name: "Earth" },
  { r: JUP_R,   name: "Jupiter" },
  { r: 1.0,     name: "Sun" },
];

// Planet ORBITS (semi-major axis), in R_sun — drawn as open rings, labelled ABOVE.
// This is the "vastly different sizes of stars" reference: a giant is as wide as a
// planet's orbit.
const ORBITS = [
  { au: 0.3871, name: "Mercury" },
  { au: 0.7233, name: "Venus" },
  { au: 1.0,    name: "Earth" },
  { au: 1.5237, name: "Mars" },
  { au: 5.2026, name: "Jupiter" },
].map((o) => ({ r: o.au * RSUN_PER_AU, name: o.name }));

// SN-mode orbit landmarks — a supernova's expanding fireball reaches AU scale (hundreds of
// AU within months), FAR past Jupiter's orbit, so the normal strip pins its marker to the
// right edge and reads as broken. SN mode widens the axis and swaps in the OUTER solar
// system (Saturn, Neptune) so "past Neptune's orbit" is SHOWN, not just claimed. A curated
// 5 (Venus/Mars/Uranus dropped) so the inner cluster doesn't crush on the widened log axis.
const ORBITS_SN = [
  { au: 0.3871, name: "Mercury" },
  { au: 1.0,    name: "Earth" },
  { au: 5.2026, name: "Jupiter" },
  { au: 9.5388, name: "Saturn" },
  { au: 30.07,  name: "Neptune" },
].map((o) => ({ r: o.au * RSUN_PER_AU, name: o.name }));
const MERCURY_R = ORBITS_SN[0].r;                      // ~83 R☉ — the inner-orbit anchor
const NEPTUNE_R = ORBITS_SN[ORBITS_SN.length - 1].r;   // ~6466 R☉ — the outer-planet edge

const COL_GRID = "#283149";
const COL_LABEL = "#8a93a6";
const COL_BODY = "#ffce6b";    // warm — physical bodies
const COL_ORBIT = "#6fb0ff";   // cool blue — orbits
const COL_PANEL = "#141826";   // --panel (pill background)
const COL_INK = "#e7ecf5";     // --ink

// Format an R_sun value compactly: "0.0092", "0.2", "1", "154", "1119".
function fmtRsun(v) {
  if (v >= 10) return Math.round(v).toString();
  if (v >= 1) return (Math.round(v * 10) / 10).toString();
  if (v >= 0.001) return parseFloat(v.toPrecision(2)).toString();
  return v.toExponential(1);
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export function createScale(canvas) {
  if (!canvas) return { update() {}, resize() {} };
  const caption = document.getElementById("scale-caption");
  // W/H/plotW are `let` so resize() can re-fit to a new display width; xOf captures
  // plotW/W so it tracks the new size on the next draw().
  let ctx, W, H, plotW;
  ({ ctx, W, H } = fitCanvas(canvas, 480, 150));
  plotW = W - PAD_L - PAD_R;

  let R = null, css = "#ffffff";
  // SN mode is re-derived from opts on EVERY update() (see update): absence auto-reverts to
  // the normal axis, so returning to a living star needs no manual reset (no stranded SN
  // bounds — the state-leak trap). `logLo`/`logHi` are the ACTIVE axis bounds; SN widens
  // them to fit the AU-scale fireball, the normal star uses the fixed LOG_LO/LOG_HI.
  let sn = false, snFailed = false;
  let logLo = LOG_LO, logHi = LOG_HI;

  // log position, clamped to the plot so an off-axis star still pins to an edge.
  const xOf = (r) => {
    const f = (Math.log10(r) - logLo) / (logHi - logLo);
    return PAD_L + Math.max(0, Math.min(1, f)) * plotW;
  };

  function update(state, opts) {
    if (!state || state.R_rsun == null) return;
    R = state.R_rsun;
    css = teffToCSS(state.Teff_K);
    sn = !!(opts && opts.endgame === "sn");
    snFailed = !!(opts && opts.failed);
    if (sn) {
      // Fit the axis to the model's PEAK fireball radius (passed once per model via
      // axisMaxRsun) so the marker rides the strip as it expands instead of pinning; keep
      // the outer orbits on-scale (hiR clears Neptune) so the "past Neptune" reach is shown.
      // loR anchors the inner solar system at the left edge.
      const maxR = (opts && opts.axisMaxRsun) || R;
      logLo = Math.log10(MERCURY_R / 2);
      logHi = Math.log10(Math.max(maxR, NEPTUNE_R) * 1.25);
    } else {
      logLo = LOG_LO;
      logHi = LOG_HI;
    }
    draw();
    renderCaption();
  }

  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    plotW = W - PAD_L - PAD_R;
    draw();
  }

  // Vertical layout (logical px). axisY and the landmark bands are fixed; the bottom
  // value/title rows are pinned to H so they survive a height change.
  const ORBIT_TOP = 52, AXIS_Y = 84, BODY_BOT = 98;

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (R == null) return;
    const xs = xOf(R);

    // "Reach" tint: everything LEFT of the marker is smaller than this star.
    ctx.fillStyle = css; ctx.globalAlpha = 0.10;
    ctx.fillRect(PAD_L, ORBIT_TOP, xs - PAD_L, BODY_BOT - ORBIT_TOP);
    ctx.globalAlpha = 1;

    // Decade gridlines + value labels.
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "center";
    for (const v of valueTicks()) {
      const x = xOf(v);
      ctx.strokeStyle = COL_GRID; ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, ORBIT_TOP); ctx.lineTo(x, BODY_BOT); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = COL_LABEL;
      ctx.fillText(fmtRsun(v), x, H - 18);
    }

    // The axis line.
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(PAD_L, AXIS_Y); ctx.lineTo(W - PAD_R, AXIS_Y); ctx.stroke();

    drawOrbits();
    if (!sn) drawBodies();   // at AU scale a body's RADIUS (even the Sun's) is an invisible dot
    drawMarker(xs);

    // Axis title.
    ctx.fillStyle = COL_LABEL; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(sn
      ? "the expanding fireball — radius in R☉ (log); planet orbits mark the scale"
      : "true size — radius in solar radii (R☉), log scale", W / 2, H - 4);
    ctx.textAlign = "left";
  }

  // Decade value labels: every power of 10 inside the current axis span, so the SN-widened
  // axis auto-adds 1e4/1e5 and the normal axis stays 0.01…1000 (the old static VALUE_TICKS).
  function valueTicks() {
    const out = [];
    for (let k = Math.ceil(logLo); k <= Math.floor(logHi); k++) out.push(10 ** k);
    return out;
  }

  // Orbits ABOVE the axis: a faint "planet orbits" bracket over the cluster, open
  // rings on the axis, and staggered (2-row) collision-skipped labels.
  function drawOrbits() {
    const orbits = sn ? ORBITS_SN : ORBITS;
    const xl = xOf(orbits[0].r), xr = xOf(orbits[orbits.length - 1].r);
    // Bracket (the SED "detailed spectrum" idiom): groups the cluster AND tells the
    // reader these are orbits — disambiguating "Earth" (orbit, 215 R☉) above from
    // "Earth" (body, 0.009 R☉) below.
    ctx.strokeStyle = COL_ORBIT; ctx.globalAlpha = 0.55; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xl, 18); ctx.lineTo(xl, 14); ctx.lineTo(xr, 14); ctx.lineTo(xr, 18);
    ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillStyle = COL_ORBIT; ctx.font = "9.5px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("planet orbits", (xl + xr) / 2, 11);

    ctx.font = "10px system-ui, sans-serif";
    const rowRight = [-1e9, -1e9];      // last label's right edge, per stagger row
    orbits.forEach((o, i) => {
      const x = xOf(o.r);
      ctx.strokeStyle = COL_ORBIT; ctx.globalAlpha = 0.85; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, AXIS_Y); ctx.lineTo(x, ORBIT_TOP + 3); ctx.stroke();
      ctx.beginPath(); ctx.arc(x, ORBIT_TOP, 3.2, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = 1;
      const row = i % 2;                // 0 -> upper, 1 -> lower
      const ly = row === 0 ? 30 : 44;
      const w = ctx.measureText(o.name).width;
      if (x - w / 2 > rowRight[row] + 5) {
        ctx.fillStyle = COL_ORBIT; ctx.textAlign = "center";
        ctx.fillText(o.name, x, ly);
        rowRight[row] = x + w / 2;
      }
    });
  }

  // Bodies BELOW the axis: filled dots + a single row of collision-skipped labels.
  function drawBodies() {
    ctx.font = "10px system-ui, sans-serif";
    let lastRight = -1e9;
    for (const b of BODIES) {
      const x = xOf(b.r);
      ctx.strokeStyle = COL_BODY; ctx.globalAlpha = 0.85; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, AXIS_Y); ctx.lineTo(x, BODY_BOT - 3); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = COL_BODY;
      ctx.beginPath(); ctx.arc(x, BODY_BOT, 3, 0, Math.PI * 2); ctx.fill();
      const w = ctx.measureText(b.name).width;
      if (x - w / 2 > lastRight + 5) {
        ctx.textAlign = "center";
        ctx.fillText(b.name, x, BODY_BOT + 14);
        lastRight = x + w / 2;
      }
    }
  }

  // The "you are here" marker: a tinted vertical line through the strip + a readout
  // pill (clamped inside the canvas) naming the star's true radius.
  function drawMarker(x) {
    ctx.strokeStyle = css; ctx.globalAlpha = 0.95; ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.moveTo(x, ORBIT_TOP - 2); ctx.lineTo(x, BODY_BOT + 2); ctx.stroke();
    ctx.globalAlpha = 1;

    const txt = sn
      ? (snFailed
          ? `supergiant · ${fmtRsun(R)} R☉`
          : `fireball · ${fmtAU(R / RSUN_PER_AU)} AU`)
      : `this star · ${fmtRsun(R)} R☉`;
    ctx.font = "11px system-ui, sans-serif";
    const tw = ctx.measureText(txt).width;
    const pad = 6, ph = 18, pw = tw + 2 * pad;
    let px = x - pw / 2;
    px = Math.max(2, Math.min(W - pw - 2, px));   // keep the pill on-canvas
    const py = AXIS_Y - ph / 2;
    ctx.fillStyle = COL_PANEL;
    roundRect(ctx, px, py, pw, ph, 5); ctx.fill();
    ctx.strokeStyle = css; ctx.lineWidth = 1.2; ctx.stroke();
    ctx.fillStyle = COL_INK; ctx.textAlign = "left";
    ctx.fillText(txt, px + pad, AXIS_Y + 4);
  }

  // The "what does this size mean" caption: an honest sentence comparing the star's
  // radius to the Sun and the planetary orbits (the precise figures the on-canvas
  // labels can't all fit).
  function renderCaption() {
    if (!caption || R == null) return;
    caption.textContent = sn ? describeSN(R, snFailed) : describe(R);
  }

  // Format an AU value compactly: "0.84", "5.2", "30", "837".
  function fmtAU(au) {
    if (au >= 10) return Math.round(au).toString();
    if (au >= 1) return (Math.round(au * 10) / 10).toString();
    return parseFloat(au.toPrecision(2)).toString();
  }

  // The SN caption: the honest "expanding fireball" framing (NOT the "this giant" star line —
  // an SN photosphere is not a star, and it swells FAR past Jupiter's orbit, out to hundreds
  // of AU). Given in AU + the outer-planet orbit it has reached. A FAILED SN does not expand
  // (it implodes at R₀), so its caption says so instead of inventing a fireball.
  function describeSN(r, failed) {
    const au = r / RSUN_PER_AU;
    const sz = `${fmtRsun(r)} R☉ ≈ ${fmtAU(au)} AU`;
    if (failed) {
      return `This failing supergiant (${sz}) does not explode outward — it implodes. It ` +
        `stays roughly the size of a red supergiant and simply fades from view as the core ` +
        `collapses to a black hole.`;
    }
    const engulfed = ORBITS_SN.filter((o) => r >= o.r);
    const beyond = ORBITS_SN.find((o) => r < o.r);
    let reach;
    if (!engulfed.length) {
      reach = "already larger than the inner planets' orbits";
    } else {
      const outer = engulfed[engulfed.length - 1].name;
      reach = beyond
        ? `already engulfing ${outer}'s orbit and reaching toward ${beyond.name}'s ` +
          `(${fmtAU(beyond.r / RSUN_PER_AU)} AU)`
        : `already past ${outer}'s orbit — out beyond the entire planetary system`;
    }
    return `The expanding fireball is now ${sz} across — ${reach}. The ejecta race outward ` +
      `at thousands of km/s, swelling past the planets within months.`;
  }

  function describe(r) {
    const sz = `${fmtRsun(r)} R☉`;
    const engulfed = ORBITS.filter((o) => r >= o.r);
    const beyond = ORBITS.find((o) => r < o.r);
    if (engulfed.length) {
      const names = engulfed.map((o) => o.name);
      const list = names.length === 1
        ? `${names[0]}'s orbit`
        : names.slice(0, -1).join(", ") + ` and ${names[names.length - 1]}'s orbits`;
      const reach = beyond
        ? `, reaching out toward ${beyond.name}'s orbit (${fmtRsun(beyond.r)} R☉)`
        : `, swelling past Jupiter's orbit`;
      return `This giant (${sz}) is so vast that, placed where the Sun is, its ` +
        `surface would swallow ${list}${reach}.`;
    }
    if (r > 1.2) {
      return `This star (${sz}) is ${fmtRsun(r)}× the Sun's radius — bigger than the ` +
        `Sun, but its surface would still sit well inside Mercury's orbit ` +
        `(${fmtRsun(ORBITS[0].r)} R☉).`;
    }
    if (r >= 0.85) {
      return `This star (${sz}) is about the size of the Sun. For scale, Jupiter is ` +
        `${fmtRsun(JUP_R)} R☉ and Earth ${fmtRsun(EARTH_R)} R☉; the planets orbit at ` +
        `83–1119 R☉.`;
    }
    const pct = Math.round(r * 100);
    const vsJup = r / JUP_R;
    return `This star (${sz}) is about ${pct}% the Sun's radius` +
      (vsJup >= 1.3
        ? ` — roughly ${vsJup.toFixed(1)}× the size of Jupiter (${fmtRsun(JUP_R)} R☉).`
        : ` — not much larger than Jupiter (${fmtRsun(JUP_R)} R☉); Earth is ${fmtRsun(EARTH_R)} R☉.`);
  }

  return { update, resize };
}
