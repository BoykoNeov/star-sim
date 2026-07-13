// Habitable-zone history (Axis D2a of the outward quartet) — the TEMPORAL twin of the
// scale-bar HZ band. Where scale.js draws the habitable zone at ONE age (a band on the
// true-size axis), this plots the whole life's HZ as distance-vs-age, so the OUTWARD MARCH
// becomes legible on one static figure instead of only being animated by the age scrub.
//
// A pure pushed-data consumer (like cmd.js / roche.js): main.js maps currentTrack through
// hz.js's habitableZone() and pushes the per-row edges via setTrack(); the age slider pushes
// the current age via setNow(). No fetch, no backend, no StellarState touch — the HZ is a
// VIEW (the Axis-D rule). The physics lives entirely in hz.js (shared with the scale-bar
// band), so the two panels agree at any age BY CONSTRUCTION — same habitableZone(Teff,L) call.
//
// AXES — settled by MEASURING the real Sun track, not the plan's first guess.
//  x = age, LINEAR. The giant-branch HZ march (the ~30× outward blow-up — the payoff) happens
//    in the last ~8% of the star's LINEAR life; a LOG-age axis compresses it into the last
//    ~1.5% (measured on 1 M☉: the inner edge climbs 1.5→10 AU between log-age fraction 0.985
//    and 0.998), crushing it against the right frame — log spreads small numbers and packs
//    large ones, the opposite of what's wanted. Linear age keeps the giant cliff visible AND
//    leaves the slow main-sequence creep (and Earth's ~5 Gyr exit — the D2b lesson) spread
//    across the left. So this deliberately DEVIATES from the plan's "log yr".
//  y = distance, LOG AU. The edges span ~2 decades (0.8 → ~70 AU over a Sun's life), so log
//    is natural; a linear-AU axis would flatten the whole main sequence to a hair-line.
//
// HONEST GAPS. A row whose Teff falls outside Kopparapu's 2600–7200 K calibration range has
// no defined HZ (main.js pushes it as {oor:true}); the band BREAKS there — never an
// interpolated bridge — so an evolving star that leaves and re-enters the window reads as
// "HZ undefined here", exactly like the scale-bar band blinking off. The "now" line still
// draws through such a gap (it marks the age, not the band).

import { fitCanvas } from "./canvas.js";

const PAD_L = 50, PAD_R = 58, PAD_T = 24, PAD_B = 42;

const COL_AXIS = "#7f8aa3";
const COL_GRID = "rgba(127,138,163,0.16)";
const COL_INK = "#c9d3e6";
const COL_HZ = "#3fbf6f";        // green — the HZ band fill (matches scale.js)
const COL_HZ_EDGE = "#63d98f";   // brighter green — the HZ edge lines / label
const COL_EARTH = "#6fb0ff";     // cool blue — Earth's orbit line (the highlighted reference)
const COL_PLANET = "rgba(111,176,255,0.5)"; // fainter blue — Venus / Mars reference lines
const COL_NOW = "#ffce6b";       // warm — the "now" age marker (matches the scale-bar tint family)
const COL_CHZ_EDGE = "#eaffef";  // near-white mint — the CHZ core outline (a crisp rectangle, distinct from the migrating band's soft green)
const COL_EXIT = "#ff8a5c";      // warm orange — the measured "Earth exits the HZ" deadline marker

// The Continuously Habitable Zone (D2b): a conservative annulus thinner than this fraction of
// its own distance is treated as COLLAPSED — the brightening star's inner edge has (nearly)
// overtaken its former outer edge, and the ~1% gaps that survive are within the climate model's
// own noise, so we draw a pinch-line rather than a hairline box. Measured on real MIST tracks:
// the Sun's conservative CHZ inverts by ~1% over its full MS; a genuine annulus only survives
// for cool ≲0.4 M☉ dwarfs (which brighten little over their >100 Gyr MS).
const CHZ_COLLAPSE_FRAC = 0.04;
const EARTH_AU = 1.0;   // Earth's orbit — a FIXED Solar-System reference (the caption owns "not this star's planet")

