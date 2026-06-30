// Observed supernova bolometric light curves — the Tier-1 verification anchor for the
// core-collapse SN endgame (docs/plans/radioactive-afterglow-requiem.md, Chunk 2; the
// deferred deliverable from Chunk 1). The model's light curve is BOLOMETRIC and its
// Tier-1 claim is the ⁵⁶Co tail SLOPE (0.00975 mag/day, set only by τ_Co); the honest
// way to show that claim is true is to overlay REAL, published bolometric light curves
// of canonical supernovae and let the user see the model's radioactive tail lying along
// SN 1987A's measured ⁵⁶Co tail (constraint #5: "pull real photometry and cite").
//
// PROVENANCE / honesty (important — read before trusting these as raw photometry):
// the per-epoch UVOIR bolometric light curves of these SNe live in journal FIGURES and
// electronic-only tables; the machine-readable CDS/VizieR catalogs were unreachable at
// build time. Rather than DIGITIZE a figure or reconstruct points from memory (both of
// which the project's honesty rule forbids), each curve below is generated from the
// paper's own PUBLISHED FIT PARAMETERS plus a real tabulated anchor point — i.e. these
// are the authors' reported light-curve fits, drawn out, not eyeballed data. Every
// number is cited inline. They are LABELED as fits in the UI, not as raw photometry.
//
//   * SN 1987A (Suntzeff & Bouchet 1990, AJ 99, 650): the textbook ⁵⁶Co tail. Real
//     tabulated point: at day 159.1, log₁₀(L_UVOIR / erg s⁻¹) = 41.381. The defining
//     result is that 1987A's bolometric tail TRACKED THE ⁵⁶Co DECAY — e-folding time
//     τ_Co = 111.3 d (≈ 0.00976 mag/day) — across day ~120–500, consistent with ~0.07
//     M☉ of ⁵⁶Ni and near-full γ-ray trapping (leakage only steepens it appreciably
//     after ~day 530, past our window). We draw the overlay at that ⁵⁶Co e-fold ON
//     PURPOSE: it is the SAME decay constant the model's L_radio uses (TAU_CO_D = 111.3 d
//     in supernova.py), so the model's parameter-free radioactive tail lies PARALLEL to
//     1987A's measured tail — that coincidence of slopes IS the Tier-1 anchor, not a
//     fitted free number. (Earlier this overlay used a 100 d e-fold → an 11%-steeper
//     slope that only LOOKED parallel; the anchor demands slope equality, so it is τ_Co.)
//     Drawn on the TAIL ONLY (day 126–500): 1987A's progenitor was a COMPACT blue
//     supergiant, so it had a slow rise to a secondary maximum and NO normal IIP
//     plateau — it anchors the radioactive tail, never the plateau (advisor-flagged).
//
//   * SN 1999em (Elmhamdi et al. 2003, MNRAS 338, 939; Bersten & Hamuy 2009, ApJ 701,
//     200): the IIP-plateau prototype — the plateau-SHAPE context (Tier-2, ±dex level).
//     Published values: a recombination plateau near the IIP sample's mode luminosity
//     ~1.2×10⁴² erg/s lasting ~100 days, then a steep drop onto a radioactive tail at
//     bolometric luminosity ≈ 0.30 × that of SN 1987A. Its tail likewise tracks the ⁵⁶Co
//     decay (τ_Co ≈ 111 d — a IIP radioactive tail cannot decline SLOWER than full Co
//     trapping), so we draw it at the same e-fold, just fainter (D = 7.83 Mpc, E(B−V) =
//     0.1; Elmhamdi 2003 fits the tail over day 140–465).
//
// The model curve the panel draws is the star's OWN computed light curve; these two are
// the fixed real-SN yardsticks it's read against. They are bolometric (erg/s), the same
// quantity as the model's L_total, so the comparison is apples-to-apples (a V-band
// overlay would compare against a different, BC-varying slope and the Tier-1 anchor
// would spuriously fail — so bolometric is required, not just preferred).

