// Habitable zone — the Kopparapu (2014) circumstellar liquid-water zone (outward quartet, Axis D).
//
// A PURE function of two StellarState numbers — Teff and L — returning the AU distances of the
// classical HZ edges. It is the compute half of the habitable-zone overlay; scale.js is the draw
// half (it plots these edges on its existing log-distance axis, alongside the planet-orbit rings).
// Kept separate from scale.js so the physics is unit-checkable in isolation (the Gate-0 solar
// anchor below), mirroring gravdark.js as a pure helper to a drawing module.
//
// THE PHYSICS (Tier-2, labeled). Kopparapu, Ramirez et al. 2014 (ApJ 787, L29 — the corrected
// update to Kopparapu 2013) parameterize the effective stellar flux at each HZ edge as a quartic
// in T* = Teff - 5780 K:
//
//     S_eff(Teff) = S_eff⊙ + a·T* + b·T*² + c·T*³ + d·T*⁴
//
// and the edge distance follows from the inverse-square law with the star's luminosity:
//
//     d = √( (L / L⊙) / S_eff )   [AU]
//
// So ONLY Teff and L enter — Teff sets the flux thresholds (this is exactly where the star's
// SPECTRUM enters: a cool star's redder light is absorbed/reflected differently by water, CO₂ and
// ice, which is what the Teff-dependence encodes), and L sets the absolute distance (this is what
// makes the band march OUTWARD as the star brightens up the giant branch — the payoff). Mass,
// gravity, composition and rotation do NOT enter Kopparapu and are deliberately excluded (the
// project's "don't fake a feature" rule). Planet mass is fixed at 1 M⊕ (no planetary sandbox).
//
// WHAT THIS IS NOT. The classical HZ is a liquid-water ENERGY-BALANCE zone only. UV/X-ray flux,
// flares and stellar activity bear on habitability (atmospheric erosion, ozone) but are a separate,
// far more speculative concept — they are NOT drawn here; the scale.js caption owns that caveat.
//
// THE VALIDITY GATE (load-bearing). The quartic is calibrated for Teff ∈ [2600, 7200] K. Outside
// that range it does not merely lose accuracy — a quartic in T* DIVERGES (for a 30 kK star T*⁴ is
// ~1e17, S_eff goes garbage/negative, √ gives NaN or an absurd distance that would break the draw).
// So callers MUST check `inRange(Teff)` and skip the band entirely when false — never extrapolate.
// A 1 M☉ star's whole MS→RGB story stays in range (~5800 → ~3500 K), so the marquee case is fully
// computable; an evolving star legitimately blinks the band on/off as it crosses 7200 K.

// Kopparapu et al. 2014 (ApJ 787, L29), Table 1 — coefficients for a 1 M⊕ planet. T* = Teff-5780.
// The 2014 update revised the runaway-greenhouse inner edge (and recent-Venus/max-greenhouse/early-
// Mars are mass-independent). MOIST GREENHOUSE is intentionally omitted: the 2014 runaway revision
// moved inside the un-revised 2013 moist edge, so mixing the two is internally inconsistent — the
// 2014 paper itself drops it. These four give a clean nested pair: conservative (runaway↔max
// greenhouse) inside optimistic (recent Venus↔early Mars).
const COEFFS = {
  recentVenus:   { seff: 1.776, a: 2.136e-4, b: 2.533e-8, c: -1.332e-11, d: -3.097e-15 },
  runaway:       { seff: 1.107, a: 1.332e-4, b: 1.580e-8, c: -8.308e-12, d: -1.931e-15 },
  maxGreenhouse: { seff: 0.356, a: 6.171e-5, b: 1.698e-9, c: -3.198e-12, d: -5.575e-16 },
  earlyMars:     { seff: 0.320, a: 5.547e-5, b: 1.526e-9, c: -2.874e-12, d: -5.011e-16 },
};

export const TEFF_MIN = 2600, TEFF_MAX = 7200;   // Kopparapu calibration range (K)

// Is Teff inside the Kopparapu calibration range? Callers MUST gate on this (see the header).
export function inRange(Teff) {
  return Number.isFinite(Teff) && Teff >= TEFF_MIN && Teff <= TEFF_MAX;
}

function seffOf(k, tstar) {
  const c = COEFFS[k];
  return c.seff + c.a * tstar + c.b * tstar ** 2 + c.c * tstar ** 3 + c.d * tstar ** 4;
}

// The HZ edges for a star of effective temperature Teff (K) and luminosity L (L⊙).
// Returns { recentVenus, runaway, maxGreenhouse, earlyMars } distances in AU (inner→outer), or
// null when Teff is out of the calibration range (the caller draws no band). Distances grow with
// √L, so a brighter star pushes every edge outward.
export function habitableZone(Teff, L) {
  if (!inRange(Teff) || !(L > 0)) return null;
  const tstar = Teff - 5780;
  const dist = (k) => Math.sqrt(L / seffOf(k, tstar));   // AU
  return {
    recentVenus:   dist("recentVenus"),     // optimistic inner (empirical: Venus had water ~1 Gyr ago)
    runaway:       dist("runaway"),         // conservative inner (oceans evaporate, H escapes)
    maxGreenhouse: dist("maxGreenhouse"),   // conservative outer (max CO₂ warming before it condenses)
    earlyMars:     dist("earlyMars"),       // optimistic outer (empirical: Mars had water ~3.8 Gyr ago)
  };
}
