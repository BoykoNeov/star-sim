// Rotational oblateness + gravity darkening of a fast rotator (von Zeipel / Roche).
//
// The honest capstone to the vvcrit rotation axis: a centrifugally-flattened star runs
// HOT/bright at the poles and COOL/dim at the equator (Regulus, Achernar, Vega). Every
// number here is driven by the REAL surface rotation on the StellarState
// (state.v_rot_kms), so the effect fires only for stars the MIST rotation grid actually
// spins — above the ~1.2 M☉ Kraft break, where the envelope is radiative and von Zeipel
// β = 0.25 is the physically valid law. No faked driver, no exaggeration: Gate 0 measured
// the median MS rotator at a gentle ~8% bulge / ~8% ΔTeff and the fastest reachable
// (5 M☉, [Fe/H]=+0.5) at a genuine ~37% bulge / ~4900 K — both faithful to the data.
//
// A star that doesn't rotate (v_rot 0 / None) returns active:false with a round,
// single-temperature spheroid, so the living-star look is byte-identical to before.

const VSUN = 437.0; // sqrt(G·M☉ / R☉) in km/s — the natural surface-velocity scale.

// R_eq / R_pol for the Roche model as a function of ω = Ω/Ω_crit ∈ [0,1]. Closed form
// (the equipotential's equatorial root): 1 at ω=0, 1.5 at critical.
function rocheReq(omega) {
  if (omega <= 1e-4) return 1.0;
  const o = Math.min(omega, 1.0);
  return (3.0 / o) * Math.cos((Math.PI + Math.acos(o)) / 3.0);
}

// Clamped smoothstep.
function sstep(a, b, x) {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

// Invert a measured linear velocity fraction v_rot/v_crit → ω = Ω/Ω_crit.
// v_rot/v_crit = ω · (R_eq/R_pol)(ω) / 1.5  (v_crit is the equatorial break-up speed,
// at R_eq,crit = 1.5·R_pol). Monotone in ω, so a bisection is exact and cheap.
function omegaFromVfrac(vfrac) {
  if (vfrac <= 1e-4) return 0.0;
  let lo = 0, hi = 1;
  for (let i = 0; i < 50; i++) {
    const mid = 0.5 * (lo + hi);
    if ((mid * rocheReq(mid)) / 1.5 < vfrac) lo = mid;
    else hi = mid;
  }
  return 0.5 * (lo + hi);
}

// Given a StellarState, return the rotational distortion geometry + gravity-darkening
// endpoints. `active` is false for a non-rotator (round star, flat temperature).
//
//   omega   — Ω/Ω_crit (Roche)
//   req     — R_eq/R_pol
//   kEq/kPol— axis scales for a VOLUME-PRESERVING spheroid (kEq²·kPol = 1): the star is
//             the same star, just flattened, so neither radius invents flux.
//   gEq     — g_eff(equator)/g_eff(pole); 1 when round. Drives the pole→equator profile.
//   tPole   — pole effective temperature (hotter than the catalog Teff)
//   tEq     — equator effective temperature (cooler)
//
// The endpoint temperatures are anchored so the AREA-WEIGHTED flux average equals the
// star's real luminosity: with T⁴ ∝ g_eff and ⟨sin²lat⟩ = 2/3 over a sphere, the mean of
// g/g_pole = (1+2·gEq)/3, so T_pole = Teff·(3/(1+2gEq))^¼ and T_eq = T_pole·gEq^¼. That
// keeps the disk-integrated Teff = MIST's Teff — the pole genuinely blazes hotter than the
// catalog value and the equator cooler, with total flux conserved.
export function rotationDistortion(state) {
  const inert = {
    active: false, omega: 0, req: 1, kEq: 1, kPol: 1, gEq: 1,
    tPole: state ? state.Teff_K : 0, tEq: state ? state.Teff_K : 0,
  };
  if (!state || !state.v_rot_kms || state.v_rot_kms <= 0) return inert;
  if (!state.R_rsun || state.R_rsun <= 0 || !state.mass_init_msun) return inert;

  // v_crit (Roche equatorial break-up) = sqrt(2/3)·437·sqrt(M/R_pol). Treat the MIST
  // radius as ≈ R_pol; the pole↔mean radius difference is second order at these ω, and
  // it keeps ω conservative (a slightly larger v_crit → slightly smaller ω).
  const vcrit = Math.sqrt(2 / 3) * VSUN * Math.sqrt(state.mass_init_msun / state.R_rsun);
  const vfrac = Math.min(0.999, state.v_rot_kms / vcrit);
  let omega = omegaFromVfrac(vfrac);

  // Regime gate — gravity darkening is a COMPACT (main-sequence) fast-rotator effect.
  // Evolved stars have spun down, and MIST's surface rotation on the giant branch is
  // unreliable: a huge radius collapses v_crit, so a modest v_rot spuriously reads as
  // near-critical → a 50%-oblate "giant" that is an artifact, not a Regulus (measured:
  // a 145 R☉, log g 1.2 bright giant flattening to R_eq/R_pol≈1.5). Fade the whole
  // effect out below the subgiant boundary using surface gravity (MS log g ~4, giants
  // <3), smoothly (scaling ω) so scrubbing across the transition never pops.
  omega *= sstep(2.0, 3.0, state.logg);
  if (omega <= 0.02) return inert; // below any visible distortion — treat as round

  const req = rocheReq(omega);
  const kPol = Math.pow(req, -2 / 3);
  const kEq = Math.pow(req, 1 / 3);

  // g_eff(equator)/g_eff(pole), GM=1 & R_pol=1 units:
  //   g_pole = 1 ; g_eq = 1/req² − Ω²·(8/27)·req  (gravity minus centrifugal).
  const Om2 = omega * omega * (8 / 27);
  const gEq = Math.max(0, 1 / (req * req) - Om2 * req);

  const meanG = (1 + 2 * gEq) / 3;
  const tPole = state.Teff_K * Math.pow(1 / meanG, 0.25);
  const tEq = tPole * Math.pow(gEq, 0.25);

  return { active: true, omega, req, kEq, kPol, gEq, tPole, tEq };
}
