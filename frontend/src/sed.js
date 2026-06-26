// Broadband spectral-energy-distribution panel — the WHOLE electromagnetic
// spectrum, gamma rays through radio (STAR_SIM_SPEC §5, the "wider range" view).
//
// Where the synthetic-spectrum panel (spectrum.js) is a model-atmosphere spectrum
// over a narrow optical window (3000–9000 Å), THIS panel zooms all the way out: it
// plots the star's Planck blackbody flux Fλ across ~14 decades of wavelength on a
// log–log axis, with the seven EM bands (γ-ray · X-ray · UV · visible · IR ·
// microwave · radio) labelled. It is the SED — where a star's light lives across
// the spectrum — with the detailed spectrum panel as just the optical zoom-in.
//
// A SIBLING to the §3 spine, like lane.js: it is driven by ONE number, Teff, and
// owns no fetch (a blackbody ignores log g and [Fe/H]). update(state) reads Teff
// off the marker and redraws — pure frontend, no backend, no grid.
//
// HONEST about the seams (the project rule — cf. the corona layer "evocative, not
// predictive"): a real star is NOT a blackbody at the EM extremes, and the panel
// says so at BOTH ends.
//   • High energy: a thermal blackbody at stellar Teff emits essentially nothing in
//     X-rays/γ-rays — the exponent hc/λkT overflows and Fλ underflows to zero, so
//     the curve simply floors there (handled exactly like lithium in comp.js: a
//     decade-capped log axis with a clamp-to-floor, so the curve exits the bottom
//     rather than producing −∞/NaN gaps). That floor is physically correct: real
//     stellar X-ray/γ-ray light is CORONAL / flare emission (magnetic activity),
//     not photospheric — which this simulator does not model.
//   • Radio: the blackbody's Rayleigh–Jeans tail (Fλ ∝ λ⁻⁴) is a FLOOR, not the
//     real radio flux — actual stellar radio emission (optically-thick chromosphere
//     /corona, gyrosynchrotron) sits orders of magnitude ABOVE it.
//
// Representation choice: Fλ (flux per unit wavelength), SAME quantity as the detail
// panel — so this really is "the same curve, zoomed out", and the Wien-peak marker
// reuses the Fλ displacement constant (λ_max·T = 2.8978e7 Å·K). (λFλ / νFν would
// move the peak and need a different constant — deliberately not used.) Normalized
// to the blackbody's own peak (= 0 dex at top); absolute luminosity lives in the L
// readout and the 3D star, exactly as in the detail panel.

import { fitCanvas } from "./canvas.js";
import { planck, HC_OVER_K_NM, wavelengthToCSS } from "./color.js";

const PAD_L = 46, PAD_R = 14, PAD_T = 28, PAD_B = 40;

// The wavelength axis, in nanometres, log-spaced. From deep gamma (1e-4 nm = 0.1 pm)
// to long radio (1e10 nm = 10 m): 14 decades, enough to show every EM band and let
// both non-thermal tails clearly bottom out within their bands.
const LAM_MIN = 1e-4, LAM_MAX = 1e10;
const LOG_LO = Math.log10(LAM_MIN), LOG_HI = Math.log10(LAM_MAX);

// How many decades of flux below the blackbody peak the y-axis spans. The thermal
// hump crashes super-exponentially on the short-λ (Wien) side and falls as λ⁻⁴ on
// the long-λ (Rayleigh–Jeans) side, so a ~14-decade window shows the hump tall
// while letting the X-ray/γ-ray and microwave/radio bands sit honestly on the floor.
const FLOOR_DECADES = 14;

// F_λ Wien displacement: λ_max · T = 2.8977719e7 Å·K  (= 2.8977719e6 nm·K).
const WIEN_NM_K = 2.8977719e6;
// The peak of B_λ is at x = hc/λkT ≈ 4.9651, so λ_peak = (hc/k)/(4.9651·T).
const WIEN_X = 4.965114231744276;

