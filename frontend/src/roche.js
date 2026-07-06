// Roche-lobe / mass-transfer geometry panel (binary path (b) Chunk 3).
//
// A genuinely new TWO-STAR render: the orbital-plane cross-section at the moment of
// Case-B mass transfer — the two Roche lobes meeting at L1, the donor filling its lobe
// and streaming through L1 onto the lighter companion. It is the CAUSAL story behind
// the stripped star the other panels show, and it is a DIFFERENT evolutionary snapshot:
//
//   * AT RLOF (this panel): the donor (M1) is still the MORE massive star — it fills its
//     (bigger) lobe and overflows. It is a bloated, cool, post-main-sequence GIANT, NOT
//     the hot compact stripped product; we have no RLOF-moment temperature for it (the
//     Götberg table is the stripped state), so it is drawn with a neutral schematic giant
//     tint, never the stripped Teff colour.
//   * POST-STRIP (every other panel): the donor is the LIGHTER object and the mass ratio
//     has reversed (mass_ratio_final > 1). The caption owns this cross-panel reversal — it
//     is the same convention-mismatch class that bit path (b) Chunk 1.
//
// The GEOMETRY is honest (roche_geometry in binary.py): the lobe shape depends only on q
// (=0.8, known), the separation comes from Kepler on the node's real (M1, M2, P_init).
// The companion sphere is drawn at its REAL modelled radius (from /binary_pair) — compact,
// deep inside its own lobe (only the donor overflows). The only illustrative element is
// the stream (a schematic Coriolis-deflected arc), labelled as such.
//
// A pushed-data consumer (main.js hands it the /binary_pair `roche` block + companion
// state); it never fetches. Shown only in stripped-mode with "Show companion" on.

import { fitCanvas } from "./canvas.js";
import { teffToCSS } from "./color.js";

const PAD = 46;   // room for the L-point / star labels around the figure

// The donor at RLOF is a bloated post-MS giant of unknown (un-modelled) temperature, so
// it gets a neutral WARM schematic tint — evocative of a cool, extended giant, NOT a Teff
// claim (the caption says so). The companion is drawn in its real modelled colour.
const DONOR_FILL = "rgba(226,150,96,0.30)";
const DONOR_STROKE = "#e29a60";
const COMP_LOBE_STROKE = "#7f9bd0";
const COMP_LOBE_FILL = "rgba(127,155,208,0.10)";
const STREAM_COL = "#ffcf8c";
const LPT_COL = "#c3ccdd";
const AXIS_COL = "#2b3550";

