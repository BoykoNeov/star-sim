// hz.js — the Kopparapu (2014) habitable zone.
//
// Two things matter here: the published solar anchor, and the validity gate. The
// gate is load-bearing in a way a range check usually is not — S_eff is a QUARTIC
// in (Teff - 5780), so outside the calibration band it does not lose accuracy, it
// diverges: a 30 kK star gives a garbage or negative S_eff and the sqrt returns
// NaN. Anything that lets an out-of-range Teff through paints nonsense.

import test from "node:test";
import assert from "node:assert/strict";
import { habitableZone, inRange, TEFF_MIN, TEFF_MAX } from "../src/hz.js";

test("the solar anchor: the Sun's conservative HZ is ~0.95 to ~1.68 AU", () => {
  // Kopparapu et al. 2014's own published solar values, to 0.01 AU. Note this is
  // the REAL Sun (5772 K, 1 L_sun), not the sim's ~5835 K one — the coefficients
  // are anchored at 5780 K and must not be fed a model-specific temperature.
  const z = habitableZone(5772, 1.0);
  assert.ok(Math.abs(z.runaway - 0.95) < 0.01, `runaway greenhouse at ${z.runaway} AU`);
  assert.ok(Math.abs(z.maxGreenhouse - 1.68) < 0.01, `max greenhouse at ${z.maxGreenhouse} AU`);
  // Earth sits inside the conservative zone; Venus (0.72) and Mars (1.52) do not
  // and do, respectively — the textbook picture the panel is teaching.
  assert.ok(z.runaway < 1.0 && 1.0 < z.maxGreenhouse, "Earth must be in the conservative HZ");
  // The two empirical edges are named for what they encode: TODAY'S Venus (0.72 AU)
  // sits just INSIDE the recent-Venus edge (0.75 AU) — it lost its water when the
  // brightening Sun overtook it — while Mars (1.52 AU) sits comfortably inside the
  // early-Mars edge, which is why Mars once had liquid water.
  assert.ok(Math.abs(z.recentVenus - 0.75) < 0.01, `recent Venus at ${z.recentVenus} AU`);
  assert.ok(z.recentVenus > 0.72, "Venus must fall inside the optimistic inner edge");
  assert.ok(z.earlyMars > 1.52, "the optimistic outer edge reaches past Mars");
});

test("the four edges nest: optimistic strictly outside conservative", () => {
  for (const [Teff, L] of [[5772, 1.0], [3200, 0.01], [6800, 3.0]]) {
    const z = habitableZone(Teff, L);
    assert.ok(z.recentVenus < z.runaway, `inner edges out of order at ${Teff} K`);
    assert.ok(z.runaway < z.maxGreenhouse, `the zone has no width at ${Teff} K`);
    assert.ok(z.maxGreenhouse < z.earlyMars, `outer edges out of order at ${Teff} K`);
  }
});

test("the band marches outward as sqrt(L) — the whole point of the panel", () => {
  // The star brightening 100x must push every edge out by exactly 10x at fixed Teff.
  const a = habitableZone(5772, 1.0);
  const b = habitableZone(5772, 100.0);
  for (const k of ["recentVenus", "runaway", "maxGreenhouse", "earlyMars"]) {
    assert.ok(Math.abs(b[k] / a[k] - 10) < 1e-12, `${k} scaled by ${b[k] / a[k]}, not 10`);
  }
});

test("the validity gate refuses outside the calibration band rather than extrapolating", () => {
  assert.equal(inRange(TEFF_MIN), true, "the band edges themselves are valid");
  assert.equal(inRange(TEFF_MAX), true);
  assert.equal(inRange(TEFF_MIN - 1), false);
  assert.equal(inRange(TEFF_MAX + 1), false);
  assert.equal(inRange(NaN), false);
  // A hot star must return null, NOT an absurd distance or a NaN — the quartic
  // would give |T*|^4 ~ 1e17 here.
  assert.equal(habitableZone(30000, 1e5), null);
  assert.equal(habitableZone(2000, 1e-4), null);
  assert.equal(habitableZone(5772, 0), null, "a dark star has no habitable zone");
  assert.equal(habitableZone(5772, -1), null);
});

test("every returned edge is a finite positive distance", () => {
  for (let Teff = TEFF_MIN; Teff <= TEFF_MAX; Teff += 25) {
    const z = habitableZone(Teff, 1.0);
    for (const [k, v] of Object.entries(z)) {
      assert.ok(Number.isFinite(v) && v > 0, `${k} = ${v} at ${Teff} K`);
    }
  }
});
