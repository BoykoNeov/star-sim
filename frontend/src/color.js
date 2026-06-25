// Teff -> star color, the most physically honest pixel in the app (spec §7).
//
// THE REFERENCE PIPELINE (no longer an approximation): we take the Planck
// blackbody spectrum at Teff, integrate it against the CIE 1931 color-matching
// functions to get XYZ, convert XYZ -> linear sRGB with the standard (D65)
// matrix, then gamma-encode to display sRGB. The CMFs use the Wyman/Sloan/
// Shirley (2013) multi-lobe Gaussian fit — compact, table-free, accurate to a
// percent or two, which is far below what the eye resolves here.
//
// Sanity target (spec §10): the Sun (~5772 K) renders as a slightly-warm
// near-white — NOT cartoon yellow — while 3000 K is orange-red and 40000 K is
// blue-white. Print-tested in tools/ during development.
//
// Two outputs, by colorspace:
//   * teffToLinearRGB — LINEAR sRGB (no gamma). This is what the star shader
//     wants: limb darkening and granulation multiply the surface in *linear*
//     light, and the shader applies the gamma transfer once at the very end.
//   * teffToRGB / teffToCSS — gamma-encoded *display* sRGB, for the 2D UI
//     (status line, any CSS color) which expects ready-to-display values.

// --- CIE 1931 color-matching functions (Wyman et al. 2013 analytic fit) -------
// Each CMF is a sum of skewed Gaussians g(λ; μ, σ₁, σ₂): the falloff uses σ₁
// below the peak μ and σ₂ above it (λ in nanometres). This is the "multi-lobe"
// approximation from "Simple Analytic Approximations to the CIE XYZ Color
// Matching Functions" (JCGT 2013, Table 1).
function lobe(lambda, mu, s1, s2) {
  const t = (lambda - mu) * (lambda < mu ? s1 : s2);
  return Math.exp(-0.5 * t * t);
}
function cieX(l) {
  return 1.056 * lobe(l, 599.8, 0.0264, 0.0323)
       + 0.362 * lobe(l, 442.0, 0.0624, 0.0374)
       - 0.065 * lobe(l, 501.1, 0.0490, 0.0382);
}
function cieY(l) {
  return 0.821 * lobe(l, 568.8, 0.0213, 0.0247)
       + 0.286 * lobe(l, 530.9, 0.0613, 0.0322);
}
function cieZ(l) {
  return 1.217 * lobe(l, 437.0, 0.0845, 0.0278)
       + 0.681 * lobe(l, 459.0, 0.0385, 0.0725);
}

// Planck spectral radiance vs wavelength, up to a constant (we normalize later,
// so the 2hc² prefactor drops out): B(λ,T) ∝ λ⁻⁵ / (exp(hc/λkT) − 1).
// hc/k = 1.438776877e7 nm·K, so the exponent is that constant / (λ_nm · T).
//
// Exported (used by sed.js for the broadband SED panel, which plots this curve
// across the whole EM spectrum). It is numerically robust at the extremes the SED
// reaches: at gamma/X-ray λ the exponent overflows so expm1 → +∞ and B → 0 (a star
// is not a thermal gamma source — physically correct, never NaN/∞); at radio λ it
// tends to the Rayleigh–Jeans λ⁻⁴ tail. The caller clamps log10(0) to a floor.
export const HC_OVER_K_NM = 1.438776877e7;
export function planck(lambdaNm, tempK) {
  const x = HC_OVER_K_NM / (lambdaNm * tempK);
  return Math.pow(lambdaNm, -5) / (Math.expm1(x)); // expm1 keeps precision for large λT
}

// Integrate Planck × CMF over the visible band (380–780 nm, 5 nm steps) -> XYZ.
// Absolute scale is irrelevant (we max-normalize the RGB afterward), so a plain
// Riemann sum with a fixed Δλ is plenty.
function planckToXYZ(tempK) {
  let X = 0, Y = 0, Z = 0;
  for (let l = 380; l <= 780; l += 5) {
    const b = planck(l, tempK);
    X += b * cieX(l);
    Y += b * cieY(l);
    Z += b * cieZ(l);
  }
  return [X, Y, Z];
}

// XYZ -> linear sRGB (IEC 61966-2-1, D65 white point).
function xyzToLinearSRGB(X, Y, Z) {
  return [
     3.2406 * X - 1.5372 * Y - 0.4986 * Z,
    -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
     0.0557 * X - 0.2040 * Y + 1.0570 * Z,
  ];
}

// Linear -> display sRGB (the standard piecewise gamma transfer).
function linearToSRGB(c) {
  return c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055;
}

// --- public API ---------------------------------------------------------------

// Teff -> LINEAR sRGB in 0..1, max-channel normalized. The order matters (spec
// §10): clamp out-of-gamut negatives to 0 FIRST (blackbody chromaticities fall
// outside sRGB at the temperature extremes), THEN normalize by the brightest
// channel — we want full-brightness chromaticity for a self-luminous disk, so we
// keep the hue and discard the absolute luminance (size + glow carry brightness).
export function teffToLinearRGB(kelvin) {
  const t = Math.max(1000, Math.min(40000, kelvin)); // grid never leaves this band
  const [X, Y, Z] = planckToXYZ(t);
  let rgb = xyzToLinearSRGB(X, Y, Z).map((c) => Math.max(0, c));
  const max = Math.max(rgb[0], rgb[1], rgb[2]) || 1;
  return rgb.map((c) => c / max);
}

// Teff -> display sRGB in 0..1 (gamma applied last). For the 2D UI; the 3D star
// uses teffToLinearRGB and gamma-encodes inside the shader instead.
export function teffToRGB(kelvin) {
  return teffToLinearRGB(kelvin).map(linearToSRGB);
}

export function teffToCSS(kelvin) {
  const [r, g, b] = teffToRGB(kelvin).map((v) => Math.round(v * 255));
  return `rgb(${r}, ${g}, ${b})`;
}

// Monochromatic wavelength (nm) -> the perceived sRGB hue of light at exactly
// that wavelength, for the spectrum panel's "rainbow" continuum shading. Same
// CIE-fit machinery as the Teff color, but the XYZ tristimulus IS the CMF value
// at this single λ (a delta-function spectrum). Clamp out-of-gamut negatives,
// normalize to a vivid full-brightness hue (we're painting a spectral strip, not
// matching a luminance), gamma last. Outside ~380–700 nm the CMFs fall to ~0, so
// the deep violet/red ends darken naturally.
export function wavelengthToCSS(nm) {
  const X = cieX(nm), Y = cieY(nm), Z = cieZ(nm);
  let rgb = xyzToLinearSRGB(X, Y, Z).map((c) => Math.max(0, c));
  const max = Math.max(rgb[0], rgb[1], rgb[2]) || 1;
  const [r, g, b] = rgb
    .map((c) => linearToSRGB(c / max))
    .map((v) => Math.round(Math.max(0, Math.min(1, v)) * 255));
  return `rgb(${r}, ${g}, ${b})`;
}
