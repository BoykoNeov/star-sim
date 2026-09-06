// The observational colour–magnitude diagram (Axis A3 of the outward quartet) — the
// observer's version of the HR diagram. Where the HR panel plots the intrinsic L vs
// Teff, this plots what a telescope measures: a colour against an absolute magnitude,
// and then shows what DISTANCE and interstellar DUST do to it.
//
// **Which diagram** is a choice, not a constant. The baked spectrum cube reaches 2.5 µm,
// so the same track can be drawn as Johnson (B−V, M_V), as Gaia (BP−RP, M_G) — the plane
// nearly every modern cluster paper uses — or as 2MASS (J−Ks, M_Ks), where interstellar
// dust is ~9× weaker and the giant branch separates cleanly. The panel holds no band
// arithmetic of its own: each locus row carries a `mag` dict from /photometry_track and
// the marker carries the absolute/apparent dicts from /photometry, so a diagram is just
// which two bands to subtract and which one to plot down the side.
//
// A pure pushed-data consumer (like roche.js / the population overlay): main.js fetches
// the intrinsic locus from /photometry_track once per (mass,[Fe/H]) and pushes it via
// setLocus(); the current-age marker's EXACT intrinsic + observed positions come from
// /photometry (setMarker). Nothing approximate is ever plotted as truth — the observed
// marker and the arrow tip are the tested-path exact values; only the faint "as observed"
// LOCUS applies the marker's reddening+distance vector uniformly (the standard de-reddening
// assumption), and it is labelled as such.
//
// Axis convention (the real observational CMD): colour increases to the RIGHT (blue left,
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

// The diagrams this panel can draw. `colour` is the pair to subtract (blue band first,
// so the colour grows to the red), `mag` the band plotted down the side. Availability is
// decided by the served payload's `bands`, never by a hardcoded assumption: on an
// optical-only cube only Johnson resolves, and the other two say so rather than vanish.
export const CMD_DIAGRAMS = [
  {
    id: "bv", name: "Johnson", colour: ["B", "V"], mag: "V",
    x: "B − V  (colour → redder)", y: "M_V  (brighter ↑)",
    colourLabel: "(B−V)", excessLabel: "E(B−V)", magLabel: "V",
  },
  {
    id: "gaia", name: "Gaia", colour: ["BP", "RP"], mag: "G",
    x: "BP − RP  (colour → redder)", y: "M_G  (brighter ↑)",
    colourLabel: "(BP−RP)", excessLabel: "E(BP−RP)", magLabel: "G",
  },
  {
    id: "2mass", name: "2MASS", colour: ["J", "Ks"], mag: "Ks",
    x: "J − Ks  (colour → redder)", y: "M_Ks  (brighter ↑)",
    colourLabel: "(J−Ks)", excessLabel: "E(J−Ks)", magLabel: "Ks",
  },
];

// The bands a diagram needs present before it can be drawn at all.
export function diagramBands(d) {
  return [...new Set([...d.colour, d.mag])];
}

