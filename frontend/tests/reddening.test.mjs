// reddening.js — the CCM89 extinction law.
//
// This module's header calls itself "a VERBATIM port of the backend photometry.py
// ccm89" and says the two must stay identical, because the same physical extinction
// feeds BOTH the served magnitude readout (Python) and the reddened curve drawn
// beside it (JS). Until now that match was re-run by hand. The three anchor values
// below are asserted HERE and, byte-identical, in
// backend/tests/test_photometry.py::test_ccm89_matches_the_javascript_port — so a
// change to either language fails a test instead of silently drifting.
//
// The anchors were generated once from the Python side:
//   python -c "from star_sim.photometry import ccm89; print(float(ccm89(5000.0)))"

import test from "node:test";
import assert from "node:assert/strict";
import { ccm89, extinctionFactor } from "../src/reddening.js";

// A(lambda)/A(V) from photometry.py at the three wavelengths the port was checked
// against: the optical branch, the 2175 A bump, and the deep UV.
const PY = {
  5000: 1.122246878899302,   // optical branch (CCM89 eq. 3a/3b)
  2175: 3.185101275314405,   // the UV bump — the b(x) Lorentzian peak
  1500: 2.6366457176802633,  // deep UV, base eq. 4a/4b with NO F_a/F_b term
};

test("the port still matches photometry.py at the three checked wavelengths", () => {
  for (const [lam, expected] of Object.entries(PY)) {
    const got = ccm89(Number(lam));
    assert.ok(Math.abs(got - expected) < 1e-12,
      `ccm89(${lam}) = ${got}, Python gives ${expected} — the two implementations have drifted`);
  }
});

test("the deep-UV branch keeps its deliberate omission of the F_a/F_b correction", () => {
  // A textbook CCM89 adds a deep-UV correction above x = 5.9 (below ~1695 A). This
  // port deliberately does not, to match photometry.py. If someone "fixes" it from a
  // reference, a(1500) moves by ~0.03 and the drawn overlay leaves the served
  // readout behind — so pin the uncorrected value specifically.
  const x = 1e4 / 1500;
  assert.ok(x > 5.9, "1500 A must be in the range where the correction would apply");
  assert.ok(Math.abs(ccm89(1500) - PY[1500]) < 1e-12);
});

test("reddening is exactly identity outside 1.1-8 inverse microns", () => {
  // Not "small" — exactly zero. The SED panel spans gamma-ray to radio, so most of
  // its 14 decades must be untouched rather than nudged.
  assert.equal(ccm89(9500), 0, "past 9091 A the coefficients are zero");
  assert.equal(ccm89(1e6), 0, "radio");
  assert.equal(ccm89(1200), 0, "below 1250 A the coefficients are zero");
  assert.equal(ccm89(1), 0, "X-ray");
  assert.equal(extinctionFactor(9500, 1.0), 1.0);
  assert.equal(extinctionFactor(1200, 1.0), 1.0);
});

test("the band edges are inclusive (9091 A and 1250 A are reddened, not identity)", () => {
  assert.ok(ccm89(1e4 / 1.1) !== 0, "x = 1.1 exactly is inside the optical branch");
  assert.ok(ccm89(1e4 / 8.0) !== 0, "x = 8.0 exactly is inside the UV branch");
});

test("A_V = 0 is a no-op: 'Observer off' must not touch a single flux value", () => {
  for (const lam of [1200, 1500, 2175, 5000, 9500]) {
    assert.equal(extinctionFactor(lam, 0), 1.0);
    assert.equal(extinctionFactor(lam, null), 1.0);
    assert.equal(extinctionFactor(lam, undefined), 1.0);
  }
});

test("extinction dims, and dims the blue more than the red", () => {
  const av = 1.0;
  const blue = extinctionFactor(4400, av);   // B band
  const red = extinctionFactor(6400, av);    // R band
  assert.ok(blue > 0 && blue < 1, `B-band factor ${blue} must dim`);
  assert.ok(red > 0 && red < 1, `R-band factor ${red} must dim`);
  assert.ok(blue < red, "reddening means the blue is extinguished harder — hence the name");
});

test("A(V)/A(V) is 1 at the V band by construction of R_V", () => {
  // CCM89 is normalized so the V band (5500 A) has A(lambda)/A(V) = 1 for the
  // standard R_V = 3.1. This is the law's own definition, not a value from this code.
  assert.ok(Math.abs(ccm89(5500, 3.1) - 1.0) < 0.01, `A(V)/A(V) = ${ccm89(5500, 3.1)}`);
});

test("a larger R_V flattens the law (a greyer, less selective extinction)", () => {
  const b31 = ccm89(4400, 3.1), b50 = ccm89(4400, 5.0);
  assert.ok(b50 < b31, "the blue excess shrinks as R_V grows");
});