// ─── Non-thermal coronal/activity overlay (Phase 5, "magnetic-ember" Chunk 1) ───
// The blackbody floors in X-rays — but real stellar X-rays are CORONAL, driven by
// magnetic activity, not photospheric. We overlay the order-of-magnitude band the
// accepted rotation–activity scaling permits — honestly a RANGE, not a value,
// because the sim models no rotation/age (the `activity` proxy is a pure Teff ramp,
// so placing a single L_X from it would fake precision — the project's recurring
// "label a non-feature" trap). See docs/plans/magnetic-ember-broadcast.md.
//
// Placement (the trick the plan flagged): the y-axis is decades below the blackbody's
// OWN peak Fλ, so a luminosity ratio L_X/L_bol must be turned into an Fλ level. For a
// blackbody the integral and the peak are tied by a fixed effective width,
//     L_bol / F_peak = (π⁴/15)·(e^xp−1)/xp⁴ · λ_peak ≈ 1.521·λ_peak   (xp = 4.9651),
// and spreading L_X over the soft-X-ray band Δλ_X gives that band's Fλ — with L_bol
// CANCELLING out:
//     Fλ_X / F_peak = (L_X/L_bol) · (1.521·λ_peak) / Δλ_X,
// so the band placement depends on Teff alone (via λ_peak), no L_bol needed.
const BB_XP = 4.965114231744276;                       // peak of B_λ in x = hc/λkT
const BB_EFF_WIDTH = (Math.PI ** 4 / 15) * (Math.exp(BB_XP) - 1) / BB_XP ** 4; // ≈1.521
const XRAY_LO = 0.1, XRAY_HI = 10;                     // soft-X-ray band, nm (coronal)
const XRAY_DLAM = XRAY_HI - XRAY_LO;                    // Δλ_X ≈ 10 nm the L_X spreads over

// Güdel–Benz (1993): a tight cool-star X-ray↔radio correlation, L_X / L_R ≈ 10^15.5 Hz
// (L_R the radio spectral luminosity per Hz). Mapped onto the Fλ axis it lands at
//     Fλ_R / F_peak = (L_X/L_bol) · (1.521·λ_peak) · c / (10^15.5 · λ_R²),
// which for normal stars is BELOW this 14-decade window — per-Hz radio becomes tiny
// per-nm flux (the λ² makes radio intrinsically faint on an Fλ axis: the AXIS, not the
// physics). So it is a compact marker near the floor, not a ribbon; the genuine
// radio-above-floor story is the hot-star wind tail, not this coronal correlate.
const GB_LOG_HZ = 15.5;                                 // log10(L_X / L_R), Hz
const C_NM_S = 2.99792458e17;                           // speed of light, nm/s
const LAM_RADIO = 6e7;                                  // nm ≈ 6 cm ≈ 5 GHz (the GB band)

// The seven EM bands, by wavelength in nm (standard teaching boundaries). The
// visible band is painted as the true spectral rainbow (reusing color.js); the rest
// get a muted tint. Note how THIN visible is — ~0.3 of a decade out of 14: the slice
// the eye sees, and the slice the detail spectrum panel covers, is a sliver of the
// whole. Short names render on-canvas; the legend carries the pedagogy.
const BANDS = [
  { lo: LAM_MIN, hi: 1e-2, name: "γ-ray",     col: "rgba(180,120,255,0.10)" },
  { lo: 1e-2,    hi: 1e1,  name: "X-ray",     col: "rgba(120,150,255,0.10)" },
  { lo: 1e1,     hi: 380,  name: "UV",        col: "rgba(110,110,240,0.12)" },
  { lo: 380,     hi: 750,  name: "visible",   rainbow: true },
  { lo: 750,     hi: 1e6,  name: "IR",        col: "rgba(255,140,90,0.10)" },
  { lo: 1e6,     hi: 1e9,  name: "microwave", col: "rgba(120,180,150,0.09)" },
  { lo: 1e9,     hi: LAM_MAX, name: "radio",  col: "rgba(150,160,180,0.08)" },
];

// The optical window the detailed spectrum panel covers (3000–9000 Å = 300–900 nm).
// Bracketed so the two panels read as "this detail view is this slice of the SED".
const DETAIL_LO = 300, DETAIL_HI = 900;