export function createCMD(canvas) {
  if (!canvas) {
    return { setLocus() {}, setMarker() {}, setDiagram() {}, isAvailable() { return false; },
      clear() {}, resize() {} };
  }
  let ctx, W, H, plotW, plotH;
  ({ ctx, W, H } = fitCanvas(canvas, 460, 300));
  plotW = W - PAD_L - PAD_R;
  plotH = H - PAD_T - PAD_B;

  // locus: [{mag:{band:value}, teff}]; markers: the absolute/apparent mag dicts.
  let locus = null, bands = null;
  // Whether a /photometry_track fetch has actually RESOLVED yet. Without this, "no bands
  // known" (nothing fetched) is indistinguishable from a resolved "this cube cannot do
  // this diagram" — so the panel would flash "unavailable" during the pre-load gap even
  // though the bands are fine. We only ever show that notice once a fetch has returned.
  let locusLoaded = false;
  let mAbs = null, mApp = null;
  let diagram = CMD_DIAGRAMS[0];
  // Cached fit bounds (recomputed on setLocus / setMarker / setDiagram).
  let x0 = -0.4, x1 = 1.8, y0 = -8, y1 = 6;

  // A magnitude dict → this diagram's (colour, magnitude), or null when the dict is
  // missing a band. Returning null rather than NaN keeps every "is there a point here?"
  // test a plain null check, the way the old bv0-may-be-absent code read.
  function pointOf(mag) {
    if (!mag) return null;
    const [a, b] = diagram.colour;
    const c = mag[a], d = mag[b], m = mag[diagram.mag];
    if (c == null || d == null || m == null) return null;
    return { c: c - d, m };
  }

  // Is the selected diagram answerable from what the last fetch returned? (`bands` is the
  // list the SERVED cube could measure — see photometry.bands_within.)
  function isAvailable(which = diagram) {
    const d = typeof which === "string" ? CMD_DIAGRAMS.find((x) => x.id === which) : which;
    if (!d || !bands) return false;
    return diagramBands(d).every((b) => bands.includes(b));
  }

  // The bands this diagram needs that the served cube did not supply — what the
  // "unavailable" notice names, so it points at the missing data rather than scolding.
  function missingBands(d = diagram) {
    if (!bands) return diagramBands(d);
    return diagramBands(d).filter((b) => !bands.includes(b));
  }

  function fit() {
    const cs = [], ms = [];
    const pts = [];
    if (locus) for (const p of locus) { const q = pointOf(p.mag); if (q) pts.push(q); }
    for (const q of pts) { cs.push(q.c); ms.push(q.m); }
    const qAbs = pointOf(mAbs), qApp = pointOf(mApp);
    for (const q of [qAbs, qApp]) if (q) { cs.push(q.c); ms.push(q.m); }
    // The "as observed" locus shifts by the marker vector — include its extremes so the
    // dashed trail can't run off the frame.
    if (qAbs && qApp) {
      const dc = qApp.c - qAbs.c, dm = qApp.m - qAbs.m;
      for (const q of pts) { cs.push(q.c + dc); ms.push(q.m + dm); }
    }
    if (!ms.length) return;
    let cLo = Math.min(...cs), cHi = Math.max(...cs);
    let mLo = Math.min(...ms), mHi = Math.max(...ms);
    if (!isFinite(cLo)) { cLo = -0.4; cHi = 1.8; }
    const cPad = Math.max(0.1, (cHi - cLo) * 0.08);
    const mPad = Math.max(0.3, (mHi - mLo) * 0.06);
    x0 = cLo - cPad; x1 = cHi + cPad;
    y0 = mLo - mPad; y1 = mHi + mPad;   // y0 = brightest (top), y1 = faintest (bottom)
  }

  const xOf = (c) => PAD_L + ((c - x0) / (x1 - x0)) * plotW;
  const yOf = (m) => PAD_T + ((m - y0) / (y1 - y0)) * plotH;   // inverted: bright up

  function niceStep(span, target) {
    const raw = span / target;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
    return 10 * mag;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    const qAbs = pointOf(mAbs), qApp = pointOf(mApp);
    if (!locus && !qAbs) {
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
    ctx.fillText(diagram.x, PAD_L + plotW / 2, PAD_T + plotH + 22);
    ctx.save();
    ctx.translate(12, PAD_T + plotH / 2); ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = "middle";
    ctx.fillText(diagram.y, 0, 0);
    ctx.restore();

    // Show the "unavailable" notice only for a RESOLVED absence — and never when the
    // marker itself carries this diagram's bands, since the readout below the panel
    // prints that colour and the graph must not contradict it. Before the first locus
    // fetch resolves we just draw the axes (no flash).
    if (!isAvailable() && !qAbs) {
      if (locusLoaded) {
        ctx.fillStyle = COL_AXIS; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(`(${missingBands().join(", ")} unavailable from this spectrum grid)`,
          PAD_L + plotW / 2, PAD_T + plotH / 2);
      }
      return;
    }

    // --- the "as observed" locus (dashed): intrinsic shifted by the marker's vector ---
    let dc = 0, dm = 0, shifted = false;
    if (qAbs && qApp) {
      dc = qApp.c - qAbs.c;
      dm = qApp.m - qAbs.m;
      shifted = Math.abs(dc) > 1e-3 || Math.abs(dm) > 1e-3;
    }
    if (locus && shifted) {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = COL_APPARENT; ctx.lineWidth = 1.4; ctx.globalAlpha = 0.7;
      ctx.beginPath();
      let started = false;
      for (const p of locus) {
        const q = pointOf(p.mag);
        if (!q) continue;
        const x = xOf(q.c + dc), y = yOf(q.m + dm);
        if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.restore();
    }

    // --- the intrinsic locus (solid, Teff-coloured) ---
    if (locus) {
      ctx.lineWidth = 2.2;
      for (let i = 1; i < locus.length; i++) {
        const a = pointOf(locus[i - 1].mag), b = pointOf(locus[i].mag);
        if (!a || !b) continue;
        ctx.strokeStyle = teffToCSS(locus[i].teff);
        ctx.beginPath();
        ctx.moveTo(xOf(a.c), yOf(a.m));
        ctx.lineTo(xOf(b.c), yOf(b.m));
        ctx.stroke();
      }
    }

    // --- the reddening/distance vector arrow (intrinsic → observed) ---
    if (qAbs && qApp && shifted) {
      drawArrow(xOf(qAbs.c), yOf(qAbs.m), xOf(qApp.c), yOf(qApp.m));
    }

    // --- the markers ---
    if (qAbs) {
      const x = xOf(qAbs.c), y = yOf(qAbs.m);
      ctx.beginPath(); ctx.arc(x, y, 5, 0, 2 * Math.PI);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = "rgba(20,26,40,0.6)"; ctx.fill();
    }
    if (qApp && shifted) {
      const x = xOf(qApp.c), y = yOf(qApp.m);
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

  // main.js pushes the intrinsic locus from /photometry_track (once per mass/[Fe/H]),
  // along with the band list the served cube could actually measure.
  function setLocus(points, bandList) {
    locus = points && points.length ? points : null;
    bands = bandList && bandList.length ? [...bandList] : null;
    locusLoaded = true;   // a fetch resolved — "unavailable" may now legitimately show
    fit(); draw();
  }
  // main.js pushes the EXACT intrinsic + observed magnitude dicts from /photometry.
  // Pass observed=null (or equal to intrinsic) when there is no distance/dust shift.
  function setMarker(absolute, apparent) {
    mAbs = absolute || null;
    mApp = apparent || null;
    fit(); draw();
  }
  // Choose which colour–magnitude plane to draw. Pure reframe of the SAME pushed data —
  // no refetch, because every band already rode along in the payload.
  function setDiagram(id) {
    const found = CMD_DIAGRAMS.find((d) => d.id === id);
    if (!found || found === diagram) return;
    diagram = found;
    fit(); draw();
  }
  function clear() {
    locus = null; mAbs = null; mApp = null; bands = null; locusLoaded = false;
    draw();
  }
  function resize(cssW, cssH) {
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    plotW = W - PAD_L - PAD_R; plotH = H - PAD_T - PAD_B;
    draw();
  }

  draw();
  return { setLocus, setMarker, setDiagram, isAvailable, clear, resize };
}