// Solar-System orbit references (AU) — a FIXED reference, not this star's own planets (the
// caption owns that). Earth is highlighted; Venus/Mars bracket it.
const PLANETS = [
  { au: 0.7233, name: "Venus", earth: false },
  { au: 1.0,    name: "Earth", earth: true },
  { au: 1.5237, name: "Mars",  earth: false },
];

// Format an age for the axis, in a unit shared across all ticks (chosen from the max age).
function ageUnit(maxYr) {
  if (maxYr >= 1e9) return { scale: 1e9, label: "Gyr" };
  if (maxYr >= 1e6) return { scale: 1e6, label: "Myr" };
  if (maxYr >= 1e3) return { scale: 1e3, label: "kyr" };
  return { scale: 1, label: "yr" };
}

// Format an AU value compactly: "0.72", "1", "5.2", "30", "68".
function fmtAU(au) {
  if (au >= 10) return Math.round(au).toString();
  if (au >= 1) return (Math.round(au * 10) / 10).toString();
  return parseFloat(au.toPrecision(2)).toString();
}

function niceStep(span, target) {
  const raw = span / Math.max(1, target);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
  return 10 * mag;
}

// Log-decade "nice" tick values (1-2-5 mantissa) within [lo, hi] AU.
function logTicks(lo, hi) {
  const out = [];
  const kLo = Math.floor(Math.log10(lo)), kHi = Math.ceil(Math.log10(hi));
  for (let k = kLo; k <= kHi; k++) {
    for (const m of [1, 2, 5]) {
      const v = m * 10 ** k;
      if (v >= lo * 0.999 && v <= hi * 1.001) out.push(v);
    }
  }
  return out;
}

