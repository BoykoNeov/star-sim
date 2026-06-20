// Teff -> sRGB color.
//
// HONEST SEAM (STAR_SIM_SPEC.md §7): the *reference* pipeline is
// Planck blackbody spectrum -> integrate against CIE XYZ -> XYZ->sRGB with the
// correct white point and gamma. That lands in Phase 2. For the Phase 0 shell we
// use a fast, well-known blackbody approximation (Tanner Helland / Neil
// Bartlett). It already hits the key sanity target: the Sun (~5772 K) reads as a
// slightly-warm near-white, NOT cartoon yellow.

function clamp255(v) {
  return Math.max(0, Math.min(255, v));
}

// Returns [r, g, b] in 0..1.
export function teffToRGB(kelvin) {
  const t = Math.max(1000, Math.min(40000, kelvin)) / 100;
  let r, g, b;

  // red
  r = t <= 66 ? 255 : 329.698727446 * Math.pow(t - 60, -0.1332047592);

  // green
  g = t <= 66
    ? 99.4708025861 * Math.log(t) - 161.1195681661
    : 288.1221695283 * Math.pow(t - 60, -0.0755148492);

  // blue
  if (t >= 66) b = 255;
  else if (t <= 19) b = 0;
  else b = 138.5177312231 * Math.log(t - 10) - 305.0447927307;

  return [clamp255(r) / 255, clamp255(g) / 255, clamp255(b) / 255];
}

export function teffToCSS(kelvin) {
  const [r, g, b] = teffToRGB(kelvin).map((v) => Math.round(v * 255));
  return `rgb(${r}, ${g}, ${b})`;
}