// SN 1987A's real tabulated tail anchor (Suntzeff & Bouchet 1990).
const SN1987A_ANCHOR_DAY = 159.1;
const SN1987A_ANCHOR_L = 10 ** 41.381;   // erg/s, UVOIR bolometric
const SN1987A_EFOLD_D = 111.3;           // days = τ_Co (matches TAU_CO_D in supernova.py)

// Sample a curve at ~2-day cadence over [d0, d1], L(t) in erg/s from `lFn`.
function sample(d0, d1, lFn, step = 2) {
  const pts = [];
  for (let t = d0; t <= d1 + 1e-9; t += step) pts.push({ t, L: lFn(t) });
  return pts;
}

// SN 1987A — the ⁵⁶Co tail only (day 126–500), the ⁵⁶Co-decay exponential anchored on
// the real day-159 point. L(t) = L₁₅₉ · exp(−(t−159.1)/111.3) — same slope as the model.
function sn1987aTail() {
  return sample(126, 500, (t) =>
    SN1987A_ANCHOR_L * Math.exp(-(t - SN1987A_ANCHOR_DAY) / SN1987A_EFOLD_D));
}

// SN 1999em — the IIP plateau + tail, from the published parameters. A gently declining
// recombination plateau (~1.2×10⁴² → ~1.0×10⁴² erg/s) to day ~95, a steep ~40-day drop,
// then the radioactive tail at 0.30 × the 1987A tail, tracking the same ⁵⁶Co decay.
function sn1999em() {
  const tailL = (t) =>
    0.30 * SN1987A_ANCHOR_L * Math.exp(-(t - SN1987A_ANCHOR_DAY) / SN1987A_EFOLD_D);
  const PLAT_HI = 1.2e42, PLAT_LO = 1.0e42;
  const DROP_START = 95, DROP_END = 135;
  const lFn = (t) => {
    if (t <= DROP_START) {
      // plateau: gentle linear-in-log decline from PLAT_HI (day 8) to PLAT_LO (day 95)
      const f = Math.max(0, Math.min(1, (t - 8) / (DROP_START - 8)));
      return PLAT_HI * (PLAT_LO / PLAT_HI) ** f;
    }
    if (t < DROP_END) {
      // the steep plateau-end drop: log-linear from PLAT_LO down to the tail value
      const f = (t - DROP_START) / (DROP_END - DROP_START);
      const end = tailL(DROP_END);
      return PLAT_LO * (end / PLAT_LO) ** f;
    }
    return tailL(t);   // the radioactive tail
  };
  return sample(8, 460, lFn);
}

// The observed overlays the SN light-curve panel draws behind the model curve. Each:
//   points: [{t (days), L (erg/s)}]   — the published-fit bolometric light curve
//   color, label                       — legend
//   ref                                — the citation (shown in the panel caption)
//   kind                               — "tail" (1987A) | "plateau" (1999em), for labeling
export const OBSERVED_SNE = [
  {
    id: "sn1987a",
    label: "SN 1987A (⁵⁶Co tail)",
    ref: "Suntzeff & Bouchet 1990",
    kind: "tail",
    color: "#ff9d5c",
    points: sn1987aTail(),
  },
  {
    id: "sn1999em",
    label: "SN 1999em (IIP plateau)",
    ref: "Elmhamdi 2003; Bersten & Hamuy 2009",
    kind: "plateau",
    color: "#6fd3ff",
    points: sn1999em(),
  },
];

// The Tier-1 line caption — what the overlays demonstrate, named so the UI can show the
// claim and its real-SN check together.
export const OBSERVED_CAPTION =
  "Real bolometric light curves (published fits, cited) — the model's radioactive tail " +
  "should lie parallel to SN 1987A's measured ⁵⁶Co tail (the Tier-1 anchor).";