export function createRoche() {
  const canvas = document.getElementById("roche-canvas");
  const caption = document.getElementById("roche-caption");
  if (!canvas) return { draw() {}, resize() {}, clear() {} };

  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, 380, 300));

  let geo = null;        // last /binary_pair `roche` block
  let companion = null;  // last companion StellarState (for size + colour)

  // World-space (units of separation a) → canvas, EQUAL aspect on both axes (this is a
  // physical geometry — it must not be stretched). The frame spans L3 (behind the donor)
  // to L2 (behind the companion) in x, and the taller lobe in y, with a little margin.
  function transform() {
    const xLo = Math.min(geo.l3_x, -0.1) - 0.12;
    const xHi = Math.max(geo.l2_x, 1.1) + 0.12;
    let yMax = 0.1;
    for (const p of geo.donor_lobe) yMax = Math.max(yMax, Math.abs(p[1]));
    for (const p of geo.companion_lobe) yMax = Math.max(yMax, Math.abs(p[1]));
    yMax *= 1.18;
    const spanX = xHi - xLo, spanY = 2 * yMax;
    const s = Math.min((W - 2 * PAD) / spanX, (H - 2 * PAD) / spanY);
    const cx = (xLo + xHi) / 2, cy = 0;
    const ox = W / 2 - s * cx, oy = H / 2 + s * cy;   // y flips (screen y grows downward)
    return {
      s,
      X: (x) => ox + s * x,
      Y: (y) => oy - s * y,
    };
  }

  function poly(pts, T) {
    ctx.beginPath();
    pts.forEach(([x, y], i) => {
      const px = T.X(x), py = T.Y(y);
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!geo) return;
    const T = transform();

    // Orbital axis (the line of centres) + centre of mass — faint reference.
    ctx.strokeStyle = AXIS_COL; ctx.lineWidth = 1; ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.moveTo(T.X(geo.l3_x - 0.05), T.Y(0)); ctx.lineTo(T.X(geo.l2_x + 0.05), T.Y(0)); ctx.stroke();
    ctx.setLineDash([]);

    // Companion Roche lobe (faint — it is NOT filled; the companion sits well inside it).
    poly(geo.companion_lobe, T);
    ctx.fillStyle = COMP_LOBE_FILL; ctx.fill();
    ctx.strokeStyle = COMP_LOBE_STROKE; ctx.lineWidth = 1.5; ctx.stroke();

    // Donor Roche lobe — FILLED (the donor overflows it). The bloated-giant schematic tint.
    poly(geo.donor_lobe, T);
    ctx.fillStyle = DONOR_FILL; ctx.fill();
    ctx.strokeStyle = DONOR_STROKE; ctx.lineWidth = 2; ctx.stroke();

    // The mass-transfer stream L1 → companion (schematic). A glowing warm curve with an
    // arrowhead, drawn over the lobes.
    if (geo.stream && geo.stream.length > 1) {
      ctx.strokeStyle = STREAM_COL; ctx.lineWidth = 2.4; ctx.globalAlpha = 0.9;
      poly(geo.stream, T); ctx.stroke();
      ctx.globalAlpha = 1;
      // arrowhead at the companion end
      const a = geo.stream[geo.stream.length - 2], b = geo.stream[geo.stream.length - 1];
      const ang = Math.atan2(T.Y(b[1]) - T.Y(a[1]), T.X(b[0]) - T.X(a[0]));
      const hx = T.X(b[0]), hy = T.Y(b[1]);
      ctx.fillStyle = STREAM_COL;
      ctx.beginPath();
      ctx.moveTo(hx, hy);
      ctx.lineTo(hx - 8 * Math.cos(ang - 0.4), hy - 8 * Math.sin(ang - 0.4));
      ctx.lineTo(hx - 8 * Math.cos(ang + 0.4), hy - 8 * Math.sin(ang + 0.4));
      ctx.closePath(); ctx.fill();
    }

    // The companion star: a filled disc at its REAL modelled radius (compact — deep inside
    // its lobe). Floor the pixel radius so it stays visible on a tiny orbit.
    if (companion) {
      const rWorld = (companion.R_rsun || 0) / geo.separation_rsun;
      const rPx = Math.max(3.5, T.s * rWorld);
      ctx.fillStyle = teffToCSS(companion.Teff_K);
      ctx.beginPath(); ctx.arc(T.X(1), T.Y(0), rPx, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 1; ctx.stroke();
    }

    // Lagrange points (small × + labels).
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "center";
    for (const [lx, lab] of [[geo.l1_x, "L₁"], [geo.l2_x, "L₂"], [geo.l3_x, "L₃"]]) {
      const px = T.X(lx), py = T.Y(0);
      ctx.strokeStyle = LPT_COL; ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(px - 3, py - 3); ctx.lineTo(px + 3, py + 3);
      ctx.moveTo(px - 3, py + 3); ctx.lineTo(px + 3, py - 3); ctx.stroke();
      ctx.fillStyle = LPT_COL; ctx.fillText(lab, px, py - 7);
    }
    // Centre of mass.
    const cmx = T.X(geo.x_cm);
    ctx.strokeStyle = "#8a93a6"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(cmx, T.Y(0), 3.5, 0, 2 * Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cmx, T.Y(0) - 3.5); ctx.lineTo(cmx, T.Y(0) + 3.5); ctx.stroke();

    // Star labels.
    ctx.fillStyle = "#c9d2e4"; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("donor (M₁, heavier)", T.X(0), T.Y(0) + 4 + labelDrop(T, geo.donor_lobe));
    ctx.fillText("companion (M₂, accretor)", T.X(1), T.Y(0) - 6 - labelDrop(T, geo.companion_lobe));

    // Scale bar (bottom-left): the physical separation.
    drawScaleBar(T);

    if (caption) caption.textContent = captionText();
  }

  // Push a label just past the lobe's vertical extent so it doesn't sit on the star.
  function labelDrop(T, lobe) {
    let yMax = 0;
    for (const p of lobe) yMax = Math.max(yMax, Math.abs(p[1]));
    return T.s * yMax + 12;
  }

  function drawScaleBar(T) {
    // a bar one separation `a` long, labelled in R☉.
    const x0 = PAD, y0 = H - 14;
    const px = T.s * 1.0;   // one separation in pixels (may exceed the panel; cap the bar)
    const barPx = Math.min(px, W - 2 * PAD);
    const shown = barPx / T.s;   // separations represented by the drawn bar
    ctx.strokeStyle = "#8a93a6"; ctx.lineWidth = 1.5; ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + barPx, y0);
    ctx.moveTo(x0, y0 - 4); ctx.lineTo(x0, y0 + 4);
    ctx.moveTo(x0 + barPx, y0 - 4); ctx.lineTo(x0 + barPx, y0 + 4);
    ctx.stroke();
    ctx.fillStyle = "#8a93a6"; ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "left";
    const rsun = geo.separation_rsun * shown;
    ctx.fillText(`${rsun.toFixed(0)} R☉` + (shown < 0.999 ? "" : "  (separation a)"), x0 + 4, y0 - 6);
  }

  function captionText() {
    const md = geo.m_donor_msun, mc = geo.m_companion_msun;
    const a = geo.separation_rsun;
    // The stripped-donor current mass isn't in the roche block; the reversal is carried by
    // the ordering statement + the other panels. Keep the caption self-contained on what
    // THIS panel shows, and explicitly flag the cross-panel reversal.
    return (
      `Case-B mass transfer: the donor (M₁ = ${md.toFixed(2)} M☉) fills its Roche lobe and ` +
      `streams through L₁ onto the lighter companion (M₂ = ${mc.toFixed(2)} M☉, the accretor). ` +
      `Separation a ≈ ${a.toFixed(0)} R☉ from the initial orbital period (the RLOF-onset ` +
      `approximation). Note the reversal vs the other panels: HERE the donor is still the ` +
      `MORE massive star; by the stripped state shown elsewhere it has become the lighter ` +
      `object and the mass ratio has flipped. The donor's giant tint and the stream are ` +
      `schematic — only the lobe shapes, L-points and separation are computed.`
    );
  }

  function drawPanel(rocheBlock, companionState) {
    geo = rocheBlock || null;
    companion = companionState || null;
    // fitCanvas may have measured 0×0 while the panel was hidden; re-fit now it is visible.
    ({ ctx, W, H } = fitCanvas(canvas, canvas.clientWidth || 380, canvas.clientHeight || 300));
    draw();
  }

  function clear() {
    geo = null; companion = null;
    ctx.clearRect(0, 0, W, H);
    if (caption) caption.textContent = "";
  }

  function resize(cssW, cssH) {
    if (!geo) return;                 // hidden / no data — nothing to refit
    if (cssW === W && cssH === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    draw();
  }

  return { draw: drawPanel, resize, clear };
}
