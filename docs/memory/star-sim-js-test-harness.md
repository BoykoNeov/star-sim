---
name: star-sim-js-test-harness
description: The frontend/tests node --test harness — what it covers, the extract-don't-shim rule, and the cross-language CCM89 parity pin.
metadata:
  type: project
---

# The JS test harness (`frontend/tests`, shipped 2026-09-03)

**Current state.** 50 tests over six DOM-free modules under Node's own runner, in
CI as a second job. Run it with `cd frontend/tests && node --test` — bare, from
inside the directory. Covered: `color.js`, `hz.js`, `seismo.js`, `gravdark.js`,
`classify.js`, `reddening.js`. Not covered, by design: everything that draws.
`frontend/tests/README.md` is the operational doc; this file is the why.

## The three rules it establishes

**A helper earns a test by being extracted, never by the harness growing a stub.**
`classify.js` was on the plan's "pure, no DOM" list but wasn't: its only export was
`createClassification(el)`, which writes `el.innerHTML`. The fix was to lift
`classifyLabel(state, mode, opts)` out as a named export and leave the factory as
two DOM writes. A fake `el` would have worked and would have been the wrong move —
a DOM shim in a harness whose entire value is needing no shim. Same call next time.

**Invariants first, pinned values second.** A number harvested from the code under
test preserves a flipped sign or a wrong exponent perfectly happily, which is this
project's named defect class (*plausible but wrong*). So the load-bearing assertions
are identities the modules' own headers state — `kEq²·kPol = 1` and area-weighted
flux conservation in `gravdark.js`, the seismic relations **inverting** back to the
(M, R) they were given (one assertion pinning four exponents), CCM89 being *exactly*
identity outside 1.1–8 µm⁻¹, Wien's law falling out of `planck()`. Published anchors
and the regressions the headers record sit under those. Anything pinned from current
output is labeled "pinned from current implementation" in a comment; that line is the
harness's honesty gate and must stay visible.

**Cross-language ports get pinned from both ends.** `reddening.js` is a hand port of
`photometry.py`'s `ccm89`, and the two paint the *same* extinction side by side (the
served magnitude readout vs. the drawn overlay). Its header said to re-run the match
by hand. The same three anchors now live in
`backend/tests/test_photometry.py::test_ccm89_matches_the_javascript_port`, so either
side moving fails a test. Includes 1500 Å specifically, where the port deliberately
omits the deep-UV F_a/F_b correction a textbook CCM89 adds — a one-sided "fix" would
silently put the two on different laws.

## Two gotchas

**Invocation form.** `node --test` with a *glob* argument needs Node ≥ 22; with a
*directory* argument it fails outright on Node 24 (`Cannot find module …/tests`).
Bare `node --test` from inside the directory discovers `*.test.mjs` by Node's own
naming convention on every version — that is what CI runs and what the README says.

**`seismo.js` imports `canvas.js`.** It loads under bare Node only because
`fitCanvas` touches `window` inside its body, not at module scope. Hoisting a
`window.devicePixelRatio` read to `canvas.js`'s top level breaks `seismo.test.mjs`
with an error a long way from its cause.

## Three assertions the harness caught in its own first hour

Written from memory, all wrong, all failed immediately: Venus (0.72 AU) is *inside*
the 0.75 AU recent-Venus edge, not outside; a log g 2.5 giant rings at ~40 µHz, not
below 1 % of solar; and blue/red is flat, not rising, below ~1800 K where the blue
channel clamps out of gamut. Cheap evidence that the tests test something.

Related: [[star-sim-mainjs-guards-chokepoint]] (the same-day refactors that had only a
screenshot pass), [[star-sim-ci-data-free-contract]], [[star-sim-observer-cmd]] (the
photometry side of the CCM89 pin), [[star-sim-frontend-ux]].
