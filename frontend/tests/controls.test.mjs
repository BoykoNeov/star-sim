// controls.js — the slider/number-box arithmetic every control shares.
//
// Priority order per the README: the identities the module's header states first
// (round-trip, geometric mean, "outside the tolerance nothing moves"), then the
// honesty gates (a blank box commits nothing), then the one published anchor
// (the distance modulus), then the behaviours the seven hand-written loops this
// module replaced actually had — first-wins ties and a STRICT tolerance. Those
// last two are the ones a rewrite could silently change.

import test from "node:test";
import assert from "node:assert/strict";

import {
  nearestWithin,
  snapWithin,
  logValueAt,
  logPosOf,
  commitNumber,
} from "../src/controls.js";

const near = (a, b, tol = 1e-12) =>
  assert.ok(Math.abs(a - b) <= tol, `${a} !~= ${b} (within ${tol})`);

// --- nearestWithin / snapWithin ---------------------------------------------

test("nothing within the tolerance leaves the value untouched", () => {
  // The whole point of a magnetic landmark: every position BETWEEN landmarks
  // stays reachable. A snap that always snapped would trap the age slider.
  const ticks = [0, 0.5, 1];
  assert.equal(nearestWithin(0.3, ticks, 0.015), -1);
  assert.equal(snapWithin(0.3, ticks, 0.015), 0.3);
});

test("a value inside the tolerance snaps to the EXACT landmark", () => {
  // Not "close to" the landmark — the exact float. main.js then derives a track
  // row with Math.round() from this, so an approximate snap lands one row off.
  const ticks = [0, 0.46, 1];
  assert.equal(snapWithin(0.4655, ticks, 0.015), 0.46);
  assert.equal(nearestWithin(0.4655, ticks, 0.015), 1);
});

test("the tolerance is strict: exactly `tol` away does not snap", () => {
  assert.equal(nearestWithin(0.015, [0], 0.015), -1);
  assert.equal(nearestWithin(0.0149, [0], 0.015), 0);
});

test("ties go to the first target in scan order", () => {
  // The hand-written loops all used `d < bestD`, so the earlier of two
  // equidistant targets won. The age strip relies on it: a late landmark row can
  // sit the same distance from the drag as the 1.0 endpoint.
  assert.equal(nearestWithin(0.5, [0.4, 0.6], 0.2), 0);
  assert.equal(nearestWithin(0.5, [0.6, 0.4], 0.2), 0);
});

test("snapping is idempotent", () => {
  const ticks = [0, 0.12, 0.28, 1];
  const once = snapWithin(0.275, ticks, 0.015);
  assert.equal(snapWithin(once, ticks, 0.015), once);
});

test("no targets, or an infinite tolerance, both behave", () => {
  assert.equal(nearestWithin(0.5, [], 0.015), -1);
  assert.equal(snapWithin(0.5, [], 0.015), 0.5);
  // tol = Infinity is the plain nearest-neighbour search the SN day -> sample
  // lookup needs (no "close enough" notion there).
  assert.equal(nearestWithin(97, [0, 30, 120, 400], Infinity), 2);
});

// --- logValueAt / logPosOf ---------------------------------------------------

test("position -> value -> position is the identity", () => {
  // The invariant that pins BOTH directions at once: a flipped sign or a swapped
  // lo/hi in either function breaks the round trip.
  for (const p of [0, 0.05, 0.25, 0.5, 0.7159, 1]) {
    near(logPosOf(logValueAt(p, 0.001, 0.3), 0.001, 0.3), p);
    near(logPosOf(logValueAt(p, 3.9, 286), 3.9, 286), p);   // POSYDON M1 span
  }
});

test("the endpoints are the bounds themselves", () => {
  near(logValueAt(0, 0.001, 0.3), 0.001);
  near(logValueAt(1, 0.001, 0.3), 0.3);
  assert.equal(logPosOf(0.001, 0.001, 0.3), 0);
  assert.equal(logPosOf(0.3, 0.001, 0.3), 1);
});

test("the midpoint of a log slider is the geometric mean", () => {
  // An independent identity, not a value harvested from the implementation:
  // halfway along a log axis is sqrt(min*max) — 0.1 d and 5179 d meet at ~22.8 d.
  near(logValueAt(0.5, 0.1, 5179), Math.sqrt(0.1 * 5179), 1e-9);
  near(logValueAt(0.5, 10, 1e5), Math.sqrt(10 * 1e5), 1e-9);
});

test("the map is monotonic increasing", () => {
  let prev = -Infinity;
  for (let p = 0; p <= 1.0001; p += 0.05) {
    const v = logValueAt(p, 0.1, 5179);
    assert.ok(v > prev, `not increasing at pos=${p}`);
    prev = v;
  }
});

test("out-of-range inputs park at the ends instead of running off", () => {
  // A grid whose bounds shrank under a [Fe/H] bucket change must not leave the
  // thumb off the track or the value outside the new grid.
  near(logValueAt(-0.3, 3.9, 286), 3.9);
  near(logValueAt(1.4, 3.9, 286), 286);
  assert.equal(logPosOf(1.0, 3.9, 286), 0);
  assert.equal(logPosOf(1e6, 3.9, 286), 1);
});

test("100 pc sits a quarter along the observer's 10 pc – 100 kpc slider", () => {
  // The published anchor: distance modulus μ = 5 log10(d/10 pc), so d = 100 pc
  // is one decade into a four-decade axis. Independent of this code.
  near(logPosOf(100, 10, 1e5), 0.25);
  near(logValueAt(0.25, 10, 1e5), 100);
});

// --- commitNumber ------------------------------------------------------------

test("a blank or unparseable box commits nothing", () => {
  // The honesty gate: `null` means "leave the model alone". Returning 0 here
  // would silently reset the star's mass when the user cleared the box.
  assert.equal(commitNumber("", 0.1, 300), null);
  assert.equal(commitNumber("   ", 0.1, 300), null);
  assert.equal(commitNumber("abc", 0.1, 300), null);
  assert.equal(commitNumber("1.2.3", 0.1, 300), null);
  assert.equal(commitNumber(null, 0.1, 300), null);
  assert.equal(commitNumber(undefined, 0.1, 300), null);
  assert.equal(commitNumber("Infinity", 0.1, 300), null);
  assert.equal(commitNumber("NaN", 0.1, 300), null);
});

test("a real number is clamped, never snapped", () => {
  // The number box is the arbitrary-precision escape hatch: 0.99 must stay 0.99
  // (the slider would have snapped it to 1.0), but it still can't leave the
  // provider's valid domain.
  assert.equal(commitNumber("0.99", 0.1, 300), 0.99);
  assert.equal(commitNumber("0.05", 0.1, 300), 0.1);
  assert.equal(commitNumber("1000", 0.1, 300), 300);
  assert.equal(commitNumber("1e2", 0.1, 300), 100);
  assert.equal(commitNumber("  2.5  ", 0.1, 300), 2.5);
});

test("zero commits as zero", () => {
  // A falsy-but-valid value: A_V = 0 and [Fe/H] = 0 are both meaningful, so a
  // truthiness test at the call site would have dropped them.
  assert.equal(commitNumber("0", -0.5, 0.5), 0);
  assert.equal(commitNumber("-0.3", -0.5, 0.5), -0.3);
});

test("with no bounds given, nothing is clamped", () => {
  // The age box: its range is only known after the track it is about to trigger.
  assert.equal(commitNumber("13.8"), 13.8);
  assert.equal(commitNumber("-5"), -5);
});