export function createHZHist(canvas) {
  if (!canvas) return { setTrack() {}, setNow() {}, clear() {}, resize() {} };
  const caption = document.getElementById("hz-history-caption");
  let ctx, W, H, plotW, plotH;
  ({ ctx, W, H } = fitCanvas(canvas, 520, 300));
  plotW = W - PAD_L - PAD_R;
  plotH = H - PAD_T - PAD_B;

  // series: [{ age, ms, recentVenus, runaway, maxGreenhouse, earlyMars } | { age, ms, oor:true }]
  let series = null, nowAge = null;
  let x0 = 0, x1 = 1, ly0 = -1, ly1 = 2;   // x in yr; ly in log10(AU)
  let unit = { scale: 1e9, label: "Gyr" };
  let anyHZ = false;
  let chz = null;   // the Continuously Habitable Zone result (D2b) — see computeCHZ()

  function fit() {
    if (!series || !series.length) return;
    const ages = series.map((p) => p.age).filter((a) => a > 0);
    x0 = 0;
    x1 = (ages.length ? Math.max(...ages) : 1) * 1.02;
    unit = ageUnit(x1);
    // y bounds: every edge of every in-range row, plus the planet reference lines so they're
    // always on-axis. Fall back to the planet lines alone if the whole track is out of range.
    let lo = Infinity, hi = -Infinity;
    anyHZ = false;
    for (const p of series) {
      if (p.oor) continue;
      anyHZ = true;
      lo = Math.min(lo, p.recentVenus, p.runaway, p.maxGreenhouse, p.earlyMars);
      hi = Math.max(hi, p.recentVenus, p.runaway, p.maxGreenhouse, p.earlyMars);
    }
    for (const pl of PLANETS) { lo = Math.min(lo, pl.au); hi = Math.max(hi, pl.au); }
    if (!isFinite(lo)) { lo = 0.5; hi = 2; }
    const pad = 0.06 * (Math.log10(hi) - Math.log10(lo) || 1);
    ly0 = Math.log10(lo) - pad;
    ly1 = Math.log10(hi) + pad;
    computeCHZ();
  }

  // The Continuously Habitable Zone (D2b): the annulus that stays inside the HZ for the star's
  // WHOLE main sequence (ZAMS→TAMS) — far narrower than the zone at any single age, because the
  // brightening star drags the zone outward under the planet. Computed as the intersection over
  // the discrete MS rows — inner = max(inner edge), outer = min(outer edge) — NOT the endpoint
  // shortcut [inner(TAMS), outer(ZAMS)], which the non-monotone Teff at the TAMS hook would make
  // subtly wrong for heavier masses. "Continuous" requires an unbroken in-range MS: if any MS row
  // falls outside Kopparapu's 2600–7200 K range the CHZ is UNDEFINED (we can't claim habitability
  // across a stretch where the HZ itself is undefined). Both a conservative (runaway→maxGreenhouse)
  // and an optimistic (recentVenus→earlyMars) annulus are computed, nested like the migrating band.
  function computeCHZ() {
    chz = null;
    if (!series || !series.length) return;
    const ms = series.filter((p) => p.ms);
    if (!ms.length) return;                                  // no main sequence in the track
    const zamsAge = ms[0].age, tamsAge = ms[ms.length - 1].age;
    if (ms.some((p) => p.oor)) { chz = { defined: false, zamsAge, tamsAge }; return; }
    const consIn = Math.max(...ms.map((p) => p.runaway));
    const consOut = Math.min(...ms.map((p) => p.maxGreenhouse));
    const optIn = Math.max(...ms.map((p) => p.recentVenus));
    const optOut = Math.min(...ms.map((p) => p.earlyMars));
    // Collapsed: the conservative annulus is drawn as a pinch-line (rather than a hairline box)
    // when its width is under a few % of its distance — inside the model's own noise. This covers
    // TWO physically distinct cases that must NOT share caption wording (a documented false-caption
    // hazard): genuinely INVERTED (inner ≥ outer — no orbit survives, e.g. the Sun) vs a thin but
    // real SLIVER (0 < width < the floor — a razor-thin band that does survive, e.g. a ≲0.2 M☉
    // dwarf). Same pinch-line render; the caption branches on consInverted.
    const consInverted = consIn >= consOut;
    const consCollapsed = consOut - consIn < CHZ_COLLAPSE_FRAC * consOut;
    // Earth-exit deadline: the age at which the conservative inner edge (runaway greenhouse)
    // sweeps OUTWARD past 1 AU — MEASURED off the track by interpolating the straddling rows,
    // never a hardcoded literature "~1 Gyr". Null when the zone never reaches 1 AU (e.g. a cool
    // dwarf whose whole zone stays sub-AU) — then there is no exit to mark.
    let exitAge = null;
    for (let i = 1; i < series.length; i++) {
      const a = series[i - 1], b = series[i];
      if (a.oor || b.oor) continue;
      if (a.runaway < EARTH_AU && b.runaway >= EARTH_AU) {
        const f = (EARTH_AU - a.runaway) / (b.runaway - a.runaway);
        exitAge = a.age + f * (b.age - a.age);
        break;
      }
    }
    chz = {
      defined: true, zamsAge, tamsAge, consIn, consOut, consCollapsed, consInverted, optIn, optOut, exitAge,
      earthInCons: EARTH_AU > consIn && EARTH_AU < consOut,
    };
  }

  const xOf = (age) => PAD_L + ((age - x0) / (x1 - x0 || 1)) * plotW;
  // bigger AU → higher up (smaller y)
  const yOf = (au) => PAD_T + (1 - (Math.log10(au) - ly0) / (ly1 - ly0 || 1)) * plotH;

  // Contiguous runs of in-range rows (so a Teff gap breaks the band, never bridges it).
  function runs() {
    const rs = [];
    let cur = null;
    for (const p of series) {
      if (p.oor) { cur = null; continue; }
      if (!cur) { cur = []; rs.push(cur); }
      cur.push(p);
    }
    return rs;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!series || !series.length) {
      ctx.fillStyle = COL_AXIS;
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("Habitable-zone history", W / 2, H / 2);
      return;
    }

    // --- grid + ticks ---
    ctx.font = "10.5px system-ui, sans-serif"; ctx.lineWidth = 1;
    // x (linear age)
    const xStep = niceStep(x1 - x0, 6);
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (let v = 0; v <= x1 + 1e-6; v += xStep) {
      const x = xOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, PAD_T + plotH); ctx.stroke();
      const lab = (v / unit.scale);
      ctx.fillStyle = COL_AXIS;
      ctx.fillText(lab >= 10 || lab === 0 ? lab.toFixed(0) : lab.toFixed(1), x, PAD_T + plotH + 6);
    }
    // y (log AU)
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (const v of logTicks(10 ** ly0, 10 ** ly1)) {
      const y = yOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(PAD_L + plotW, y); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(fmtAU(v), PAD_L - 6, y);
    }

    // --- the migrating HZ band (behind the planet lines so the references read on top) ---
    if (anyHZ) drawBands();

    // --- the Continuously Habitable Zone annulus (D2b), over the migrating band ---
    drawCHZ();

    // --- planet reference lines (dashed horizontals) ---
    for (const pl of PLANETS) {
      const y = yOf(pl.au);
      if (y < PAD_T - 0.5 || y > PAD_T + plotH + 0.5) continue;   // off-axis (e.g. very faint star)
      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = pl.earth ? COL_EARTH : COL_PLANET;
      ctx.lineWidth = pl.earth ? 1.6 : 1.1;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(PAD_L + plotW, y); ctx.stroke();
      ctx.restore();
      ctx.fillStyle = pl.earth ? COL_EARTH : COL_PLANET;
      ctx.font = pl.earth ? "10.5px system-ui, sans-serif" : "10px system-ui, sans-serif";
      ctx.textAlign = "left"; ctx.textBaseline = "middle";
      ctx.fillText(`${pl.name} ${fmtAU(pl.au)}`, PAD_L + plotW + 5, y);
    }

    // --- the measured Earth-exit deadline marker, on top of the Earth reference line ---
    drawEarthExit();

    // --- the "now" age marker (drawn even through an out-of-range gap) ---
    if (nowAge != null && nowAge >= x0 && nowAge <= x1) {
      const x = xOf(nowAge);
      ctx.strokeStyle = COL_NOW; ctx.globalAlpha = 0.9; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, PAD_T + plotH); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillStyle = COL_NOW; ctx.font = "10px system-ui, sans-serif";
      ctx.textAlign = Math.abs(x - (PAD_L + plotW)) < 30 ? "right" : "left"; ctx.textBaseline = "top";
      ctx.fillText("now", x + (ctx.textAlign === "right" ? -3 : 3), PAD_T + 2);
    }

    // --- axis frame + titles ---
    ctx.strokeStyle = COL_AXIS; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, plotW, plotH);
    ctx.fillStyle = COL_AXIS; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillText(`stellar age (${unit.label})`, PAD_L + plotW / 2, PAD_T + plotH + 24);
    ctx.save();
    ctx.translate(12, PAD_T + plotH / 2); ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = "middle";
    ctx.fillText("distance from star (AU, log)", 0, 0);
    ctx.restore();

    // --- out-of-range whole-track note (a hot star: no band anywhere) ---
    if (!anyHZ) {
      ctx.fillStyle = COL_AXIS; ctx.font = "11px system-ui, sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText("no habitable zone in the 2600–7200 K climate-model range", PAD_L + plotW / 2, PAD_T + plotH / 2);
    }

    renderCaption();
  }

  // The migrating band: for each contiguous in-range run, a fainter OPTIMISTIC fill
  // (recentVenus→earlyMars) with a stronger CONSERVATIVE fill (runaway→maxGreenhouse)
  // inside it, then the four edge polylines (conservative solid, optimistic dashed).
  function drawBands() {
    for (const run of runs()) {
      if (run.length < 2) { drawBandStub(run[0]); continue; }
      fillBand(run, "recentVenus", "earlyMars", 0.10);   // optimistic
      fillBand(run, "runaway", "maxGreenhouse", 0.20);   // conservative
    }
    // Edge lines on top of every run.
    edgeLine("runaway", true); edgeLine("maxGreenhouse", true);       // solid conservative
    edgeLine("recentVenus", false); edgeLine("earlyMars", false);     // dashed optimistic

    // Label the band, placed at the right end of the last run over the conservative mid-band.
    const rs = runs();
    const last = rs.length ? rs[rs.length - 1] : null;
    if (last && last.length) {
      const p = last[last.length - 1];
      const x = Math.min(PAD_L + plotW - 4, xOf(p.age));
      const y = yOf(Math.sqrt(p.runaway * p.maxGreenhouse));
      ctx.font = "9.5px system-ui, sans-serif"; ctx.textAlign = "right"; ctx.textBaseline = "middle";
      ctx.fillStyle = "rgba(9,12,20,0.85)"; ctx.fillText("habitable zone", x + 0.6, y + 0.6);
      ctx.fillStyle = COL_HZ_EDGE; ctx.fillText("habitable zone", x, y);
    }
  }

  function fillBand(run, innerKey, outerKey, alpha) {
    ctx.fillStyle = COL_HZ; ctx.globalAlpha = alpha;
    ctx.beginPath();
    run.forEach((p, i) => {
      const x = xOf(p.age), y = yOf(p[outerKey]);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    for (let i = run.length - 1; i >= 0; i--) {
      const p = run[i];
      ctx.lineTo(xOf(p.age), yOf(p[innerKey]));
    }
    ctx.closePath(); ctx.fill();
    ctx.globalAlpha = 1;
  }

  // A single in-range row wedged between two gaps: draw a short vertical tick spanning the
  // optimistic band so it isn't invisible.
  function drawBandStub(p) {
    if (!p) return;
    ctx.strokeStyle = COL_HZ_EDGE; ctx.globalAlpha = 0.6; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(xOf(p.age), yOf(p.recentVenus)); ctx.lineTo(xOf(p.age), yOf(p.earlyMars)); ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function edgeLine(key, solid) {
    ctx.save();
    if (!solid) { ctx.setLineDash([4, 4]); ctx.globalAlpha = 0.85; }
    ctx.strokeStyle = COL_HZ_EDGE; ctx.lineWidth = solid ? 1.5 : 1.2;
    for (const run of runs()) {
      if (run.length < 2) continue;
      ctx.beginPath();
      run.forEach((p, i) => {
        const x = xOf(p.age), y = yOf(p[key]);
        i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
      });
      ctx.stroke();
    }
    ctx.restore();
  }

  // The CHZ annulus (D2b): a constant-distance band over the ZAMS→TAMS age span — the narrow
  // core of the migrating band that stays habitable for the WHOLE main sequence. Drawn as the
  // optimistic annulus (outer, faint fill; robustly nonempty so there's always something to
  // shade) with the conservative annulus nested inside it — a crisp bordered rectangle when it
  // survives, or a dashed pinch-line at the collapse distance when the brightening star has
  // squeezed it to nothing. The rectangle's straight edges read as the FIXED always-safe region
  // against the migrating band's moving polygon (same green family, distinct geometry).
  function drawCHZ() {
    if (!chz || !chz.defined) return;
    const xa = Math.max(PAD_L, xOf(chz.zamsAge));
    const xb = Math.min(PAD_L + plotW, xOf(chz.tamsAge));
    if (xb <= xa) return;
    const fillBox = (inner, outer, alpha, bordered) => {
      const yTop = yOf(outer), yBot = yOf(inner);
      ctx.fillStyle = COL_HZ; ctx.globalAlpha = alpha;
      ctx.fillRect(xa, yTop, xb - xa, yBot - yTop);
      ctx.globalAlpha = 1;
      if (bordered) {
        ctx.strokeStyle = COL_CHZ_EDGE; ctx.lineWidth = 1.2;
        ctx.strokeRect(xa + 0.5, yTop + 0.5, xb - xa - 1, yBot - yTop - 1);
      }
    };
    // optimistic CHZ — outer, faint (only when a real annulus survives)
    if (chz.optIn < chz.optOut) fillBox(chz.optIn, chz.optOut, 0.14, false);
    // conservative CHZ — inner bordered box, or a collapsed pinch-line
    const collapseAU = Math.sqrt(chz.consIn * chz.consOut);   // geometric mean = collapse distance
    if (!chz.consCollapsed) {
      fillBox(chz.consIn, chz.consOut, 0.26, true);
    } else {
      const yc = yOf(collapseAU);
      ctx.save();
      ctx.setLineDash([5, 4]); ctx.strokeStyle = COL_CHZ_EDGE; ctx.globalAlpha = 0.9; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.moveTo(xa, yc); ctx.lineTo(xb, yc); ctx.stroke();
      ctx.restore();
    }
    // label, above the conservative box top / pinch-line. The pinch-line label distinguishes a
    // genuinely-collapsed (inverted) band from a surviving razor-thin sliver — the two share the
    // drawing but not the physics.
    const labAU = chz.consCollapsed ? collapseAU : chz.consOut;
    const labY = yOf(labAU) - 3;
    const txt = !chz.consCollapsed ? "continuously habitable"
      : chz.consInverted ? "continuously habitable (collapsed)"
      : "continuously habitable (a sliver)";
    ctx.font = "9.5px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "bottom";
    ctx.fillStyle = "rgba(9,12,20,0.85)"; ctx.fillText(txt, xa + 4.6, labY + 0.6);
    ctx.fillStyle = COL_CHZ_EDGE; ctx.fillText(txt, xa + 4, labY);
  }

  // The measured Earth-exit deadline: a marker where the conservative inner edge crosses Earth's
  // 1 AU reference line. Labeled by ABSOLUTE age — "from now" is left to the caption because it
  // would couple to the slider's now-line and confuse the static figure. Only drawn when the
  // crossing exists and both it and Earth's line are on-axis.
  function drawEarthExit() {
    if (!chz || !chz.defined || chz.exitAge == null) return;
    if (chz.exitAge < x0 || chz.exitAge > x1) return;
    const x = xOf(chz.exitAge), y = yOf(EARTH_AU);
    if (y < PAD_T || y > PAD_T + plotH) return;   // Earth line off-axis (a very faint/bright star)
    ctx.fillStyle = COL_EXIT; ctx.strokeStyle = "#0b0e16"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(x, y, 3.6, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
    const gyr = chz.exitAge / 1e9;
    const lab = `Earth exits HZ · ${gyr >= 10 ? gyr.toFixed(0) : gyr.toFixed(1)} Gyr`;
    const right = x < PAD_L + plotW - 118;
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = right ? "left" : "right"; ctx.textBaseline = "bottom";
    const tx = x + (right ? 7 : -7), ty = y - 5;
    ctx.fillStyle = "rgba(9,12,20,0.85)"; ctx.fillText(lab, tx + 0.6, ty + 0.6);
    ctx.fillStyle = COL_EXIT; ctx.fillText(lab, tx, ty);
  }

  function renderCaption() {
    if (!caption) return;
    if (!series || !series.length) { caption.textContent = ""; return; }
    caption.textContent =
      "The habitable zone's distance from the star over its whole life (age is linear; distance is " +
      "log AU). The green band is where a planet could hold liquid surface water — solid conservative " +
      "(runaway → maximum greenhouse), dashed optimistic (recent Venus → early Mars); it marches " +
      "outward as the star brightens, exploding up the giant branch in the final few percent of its " +
      "life. The blue lines are the Solar-System orbits as a fixed reference (not this star's own " +
      "planets); the amber line is the current age. Any break in the band is an age outside the " +
      "climate model's 2600–7200 K range." + chzSentence() +
      " This is a liquid-water (energy-balance) zone only — it does NOT include the star's UV/X-ray " +
      "output or flares, a separate habitability hazard.";
  }

  // The dynamic D2b sentence: describe the Continuously Habitable Zone result for THIS star and
  // the measured Earth-exit deadline. Branches on the three real render paths (nonempty box /
  // collapsed pinch-line / undefined) — all confirmed against real MIST tracks — and always
  // states the numbers are measured off the track and model/edge-definition dependent.
  function chzSentence() {
    if (!chz) return "";
    if (!chz.defined) {
      return " This star's main sequence is (partly) hotter than the model's 2600–7200 K range, so " +
        "no continuously-habitable annulus is defined for it.";
    }
    const au = (v) => fmtAU(v);
    const exit = chz.exitAge != null
      ? ` Earth's 1 AU orbit leaves the conservative zone — its inner (runaway) edge sweeping past — ` +
        `at ${(chz.exitAge / 1e9).toFixed(1)} Gyr (measured off this track; edge-definition dependent).`
      : "";
    if (chz.consCollapsed) {
      const mid = au(Math.sqrt(chz.consIn * chz.consOut));
      const lead = " The bright dashed line is the Continuously Habitable Zone — the orbits that would " +
        "stay habitable for the star's WHOLE main sequence, far narrower than the zone at any single age. ";
      if (chz.consInverted) {
        // Genuinely inverted (inner edge overtook the outer): no conservative orbit survives.
        return lead +
          `Here the conservative continuously-habitable band has COLLAPSED near ~${mid} AU: the brightening ` +
          "star's inner edge overtakes its own former outer edge, so no orbit stays conservatively " +
          `habitable the whole time. Only a thin OPTIMISTIC band (${au(chz.optIn)}–${au(chz.optOut)} AU) survives, ` +
          "and Earth at 1 AU is outside even that." + exit;
      }
      // Thin but real: a razor-thin conservative sliver DID survive — say so, don't claim collapse.
      return lead +
        `Here it has narrowed to a razor-thin sliver near ~${mid} AU (only ~${au(chz.consOut - chz.consIn)} AU ` +
        "wide — within the climate model's own uncertainty); a planet there barely stays conservatively " +
        "habitable for the whole main sequence." +
        (chz.earthInCons ? "" : " Earth at 1 AU is outside it.") + exit;
    }
    return " The bordered box is the Continuously Habitable Zone — the orbits that stay habitable for " +
      `the star's WHOLE main sequence (conservative ${au(chz.consIn)}–${au(chz.consOut)} AU, nested inside the ` +
      `fainter optimistic ${au(chz.optIn)}–${au(chz.optOut)} AU), much narrower than the zone at any single age.` +
      (chz.earthInCons ? "" : " Earth's 1 AU orbit lies outside it.") + exit;
  }

  // main.js pushes the whole-life series (one entry per track row): the four HZ edges in AU,
  // or {oor:true} for a row whose Teff is outside Kopparapu's range. Age-independent, so it's
  // pushed only on a track change (mass/[Fe/H]/vvcrit), not on an age scrub.
  function setTrack(pts) {
    series = pts && pts.length ? pts : null;
    fit(); draw();
  }
  // main.js pushes the current age (from the age slider's picked row) — moves the "now" line.
  function setNow(age) {
    nowAge = (age != null && isFinite(age)) ? age : null;
    draw();
  }
  function clear() {
    series = null; nowAge = null; chz = null;
    draw();
    if (caption) caption.textContent = "";
  }
  function resize(cssW, cssH) {
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    plotW = W - PAD_L - PAD_R; plotH = H - PAD_T - PAD_B;
    draw();
  }

  draw();
  return { setTrack, setNow, clear, resize };
}
