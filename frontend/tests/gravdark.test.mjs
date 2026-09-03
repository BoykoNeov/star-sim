// gravdark.js — rotational oblateness + gravity darkening.
//
// The two identities in the module header do all the work here: the spheroid is
// volume-preserving and the darkened surface conserves flux. Both hold *exactly*
// by construction, so they are checked to machine precision — an exponent typo in
// either would move them far outside 1e-12.

import test from "node:test";
import assert from "node:assert/strict";
import { rotationDistortion } from "../src/gravdark.js";

// A main-sequence fast rotator: log g 4.0 is above the sstep(2,3) fade, so the
// effect is fully on.
const fast = { Teff_K: 15000, v_rot_kms: 250, R_rsun: 3.0, mass_init_msun: 5.0, logg: 4.0 };

test("volume is preserved: kEq^2 * kPol === 1", () => {
  const d = rotationDistortion(fast);
  assert.ok(d.active, "the test star must actually be distorted");
  assert.ok(Math.abs(d.kEq ** 2 * d.kPol - 1) < 1e-12,
    `kEq^2*kPol = ${d.kEq ** 2 * d.kPol}, must be 1 — the star is flattened, not resized`);
});

test("gravity darkening conserves flux: the area-weighted mean T^4 is the catalog Teff^4", () => {
  const d = rotationDistortion(fast);
  // <sin^2 lat> = 2/3 over a sphere, so mean(g/g_pole) = (1 + 2*gEq)/3 and
  // T_pole^4 * that mean must return Teff^4 (the header's anchoring rule).
  const mean4 = d.tPole ** 4 * ((1 + 2 * d.gEq) / 3);
  assert.ok(Math.abs(mean4 / fast.Teff_K ** 4 - 1) < 1e-12,
    `disk-integrated Teff^4 drifted by ${mean4 / fast.Teff_K ** 4 - 1}`);
});

test("the pole is hotter and the equator cooler than the catalog Teff", () => {
  const d = rotationDistortion(fast);
  assert.ok(d.tPole > fast.Teff_K, "pole must exceed the catalog Teff");
  assert.ok(d.tEq < fast.Teff_K, "equator must fall below the catalog Teff");
  assert.ok(d.req > 1, "a rotator bulges at the equator");
  assert.ok(d.req <= 1.5 + 1e-12, "R_eq/R_pol cannot exceed the critical 1.5");
});

test("a non-rotator is byte-identical to a round, single-temperature star", () => {
  for (const v of [0, null, undefined]) {
    const d = rotationDistortion({ ...fast, v_rot_kms: v });
    assert.equal(d.active, false);
    assert.equal(d.kEq, 1);
    assert.equal(d.kPol, 1);
    assert.equal(d.req, 1);
    assert.equal(d.gEq, 1);
    assert.equal(d.tPole, fast.Teff_K);
    assert.equal(d.tEq, fast.Teff_K);
  }
});

test("the evolved-star gate: a bright giant stays round (the measured 145 R_sun artifact)", () => {
  // The header records the bug this gate exists for: a huge radius collapses v_crit,
  // so a modest v_rot reads as near-critical and a giant spuriously flattens to
  // R_eq/R_pol ~= 1.5. sstep(2,3,logg) is exactly 0 at log g <= 2.
  const giant = { Teff_K: 4500, v_rot_kms: 20, R_rsun: 145, mass_init_msun: 5.0, logg: 1.2 };
  assert.equal(rotationDistortion(giant).active, false);
  // ...and it fades in smoothly rather than popping: still inert at the gate's foot.
  assert.equal(rotationDistortion({ ...giant, logg: 2.0 }).active, false);
});

test("missing state fields degrade to inert rather than NaN", () => {
  assert.equal(rotationDistortion(null).active, false);
  assert.equal(rotationDistortion({ ...fast, R_rsun: 0 }).active, false);
  assert.equal(rotationDistortion({ ...fast, mass_init_msun: null }).active, false);
});
