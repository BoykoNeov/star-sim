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

// ─── Chunk 2: hot-star wind thermal free–free excess (mid/far-IR → sub-mm) ──────
// A radiatively-driven IONIZED wind emits optically-thick thermal free–free
// (bremsstrahlung) with Fλ ∝ λ⁻²·⁶ — SHALLOWER than the photosphere's Rayleigh–Jeans
// floor (λ⁻⁴), so it OVERTAKES the blackbody and rises above it at long wavelengths.
// Unlike the coronal band (an evocative RANGE — no rotation/age), this is DATA-GROUNDED:
// computed from the real on-disk mass-loss rate Ṁ (mdot_msun_yr, threaded onto the spine
// in Chunk 2). Drawn as a SOLID line — the predictive tier — vs the hatched coral band.
//
// Wright & Barlow (1975) / Panagia & Felli (1975) flux of an isothermal, constant-
// velocity, fully-ionized wind:
//   S_ν = 23.2 (Ṁ₋₆/(μ v∞))^(4/3) ν_GHz^0.6 D_kpc⁻² γ^(2/3) g^(2/3) Z^(4/3)  [mJy]
// (Ṁ in 10⁻⁶ M☉/yr, v∞ km/s, ν GHz, D kpc.) We want a LUMINOSITY (distance cancels under
// per-peak normalization), so L_ν = 4πD²·S_ν at D = 1 kpc:
//   L_ν,wind = K_LNU · (Ṁ₋₆/(μ v∞))^(4/3) · g^(2/3) · ν_GHz^0.6   [erg/s/Hz],
//   K_LNU = 4π(kpc in cm)² · 23.2e-26.
// Then L_λ = L_ν·c/λ², placed on the panel by ratio against the blackbody's OWN peak
// luminosity L_λ,BB,peak = 4πR²·πB_λ(λpeak) (R² INCLUDED — the BB curve self-normalizes,
// but the wind must reference the SAME absolute peak to share the axis: dec = 0 ≙ the BB
// peak for both).
//
// MEASURE-FIRST VERIFICATION (the "one open number" the plan flagged — resolved against
// primary sources, NOT calibrated to any in-house value):
//   • Coefficient at FACE value lands ζ Pup at ≈0.26 mJy@5 GHz vs ~1.5 observed — 0.7 dex
//     low, the EXPECTED smooth-Vink-Ṁ-vs-clumped-observation gap, not a unit error.
//   • The BB normalization checks to 0.2% (∫L_λ = 4πR²σT⁴ = MIST L; L_λ,peak·1.521·λpeak
//     = L_bol). So the placement is sound and the plan's old table was ~4 dex too bright.
//   • The visible excess is a mid/far-IR → sub-mm feature (peaks ~35–260 µm) for EVOLVED
//     hot supergiants (strong winds, Ṁ up to ~7e-5); ZAMS O stars sit near/below the floor.
//     The SELF-GATING draw (only where wind > BB, exit at the floor) yields exactly that
//     with no regime special-casing.
// The LEVEL carries ±~dex (v∞ across the ~21 kK bistability jump where v∞/v_esc drops from
// ~2.6 toward ~1.3, + wind clumping); the SLOPE (λ⁻²·⁶) is the robust, teachable part.
const WIND_TEFF_MIN = 12000;        // below this the wind is dusty/molecular, not ionized free–free
const WIND_MDOT_MIN = 1e-9;         // |Ṁ| (M☉/yr) below which there is no meaningful wind
const WIND_MU = 1.4, WIND_Z = 1, WIND_GAMMA = 1;   // ionized OB-wind composition (μ per ion, charge, e⁻/ion)
const WIND_NU_REF_GHZ = 230;        // fix the Gaunt factor at this ν → a clean λ⁻²·⁶ slope
const VINF_OVER_VESC = 2.6;         // Lamers & Cassinelli hot-star ratio (level ±dex — see note)
// cgs constants for the absolute L_λ,wind / L_λ,BB,peak ratio.
const CGS_G = 6.674e-8, CGS_MSUN = 1.989e33, CGS_RSUN = 6.957e10, CGS_KPC = 3.086e21;
const CGS_H = 6.626e-27, CGS_C = 2.998e10, CGS_K = 1.381e-16;
const WIND_K_LNU = 4 * Math.PI * CGS_KPC ** 2 * 23.2e-26;   // L_ν = K·X  [erg/s/Hz] at D = 1 kpc
const COL_WIND = "rgba(130,222,176,0.95)";                  // teal-green: the data-grounded tier

// Free–free Gaunt factor (Wright & Barlow): g_ν = 9.77(1 + 0.13·log₁₀(T_e^1.5/(Zν))).
function gauntFF(nuGHz, Te) {
  return 9.77 * (1 + 0.13 * Math.log10(Te ** 1.5 / (WIND_Z * nuGHz)));
}
// Planck B_λ in cgs (erg s⁻¹ cm⁻² cm⁻¹ sr⁻¹) — the absolute form the wind ratio needs.
function planckCgs(lamCm, T) {
  const x = CGS_H * CGS_C / (lamCm * CGS_K * T);
  if (x > 700) return 0;                                    // Wien underflow guard
  return (2 * CGS_H * CGS_C ** 2 / lamCm ** 5) / Math.expm1(x);
}

