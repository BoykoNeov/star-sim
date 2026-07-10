---
name: star-sim-habitable-zone
description: "Axis D of the outward quartet — the circumstellar habitable-zone band on the true-size scale bar (hz.js + scale.js), a pure L+Teff view from Kopparapu 2014, marching outward as the star brightens. D1 BUILT."
metadata: 
  node_type: memory
  type: project
  originSessionId: 80959481-33ff-4949-b37d-cc40d832fdb4
---

**Axis D — the habitable-zone band. D1 BUILT 2026-07-10** (frontend-only, no backend
change, 412 pytest unchanged, Playwright 1440+390 zero console errors). The third of the
outward quartet's four axes to ship (after [[star-sim-isochrone-cluster]] Axis B); the
scope-edge axis (edges toward planets).

## What it is
The circumstellar liquid-water zone drawn on the true-size **scale bar** (rides
`scale.js`, like the swallowed-orbit rings). A pure **VIEW** of two `StellarState`
numbers — **L + Teff** — that never touches the HR marker. The payoff is watching the
band **march outward** as the star brightens up the giant branch (Earth's fate: the zone
sweeps past 1 AU, then the swelling giant engulfs Earth).

## Architecture (the split)
- **`frontend/src/hz.js`** — the PURE compute: `habitableZone(Teff, L)` → the four edge
  distances in AU, or `null` out of range; `inRange(Teff)` gate; `TEFF_MIN/MAX`. A
  helper-to-a-drawing-module (the SED/gravdark precedent), unit-checkable in isolation.
- **`scale.js`** — the DRAW half: `setHZ(on)` (retained flag, redraws from the scale
  bar's retained Teff/L/R — the `sed.js setPopulation` idiom), `drawHZ()`, the caption
  branch `describeHZ()`, and axis widening in `update()`/`redrawFromRetained()`.
- **`main.js`** — `hzOn` state, `#hz-toggle` listener (guarded to live mode),
  `dropHZForModeSwitch()` in the shared `dropHeliumForModeSwitch()` chokepoint.
- **`styles.css`** — `.hz-toggle-row` hidden in wd/wr/sn/stripped modes.

## The physics (Tier-2, labeled)
**Kopparapu et al. 2014** (ApJ 787, L29 — the *corrected* update, NOT 2013), 1 M⊕:
`S_eff = S_eff⊙ + a·T* + b·T*² + c·T*³ + d·T*⁴`, `T* = Teff − 5780 K`, then
`d = √((L/L⊙)/S_eff)` AU. **Four internally-consistent edges** drawn as nested bands:
- solid **conservative** band: runaway greenhouse (inner) → maximum greenhouse (outer)
- dashed **optimistic** edges: recent Venus (inner) → early Mars (outer)
- **moist greenhouse DROPPED** — the 2014 runaway revision moved *inside* the un-revised
  2013 moist edge, so mixing them is inconsistent; the 2014 paper itself omits it.

Coefficients (verify against the solar anchor if ever re-touched — Sun T*=0 → runaway
**0.95 AU**, maxGH **1.68 AU**, recent Venus 0.75, early Mars 1.77; these 4 numbers are
the guard on any transcription). Pulled from the paper via ar5iv, NOT memory.

## The two load-bearing honesty gates (advisor-driven)
1. **Measure-first: validate coefficients against the solar anchor BEFORE drawing.** A
   wrong coefficient is a plausible-but-wrong band a screenshot can't catch. Ran a
   standalone `node` check of `hz.js` first (Sun → 0.95/1.68 exactly) → only then wired
   the canvas.
2. **The quartic DIVERGES outside 2600–7200 K** (not just loses accuracy — T*⁴ explodes,
   S_eff goes negative, √ → NaN/absurd distance that breaks the draw). So `inRange()`
   skips the compute AND the band entirely, never extrapolates. The band honestly
   **blinks off** for hot stars (Teff>7200) with an out-of-range caption — an evolving
   star crossing 7200 K is expected, the caption owns it. A 1 M☉ MS→RGB stays in range.

## Scoping decisions (what's IN vs OUT, and why)
- **Only L + Teff enter.** Mass/gravity/composition/rotation do NOT enter Kopparapu —
  deliberately excluded (the "don't fake a feature" rule).
- **Spectrum enters THROUGH Teff** — the near-IR albedo/absorption climate effect IS the
  Teff-dependence of the coefficients. NO `/spectrum` coupling (would fake precision).
- **UV/X-ray/flares OUT of the band** — a separate, speculative habitability hazard (not
  the liquid-water energy-balance zone). Owned by the caption caveat (M-dwarf flares).
- **Planet mass fixed at 1 M⊕** — no planetary sandbox (restrained overlay).
- **R_rsun** doesn't set the edges but drives engulfment (the scale bar's swallowed-orbit
  rings) — the "giant swallows Earth" story.

## Axis widening (the SN idiom)
The scale bar maxes at 1500 R☉ (~7 AU), but a luminous giant's HZ is tens of AU ≈
thousands of R☉. When `earlyMars·215 > R_MAX`, `hzWide` extends `logHi` to fit it and
`drawOrbits` swaps in the outer-planet set (Mercury→Neptune, reuses `ORBITS_SN`) so the
band lands against Neptune's orbit, not a bare edge. `logLo` stays at `LOG_LO` so the
star's own radius marker always shows. SN mode always wins (HZ never composes with it).

## Gate 0 (PASSED through the runtime)
- Sun: 0.98–1.7 AU (evolved; standalone ZAMS = 0.95/1.68) straddling Earth's ring.
- Same 1 M☉ at old age → **34–65 AU past Neptune**, axis widened, Earth "left inside the
  conservative inner edge."
- K/M dwarf zones correctly **closer in** (0.55 M☉ → 0.24–0.45 AU).
- Hot star (Teff 12637 K) → out of range, no band, honest caption.
- Teardown verified: entering stripped-mode hides the toggle + drops the band (no leak).

## Advisor's caught bug (fixed before commit)
The faint-star caption clause said "the zone lies **farther out**" — BACKWARDS. A faint
star's HZ is **closer in** (smaller AU); Earth is too cold *because* the zone is closer.
Hits most K/M dwarfs. Fixed to "this faint star's zone lies closer in." (I'd truncated the
K-dwarf screenshot caption, so it slipped my own Gate 0 — read captions in full.)

## Not built
**D2** (HZ history — a ghost trail of the band at ZAMS vs now vs RGB) is deferred: the
live march-outward on the age scrub already carries the payoff.

Plan: `docs/plans/outward-quartet-atlas.md` §Axis D. Next quartet axis = **C
asteroseismology** (frontend-only, échelle diagram), then **A the observer's view** (the
capstone — reddening + SVO photometry + a CMD, composes with Axis B into a Gaia diagram).
