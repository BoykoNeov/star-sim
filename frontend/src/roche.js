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
import { teffToCSS, teffToRGB } from "./color.js";

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

  let geo = null;        // last /binary_pair `roche` block (or a /binary_track step's)
  let companion = null;  // last companion StellarState (for size + colour)

  // path (b) Chunk 4b — the LIVE per-step view (a co-evolving POSYDON track, drawLive()),
  // as opposed to the STATIC Chunk-3 snapshot above (drawPanel(), one fixed q=0.8 RLOF
  // moment). Unlike the snapshot, here BOTH stars have real modelled Teff/R at every step
  // (no "unknown giant temperature" gap — see drawLive's docstring), so both are drawn as
  // real discs, Teff-coloured, at every step; a lobe additionally FILLS (translucent, in
  // that star's own colour) + the stream draws only while `mtState` flags it as actively
  // overflowing — donor at cx=0 / companion at cx=1 by FIXED IDENTITY throughout, never by
  // which currently masses more (the reversal is the fill/size swapping sides, not a label
  // swap — the Chunk-1/Chunk-3 convention-mismatch class of bug).
  let liveMode = false;
  let donorState = null;
  let mtState = "detached";

  // Chunk 1b — the CO-HMS_RLO variant of the live view: the accretor is a COMPACT OBJECT
  // (NS/BH/WD), a point mass with no photosphere. `coMode` swaps the companion's Teff disc
  // for a schematic marker (a real compact object is ~km across — utterly invisible at
  // orbital scale, so a fixed-pixel schematic marker is the HONEST render, not a scaled
  // disc). `coType` picks the marker: BH = a persistent dark disc + bright ring (an ongoing
  // orbiting companion — NOT the SN arc's "winks out"), NS/other = a tiny hot point + halo.
  let coMode = false;
  let coType = null;

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

  // The orbital axis (line of centres) — shared by both the static and live views.
  function drawAxisLine(T) {
    ctx.strokeStyle = AXIS_COL; ctx.lineWidth = 1; ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.moveTo(T.X(geo.l3_x - 0.05), T.Y(0)); ctx.lineTo(T.X(geo.l2_x + 0.05), T.Y(0)); ctx.stroke();
    ctx.setLineDash([]);
  }

  // The mass-transfer stream (schematic Coriolis-deflected arc) with an arrowhead at its
  // companion-ward end — shared by both views (the live view only calls it while a star is
  // actually flagged as overflowing).
  function drawStream(T, pts, col) {
    if (!pts || pts.length < 2) return;
    ctx.strokeStyle = col; ctx.lineWidth = 2.4; ctx.globalAlpha = 0.9;
    poly(pts, T); ctx.stroke();
    ctx.globalAlpha = 1;
    const a = pts[pts.length - 2], b = pts[pts.length - 1];
    const ang = Math.atan2(T.Y(b[1]) - T.Y(a[1]), T.X(b[0]) - T.X(a[0]));
    const hx = T.X(b[0]), hy = T.Y(b[1]);
    ctx.fillStyle = col;
    ctx.beginPath();
    ctx.moveTo(hx, hy);
    ctx.lineTo(hx - 8 * Math.cos(ang - 0.4), hy - 8 * Math.sin(ang - 0.4));
    ctx.lineTo(hx - 8 * Math.cos(ang + 0.4), hy - 8 * Math.sin(ang + 0.4));
    ctx.closePath(); ctx.fill();
  }

  // A filled disc for a real modelled star at world x = cx (0 = donor, 1 = companion),
  // sized by its REAL R_rsun/separation (floored so it stays visible on a tiny orbit).
  function drawStarDisc(cx, state, T) {
    const rWorld = (state.R_rsun || 0) / geo.separation_rsun;
    const rPx = Math.max(3.5, T.s * rWorld);
    ctx.fillStyle = teffToCSS(state.Teff_K);
    ctx.beginPath(); ctx.arc(T.X(cx), T.Y(0), rPx, 0, 2 * Math.PI); ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 1; ctx.stroke();
  }

  // A schematic point-mass marker for a compact-object accretor (Chunk 1b). It is NOT sized
  // by any radius — a compact object is a point at orbital scale; this is a fixed-pixel
  // glyph, the same honesty tier as the stream/lobe-fill cues.
  function drawCoMarker(cx, T) {
    const px = T.X(cx), py = T.Y(0);
    if (coType === "BH") {
      // Persistent dark disc + a thin bright ring so it reads against the dark panel — an
      // ongoing orbiting companion, deliberately NOT the SN remnant's wink-out.
      ctx.fillStyle = "#05070d";
      ctx.beginPath(); ctx.arc(px, py, 7, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = "#8fb4ff"; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(px, py, 7.5, 0, 2 * Math.PI); ctx.stroke();
    } else {
      // NS (or WD/other): a tiny hot point + soft halo — evocative, NOT a photosphere.
      const grad = ctx.createRadialGradient(px, py, 0, px, py, 9);
      grad.addColorStop(0, "rgba(212,229,255,0.9)");
      grad.addColorStop(1, "rgba(212,229,255,0)");
      ctx.fillStyle = grad;
      ctx.beginPath(); ctx.arc(px, py, 9, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = "#eaf1ff";
      ctx.beginPath(); ctx.arc(px, py, 3, 0, 2 * Math.PI); ctx.fill();
    }
  }

  const CO_NAME = { BH: "black hole", NS: "neutron star", WD: "white dwarf" };

  function drawLPointsAndCM(T) {
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "center";
    for (const [lx, lab] of [[geo.l1_x, "L₁"], [geo.l2_x, "L₂"], [geo.l3_x, "L₃"]]) {
      const px = T.X(lx), py = T.Y(0);
      ctx.strokeStyle = LPT_COL; ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(px - 3, py - 3); ctx.lineTo(px + 3, py + 3);
      ctx.moveTo(px - 3, py + 3); ctx.lineTo(px + 3, py - 3); ctx.stroke();
      ctx.fillStyle = LPT_COL; ctx.fillText(lab, px, py - 7);
    }
    const cmx = T.X(geo.x_cm);
    ctx.strokeStyle = "#8a93a6"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(cmx, T.Y(0), 3.5, 0, 2 * Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cmx, T.Y(0) - 3.5); ctx.lineTo(cmx, T.Y(0) + 3.5); ctx.stroke();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!geo) return;
    if (liveMode) { drawLiveFrame(); return; }
    const T = transform();

    drawAxisLine(T);

    // Companion Roche lobe (faint — it is NOT filled; the companion sits well inside it).
    poly(geo.companion_lobe, T);
    ctx.fillStyle = COMP_LOBE_FILL; ctx.fill();
    ctx.strokeStyle = COMP_LOBE_STROKE; ctx.lineWidth = 1.5; ctx.stroke();

    // Donor Roche lobe — FILLED (the donor overflows it). The bloated-giant schematic tint.
    poly(geo.donor_lobe, T);
    ctx.fillStyle = DONOR_FILL; ctx.fill();
    ctx.strokeStyle = DONOR_STROKE; ctx.lineWidth = 2; ctx.stroke();

    // The mass-transfer stream L1 → companion (schematic), drawn over the lobes.
    drawStream(T, geo.stream, STREAM_COL);

    // The companion star: a filled disc at its REAL modelled radius (compact — deep inside
    // its lobe).
    if (companion) drawStarDisc(1, companion, T);

    drawLPointsAndCM(T);

    // Star labels.
    ctx.fillStyle = "#c9d2e4"; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("donor (M₁, heavier)", T.X(0), T.Y(0) + 4 + labelDrop(T, geo.donor_lobe));
    ctx.fillText("companion (M₂, accretor)", T.X(1), T.Y(0) - 6 - labelDrop(T, geo.companion_lobe));

    // Scale bar (bottom-left): the physical separation.
    drawScaleBar(T);

    if (caption) caption.textContent = captionText();
  }

  // The LIVE per-step view (path (b) Chunk 4b): a co-evolving POSYDON track's REAL q(t)/
  // a(t) at the scrubbed step, instead of the static view's one fixed q=0.8 RLOF moment.
  // Two honest upgrades this unlocks: (1) BOTH stars have a real modelled Teff/R at every
  // step (no "unknown giant temperature" gap), so both are drawn as real discs in their
  // true colour, always — not one schematic tint + one real disc; (2) the lobes RESHAPE
  // as q/a evolve, and whichever star is CURRENTLY flagged (`mtState`) as overflowing gets
  // its lobe filled (translucent, in its own colour) + the stream — the other stays an
  // unfilled outline. Note the real photospheric radius does NOT itself cross the lobe
  // outline during RLOF (Roche overflow is a local excess at L1, not a whole-photosphere
  // inflation past the mean lobe radius — measured on the real grid) — the fill is the
  // schematic "transferring right now" cue, same discipline as the static stream.
  function drawLiveFrame() {
    const T = transform();
    drawAxisLine(T);

    const donorFilling = mtState === "RLOF1" || mtState === "contact";
    // A point-mass CO can never itself overflow (RLOF2/contact never fire on this grid) —
    // force it false so the CO lobe stays an unfilled accretion-target outline.
    const companionFilling = !coMode && (mtState === "RLOF2" || mtState === "contact");
    const donorCol = donorState ? teffToCSS(donorState.Teff_K) : DONOR_STROKE;
    const compCol = companion ? teffToCSS(companion.Teff_K) : COMP_LOBE_STROKE;
    const rgbaFromTeff = (teffK, alpha) => {
      const [r, g, b] = teffToRGB(teffK).map((v) => Math.round(v * 255));
      return `rgba(${r},${g},${b},${alpha})`;
    };

    poly(geo.companion_lobe, T);
    ctx.fillStyle = companionFilling && companion
      ? rgbaFromTeff(companion.Teff_K, 0.26) : "rgba(255,255,255,0.025)";
    ctx.fill();
    ctx.strokeStyle = compCol; ctx.lineWidth = companionFilling ? 2 : 1.1; ctx.stroke();

    poly(geo.donor_lobe, T);
    ctx.fillStyle = donorFilling && donorState
      ? rgbaFromTeff(donorState.Teff_K, 0.26) : "rgba(255,255,255,0.025)";
    ctx.fill();
    ctx.strokeStyle = donorCol; ctx.lineWidth = donorFilling ? 2 : 1.1; ctx.stroke();

    // The stream direction the backend serves is L1 → companion (the RLOF1 sense — the
    // demo tracks never exercise RLOF2, the rarer reverse case); only draw it while the
    // donor is the one actively overflowing, so it never implies the wrong direction.
    if (donorFilling) drawStream(T, geo.stream, STREAM_COL);

    // The star's real disc (every step, true Teff/R). The accretor: a real disc for a normal
    // companion (HMS-HMS), or a schematic point-mass marker for a compact object (CO-HMS_RLO).
    if (donorState) drawStarDisc(0, donorState, T);
    if (coMode) drawCoMarker(1, T);
    else if (companion) drawStarDisc(1, companion, T);

    drawLPointsAndCM(T);

    ctx.fillStyle = "#c9d2e4"; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(coMode ? "star" : "donor", T.X(0), T.Y(0) + 4 + labelDrop(T, geo.donor_lobe));
    ctx.fillText(coMode ? (CO_NAME[coType] || coType) : "companion",
      T.X(1), T.Y(0) - 6 - labelDrop(T, geo.companion_lobe));

    drawScaleBar(T);

    if (caption) caption.textContent = coMode ? captionTextCo() : captionTextLive();
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

  const MT_LABEL = {
    detached: "detached — neither star fills its Roche lobe right now",
    RLOF1: "Roche-lobe overflow: the donor is actively transferring mass onto the companion",
    RLOF2: "reverse overflow: the companion is actively transferring mass onto the donor",
    contact: "contact — both stars overflow their lobes at once",
  };

  function captionTextLive() {
    const a = geo.separation_rsun;
    const label = MT_LABEL[mtState] || mtState;
    return (
      `${label}. Separation a ≈ ${a.toFixed(0)} R☉. Both stars are drawn at their REAL ` +
      `modelled Teff and radius, every step — unlike the fixed RLOF snapshot above, this ` +
      `movie has a real temperature for the donor too. Donor and companion stay at the ` +
      `SAME positions throughout (donor left, companion right) — it is the lobe SIZES and ` +
      `fills that swap as the mass ratio reverses, never the labels. The lobe fill + stream ` +
      `are the schematic "transferring now" cue: Roche overflow is a local excess at L₁, so ` +
      `the real photospheric disc stays inside the outline even while a lobe is filled.`
    );
  }

  function captionTextCo() {
    const a = geo.separation_rsun;
    const label = MT_LABEL[mtState] || mtState;
    const coName = CO_NAME[coType] || `${coType} remnant`;
    return (
      `${label}. The accretor is a ${coName} — a POINT MASS, drawn as a schematic marker, ` +
      `NOT a photosphere (a compact object is ~km across, invisible at this orbital scale, ` +
      `and has no surface temperature). Separation a ≈ ${a.toFixed(0)} R☉. The star sits ` +
      `LEFT, the compact object RIGHT, by fixed identity throughout — it is the lobe SIZES ` +
      `that swap as the star is stripped and the compact object accretes. During overflow ` +
      `the star streams gas through L₁ toward the compact object (the lobe fill + stream are ` +
      `the schematic "transferring now" cue); the released accretion power is shown in the ` +
      `caption under the time slider, not here.`
    );
  }

  function drawPanel(rocheBlock, companionState) {
    liveMode = false; coMode = false; coType = null;
    donorState = null; mtState = "detached";
    geo = rocheBlock || null;
    companion = companionState || null;
    // fitCanvas may have measured 0×0 while the panel was hidden; re-fit now it is visible.
    ({ ctx, W, H } = fitCanvas(canvas, canvas.clientWidth || 380, canvas.clientHeight || 300));
    draw();
  }

  // path (b) Chunk 4b: one step of a co-evolving POSYDON track — `rocheBlock` is that
  // step's own geometry (`binary.track_roche_geometry`, real q(t)/a(t), NOT the static
  // fixed-q=0.8 snapshot). `donor`/`companionState` are that step's real StellarStates.
  function drawLive(rocheBlock, donor, companionState, mtStateNow) {
    liveMode = true; coMode = false; coType = null;
    geo = rocheBlock || null;
    donorState = donor || null;
    companion = companionState || null;
    mtState = mtStateNow || "detached";
    ({ ctx, W, H } = fitCanvas(canvas, canvas.clientWidth || 380, canvas.clientHeight || 300));
    draw();
  }

  // Chunk 1b: one step of a CO-HMS_RLO track — the star (a real StellarState) plus a
  // compact-object accretor rendered as a schematic point-mass marker (`coTypeNow` picks
  // the glyph). Same per-step Roche geometry as drawLive, but with no companion StellarState.
  function drawLiveCo(rocheBlock, star, coTypeNow, mtStateNow) {
    liveMode = true; coMode = true; coType = coTypeNow || "NS";
    geo = rocheBlock || null;
    donorState = star || null;
    companion = null;
    mtState = mtStateNow || "detached";
    ({ ctx, W, H } = fitCanvas(canvas, canvas.clientWidth || 380, canvas.clientHeight || 300));
    draw();
  }

  function clear() {
    geo = null; companion = null; donorState = null; liveMode = false; mtState = "detached";
    coMode = false; coType = null;
    ctx.clearRect(0, 0, W, H);
    if (caption) caption.textContent = "";
  }

  function resize(cssW, cssH) {
    if (!geo) return;                 // hidden / no data — nothing to refit
    if (cssW === W && cssH === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    draw();
  }

  return { draw: drawPanel, drawLive, drawLiveCo, resize, clear };
}