// ─── Chunk 3: collapse the X-ray BAND to a LINE via rotation (gyrochronology) ───
// The Chunk-1 band is wide only because ONE dimension is missing — rotation. The
// rotation–activity dynamo (Wright 2011) fixes L_X/L_bol from the Rossby number
// Ro = P_rot/τ_conv, so supplying P_rot collapses the band to a line — kept with a
// FUZZ (the relation carries ~0.4–0.5 dex scatter + a ~10× activity-cycle wobble, so
// a razor-thin line would be the fake-precision trap the project guards against).
// Two honest sources of P_rot, an upgrade ladder ON TOP of the band:
//   (a) DERIVED from the age the sim already carries, via gyrochronology — but only
//       for a main-sequence cool star (the convective-dynamo regime), and
//   (b) a USER slider that PINS rotation directly (the Lane–Emden-n precedent: the
//       user supplies the dimension the sim won't fabricate from a Teff ramp).
//
// ONE self-consistent calibration — do NOT mix scales (Ro_sat/β are defined with
// Wright's OWN τ; pairing them with e.g. Noyes 1984 τ silently shifts the zero-point
// off the Sun). Wright (2011) throughout: mass-based τ_conv(M) + Ro_sat = 0.13,
// β = −2.7, saturated log(L_X/L_bol) = −3.13. This chain lands the Sun at
// L_X/L_bol ≈ 10^−6.2 (observed ~10^−6.3) — the cross-check anchor. Refs: Mamajek &
// Hillenbrand 2008 (gyro P_rot = a·[(B−V)−c]^b·t^n); Ballesteros 2012 (Teff↔B−V);
// Wright 2011 (τ_conv(M), rotation–activity); van Saders 2016 (weakened braking).
const ROT_SAT = 0.13;            // Wright 2011 saturation Rossby number
const ROT_BETA = -2.7;           // Wright 2011 unsaturated slope
const LXLB_SAT_LOG = -3.13;      // Wright 2011 saturated log10(L_X/L_bol)
const LXLB_FLOOR_LOG = -7;       // quiet end of the activity band (the display clamp)
const MH_A = 0.407, MH_B = 0.325, MH_C = 0.495, MH_N = 0.566;   // Mamajek–Hillenbrand 2008
// Gate the gyro line REDWARD of the (B−V)=0.495 singularity: just blueward the term
// [(B−V)−0.495]^0.325 is NaN (a fractional power of a negative), and just redward it
// → 0 → P_rot → 0 → a spurious "saturated" verdict. 0.55 (≈ Teff 6150 K) is safely past.
const GYRO_BV_MIN = 0.55;
const GYRO_BV_MAX = 1.40;        // MH08 is calibrated to ~K; redder (M) is flagged extrapolation
const YOUNG_MYR = 300;           // younger: rotation hasn't converged → no age-derived line
const OLD_MYR = 4600;            // older (van Saders): braking weakens → wider fuzz, flagged

// Teff → (B−V)₀, inverting Ballesteros (2012):
//   T = 4600·[1/(0.92(B−V)+1.7) + 1/(0.92(B−V)+0.62)]  → a quadratic in u = 0.92(B−V).
// (Sun T=5772 → B−V≈0.65 ✓.) Returns null if no real positive root.
function teffToBV(t) {
  const k = t / 4600;
  const a = k, b = 2.32 * k - 2, c = 1.054 * k - 2.32;
  const disc = b * b - 4 * a * c;
  if (disc < 0) return null;
  return ((-b + Math.sqrt(disc)) / (2 * a)) / 0.92;
}

// Wright (2011) mass-based convective turnover time, days:
//   log10 τ_conv = 1.16 − 1.49·log10 M − 0.54·(log10 M)²   (M in M_sun).
function tauConvDays(massMsun) {
  const lm = Math.log10(Math.max(0.1, massMsun));
  return 10 ** (1.16 - 1.49 * lm - 0.54 * lm * lm);
}

// Mamajek & Hillenbrand (2008) gyrochronology rotation period (days). null blueward
// of the singularity (the caller also gates on GYRO_BV_MIN).
function gyroProtDays(bv, ageMyr) {
  if (bv == null || bv <= MH_C) return null;
  return MH_A * Math.pow(bv - MH_C, MH_B) * Math.pow(ageMyr, MH_N);
}

// Wright (2011) rotation–activity: log10(L_X/L_bol) from P_rot. SATURATES (plateaus)
// at Ro_sat — it must NOT keep climbing for Ro < Ro_sat.
function lxlbLogFromProt(protDays, massMsun) {
  const ro = protDays / tauConvDays(massMsun);
  if (ro <= ROT_SAT) return LXLB_SAT_LOG;
  return LXLB_SAT_LOG + ROT_BETA * Math.log10(ro / ROT_SAT);
}

// The rotation slider's period domain (days, log-spaced) + its landmark presets.
const PROT_MIN_D = 0.3, PROT_MAX_D = 70;
const PROT_PRESETS = [
  { d: 1,  label: "1 d" },    // fast young rotator — saturated
  { d: 5,  label: "5 d" },
  { d: 12, label: "12 d" },
  { d: 25, label: "25 d" },   // ≈ the present Sun
  { d: 50, label: "50 d" },   // slow / old
];
const protToFrac = (d) =>
  (Math.log10(d) - Math.log10(PROT_MIN_D)) / (Math.log10(PROT_MAX_D) - Math.log10(PROT_MIN_D));
