// The observational colour–magnitude diagram (Axis A3 of the outward quartet) — the
// observer's version of the HR diagram. Where the HR panel plots the intrinsic L vs
// Teff, this plots what a telescope measures: colour (B−V) against absolute magnitude
// M_V, and then shows what DISTANCE and interstellar DUST do to it.
//
// A pure pushed-data consumer (like roche.js / the population overlay): main.js fetches
// the intrinsic locus from /photometry_track once per (mass,[Fe/H]) and pushes it via
// setLocus(); the current-age marker's EXACT intrinsic + observed positions come from
// /photometry (setMarker). Nothing approximate is ever plotted as truth — the observed
// marker and the arrow tip are the tested-path exact values; only the faint "as observed"
// LOCUS applies the marker's reddening+distance vector uniformly (the standard de-reddening
// assumption), and it is labelled as such.
//
// Axis convention (the real observational CMD): B−V increases to the RIGHT (blue left,
// red right); magnitude increases DOWNWARD (bright/negative at the top) — so the y-axis
// is inverted, exactly as astronomers draw it.
import { fitCanvas } from "./canvas.js";
import { teffToCSS } from "./color.js";

const PAD_L = 48, PAD_R = 14, PAD_T = 26, PAD_B = 40;

const COL_AXIS = "#7f8aa3";
const COL_GRID = "rgba(127,138,163,0.16)";
const COL_INK = "#c9d3e6";
const COL_APPARENT = "rgba(255,150,90,0.85)";   // the reddened/dimmed "as observed" — dusty orange
const COL_ARROW = "rgba(255,150,90,0.95)";