// λ landmarks to label on the axis, in friendly units (pm/nm/µm/mm/m). Every decade
// gets a faint gridline; only these get a text label, collision-skipped.
const LAM_TICKS = [
  { nm: 1e-3, label: "1 pm" },
  { nm: 1,    label: "1 nm" },
  { nm: 1e3,  label: "1 µm" },
  { nm: 1e6,  label: "1 mm" },
  { nm: 1e9,  label: "1 m" },
];

const COL_CURVE = "#eef2f9";
const COL_GRID = "#283149";

export function createSED(canvas) {
  if (!canvas) return { update() {}, resize() {} };
  const caption = document.getElementById("sed-caption");
  // W/H/plotW are `let` so resize() can re-fit to a new display width; xOf/yOf
  // capture the plotW/W/H bindings, so they track the new size on the next draw().
  let ctx, W, H, plotW;
  ({ ctx, W, H } = fitCanvas(canvas, 720, 300));
  plotW = W - PAD_L - PAD_R;

  let teff = null, logg = null;

  const xOf = (lamNm) =>
    PAD_L + (Math.log10(lamNm) - LOG_LO) / (LOG_HI - LOG_LO) * plotW;
  // y maps decades-below-peak: 0 dex (peak) at the top, −FLOOR_DECADES at the axis.
  const yOf = (dec) =>
    PAD_T + (-dec / FLOOR_DECADES) * (H - PAD_T - PAD_B);

  function update(state) {
    if (!state || state.Teff_K == null) return;
    // logg gates the activity overlay (dwarf dynamo vs cool-giant suppressed corona),
    // so it must be part of the redraw key: two stars at the same Teff but different
    // logg (a dwarf vs a giant crossing the same temperature) draw different bands.
    const g = state.logg ?? null;
    if (state.Teff_K === teff && g === logg) return;
    teff = state.Teff_K; logg = g;
    draw();
    renderCaption();
  }

  // Re-fit to a new display size (responsive layout) and redraw from the last Teff.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    plotW = W - PAD_L - PAD_R;
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (teff == null) return;

    drawBands();
    drawDetailWindow();
    drawGrid();

    // The blackbody curve, normalized to its own peak. log10(Fλ) − log10(F_peak),
    // clamped to the floor: gamma/X-ray underflow to 0 → −∞ → clamped, so the curve
    // runs flat along the bottom there (honestly: ~no thermal flux), no NaN gaps.
    const lamPeak = HC_OVER_K_NM / (WIEN_X * teff);          // nm
    const logPeak = Math.log10(planck(lamPeak, teff));
    const N = 700;
    ctx.beginPath();
    for (let i = 0; i < N; i++) {
      const logLam = LOG_LO + (i / (N - 1)) * (LOG_HI - LOG_LO);
      const lam = 10 ** logLam;
      const b = planck(lam, teff);
      let dec = b > 0 ? Math.log10(b) - logPeak : -FLOOR_DECADES;
      if (dec < -FLOOR_DECADES) dec = -FLOOR_DECADES;
      if (dec > 0) dec = 0;
      const x = xOf(lam), y = yOf(dec);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COL_CURVE; ctx.lineWidth = 1.6; ctx.stroke();

    drawActivity(lamPeak);
    drawWienPeak(lamPeak);
    drawFrameAndAxes();
  }

  // Regime gates the activity overlay honestly: a cool convective dynamo (full band)
  // vs a hot wind-shock collapse (~10⁻⁷) vs the A/early-F X-ray gap (no band) vs a
  // cool giant's suppressed corona past the Linsky–Haisch corona–wind dividing line.
  function regimeOf(t, g) {
    if (t >= 10000) return "hot";          // O/B: embedded wind shocks, no dynamo
    if (t > 6500) return "gap";            // A / early-F: X-ray-quiet gap
    if (g != null && g < 3.0 && t < 5000) return "coolgiant"; // suppressed corona
    return "cool";                         // F/G/K/M dwarf/subgiant: full envelope
  }

  // The coronal soft-X-ray ACTIVITY band (+ its Güdel–Benz radio marker). Drawn as a
  // hatched, translucent RANGE — never a crisp line — so a later data-grounded curve
  // (the hot-star wind tail, Chunk 2) will read as a visibly distinct tier. lamPeak is
  // the Fλ peak wavelength in nm.
  function drawActivity(lamPeak) {
    const reg = regimeOf(teff, logg);
    if (reg === "gap") return;             // A/early-F: nothing to draw, caption only

    // The L_X/L_bol envelope per regime. Cool dwarfs span the full saturated→quiet
    // band; hot stars collapse to the narrow wind-shock value; cool giants are dimmed
    // and capped below saturation (corona suppressed — see Linsky–Haisch).
    let fxLo, fxHi, topLabel, botLabel, tag, dim;
    if (reg === "hot") {
      fxLo = 10 ** -7.5; fxHi = 10 ** -6.5;
      topLabel = ""; botLabel = ""; tag = "wind X-ray ~10⁻⁷"; dim = false;
    } else if (reg === "coolgiant") {
      fxLo = 1e-8; fxHi = 1e-5;
      topLabel = "10⁻⁵"; botLabel = "10⁻⁸"; tag = "coronal X-ray"; dim = true;
    } else {
      fxLo = 1e-7; fxHi = 1e-3;
      topLabel = "10⁻³"; botLabel = "10⁻⁷"; tag = "coronal X-ray"; dim = false;
    }

    const w = BB_EFF_WIDTH * lamPeak / XRAY_DLAM;
    const decOf = (fx) => Math.log10(fx) + Math.log10(w);   // dec below the BB peak Fλ
    const decTop = Math.min(0, decOf(fxHi));
    const decBot = Math.max(-FLOOR_DECADES, decOf(fxLo));
    if (decTop <= decBot) return;

    const x0 = xOf(XRAY_LO), x1 = xOf(XRAY_HI);
    const yTop = yOf(decTop), yBot = yOf(decBot), hh = yBot - yTop;

    // translucent fill + diagonal hatch = the "evocative range" styling.
    ctx.fillStyle = `rgba(255,140,110,${dim ? 0.10 : 0.18})`;
    ctx.fillRect(x0, yTop, x1 - x0, hh);
    ctx.save();
    ctx.beginPath(); ctx.rect(x0, yTop, x1 - x0, hh); ctx.clip();
    ctx.strokeStyle = `rgba(255,170,135,${dim ? 0.22 : 0.4})`; ctx.lineWidth = 1;
    for (let p = x0 - hh; p < x1; p += 7) {
      ctx.beginPath(); ctx.moveTo(p, yBot); ctx.lineTo(p + hh, yTop); ctx.stroke();
    }
    ctx.restore();
    // solid top/bottom edges
    ctx.strokeStyle = `rgba(255,175,145,${dim ? 0.55 : 0.85})`; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(x0, yTop); ctx.lineTo(x1, yTop); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x0, yBot); ctx.lineTo(x1, yBot); ctx.stroke();

    // The dimensionless L_X/L_bol edge labels — the explicit guard against reading the
    // band as a pixel-precise flux. The tag names the mechanism.
    ctx.fillStyle = "#ff9e85"; ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "right";
    if (topLabel && decOf(fxHi) <= 0) ctx.fillText(topLabel, x1 - 2, yTop + 10);
    if (botLabel && decOf(fxLo) >= -FLOOR_DECADES) ctx.fillText(botLabel, x1 - 2, yBot - 3);
    ctx.textAlign = "center";
    ctx.fillText(tag, (x0 + x1) / 2, yTop - 4);
    ctx.textAlign = "left";

    // Güdel–Benz radio correlate — a cool-star phenomenon only; compact marker.
    if (reg === "cool" || reg === "coolgiant") drawGudelBenzRadio(lamPeak, fxHi);
  }

  // The Güdel–Benz radio counterpart of the X-ray band, anchored at the cm-wave (GHz)
  // position. On this per-wavelength axis it sits below the window for normal stars —
  // drawn as a short tick rising from the floor (clamped) to its highest (saturated)
  // level, a compact footnote to the X-ray band rather than a competing ribbon.
  function drawGudelBenzRadio(lamPeak, fxHi) {
    const xr = xOf(LAM_RADIO);
    const decR = Math.log10(fxHi) + Math.log10(BB_EFF_WIDTH * lamPeak)
      + Math.log10(C_NM_S) - GB_LOG_HZ - 2 * Math.log10(LAM_RADIO);
    const yFloor = yOf(-FLOOR_DECADES);
    const yTop = yOf(Math.min(0, Math.max(decR, -FLOOR_DECADES)));   // clamped to window
    ctx.strokeStyle = "rgba(255,160,130,0.55)"; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(xr, yFloor); ctx.lineTo(xr, yTop); ctx.stroke();
    ctx.fillStyle = "rgba(255,160,130,0.85)";
    ctx.beginPath();
    ctx.moveTo(xr, yTop - 3); ctx.lineTo(xr + 3, yTop);
    ctx.lineTo(xr, yTop + 3); ctx.lineTo(xr - 3, yTop); ctx.closePath(); ctx.fill();
    ctx.fillStyle = "#ff9e85"; ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Güdel–Benz radio", xr, yFloor - 5);
    ctx.textAlign = "left";
  }

  // Faint translucent EM-band columns; the visible band is the true rainbow.
  function drawBands() {
    for (const band of BANDS) {
      const x0 = xOf(Math.max(band.lo, LAM_MIN));
      const x1 = xOf(Math.min(band.hi, LAM_MAX));
      if (band.rainbow) {
        // Paint the visible band column-by-column in its per-wavelength colour.
        ctx.globalAlpha = 0.6;
        const step = 1;
        for (let x = x0; x < x1; x += step) {
          const lam = 10 ** (LOG_LO + (x - PAD_L) / plotW * (LOG_HI - LOG_LO));
          ctx.fillStyle = wavelengthToCSS(lam);   // λ already in nm
          ctx.fillRect(x, PAD_T, step + 0.5, H - PAD_T - PAD_B);
        }
        ctx.globalAlpha = 1;
      } else {
        ctx.fillStyle = band.col;
        ctx.fillRect(x0, PAD_T, x1 - x0, H - PAD_T - PAD_B);
      }
      // Band divider + label along the top.
      ctx.strokeStyle = "rgba(120,130,150,0.25)"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x1, PAD_T); ctx.lineTo(x1, H - PAD_B); ctx.stroke();
      ctx.fillStyle = band.rainbow ? "#cdd6e6" : "#7e88a0";
      ctx.font = "10px system-ui, sans-serif";
      ctx.textAlign = "center";
      const mid = (x0 + x1) / 2;
      // Skip a label that wouldn't fit its band (the visible sliver is too narrow —
      // it's covered by the legend + the "detailed spectrum" bracket below it).
      if (x1 - x0 > 26) ctx.fillText(band.name, mid, PAD_T - 4);
    }
    ctx.textAlign = "left";
  }

  // A bracket under the optical window the detail spectrum panel covers — the link
  // between the two panels ("the detailed spectrum is this slice of the whole SED").
  function drawDetailWindow() {
    const x0 = xOf(DETAIL_LO), x1 = xOf(DETAIL_HI);
    const y = H - PAD_B;
    ctx.strokeStyle = "rgba(255,210,127,0.7)"; ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x0, y - 5); ctx.lineTo(x0, y); ctx.lineTo(x1, y); ctx.lineTo(x1, y - 5);
    ctx.stroke();
    ctx.fillStyle = "#ffd27f"; ctx.font = "9.5px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("detailed spectrum", (x0 + x1) / 2, y - 7);
    ctx.textAlign = "left";
  }

  function drawGrid() {
    ctx.strokeStyle = COL_GRID; ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
    // Vertical: every decade of wavelength.
    for (let e = Math.ceil(LOG_LO); e <= LOG_HI; e++) {
      const x = xOf(10 ** e);
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
    }
    // Horizontal: every 2 decades of flux.
    for (let d = 0; d >= -FLOOR_DECADES; d -= 2) {
      const y = yOf(d);
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function drawWienPeak(lamPeak) {
    const x = xOf(lamPeak);
    ctx.strokeStyle = "rgba(255,210,127,0.7)"; ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ffd27f"; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Wien peak", x, PAD_T - 16);
    ctx.textAlign = "left";
  }

  function drawFrameAndAxes() {
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, plotW, H - PAD_T - PAD_B);

    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";

    // x labels at the friendly landmark wavelengths.
    ctx.textAlign = "center";
    let lastX = -1e9;
    for (const t of LAM_TICKS) {
      const x = xOf(t.nm);
      if (x - lastX < 34) continue;
      lastX = x;
      ctx.fillText(t.label, x, H - PAD_B + 14);
    }
    ctx.fillText("wavelength  (gamma ← short · long → radio)", W / 2, H - 6);

    // y labels: decades below the blackbody peak.
    ctx.textAlign = "right";
    for (let d = 0; d >= -FLOOR_DECADES; d -= 2) {
      ctx.fillText(d === 0 ? "peak" : `${d}`, PAD_L - 5, yOf(d) + 4);
    }
    ctx.save();
    ctx.translate(13, (H - PAD_B + PAD_T) / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center";
    ctx.fillText("flux Fλ  (log₁₀, decades below peak)", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
  }

  // The honest "what am I looking at" caption: the parameter (Teff only), the peak
  // wavelength + which band it lands in, then the coronal-activity overlay described
  // per regime — always as a RANGE we can't pin (no rotation/age), with γ kept
  // explicitly empty. "Evocative, not predictive", as for the 3D corona.
  function renderCaption() {
    if (!caption || teff == null) return;
    const lamPeakNm = WIEN_NM_K / teff;
    let where = "the infrared";
    if (lamPeakNm < 10) where = "the X-ray / extreme-UV";
    else if (lamPeakNm < 380) where = "the ultraviolet";
    else if (lamPeakNm <= 750) where = "the visible";
    else if (lamPeakNm < 1e6) where = "the infrared";
    const peakTxt = lamPeakNm < 1
      ? `${(lamPeakNm * 1000).toPrecision(3)} pm`
      : lamPeakNm < 1e3
        ? `${lamPeakNm.toPrecision(3)} nm`
        : `${(lamPeakNm / 1e3).toPrecision(3)} µm`;

    // The per-regime sentence is kept SHORT and deliberately ~equal in length across
    // regimes: a regime-dependent caption height resizes the panel as you scrub across
    // the cool→gap→hot boundaries (the jank the Lane–Emden caption fix addressed). A px
    // min-height reserve can't fix it here — the panel's flex-wrap width (and so the
    // caption's line count) varies — so instead the four branches are matched in length
    // (~130–140 chars) to wrap to the same number of lines at any width. The full story
    // lives in the legend tooltip + the panel's ? tip, not here.
    const reg = regimeOf(teff, logg);
    let act;
    if (reg === "hot")
      act = `Overlaid (coral): the X-ray band collapses to the narrow wind-shock ` +
            `value L_X/L_bol ≈ 10⁻⁷ — hot O/B stars have no convective dynamo.`;
    else if (reg === "gap")
      act = `No band drawn: A and early-F stars sit in an X-ray gap — too hot for a ` +
            `convective dynamo, too cool for strong wind shocks to make X-rays.`;
    else if (reg === "coolgiant")
      act = `Overlaid (coral, dimmed): a coronal X-ray band, but suppressed and ` +
            `uncertain past the Linsky–Haisch corona–wind dividing line — a guide only.`;
    else
      act = `Overlaid (coral, hatched): the coronal soft-X-ray activity band, ` +
            `L_X/L_bol ≈ 10⁻⁷…10⁻³ — a RANGE, not a value (rotation and age unmodeled).`;

    caption.textContent =
      `Idealized blackbody at Teff ${Math.round(teff)} K — peaks at ${peakTxt} ` +
      `(${where}). ${act} γ-rays stay empty. Evocative, not predictive.`;
  }

  return { update, resize };
}
