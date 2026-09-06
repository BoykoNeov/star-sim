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

// A(lambda)/A(V) from photometry.py at the wavelengths the port was checked
// against: the optical branch, the 2175 A bump, the deep UV, and — since the near-IR
// cube — the three 2MASS pivots on the IR branch (CCM89 eq. 2a/2b).
const PY = {
  5000: 1.122246878899302,   // optical branch (CCM89 eq. 3a/3b)
  2175: 3.185101275314405,   // the UV bump — the b(x) Lorentzian peak
  1500: 2.6366457176802633,  // deep UV, base eq. 4a/4b with NO F_a/F_b term
  12350: 0.28760574926358984,  // 2MASS J — IR branch (A_J/A_V, ~0.29)
  16620: 0.17830578090680688,  // 2MASS H
  21590: 0.11701313389302863,  // 2MASS Ks — dust is ~9x weaker here than in V
  25000: 0.09240552762537405,  // the cube's red edge, 2.5 um
};

test("the port still matches photometry.py at every checked wavelength", () => {
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

test("reddening is exactly identity outside 0.3-8 inverse microns", () => {
  // Not "small" — exactly zero. The SED panel spans gamma-ray to radio, so most of
  // its 14 decades must be untouched rather than nudged.
  assert.equal(ccm89(4e4), 0, "past 3.33 um the coefficients are zero");
  assert.equal(ccm89(1e6), 0, "radio");
  assert.equal(ccm89(1200), 0, "below 1250 A the coefficients are zero");
  assert.equal(ccm89(1), 0, "X-ray");
  assert.equal(extinctionFactor(4e4, 1.0), 1.0);
  assert.equal(extinctionFactor(1200, 1.0), 1.0);
});

test("the near-IR is reddened, and by less than the optical", () => {
  // The whole point of the IR branch: 9500 A used to return exactly 0, so a dust-
  // reddened star kept an untouched J/H/K tail beside a dimmed B/V. Extinction must
  // now be non-zero out to 3.33 um and must FALL monotonically with wavelength.
  const ir = [9500, 12350, 16620, 21590, 25000].map((l) => ccm89(l));
  for (const v of ir) assert.ok(v > 0, "the near-IR must be reddened at all");
  for (let i = 1; i < ir.length; i++) {
    assert.ok(ir[i] < ir[i - 1], "extinction must fall towards the infrared");
  }
  assert.ok(ir[0] < ccm89(5500), "the near-IR is less extinguished than V");
});

test("the IR and optical branches meet at x = 1.1 (a 3e-4 seam, not a cliff)", () => {
  // CCM89's branches are separate fits, so they do NOT agree to machine precision at
  // the seam: measured here, the IR power law gives 0.47100 and the optical
  // polynomial 0.47131 — a 3.0e-4 step (0.06 %), which is CCM89's own, not a port
  // bug. Pinned as a BOUND: a mis-transcribed coefficient would open it far wider.
  const seam = ccm89(1e4 / 1.1), justBelow = ccm89(1e4 / 1.0999999);
  const step = Math.abs(seam - justBelow);
  assert.ok(step < 1e-3, `step at the seam: ${seam} vs ${justBelow} (${step})`);
  assert.ok(step > 1e-5, "a step of exactly 0 would mean one branch never runs");
});

test("the band edges are inclusive (3.33 um and 1250 A are reddened, not identity)", () => {
  assert.ok(ccm89(1e4 / 1.1) !== 0, "x = 1.1 exactly is inside the optical branch");
  assert.ok(ccm89(1e4 / 0.3) !== 0, "x = 0.3 exactly is inside the IR branch");
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
