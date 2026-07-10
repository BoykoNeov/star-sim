// Interstellar reddening — the Cardelli, Clayton & Mathis (1989) extinction law,
// a pure client-side helper for Axis A (the observer's view). Like hz.js it is a
// unit-checkable pure function of its inputs, feeding the drawing modules
// (spectrum.js, sed.js) rather than owning any canvas.
//
// **This is a VERBATIM port of the backend `photometry.py` `ccm89`.** The two MUST
// stay identical: the served magnitude/colour readout (from /photometry, which uses
// the Python version through the filter curves) and the reddened curve drawn on the
// spectrum/SED panels are the SAME physical extinction — a divergence would make the
// drawn overlay disagree with the numbers beside it. The port was checked to match
// the Python output at 5000 Å (optical branch), 2175 Å (the UV bump), and 1500 Å
// (deep UV). If you touch either, re-run that match. Note the deliberate choices
// carried over from photometry.py:
//   • the UV branch (3.3 < x ≤ 8) uses the base CCM89 eq. 4a/4b polynomials with NO
//     deep-UV F_a/F_b correction term — matched on purpose, do not "fix" from a
//     textbook or the drawn overlay drifts from the served readout in the deep UV;
//   • outside 1.1 ≤ x ≤ 8 µm⁻¹ (λ ≳ 9091 Å or λ ≲ 1250 Å) the coefficients are 0, so
//     the extinction factor is exactly 1 — reddening is identity there. On the SED
//     (which spans γ-ray → radio) this means only the ~1250–9091 Å slice is reddened;
//     the rest of the 14 decades is untouched, and the 2175 Å bump lives in the
//     covered UV branch (the b(x) Lorentzian at x ≈ 4.6).

// A(λ)/A(V) for a single wavelength λ (Å), parameterized by R_V. The extinction in
// magnitudes is A_V · this; the flux is multiplied by 10^(−0.4 · A_V · this).
export function ccm89(lamAng, rv = 3.1) {
  const x = 1.0e4 / lamAng;      // inverse microns (1 µm = 1e4 Å, so x = 1/λ_µm)
  let a = 0, b = 0;
  if (x >= 1.1 && x <= 3.3) {
    // Optical / NIR: CCM89 eq. 3a/3b — 7th-order polynomials in y = x − 1.82.
    const y = x - 1.82;
    a = 1.0 + 0.17699 * y - 0.50447 * y ** 2 - 0.02427 * y ** 3 + 0.72085 * y ** 4
        + 0.01979 * y ** 5 - 0.77530 * y ** 6 + 0.32999 * y ** 7;
    b = 1.41338 * y + 2.28305 * y ** 2 + 1.07233 * y ** 3 - 5.38434 * y ** 4
        - 0.62251 * y ** 5 + 5.30260 * y ** 6 - 2.09002 * y ** 7;
  } else if (x > 3.3 && x <= 8.0) {
    // Near-UV: CCM89 eq. 4a/4b (base form; the 2175 Å bump is the b(x) Lorentzian).
    a = 1.752 - 0.316 * x - 0.104 / ((x - 4.67) ** 2 + 0.341);
    b = -3.090 + 1.825 * x + 1.206 / ((x - 4.62) ** 2 + 0.263);
  }
  // Below 1.1 µm⁻¹ or above 8: a = b = 0 → A(λ)/A(V) = 0 (reddening is identity).
  return a + b / rv;
}

// The multiplicative flux factor 10^(−0.4 · A_V · A(λ)/A(V)) at λ (Å): what a
// reddened spectrum's flux is scaled by. 1.0 where CCM89 is undefined (identity) and
// exactly 1.0 when av = 0 (the intrinsic view — so "Observer off" is a no-op).
export function extinctionFactor(lamAng, av, rv = 3.1) {
  if (!(av > 0)) return 1.0;
  return 10 ** (-0.4 * av * ccm89(lamAng, rv));
}
