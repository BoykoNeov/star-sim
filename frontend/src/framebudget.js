// Frame-budget governor: decides when a canvas is missing its frame budget badly
// enough that it should give up resolution rather than keep trying.
//
// Pure on purpose. It owns no canvas, no WebGL context and no clock — the caller
// feeds it a frame time, the elapsed clock and the current pixel ratio, and gets
// back either null ("stay") or the ratio to switch to. That is what lets
// `node --test` drive the false-positive cases directly (see framebudget.test.mjs);
// the alternative — asserting them through a real WebGL loop — is exactly the DOM
// shim the frontend test README says not to write.
//
// Its one consumer is star.js, whose surface shader is the most expensive thing in
// the app (108 hash evaluations per fragment). The defaults below are the measured
// ones; the reasoning for each lives at the call site.

export function createFrameBudget({
  warmupS = 3,        // seconds of animation before any sample counts (shader compile, first paint)
  windowFrames = 30,  // frames per decision window
  slowMs = 25,        // window MEDIAN above this = the budget is blown
  slowWindows = 2,    // consecutive slow windows required before acting
  step = 0.5,         // how much ratio one adaptation gives up
  floor = 1,          // never go below this
} = {}) {
  let frames = [];
  let slowRun = 0;

  return {
    // Drop everything accumulated. The caller uses this wherever the next frame
    // time is not comparable to the last one — a paused render loop resuming, or
    // a ratio change — so a window can never straddle a discontinuity.
    forget() {
      frames.length = 0;
      slowRun = 0;
    },

    // One frame. Returns null to stay put, or {ratio, median} to adapt.
    sample(dtMs, elapsedS, ratio) {
      if (elapsedS < warmupS) return null;
      if (!(ratio > floor)) return null;          // nothing left to give up
      frames.push(dtMs);
      if (frames.length < windowFrames) return null;

      // MEDIAN, not mean: dt is request-animation-frame pacing, so a single stall
      // poisons a mean — a garbage-collection pause, a fetch, or a backgrounded tab
      // coming back (frames stop entirely there, so the first one back is a
      // multi-second dt). The median ignores all of those, and for the case we
      // actually want — every frame slow — it equals the mean.
      const sorted = frames.slice().sort((a, b) => a - b);
      const median = sorted[sorted.length >> 1];
      frames.length = 0;

      if (median <= slowMs) { slowRun = 0; return null; }
      if (++slowRun < slowWindows) return null;
      slowRun = 0;
      return { ratio: Math.max(floor, ratio - step), median };
    },
  };
}