const fracToProt = (v) =>
  10 ** (Math.log10(PROT_MIN_D) + v * (Math.log10(PROT_MAX_D) - Math.log10(PROT_MIN_D)));

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

  let teff = null, logg = null, age = null, phase = null, mass = null, feh = null;
  // Chunk 2 (wind free–free): the radius + mass-loss rate the tail needs. Both are
  // marker-state quantities now on the spine (R_rsun always; mdot_msun_yr via the
  // Mdot blend), so this stays a pure sibling — no fetch.
  let rRsun = null, mdot = null;
  // Endgame (WD) mode: the non-thermal overlay is NOT suppressed outright — it is faded
  // by a degeneracy gate (the same (4−logg)/3 the 3D corona/granulation use), so the
  // thermally-pulsing AGB giant the endgame opens on keeps the (suppressed) coronal band
  // it had as a living star — a CONTINUATION across the gateway, not an abrupt vanish —
  // and the band fades to nothing as the bared core contracts into a degenerate remnant
  // (no convective dynamo; a cold WD at logg ~8 must NOT trip the cool-dwarf band — the
  // gate → 0 there guarantees it). The blackbody curve is always fine (the hot central
  // star peaks in the UV, the cold cinder in the IR). Set via update(state,{endgame}).
  let endgameMode = false;
  // WR endgame: suppress the coronal X-ray overlay ENTIRELY — a Wolf–Rayet is wind-driven,
  // not a cool convective dynamo, so its non-thermal emission is wind free–free radio
  // (SED Chunk 2), never a coronal band. (The WD path above keeps a degeneracy-gated band;
  // WR is a different physical object that must not borrow it. The blackbody continuum is
  // honest as-is — a stripped hot core peaks in the far-UV / soft X-ray.)
  let endgameWR = false;
  // SN endgame: like WR, the expanding ejecta photosphere is no dynamo corona — suppress
  // the coronal X-ray band entirely; only the (honest) blackbody continuum is drawn.
  let endgameSN = false;
  // Rotation state (Chunk 3): protAuto = the age-derived default (null when out of the
  // gyro-valid domain); userProt = a manual slider override (null = follow the
  // default). gyroFlag carries an honesty note ("young"/"old"/"mdwarf"/"warm").
  let protAuto = null, userProt = null, gyroFlag = "";

  const xOf = (lamNm) =>
    PAD_L + (Math.log10(lamNm) - LOG_LO) / (LOG_HI - LOG_LO) * plotW;
  // y maps decades-below-peak: 0 dex (peak) at the top, −FLOOR_DECADES at the axis.
  const yOf = (dec) =>
    PAD_T + (-dec / FLOOR_DECADES) * (H - PAD_T - PAD_B);

  function update(state, opts) {
    if (!state || state.Teff_K == null) return;
    const egKind = opts && opts.endgame;   // true/"wd" (WD) | "wr" (Wolf–Rayet)
    const eg = !!egKind;
    // The redraw key (Chunk 3): logg gates the band (dwarf dynamo vs cool-giant
    // suppressed corona); age/phase/mass drive the gyrochronology line; [Fe/H] only
    // matters as part of the "is this a new star?" test for the override reset.
    const g = state.logg ?? null;
    const a = state.age_yr ?? null;
    const ph = state.phase ?? null;
    const m = state.mass_init_msun ?? null;
    const fe = state.feh_init ?? null;
    const rr = state.R_rsun ?? null;
    const md = state.mdot_msun_yr ?? null;   // signed <= 0 (mass loss); |·| used below
    if (eg === endgameMode && state.Teff_K === teff && g === logg && a === age &&
        ph === phase && m === mass && fe === feh && rr === rRsun && md === mdot) return;
    endgameMode = eg;
    endgameWR = egKind === "wr";
    endgameSN = egKind === "sn";
    // A NEW star (mass or [Fe/H] changed) clears any manual rotation override; scrubbing
    // age alone KEEPS it (so you can hold a rotation and watch the X-rays evolve).
    if (m !== mass || fe !== feh) userProt = null;
    teff = state.Teff_K; logg = g; age = a; phase = ph; mass = m; feh = fe;
    rRsun = rr; mdot = md;
    recomputeRotation();
    draw();
    renderCaption();
    rot.sync();
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

    // The non-thermal coronal overlay. Living: drawn per regime. WD endgame: faded by
    // the degeneracy gate (the same (4−logg)/3 the 3D corona/granulation use), so the
    // AGB giant the endgame opens on keeps the band it had as a living star (continuity
    // across the gateway) and it dies with the dynamo as the remnant degenerates.
    if (!endgameMode) {
      drawActivity(lamPeak);
      // The hot-star wind free–free excess (Chunk 2): the data-grounded solid line, drawn
      // for a living hot massive star (gated inside; WR-endgame is out of scope for v1).
      drawWindFreeFree(lamPeak);
    } else if (!endgameWR && !endgameSN) {
      const gDeg = Math.max(0, Math.min(1, (4 - (logg ?? 8)) / 3));
      if (gDeg > 0.01) drawActivity(lamPeak, gDeg, true);   // WD endgame: dying-giant band only
    }
    // WR / SN: no coronal overlay at all (wind / freely-expanding ejecta, not a dynamo) —
    // just the honest blackbody continuum of the expanding photosphere.
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

  const smoothstep = (a, b, x) => {
    const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
    return t * t * (3 - 2 * t);
  };
  const lerp = (a, b, t) => a + (b - a) * t;

  // The coronal soft-X-ray ACTIVITY overlay (+ its Güdel–Benz radio marker). The
  // regime boundaries are physically FUZZY — the convective-dynamo X-ray decline
  // across the Kraft break (~6200 K) is gradual, not a cliff at 6500 K, and wind
  // shocks switch on over a range near ~10⁴ K — so the overlay MORPHS as you scrub
  // Teff instead of snapping on/off at a hard edge. Across the cool↔gap edge the
  // band's saturated ceiling descends until the ribbon collapses into the faint
  // dashed "X-ray gap" sliver right where it lands (one object shrinking, not two
  // ghosts crossfading); the secondary gap↔hot edge is a plain alpha crossfade.
  // Drawn hatched/translucent throughout — a RANGE we can't pin, never a crisp line
  // (see the header note). lamPeak is the Fλ peak wavelength in nm. `fade`/`endgame` are
  // the WD path only: when endgame, draw a single dimmed band at alpha `fade` (the
  // degeneracy gate) and skip the living regime machinery (see the block below + draw()).
  function drawActivity(lamPeak, fade = 1, endgame = false) {
    const logW = Math.log10(BB_EFF_WIDTH * lamPeak / XRAY_DLAM);
    const decFromLog = (logFx) => logFx + logW;             // dec below the BB peak Fλ

    // WD endgame: the only honest non-thermal feature is the dying giant's SUPPRESSED
    // corona, fading as the bared core degenerates — never a cool main-sequence dynamo
    // (the post-AGB contraction is NOT a dynamo star) nor the A/F-gap / O-wind branches.
    // So draw just the dimmed band at the degeneracy-gated alpha, with NO Teff-regime
    // switches: the contraction races up through ~5000–6500 K in a row or two, and the
    // hard coolgiant→cool branch boundary there would briefly flash the band UP to the
    // brighter dynamo level (measured: a 1-row pop for ~2 M☉ progenitors). One dimmed
    // band fading monotonically with gDeg is both smoother and more honest.
    if (endgame) {
      drawXrayBand(decFromLog, { logHi: -5, logLo: -8, dim: true,
        tag: "coronal X-ray", topLabel: "10⁻⁵", botLabel: "10⁻⁸", alpha: fade });
      drawGudelBenzRadio(lamPeak, 1e-5, fade);
      return;
    }

    // A cool LUMINOUS giant's corona is suppressed past the Linsky–Haisch dividing
    // line — a dimmed, capped band. It lives far below the warm-edge transitions
    // (Teff < 5000 K), so it stays a discrete branch, no morph. (This is also the branch
    // the living EAGB giant shows just before the gateway — so the endgame's identical
    // dimmed band above lands continuous across the click.)
    if (logg != null && logg < 3.0 && teff < 5000) {
      drawXrayBand(decFromLog, { logHi: -5, logLo: -8, dim: true,
        tag: "coronal X-ray", topLabel: "10⁻⁵", botLabel: "10⁻⁸", alpha: 1 });
      drawGudelBenzRadio(lamPeak, 1e-5, 1);
      return;
    }

    // Transition weights across the nominal (fuzzy) boundaries.
    const gapW = smoothstep(6100, 6900, teff);   // 0 cool dynamo → 1 A/early-F gap
    const hotW = smoothstep(9500, 10500, teff);  // 0 gap        → 1 O/B wind shocks

    // (1) The cool convective-dynamo band: its saturated ceiling descends from 10⁻³
    //     toward the quiet level as gapW→1, the whole ribbon fading out as it
    //     collapses — so it SHRINKS into the gap rather than vanishing abruptly.
    const coolA = 1 - gapW;
    if (coolA > 0.01) {
      // The band's CURRENT decade range — its top descends from 10⁻³ toward 10⁻⁶ as the
      // cool dynamo weakens into the gap (gapW→1). The rotation line below is clamped to
      // this SAME top, so it can't escape ABOVE the band once the top has dropped — the
      // "rotation set band beyond the X-ray limits" bug for a warm ~6400 K dwarf (1.29
      // M☉), where the band sits at ~10⁻³·⁹ but the saturated level is 10⁻³·¹³.
      const bandHi = lerp(-3, -6, gapW), bandLo = -7;
      drawXrayBand(decFromLog, { logHi: bandHi, logLo: bandLo, dim: false,
        tag: "coronal X-ray", topLabel: "10⁻³", botLabel: "10⁻⁷", alpha: coolA });
      drawGudelBenzRadio(lamPeak, 1e-3, coolA);
      // (1b) The rotation→X-ray LINE collapsing the band (Chunk 3): cool branch ONLY,
      //      its alpha tied to coolA so it fades WITH the band across the cool→gap morph.
      const line = activityLine();
      if (line) drawActivityLine(decFromLog, line, coolA, bandHi, bandLo);
    }

    // (2) The A/early-F X-ray gap: a faint dashed marker that fades IN only in the
    //     second half of the cool→gap transition — by then the band has collapsed
    //     onto its level, so the two read as ONE morph, not a double image — then
    //     back OUT as wind shocks take over toward the hot edge.
    const gapA = smoothstep(6500, 6900, teff) * (1 - hotW);
    if (gapA > 0.01) drawXrayGap(lamPeak, gapA);

    // (3) The O/B wind-shock band (~10⁻⁷): a plain crossfade in across the hot edge.
    if (hotW > 0.01) {
      drawXrayBand(decFromLog, { logHi: -6.5, logLo: -7.5, dim: false,
        tag: "wind X-ray ~10⁻⁷", topLabel: "", botLabel: "", alpha: hotW });
    }
  }

  // Draw one hatched, translucent L_X/L_bol band between two decade levels
  // (o.logLo/o.logHi = log10 L_X/L_bol). o.alpha drives the whole group so a band can
  // fade across a regime transition. Edge labels are the explicit guard against
  // reading a pixel-precise flux; they ride the same alpha (text can't interpolate, so
  // it dissolves with the band rather than popping). decFromLog maps log fx → dec.
  function drawXrayBand(decFromLog, o) {
    const decTop = Math.min(0, decFromLog(o.logHi));
    const decBot = Math.max(-FLOOR_DECADES, decFromLog(o.logLo));
    if (decTop <= decBot) return;
    const x0 = xOf(XRAY_LO), x1 = xOf(XRAY_HI);
    const yTop = yOf(decTop), yBot = yOf(decBot), hh = yBot - yTop;

    // translucent fill + diagonal hatch = the "evocative range" styling.
    ctx.save();
    ctx.globalAlpha = o.alpha;
    ctx.fillStyle = `rgba(255,140,110,${o.dim ? 0.10 : 0.18})`;
    ctx.fillRect(x0, yTop, x1 - x0, hh);
    ctx.beginPath(); ctx.rect(x0, yTop, x1 - x0, hh); ctx.clip();
    ctx.strokeStyle = `rgba(255,170,135,${o.dim ? 0.22 : 0.4})`; ctx.lineWidth = 1;
    for (let p = x0 - hh; p < x1; p += 7) {
      ctx.beginPath(); ctx.moveTo(p, yBot); ctx.lineTo(p + hh, yTop); ctx.stroke();
    }
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = o.alpha;
    // solid top/bottom edges
    ctx.strokeStyle = `rgba(255,175,145,${o.dim ? 0.55 : 0.85})`; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(x0, yTop); ctx.lineTo(x1, yTop); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x0, yBot); ctx.lineTo(x1, yBot); ctx.stroke();
    // The dimensionless L_X/L_bol edge labels + the mechanism tag.
    ctx.fillStyle = "#ff9e85"; ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "right";
    if (o.topLabel && decFromLog(o.logHi) <= 0) ctx.fillText(o.topLabel, x1 - 2, yTop + 10);
    if (o.botLabel && decFromLog(o.logLo) >= -FLOOR_DECADES) ctx.fillText(o.botLabel, x1 - 2, yBot - 3);
    ctx.textAlign = "center";
    ctx.fillText(o.tag, (x0 + x1) / 2, yTop - 4);
    ctx.textAlign = "left";
    ctx.restore();
  }

  // The A / early-F X-ray gap: a faint, dashed, clearly-LABELLED "X-ray gap" marker in
  // the soft-X-ray band — the steady-state representation the collapsing cool band
  // morphs INTO (and which fades, via alpha, across both edges so nothing pops). It is
  // honest (no fake flux band) and the placement level is nominal (the point is the
  // label, not a value: A/early-F stars are X-ray-faint — no convective dynamo, no
  // strong wind shocks). Caption-free on purpose: the "gap" caption branch is already
  // length-matched (lengthening it would resize the panel as you scrub — the jank this
  // whole panel guards against).
  function drawXrayGap(lamPeak, alpha = 1) {
    const w = BB_EFF_WIDTH * lamPeak / XRAY_DLAM;
    let dec = Math.log10(1e-6) + Math.log10(w);          // nominal quiet level
    dec = Math.max(-FLOOR_DECADES + 2, Math.min(-2, dec)); // keep it clearly in-frame
    const x0 = xOf(XRAY_LO), x1 = xOf(XRAY_HI), y = yOf(dec);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = "rgba(150,160,180,0.55)"; ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#9aa6bd"; ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("X-ray gap", (x0 + x1) / 2, y - 4);
    ctx.textAlign = "left";
    ctx.restore();
  }

  // The Güdel–Benz radio counterpart of the X-ray band, anchored at the cm-wave (GHz)
  // position. On this per-wavelength axis it sits below the window for normal stars —
  // drawn as a short tick rising from the floor (clamped) to its highest (saturated)
  // level, a compact footnote to the X-ray band rather than a competing ribbon.
  function drawGudelBenzRadio(lamPeak, fxHi, alpha = 1) {
    const xr = xOf(LAM_RADIO);
    const decR = Math.log10(fxHi) + Math.log10(BB_EFF_WIDTH * lamPeak)
      + Math.log10(C_NM_S) - GB_LOG_HZ - 2 * Math.log10(LAM_RADIO);
    const yFloor = yOf(-FLOOR_DECADES);
    const yTop = yOf(Math.min(0, Math.max(decR, -FLOOR_DECADES)));   // clamped to window
    ctx.save();
    ctx.globalAlpha = alpha;
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
    ctx.restore();
  }

  // ─── Chunk 2: the hot-star wind free–free tail (the data-grounded tier) ───────

  // Build the wind's dec(λnm) closure for the current marker, or null when the gate is
  // closed: cool/dusty wind (Teff < WIND_TEFF_MIN), negligible Ṁ, or missing R/mass.
  // dec = log₁₀(L_λ,wind / L_λ,BB,peak) — the SAME axis as the blackbody curve (0 = peak).
  // The Gaunt factor is fixed at WIND_NU_REF_GHZ so the line is a clean λ⁻²·⁶ slope.
  function windDecFn(lamPeakNm) {
    if (teff == null || teff < WIND_TEFF_MIN) return null;
    if (mdot == null || rRsun == null || mass == null) return null;
    const mdotAbs = Math.abs(mdot);
    if (mdotAbs < WIND_MDOT_MIN) return null;
    const R = rRsun * CGS_RSUN;
    const vinf = VINF_OVER_VESC * Math.sqrt(2 * CGS_G * mass * CGS_MSUN / R) / 1e5;  // km/s
    const g = gauntFF(WIND_NU_REF_GHZ, 0.5 * teff);    // wind T_e ≈ ½ Teff (standard, weak)
    const md6 = mdotAbs / 1e-6;
    const base = Math.pow(md6 / (WIND_MU * vinf), 4 / 3)
      * Math.pow(WIND_GAMMA, 2 / 3) * Math.pow(g, 2 / 3) * Math.pow(WIND_Z, 4 / 3);
    const Lbbpeak = 4 * Math.PI * R * R * Math.PI * planckCgs(lamPeakNm * 1e-7, teff);
    return (lamNm) => {
      const lamCm = lamNm * 1e-7;
      const nuGHz = CGS_C / lamCm / 1e9;
      const Lnu = WIND_K_LNU * base * Math.pow(nuGHz, 0.6);    // erg/s/Hz
      const Llam = Lnu * CGS_C / (lamCm * lamCm);              // erg/s/cm
      return Math.log10(Llam / Lbbpeak);
    };
  }

  // Draw the wind free–free excess as a SOLID line, but ONLY where it exceeds the
  // photospheric blackbody at that λ (the crossover IS the payoff) and stays in-window —
  // letting it exit the bottom past the sub-mm (the panel's clamp-and-exit idiom, no fake
  // line across the empty radio). Self-gating: a ZAMS O star draws ~nothing (its tail sits
  // below the floor), an evolved hot supergiant draws a clear mid/far-IR → sub-mm excess.
  function drawWindFreeFree(lamPeakNm) {
    const dec = windDecFn(lamPeakNm);
    if (!dec) return;
    const logBpCgs = Math.log10(planckCgs(lamPeakNm * 1e-7, teff));  // BB self-norm reference
    const N = 480;
    ctx.save();
    ctx.strokeStyle = COL_WIND; ctx.lineWidth = 1.8;
    let drawing = false, best = null;                  // best = brightest drawn point (label anchor)
    for (let i = 0; i < N; i++) {
      const lam = 10 ** (LOG_LO + (i / (N - 1)) * (LOG_HI - LOG_LO));
      const dW = dec(lam);
      const b = planckCgs(lam * 1e-7, teff);
      const dB = b > 0 ? Math.log10(b) - logBpCgs : -FLOOR_DECADES;   // the BB curve's dec at λ
      // Only on the long-wavelength (Rayleigh–Jeans) side, where the optically-thick
      // free–free model applies AND the excess is real: redward of the Wien peak, where
      // the wind tops the photosphere and stays in-window. (Blueward, the BB has
      // underflowed to the floor — "wind > floored BB" is meaningless, and the λ⁻²·⁶
      // model doesn't hold in the X-ray/UV; without this it would smear across the top.)
      const vis = lam > lamPeakNm && dW > dB && dW > -FLOOR_DECADES;
      if (vis) {
        const x = xOf(lam), y = yOf(Math.min(0, dW));
        drawing ? ctx.lineTo(x, y) : (ctx.beginPath(), ctx.moveTo(x, y));
        drawing = true;
        if (!best || dW > best.dec) best = { dec: dW, x, y, lam };
      } else if (drawing) { ctx.stroke(); drawing = false; }
    }
    if (drawing) ctx.stroke();
    if (best) {
      ctx.fillStyle = "#9fe9c6"; ctx.font = "9px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("wind free–free (Ṁ)", best.x, best.y - 5);
      ctx.textAlign = "left";
    }
    ctx.restore();
  }

  // ─── Chunk 3 helpers: the rotation→X-ray line, its gate, and its slider ───────

  // A rotation→X-ray LINE is meaningful ONLY for a cool main-sequence star with a
  // convective dynamo. Hot (no dynamo), the A/F gap, an evolved giant, and the
  // suppressed-corona cool giant all keep the band/gap/wind branch — a rotation value
  // cannot manufacture a dynamo corona there, so the slider's effect is gated to this.
  function dynamoLineAllowed() {
    if (phase !== "MS") return false;
    if (teff == null || teff >= 6500) return false;
    if (logg != null && logg < 3.0 && teff < 5000) return false;   // cool giant
    return true;
  }

  // Compute the age-derived default P_rot (protAuto) + an honesty flag (gyroFlag) for
  // the caption/fuzz. Null outside the gyro-valid domain — then only a USER slider
  // value yields a line. Called on every state change.
  function recomputeRotation() {
    protAuto = null; gyroFlag = "";
    if (!dynamoLineAllowed() || age == null) return;
    const bv = teffToBV(teff);
    if (bv == null || bv < GYRO_BV_MIN) { gyroFlag = "warm"; return; } // F-edge: no clean gyro
    const ageMyr = age / 1e6;
    if (ageMyr < YOUNG_MYR) { gyroFlag = "young"; return; }           // spin unconverged
    protAuto = gyroProtDays(bv, ageMyr);
    if (ageMyr > OLD_MYR) gyroFlag = "old";          // van Saders: braking weakens → wide fuzz
    else if (bv > GYRO_BV_MAX) gyroFlag = "mdwarf";  // MH08 extrapolated past ~K → wide fuzz
  }

  // The effective L_X/L_bol LINE for the current view, or null. Uses the user's pinned
  // P_rot if set, else the age-derived default; carries the source + an honest fuzz.
  function activityLine() {
    if (!dynamoLineAllowed()) return null;
    const prot = userProt ?? protAuto;
    if (prot == null) return null;
    const lxlbLog = lxlbLogFromProt(prot, mass ?? 1);
    // Base ~0.45 dex (Wright scatter + the activity-cycle wobble); wider where the
    // age-derived relation is extrapolated/uncertain (a pinned value keeps the base).
    let fuzz = 0.45;
    if (userProt == null && (gyroFlag === "old" || gyroFlag === "mdwarf")) fuzz = 0.7;
    return { lxlbLog, fuzz, src: userProt != null ? "set" : "age" };
  }

  // Draw the line + its ±fuzz envelope across the soft-X-ray band, clamped into the
  // band's CURRENT [bandLo, bandHi] range so it always reads INSIDE the envelope —
  // including where the band top has descended toward the X-ray gap (passed in by the
  // caller as lerp(-3,-6,gapW)). Cool blue — distinct from the coral evocative band:
  // this is the more-concrete rung of the ladder (a single rotation→activity value, not
  // the whole range). alpha fades it with the band across the cool→gap morph. NOTE: when
  // the band top has dropped below the saturated level (~10⁻³·¹³) this clamp slightly
  // understates that level — an accepted, minimal compromise vs. a line floating above
  // its own band.
  function drawActivityLine(decFromLog, line, alpha, bandHi, bandLo) {
    const lx = Math.min(bandHi, Math.max(bandLo, line.lxlbLog));
    const decMid = decFromLog(lx);
    const decHi = Math.min(0, decFromLog(Math.min(bandHi, lx + line.fuzz)));
    const decLo = Math.max(-FLOOR_DECADES, decFromLog(Math.max(bandLo, lx - line.fuzz)));
    const x0 = xOf(XRAY_LO), x1 = xOf(XRAY_HI);
    const yMid = yOf(decMid), yHi = yOf(decHi), yLo = yOf(decLo);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = "rgba(120,200,255,0.16)";
    ctx.fillRect(x0, yHi, x1 - x0, yLo - yHi);
    ctx.strokeStyle = "rgba(150,210,255,0.95)"; ctx.lineWidth = 1.8;
    ctx.beginPath(); ctx.moveTo(x0, yMid); ctx.lineTo(x1, yMid); ctx.stroke();
    ctx.fillStyle = "#bfe0ff"; ctx.font = "9px system-ui, sans-serif";
    ctx.textAlign = "left";
    // Below the line, not above: when a saturated fast rotator pins the line to the
    // band's top edge, a label above would collide with the band's own "coronal X-ray"
    // tag — keeping it under the line stays clear of that tag and inside the envelope.
    ctx.fillText(line.src === "set" ? "rotation set" : "age-derived", x0 + 2, yMid + 11);
    ctx.restore();
    ctx.textAlign = "left";
  }

  // The rotation/activity slider (Chunk 3) — a sed.js-local control like lane.js's
  // n-slider, no spine touch. It DEFAULTS from age (gyrochronology) and the user can
  // drag to override for the current star; the override is cleared on a star change
  // (see update()). Its effect is gated to the cool-MS dynamo regime: disabled and
  // grayed elsewhere (a rotation value can't make an O-star or a giant a dynamo).
  function setupRotControl() {
    const wrap = document.getElementById("sed-rot");
    const slider = document.getElementById("sed-prot");
    const num = document.getElementById("sed-prot-num");
    const marksEl = document.getElementById("sed-prot-marks");
    const note = document.getElementById("sed-rot-note");
    const resetBtn = document.getElementById("sed-rot-reset");
    if (!slider) return { sync() {} };

    slider.min = 0; slider.max = 1; slider.step = 0.001;
    if (num) { num.min = PROT_MIN_D; num.max = PROT_MAX_D; num.step = 0.5; }
    if (marksEl) marksEl.innerHTML = PROT_PRESETS.map((p) => {
      const left = (protToFrac(p.d) * 100).toFixed(2);
      return `<span class="tick" style="left:${left}%">` +
        `<span class="tick-label">${p.label}</span></span>`;
    }).join("");

    // Snap a raw period to the nearest preset within a small window (in slider-fraction
    // units, so it's magnetic, not grabby); the number box bypasses snapping.
    function snap(d) {
      const v = protToFrac(d);
      let best = d, bestD = 0.04;
      for (const p of PROT_PRESETS) {
        const dd = Math.abs(v - protToFrac(p.d));
        if (dd < bestD) { bestD = dd; best = p.d; }
      }
      return best;
    }

    slider.addEventListener("input", () => {
      userProt = snap(fracToProt(Number(slider.value)));
      sync(); draw(); renderCaption();
    });
    if (num) num.addEventListener("change", () => {
      if (num.value.trim() === "") return;
      let d = Number(num.value);
      if (!isFinite(d)) return;
      userProt = Math.min(Math.max(d, PROT_MIN_D), PROT_MAX_D);
      sync(); draw(); renderCaption();
    });
    if (resetBtn) resetBtn.addEventListener("click", () => {
      userProt = null;
      sync(); draw(); renderCaption();
    });

    function sync() {
      const allowed = dynamoLineAllowed();
      const eff = userProt ?? protAuto;
      if (wrap) wrap.classList.toggle("disabled", !allowed);
      slider.disabled = !allowed;
      if (num) num.disabled = !allowed;
      if (eff != null) {
        slider.value = protToFrac(eff);
        if (num && document.activeElement !== num) num.value = Number(eff.toPrecision(3));
      }
      if (resetBtn) resetBtn.hidden = (userProt == null);
      if (note) note.textContent = rotNote(allowed, eff);
    }

    // Short status line under the slider (its own element, so its length doesn't drive
    // the caption/canvas resize — kept terse anyway, with a reserved height in CSS).
    function rotNote(allowed, eff) {
      if (!allowed) return "Rotation → X-ray line: cool main-sequence stars only (no dynamo here).";
      if (eff == null) return gyroFlag === "warm"
        ? "No clean age–rotation relation near the F/G boundary — drag to pin a period."
        : "Too young to derive rotation from age — drag to pin a period.";
      const src = userProt != null ? "set by you" : "from age";
      let flag = "";
      // Below the saturation Rossby number the rotation–activity law plateaus: a faster
      // spin no longer raises L_X/L_bol, so the line stops moving as the slider drops
      // past ~Ro_sat·τ_conv (≈1.3 d for the Sun-like τ here). Say so — otherwise the
      // frozen line at the fast end reads as a bug ("nothing happens below ~1 day").
      if (eff / tauConvDays(mass ?? 1) <= ROT_SAT)
        flag = " · saturated: faster spin won't raise X-rays";
      else if (userProt == null && gyroFlag === "old") flag = " · old star: braking weakens, wide uncertainty";
      else if (userProt == null && gyroFlag === "mdwarf") flag = " · M-dwarf: relation extrapolated";
      return `P_rot ≈ ${eff.toPrecision(3)} d (${src})${flag}.`;
    }

    return { sync };
  }
  const rot = setupRotControl();

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
    // Endgame — TWO distinct objects, two captions. WR must NOT inherit the WD text
    // (item 7): a Wolf–Rayet is a stripped hot core driving a dense wind, not a degenerate
    // remnant. No coronal band (wind, not dynamo); its free–free radio is the un-built
    // SED Chunk 2 (so honestly "not drawn"); and the un-modeled next step is core-collapse,
    // NOT a white dwarf. One fixed sentence for the whole WR scrub (Teff aside), like WD,
    // so scrubbing within the mode can't resize the panel.
    if (endgameSN) {
      caption.textContent =
        `Idealized blackbody at Teff ${Math.round(teff)} K — peaks at ${peakTxt} ` +
        `(${where}). This is the expanding supernova photosphere cooling as it grows — a ` +
        `freely-expanding ejecta shell, not a dynamo, so no coronal band. The light curve ` +
        `(not this blackbody) is the observable. γ-rays stay empty. Evocative, not predictive.`;
      return;
    }
    if (endgameWR) {
      caption.textContent =
        `Idealized blackbody at Teff ${Math.round(teff)} K — peaks at ${peakTxt} ` +
        `(${where}). This bared hot core blows a dense wind, not a dynamo — so no coronal ` +
        `band (its free–free radio isn't drawn); the un-modeled next step is core-collapse, ` +
        `not a white dwarf. γ-rays stay empty. Evocative, not predictive.`;
      return;
    }
    // Endgame (WD): the overlay fades over the scrub rather than vanishing — the AGB
    // giant still carries its suppressed coronal band; the degenerate remnant (no
    // convective dynamo) is left with none. One fixed-structure sentence for the whole
    // sequence (so scrubbing can't resize the panel). The blackbody is the through-line:
    // the hot central star peaks in the UV, the cold cinder in the IR.
    if (endgameMode) {
      caption.textContent =
        `Idealized blackbody at Teff ${Math.round(teff)} K — peaks at ${peakTxt} ` +
        `(${where}). The dying giant's evocative coronal X-ray band fades as the bared ` +
        `core contracts into a degenerate white dwarf, which has no convective dynamo. ` +
        `γ-rays stay empty. Evocative, not predictive.`;
      return;
    }

    const reg = regimeOf(teff, logg);
    let act;
    if (reg === "hot")
      // Two non-thermal features now: the coronal X-ray collapses to the wind-shock value,
      // AND (the Chunk-2 payoff) a SOLID mid/far-IR–sub-mm free–free excess from the dense
      // ionized wind — drawn from the real Ṁ where it clears the floor (evolved supergiants;
      // a ZAMS O star's is fainter). Slope λ⁻²·⁶ is robust; the level carries ±dex (v∞ +
      // clumping). Kept ~length-matched to the other branches (the panel-resize guard).
      // A GENERAL statement (not "the green line IS here"): the line is gated to strong
      // winds (Teff ≥ 12 kK, significant Ṁ), so a hot weak-wind B star draws nothing — the
      // caption must stay true with or without a drawn line (the "don't describe an absent
      // feature" trap), in one length-matched sentence.
      act = `Overlaid: X-rays collapse to the wind-shock ≈10⁻⁷ (no dynamo); a strong wind's ` +
            `free–free excess (green, real Ṁ) crests the floor in the far-IR for supergiants — ±dex.`;
    else if (reg === "gap")
      act = `No band drawn: A and early-F stars sit in an X-ray gap — too hot for a ` +
            `convective dynamo, too cool for strong wind shocks to make X-rays.`;
    else if (reg === "coolgiant")
      act = `Overlaid (coral, dimmed): a coronal X-ray band, but suppressed and ` +
            `uncertain past the Linsky–Haisch corona–wind dividing line — a guide only.`;
    else {
      // Cool branch — varies with whether a rotation LINE is drawn. Kept ~equal length
      // across variants (and to the other regimes) so scrubbing age / the slider can't
      // resize the panel (the resize jank this panel guards against).
      const line = activityLine();
      if (line && line.src === "age")
        act = `Overlaid: coral band L_X/L_bol ≈ 10⁻⁷…10⁻³, the blue line this star's ` +
              `age-derived rotation–activity level — kept with a ±dex fuzz, not a razor.`;
      else if (line)
        act = `Overlaid: coral band L_X/L_bol ≈ 10⁻⁷…10⁻³, the blue line YOUR pinned ` +
              `rotation–activity level — drag the rotation slider; kept with a ±dex fuzz.`;
      else if (gyroFlag === "young")
        act = `Overlaid (coral, hatched): the coronal band L_X/L_bol ≈ 10⁻⁷…10⁻³ — too ` +
              `young to pin a rotation line yet (spin unconverged); drag the slider to set one.`;
      else
        act = `Overlaid (coral, hatched): the coronal soft-X-ray band L_X/L_bol ≈ ` +
              `10⁻⁷…10⁻³ — a range; set the rotation slider below to collapse it to a line.`;
    }

    caption.textContent =
      `Idealized blackbody at Teff ${Math.round(teff)} K — peaks at ${peakTxt} ` +
      `(${where}). ${act} γ-rays stay empty. Evocative, not predictive.`;
  }

  // Whether the rotation→activity LINE is honest for the CURRENT marker (cool main-
  // sequence dynamo). This is the age-dependent per-marker gate; sed.js uses it itself
  // (rot.sync() greys the relocated period slider off the MS). Exposed as an accessor.
  // NOTE: main.js gates the period facet's *visibility* on the age-INDEPENDENT cool-MS
  // family instead (so it doesn't reflow above the Age slider mid-scrub), letting this
  // per-marker gate only grey/enable the slider — see coolDynamoFamily there.
  return { update, resize, rotationAllowed: () => dynamoLineAllowed() };
}
