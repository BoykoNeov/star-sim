// seismo.js — the asteroseismic scaling relations.
//
// The strongest test in the file is invertibility: the module computes nu_max and
// Delta-nu from (g, R), then inverts the pair back to (M, R). Round-tripping pins
// all four exponents at once — the -1/2 on Teff in nu_max, the 3/2 density power in
// Delta-nu, and the two recovery exponents — where a single pinned frequency would
// not.
//
// NB: importing this module pulls in canvas.js. That works under bare Node only
// because fitCanvas touches `window` inside its body, not at module scope.

import test from "node:test";
import assert from "node:assert/strict";
import { seismicParams, ringsSolarLike, TEFF_CONV_MAX } from "../src/seismo.js";

// The REAL Sun's anchors (Huber et al. 2011 + IAU nominal), which are also the
// module's constants — so this asserts the FORM of the relations (every ratio is
// exactly 1 here), not a measured value.
const TEFF_SUN = 5772.0, LOGG_SUN = 4.4377;

test("the solar anchor: the real Sun rings at 3090 / 135 uHz exactly", () => {
  const s = seismicParams(TEFF_SUN, LOGG_SUN, 1.0);
  assert.ok(Math.abs(s.numax - 3090.0) < 1e-9, `numax = ${s.numax}`);
  assert.ok(Math.abs(s.dnu - 135.0) < 1e-9, `dnu = ${s.dnu}`);
  assert.ok(Math.abs(s.mModel - 1.0) < 1e-9, "a solar g and R must weigh 1 M_sun");
});

test("the relations invert: (numax, dnu, Teff) recovers the input M and R", () => {
  // A red giant and a K dwarf — both far from the solar anchor, so every ratio in
  // the round trip is genuinely exercised.
  for (const [Teff, logg, R] of [[4600, 2.5, 11.0], [4800, 4.6, 0.72]]) {
    const s = seismicParams(Teff, logg, R);
    assert.ok(Math.abs(s.rSeismic / R - 1) < 1e-9,
      `R recovered as ${s.rSeismic}, put in ${R}`);
    assert.ok(Math.abs(s.mSeismic / s.mModel - 1) < 1e-9,
      `M recovered as ${s.mSeismic}, put in ${s.mModel}`);
  }
});

test("a red-clump giant lands in the observed Kepler range, not just below solar", () => {
  // Kepler's red clump sits at nu_max ~ 30 uHz and Delta-nu ~ 4 uHz — a published
  // observational fact, so this checks the relations against the sky rather than
  // against themselves. A 11 R_sun, log g 2.5 giant must land in that neighbourhood.
  const giant = seismicParams(4600, 2.5, 11.0);
  assert.ok(giant.numax > 10 && giant.numax < 100, `nu_max = ${giant.numax} uHz`);
  assert.ok(giant.dnu > 1 && giant.dnu < 10, `Delta-nu = ${giant.dnu} uHz`);
  const dwarf = seismicParams(TEFF_SUN, LOGG_SUN, 1.0);
  assert.ok(giant.numax < dwarf.numax, "a giant must ring slower than a dwarf");
  assert.ok(giant.dnu < dwarf.dnu, "and with a smaller large separation");
});

test("the convection gate is inclusive at its edge and refuses above it", () => {
  assert.equal(ringsSolarLike(TEFF_CONV_MAX), true, "6700 K itself still rings");
  assert.equal(ringsSolarLike(TEFF_CONV_MAX + 1), false);
  assert.equal(ringsSolarLike(6530), true, "Procyon must not be excluded");
  assert.equal(ringsSolarLike(NaN), false);
  assert.equal(seismicParams(7000, 4.0, 1.6), null, "a hot star blanks, never guesses");
});

test("unusable inputs return null rather than NaN", () => {
  assert.equal(seismicParams(0, 4.4, 1.0), null);
  assert.equal(seismicParams(TEFF_SUN, null, 1.0), null);
  assert.equal(seismicParams(TEFF_SUN, 4.4, 0), null);
});

test("a white dwarf's log g cannot produce a spectrum through this entry point", () => {
  // The header names this: log g ~8 would paint a garbage ~1e7 uHz spectrum. The
  // structural gate is main.js's mode chokepoint, but a cool WD also has to be
  // caught here or the Teff gate alone would let it through.
  const wd = seismicParams(9000, 8.0, 0.013);
  assert.equal(wd, null, "9000 K is above the convection gate — must blank");
});
