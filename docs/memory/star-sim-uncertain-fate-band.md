---
name: star-sim-uncertain-fate-band
description: The uncertain-fate honesty gate — `fate_boundary_status()` + `/fate_boundary_status` + the gateway hedge that stops the WD↔supernova verdict flipping crisply between two grid nodes.
metadata:
  type: project
---

The **uncertain-fate caption** (6.5–8 M☉) — the *third* data-derived honesty gate on the
spine, after the rotation gate ([[star-sim-rotation-subpop-atlas]]) and the He-ignition
cliff ([[star-sim-he-ignition-cliff]]). Built 2026-09-03; it was item 2 on the
`science-hurdles.md` §6 NEXT list. It changes **no physics and no classification** — the
gateway still enters exactly the endgame it always did; this is the sentence that admits
the verdict is contested.

**What it confesses.** MIST holds one track per mass, so `endgame()` returns one fate per
star and the gateway flips from "→ Continue: White Dwarf" to "Core collapse" between two
adjacent grid nodes. That step is the grid's, not nature's: a star that ends with a
degenerate oxygen–neon core may leave an O-Ne white dwarf **or** explode as a faint
electron-capture supernova, depending on convective overshoot, super-AGB mass loss and
the carbon-burning treatment. In the band the app now says it doesn't know.

**The measured half.** `_fate_boundary(axis, grid)` scans every track's fate and returns
`(wd_max, sn_min)` — the heaviest node that still ends a WD, the lightest that
core-collapses. Measured over all ten grids (2026-09-03): **6.5 → 7.0 M☉ at solar and
+0.5**, 6.5 → 7.0 at [Fe/H] = −0.5 non-rotating but **6.2 → 6.5 rotating**, 6.0 → 6.2 at
−1.0. Every grid flips exactly once, no interleaving; a grid that didn't would return
`None` (no caption) rather than point at a boundary that isn't there. Because the edge
moves 0.5 M☉ across the grid, it is **scanned, never hardcoded**.

**The cited half — and why it is not measured.** `band_hi` is
`_FATE_UNCERTAIN_CEIL_MSUN = 8.0`, a **published** figure. MIST models neither super-AGB
thermal pulses nor electron capture, so *no track grid can be asked how wide the real
uncertainty is*; deriving it would be the false-caption failure in the other direction.
8.0 is the narrow end of the published crossover spread (~6.5–8 M☉ at solar, higher under
some prescriptions — Poelarends+2008 ApJ 675 614; Doherty+2015 MNRAS 446 2599;
Doherty+2017 PASA 34 e56). **The tooltip keeps the two edges' provenance apart** — that
separation is the feature's honesty, not a detail.

**Three design points worth not re-deriving:**

1. **One classifier, not two.** `_fate_of(track) -> (fate, r_last, final_mass)` was
   factored out of `endgame()` and is what the scan calls. A second copy of the four
   WR/WD/SN/none predicates would eventually hedge the wrong masses. Test
   `test_fate_of_is_the_same_predicate_the_endgame_answers_with` pins it.
2. **Don't materialise `states` to classify.** Calling `endgame()` per node costs ~8 s
   per grid (it builds every WD's cooling track); reading the three parsed columns costs
   milliseconds. Cached per `(vvcrit, [Fe/H])` like `_he_band_cache`.
3. **No `interpolated` flag** — the opposite of the He-cliff gate. The endgame **snaps**
   (§6), so a grid node's verdict is exactly as crisp as a blended one, and the
   uncertainty being confessed is the physics', not the interpolation's.

**Both sides, or the flip is still crisp.** Hedging only the supernova note would leave
the 6.5 M☉ white dwarf asserting its fate just as flatly. So in-band the SN note softens
("Core collapse — **in this model**. A 7 M☉ star explodes as a supernova **on this
grid**") and `#gateway-fate-note` sits under whichever control shows: *"We genuinely
don't know. Between 6.5 and 8 M☉ a star may end either way … the model has to answer, and
it answers a supernova / a white dwarf."* Outside the band every string is byte-identical
to before.

**Where it lives.** `fate_boundary_status(mass, feh, vvcrit)` is a
**`StellarStateProvider` Protocol method** (`stub.py` and `mesa.py` return
`has_data: False` — no endgame, so no boundary to place); `/fate_boundary_status` goes
through `PROVIDER` and never raises. Frontend: fetched **unawaited** from `refreshTrack`
(it only rewords the gateway), token-guarded, re-running `updateGateway()` when it lands;
reset alongside the `gatewaySnNote` reset. No mode-switch chokepoint entry is needed —
`updateGateway()` early-returns outside live mode and `#gateway` is hidden inside an
endgame, and `exitEndgame()` → `refreshMassRangeThenTrack()` refetches the band.

**ROADMAP correction it fixed:** the row read "frontend-only; the boundary masses already
come with `/endgame?meta=1`". They don't — `meta` returns only the *snapped* mass, never
the neighbouring node, so the frontend cannot learn where the flip is. Hence the backend
gate.

Related: [[star-sim-supernova-remnant-endgame]] and [[star-sim-wr-wd-endgame-plan]] (the
two fates it hedges between), [[star-sim-mist-provider]] (the snapping endgame).
