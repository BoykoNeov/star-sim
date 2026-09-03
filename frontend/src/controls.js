// Control math — the DOM-free arithmetic behind the sliders and number boxes.
//
// Every control in this app is one of three shapes, and each shape had been
// hand-written once per control (7 snap loops, 6 log-position pairs, 9 number-box
// preambles) before this module existed:
//
//   1. "snap to a landmark if the drag lands close to one, else keep the raw
//      value"  ->  nearestWithin()
//   2. "a 0..1 range input standing in for a value spanning decades"
//      ->  logValueAt() / logPosOf()
//   3. "an editable number box: ignore blank/garbage, clamp what's left"
//      ->  commitNumber()
//
// All three are pure functions of numbers — no DOM, no fetch, no module state —
// so they are covered by `frontend/tests/controls.test.mjs` under `node --test`
// (see that directory's README: this module exists partly *so* the snap/log math
// can be tested at all; the wiring that calls it stays in main.js, where the
// application state it mutates lives).
//
// Deliberately NOT here: the mass slider's own map (main.js `massFromSliderPos`).
// Its bounds are already stored as log10 values and `massValue` is the source of
// truth for every fetch, so routing it through pow/log again would risk float
// drift on the one number that must not drift.

const clamp01 = (x) => Math.min(1, Math.max(0, x));

// Index of the target nearest `value`, provided it is STRICTLY within `tol`;
// -1 when nothing is close enough (the caller then keeps the raw value, which is
// what makes every position between landmarks still reachable). Scanning order
// decides ties — the first of two equidistant targets wins — which is what the
// hand-written loops did, and matters for the age strip where a landmark row can
// coincide with the 0/1 endpoints.
//
// `tol = Infinity` degrades to a plain nearest-neighbour search (the SN light
// curve's day -> sample lookup, which has no "close enough" notion).
export function nearestWithin(value, targets, tol) {
  let bestIdx = -1, bestD = tol;
  for (let i = 0; i < targets.length; i++) {
    const d = Math.abs(value - targets[i]);
    if (d < bestD) { bestD = d; bestIdx = i; }
  }
  return bestIdx;
}

// The snap itself: the nearest target within `tol`, or `value` untouched. The
// landmarks are magnetic, never a cage.
export function snapWithin(value, targets, tol) {
  const i = nearestWithin(value, targets, tol);
  return i < 0 ? value : targets[i];
}

// A 0..1 slider position -> the physical value it stands for, logarithmically.
// Used wherever the axis spans decades (⁵⁶Ni 0.001–0.3 M☉, POSYDON periods
// 0.1–5179 d, observer distance 10 pc–100 kpc): a linear range input would spend
// 90 % of its travel in the top decade.
export function logValueAt(pos, min, max) {
  const lo = Math.log10(min), hi = Math.log10(max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
}

// The exact inverse — a physical value -> its slider position. Clamped, so a
// value outside the (grid-derived) bounds parks the thumb at the end rather than
// off the track.
export function logPosOf(value, min, max) {
  const lo = Math.log10(min), hi = Math.log10(max);
  return clamp01((Math.log10(value) - lo) / (hi - lo));
}

// An editable number box's committed value, or `null` when there is nothing to
// commit. `null` means "leave the model alone": the box is empty (the user
// cleared it and tabbed away) or holds something that isn't a finite number.
// Anything real is clamped to [min, max] — the number box is the
// arbitrary-precision escape hatch, so it BYPASSES snapping, but it is still not
// allowed off the valid domain. Bounds default to unbounded for the one box (age)
// whose range is set by the track it is about to trigger.
export function commitNumber(raw, min = -Infinity, max = Infinity) {
  if (raw === null || raw === undefined) return null;
  const text = String(raw);
  if (text.trim() === "") return null;
  const v = Number(text);
  if (!Number.isFinite(v)) return null;
  return Math.min(Math.max(v, min), max);
}
