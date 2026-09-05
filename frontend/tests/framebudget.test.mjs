// framebudget.js — the governor that lowers the 3D star's pixel ratio when a slow
// GPU cannot hold the frame budget.
//
// The interesting assertions here are all NEGATIVE. Adapting when the machine is
// genuinely slow was verified through the real runtime (SwiftShader at DPR 2, a
// 15 Msun giant: 100 ms/frame -> 33.3 ms after two steps). What the runtime pass
// CANNOT show is the expensive mistake: adapting when nothing is wrong. That is a
// silent visual regression on hardware that was fine, and every false-positive
// source below is a real thing browsers do -- a cold start's shader compile, one
// garbage-collection pause, a backgrounded tab where frames stop entirely.

import test from "node:test";
import assert from "node:assert/strict";
import { createFrameBudget } from "../src/framebudget.js";

// Feed n frames of `dtMs` starting at `t0` seconds, advancing the clock by each
// frame's own duration. Returns every non-null verdict.
function run(budget, dtMs, n, { t0 = 10, ratio = 2 } = {}) {
  const verdicts = [];
  let t = t0;
  let r = ratio;
  for (let i = 0; i < n; i++) {
    const v = budget.sample(dtMs, t, r);
    if (v) { verdicts.push(v); r = v.ratio; }
    t += dtMs / 1000;
  }
  return { verdicts, ratio: r };
}

test("a capable GPU never adapts, however long it runs", () => {
  // 16.7 ms is vsync at 60 Hz -- what the dev box reports in every state, giant
  // included. Ten minutes of it must not move the ratio by a hair.
  const b = createFrameBudget();
  const { verdicts, ratio } = run(b, 16.7, 36000);
  assert.equal(verdicts.length, 0, "vsync frames must never trigger an adaptation");
  assert.equal(ratio, 2);
});

test("sustained slow frames adapt, and only after two full windows", () => {
  const b = createFrameBudget();
  // 29 frames is one short of the first window; 59 is one short of the second.
  assert.equal(run(createFrameBudget(), 100, 29).verdicts.length, 0, "no verdict inside window 1");
  assert.equal(run(createFrameBudget(), 100, 59).verdicts.length, 0, "no verdict inside window 2");
  const { verdicts } = run(b, 100, 60);
  assert.equal(verdicts.length, 1, "exactly one adaptation at 60 frames");
  assert.equal(verdicts[0].ratio, 1.5, "one step down from 2");
  assert.equal(verdicts[0].median, 100, "reports the median it acted on");
});

test("nothing counts during the warm-up: a cold start's slow frames are ignored", () => {
  // Shader compilation and first paint land here. Feeding 200 catastrophic frames
  // inside the warm-up window must leave the ratio untouched.
  const b = createFrameBudget();
  let t = 0;
  for (let i = 0; i < 200; i++) { assert.equal(b.sample(500, t, 2), null); t += 0.01; }
  // ...and having ignored them, it must not carry a grudge: healthy frames after
  // the warm-up still do not adapt.
  assert.equal(run(b, 16.7, 600, { t0: 3 }).verdicts.length, 0);
});

test("one stall does not decide -- a backgrounded tab or a GC pause is ignored", () => {
  // The failure the median exists to prevent. A tab in the background stops
  // rendering entirely, so the first frame back can be a multi-second dt; with a
  // MEAN, one 3000 ms frame among 29 healthy ones is 116 ms and would adapt twice.
  const b = createFrameBudget();
  let t = 10;
  const verdicts = [];
  for (let w = 0; w < 20; w++) {
    for (let i = 0; i < 30; i++) {
      const dt = i === 0 ? 3000 : 16.7;      // one monster frame per window
      const v = b.sample(dt, t, 2);
      if (v) verdicts.push(v);
      t += dt / 1000;
    }
  }
  assert.equal(verdicts.length, 0, "a single stall per window must never adapt");
});

test("it steps down one notch at a time and stops at the floor", () => {
  const b = createFrameBudget();
  const { verdicts, ratio } = run(b, 100, 60 * 6);
  assert.deepEqual(verdicts.map((v) => v.ratio), [1.5, 1], "2 -> 1.5 -> 1, then nothing");
  assert.equal(ratio, 1, "the floor is 1: never below the CSS size");
  // Once at the floor it must go quiet rather than spin: further slow frames are
  // not even collected (there is nothing left to give up).
  assert.equal(run(b, 100, 600, { ratio: 1 }).verdicts.length, 0);
});

test("forget() clears a half-built slow run, so a window cannot straddle a pause", () => {
  // star.js calls this when the render loop un-parks after the canvas scrolls back
  // into view. Without it, the slow window recorded before the pause would combine
  // with one after it and adapt on evidence from two different situations.
  const b = createFrameBudget();
  run(b, 100, 30);                 // one slow window banked
  b.forget();
  const { verdicts } = run(b, 100, 30);   // a second slow window, post-pause
  assert.equal(verdicts.length, 0, "the banked window must not count after forget()");
  // A third window (the second since forget) does adapt -- forget clears, not disables.
  assert.equal(run(b, 100, 30).verdicts.length, 1);
});

test("the threshold discriminates 30 fps from vsync", () => {
  // 33.3 ms (30 fps) is above the 25 ms threshold and adapts; 16.7 ms does not.
  // This is the line the whole feature turns on, so pin it explicitly.
  assert.equal(run(createFrameBudget(), 33.3, 60).verdicts.length, 1);
  assert.equal(run(createFrameBudget(), 24.9, 60).verdicts.length, 0);
});