export function createCMD(canvas) {
  if (!canvas) return { setLocus() {}, setMarker() {}, clear() {}, resize() {} };
  let ctx, W, H, plotW, plotH;
  ({ ctx, W, H } = fitCanvas(canvas, 460, 300));
  plotW = W - PAD_L - PAD_R;
  plotH = H - PAD_T - PAD_B;

  // locus: [{bv0, mv, teff}], intrinsic marker {bv, mv}, observed marker {bv, mv}.
  let locus = null, hasBv = false;
  // Whether a /photometry_track fetch has actually RESOLVED yet. Without this, the initial
  // `hasBv=false` (nothing fetched) is indistinguishable from a resolved "grid has no B/V" — so
  // the panel would flash "unavailable" during the pre-load gap even though B/V are fine. We only
  // ever show that notice once a fetch has returned and genuinely lacks B/V (and no marker colour).
  let locusLoaded = false;
  let mInt = null, mObs = null;
  // Cached fit bounds (recomputed on setLocus / setMarker).
  let x0 = -0.4, x1 = 1.8, y0 = -8, y1 = 6;

  function fit() {
    const bvs = [], mvs = [];
    if (locus) for (const p of locus) { if (p.bv0 != null) bvs.push(p.bv0); mvs.push(p.mv); }
    for (const m of [mInt, mObs]) if (m) { if (m.bv != null) bvs.push(m.bv); mvs.push(m.mv); }
    // The "as observed" locus shifts by the marker vector — include its extremes so the
    // dashed trail can't run off the frame.
    if (locus && mInt && mObs) {
      const dbv = (mObs.bv ?? 0) - (mInt.bv ?? 0);
      const dmv = mObs.mv - mInt.mv;
      for (const p of locus) { if (p.bv0 != null) bvs.push(p.bv0 + dbv); mvs.push(p.mv + dmv); }
    }
    if (!mvs.length) return;
    let bvLo = Math.min(...bvs), bvHi = Math.max(...bvs);
    let mvLo = Math.min(...mvs), mvHi = Math.max(...mvs);
    if (!isFinite(bvLo)) { bvLo = -0.4; bvHi = 1.8; }
    const bvPad = Math.max(0.1, (bvHi - bvLo) * 0.08);
    const mvPad = Math.max(0.3, (mvHi - mvLo) * 0.06);
    x0 = bvLo - bvPad; x1 = bvHi + bvPad;
    y0 = mvLo - mvPad; y1 = mvHi + mvPad;   // y0 = brightest (top), y1 = faintest (bottom)
  }

  const xOf = (bv) => PAD_L + ((bv - x0) / (x1 - x0)) * plotW;
  const yOf = (mv) => PAD_T + ((mv - y0) / (y1 - y0)) * plotH;   // inverted: bright up

  function niceStep(span, target) {
    const raw = span / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
    return 10 * mag;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!locus && !mInt) {
      ctx.fillStyle = COL_AXIS;
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Observational colour–magnitude diagram", W / 2, H / 2);
      return;
    }

    // --- grid + ticks ---
    ctx.font = "10.5px system-ui, sans-serif";
    ctx.lineWidth = 1;
    const xStep = niceStep(x1 - x0, 6);
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (let v = Math.ceil(x0 / xStep) * xStep; v <= x1 + 1e-9; v += xStep) {
      const x = xOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, PAD_T + plotH); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(v.toFixed(xStep < 1 ? 1 : 0), x, PAD_T + plotH + 6);
    }
    const yStep = niceStep(y1 - y0, 6);
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (let v = Math.ceil(y0 / yStep) * yStep; v <= y1 + 1e-9; v += yStep) {
      const y = yOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(PAD_L + plotW, y); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(v.toFixed(0), PAD_L - 6, y);
    }

    // --- axis frame + titles ---
    ctx.strokeStyle = COL_AXIS; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, plotW, plotH);
    ctx.fillStyle = COL_AXIS; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillText("B − V  (colour → redder)", PAD_L + plotW / 2, PAD_T + plotH + 22);
    ctx.save();
    ctx.translate(12, PAD_T + plotH / 2); ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = "middle";
    ctx.fillText("M_V  (brighter ↑)", 0, 0);
    ctx.restore();

    // Show the "unavailable" notice only for a RESOLVED absence of B/V — and never when a marker
    // carries a real (B−V), since the readout below the panel prints that colour and the graph must
    // not contradict it. Before the first locus fetch resolves we just draw the axes (no flash).
    const markerHasBv = !!(mInt && mInt.bv != null);
    if (!hasBv && !markerHasBv) {
      if (locusLoaded) {
        ctx.fillStyle = COL_AXIS; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText("(B and V bands unavailable for this grid)", PAD_L + plotW / 2, PAD_T + plotH / 2);
      }
      return;
    }

    // --- the "as observed" locus (dashed): intrinsic shifted by the marker's vector ---
    let dbv = 0, dmv = 0, shifted = false;
    if (mInt && mObs) {
      dbv = (mObs.bv ?? 0) - (mInt.bv ?? 0);
      dmv = mObs.mv - mInt.mv;
      shifted = Math.abs(dbv) > 1e-3 || Math.abs(dmv) > 1e-3;
    }
    if (locus && shifted) {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = COL_APPARENT; ctx.lineWidth = 1.4; ctx.globalAlpha = 0.7;
      ctx.beginPath();
      let started = false;
      for (const p of locus) {
        if (p.bv0 == null) continue;
        const x = xOf(p.bv0 + dbv), y = yOf(p.mv + dmv);
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    }

    // --- the intrinsic locus (solid, Teff-coloured) ---
    if (locus) {
      ctx.lineWidth = 2.2;
      for (let i = 1; i < locus.length; i++) {
        const a = locus[i - 1], b = locus[i];
        if (a.bv0 == null || b.bv0 == null) continue;
        ctx.strokeStyle = teffToCSS(b.teff);
        ctx.beginPath();
        ctx.moveTo(xOf(a.bv0), yOf(a.mv));
        ctx.lineTo(xOf(b.bv0), yOf(b.mv));
        ctx.stroke();
      }
    }

    // --- the reddening/distance vector arrow (intrinsic → observed) ---
    if (mInt && mObs && shifted) {
      drawArrow(xOf(mInt.bv), yOf(mInt.mv), xOf(mObs.bv), yOf(mObs.mv));
    }

    // --- the markers ---
    if (mInt) {
      const x = xOf(mInt.bv), y = yOf(mInt.mv);
      ctx.beginPath(); ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = "rgba(20,26,40,0.6)"; ctx.fill();
    }
    if (mObs && shifted) {
      const x = xOf(mObs.bv), y = yOf(mObs.mv);
      ctx.beginPath(); ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.fillStyle = COL_APPARENT; ctx.fill();
      ctx.strokeStyle = "rgba(0,0,0,0.4)"; ctx.lineWidth = 1; ctx.stroke();
    }

    // --- legend ---
    ctx.font = "10.5px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    let lx = PAD_L + 8, ly = PAD_T + 12;
    ctx.strokeStyle = "#fff"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(lx + 4, ly, 4, 0, 2 * Math.PI); ctx.stroke();
    ctx.fillStyle = COL_INK; ctx.fillText("intrinsic (this star, absolute)", lx + 14, ly);
    if (shifted) {
      ly += 15;
      ctx.fillStyle = COL_APPARENT;
      ctx.beginPath(); ctx.arc(lx + 4, ly, 4, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = COL_INK; ctx.fillText("as observed (distance + dust)", lx + 14, ly);
    }
  }

  function drawArrow(x1p, y1p, x2p, y2p) {
    ctx.strokeStyle = COL_ARROW; ctx.fillStyle = COL_ARROW; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(x1p, y1p); ctx.lineTo(x2p, y2p); ctx.stroke();
    const ang = Math.atan2(y2p - y1p, x2p - x1p);
    const h = 7;
    ctx.beginPath();
    ctx.moveTo(x2p, y2p);
    ctx.lineTo(x2p - h * Math.cos(ang - 0.4), y2p - h * Math.sin(ang - 0.4));
    ctx.lineTo(x2p - h * Math.cos(ang + 0.4), y2p - h * Math.sin(ang + 0.4));
    ctx.closePath(); ctx.fill();
  }

  // main.js pushes the intrinsic locus from /photometry_track (once per mass/[Fe/H]).
  function setLocus(points, hasBvFlag) {
    locus = points && points.length ? points : null;
    hasBv = !!hasBvFlag;
    locusLoaded = true;   // a fetch resolved — "unavailable" may now legitimately show if !hasBv
    fit(); draw();
  }
  // main.js pushes the EXACT intrinsic + observed marker positions from /photometry.
  // Pass observed=null (or equal to intrinsic) when there is no distance/dust shift.
  function setMarker(intrinsic, observed) {
    mInt = intrinsic || null;
    mObs = observed || null;
    fit(); draw();
  }
  function clear() {
    locus = null; mInt = null; mObs = null; hasBv = false; locusLoaded = false;
    draw();
  }
  function resize(cssW, cssH) {
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    plotW = W - PAD_L - PAD_R; plotH = H - PAD_T - PAD_B;
    draw();
  }

  draw();
  return { setLocus, setMarker, clear, resize };
}
