// color.js — the Planck -> CIE XYZ -> sRGB pipeline.
//
// The header calls this "the most physically honest pixel in the app", and its
// spec-§10 sanity target is stated as prose: the Sun is a slightly-warm near-white,
// NOT cartoon yellow; 3000 K is orange-red; 40000 K is blue-white. Those become
// assertions here. The second half of the file pins the tail bug the header records
// in full — before the hue clamp, 740 nm rendered PURE GREEN.

import test from "node:test";
import assert from "node:assert/strict";
import { teffToLinearRGB, teffToRGB, teffToCSS, wavelengthToCSS, planck, HC_OVER_K_NM } from "../src/color.js";

const rgbOf = (css) => css.match(/\d+/g).map(Number);

test("the spec-10 Sun anchor: 5772 K is a near-white, never cartoon yellow", () => {
  const [r, g, b] = teffToRGB(5772);
  // "Near-white" made numeric: no channel more than 10% below the brightest.
  assert.ok(Math.min(r, g, b) > 0.9 * Math.max(r, g, b),
    `the Sun rendered ${teffToCSS(5772)} — too saturated to be near-white`);
  // "Slightly warm": red leads blue, but only slightly.
  assert.ok(r > b, "the Sun must lean warm");
  assert.ok(r - b < 0.15, "...but only slightly — this is not a yellow star");
});

test("the temperature sequence runs red -> white -> blue in the right order", () => {
  const cool = teffToRGB(3000), sun = teffToRGB(5772), hot = teffToRGB(40000);
  assert.ok(cool[0] > cool[2], "3000 K is orange-red: red dominates blue");
  assert.ok(cool[2] < 0.6, "...distinctly so");
  assert.ok(hot[2] > hot[0], "40000 K is blue-white: blue dominates red");
  // Blue/red never falls with Teff across the whole rendered band, and rises
  // strictly once blue leaves the gamut floor (below ~1800 K the blue channel
  // clamps to exactly 0, so the ratio is legitimately flat there).
  let prev = -Infinity;
  for (let T = 1000; T <= 40000; T += 500) {
    const [r, , b] = teffToLinearRGB(T);
    const ratio = b / r;
    if (b > 0) assert.ok(ratio > prev, `blue/red fell between ${T - 500} K and ${T} K`);
    else assert.ok(ratio >= prev, `blue/red fell below the gamut floor at ${T} K`);
    prev = ratio;
  }
  assert.ok(sun[0] > sun[2] && hot[0] < hot[2], "the crossover happens above the Sun");
});

test("every colour is max-normalized: the brightest channel is exactly 1", () => {
  for (let T = 1000; T <= 40000; T += 250) {
    const lin = teffToLinearRGB(T);
    assert.ok(Math.abs(Math.max(...lin) - 1) < 1e-12, `linear max = ${Math.max(...lin)} at ${T} K`);
    // The sRGB transfer maps 1 -> 1.055 - 0.055 = 1 exactly, so display sRGB agrees.
    assert.ok(Math.abs(Math.max(...teffToRGB(T)) - 1) < 1e-12, `display max off at ${T} K`);
    assert.ok(Math.min(...lin) >= 0, `negative (out-of-gamut) channel survived at ${T} K`);
  }
});

test("Teff is clamped to 1000-40000 K rather than extrapolated", () => {
  assert.deepEqual(teffToRGB(500), teffToRGB(1000));
  assert.deepEqual(teffToRGB(1e6), teffToRGB(40000));
});

test("teffToCSS emits in-range 8-bit channels", () => {
  for (let T = 1000; T <= 40000; T += 1000) {
    const ch = rgbOf(teffToCSS(T));
    assert.equal(ch.length, 3);
    for (const c of ch) assert.ok(Number.isInteger(c) && c >= 0 && c <= 255, `${c} at ${T} K`);
  }
});

test("REGRESSION: 740 nm is deep red, not the pure green it used to render", () => {
  // The header records this bug verbatim: past ~690 nm the CMF fit's lobes decay at
  // different rates, cieY outlives cieX, and normalizing to full brightness turned
  // 740 nm into vivid GREEN. The hue clamp at 680 nm is what fixed it.
  const [r, g, b] = rgbOf(wavelengthToCSS(740));
  assert.ok(r > 150, `740 nm has red = ${r}; it must read as red`);
  assert.ok(g === 0 && b === 0, `740 nm leaked green/blue: ${wavelengthToCSS(740)}`);
  assert.ok(r < 255, "...and dimmed by the edge-luminance falloff, not full-bright");
});

test("REGRESSION: the violet tail stays violet rather than drifting to cyan", () => {
  // The other half of the same bug: below ~400 nm the ratio drifted toward cyan.
  const [r, g, b] = rgbOf(wavelengthToCSS(385));
  assert.ok(b > r && r > g, `385 nm rendered ${wavelengthToCSS(385)} — must be blue-dominant violet`);
  assert.ok(g < 40, "a violet with a strong green channel is the cyan drift");
});

test("the visible band still runs violet -> green -> red across its core", () => {
  const violet = rgbOf(wavelengthToCSS(430));
  const green = rgbOf(wavelengthToCSS(550));
  const red = rgbOf(wavelengthToCSS(650));
  assert.ok(violet[2] > violet[0], "430 nm is blue-dominant");
  assert.ok(green[1] > green[0] && green[1] > green[2], "550 nm is green-dominant");
  assert.ok(red[0] > red[1] && red[0] > red[2], "650 nm is red-dominant");
});

test("the band edges fade rather than staying full-bright", () => {
  const bright = (nm) => Math.max(...rgbOf(wavelengthToCSS(nm)));
  assert.ok(bright(780) < bright(700), "the far red must dim toward the edge");
  assert.ok(bright(380) < bright(430), "the far violet must dim toward the edge");
  assert.ok(bright(780) > 0, "...to a floor, not to black — the edge stays visible");
});

test("planck() stays finite across the whole SED span (gamma-ray to radio)", () => {
  // The SED panel calls this over 14 decades. The X-ray end must go to 0, not NaN.
  for (const lam of [1e-6, 1e-3, 1, 500, 1e4, 1e7, 1e12]) {
    const v = planck(lam, 5772);
    assert.ok(Number.isFinite(v) && v >= 0, `planck(${lam} nm) = ${v}`);
  }
  assert.equal(planck(1e-6, 5772), 0, "a star is not a thermal gamma source");
});

test("Wien's law falls out of planck(): the peak tracks 2.898e6 nm.K / T", () => {
  // An independent physical check of the Planck function, from the constant it is
  // NOT written in terms of. Scan for the argmax and compare to Wien.
  for (const T of [3000, 5772, 20000]) {
    let best = 0, bestLam = 0;
    for (let lam = 10; lam < 20000; lam += 0.5) {
      const v = planck(lam, T);
      if (v > best) { best = v; bestLam = lam; }
    }
    const wien = 2.897771955e6 / T;
    assert.ok(Math.abs(bestLam / wien - 1) < 0.01, `peak ${bestLam} nm vs Wien ${wien} nm at ${T} K`);
  }
  // And the exported constant is hc/k in nm.K, which Wien's b = 4.965114 relates to.
  assert.ok(Math.abs(HC_OVER_K_NM / 4.965114231744276 / 2.897771955e6 - 1) < 1e-6);
});
