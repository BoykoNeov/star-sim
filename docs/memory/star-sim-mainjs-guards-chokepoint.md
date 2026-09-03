---
name: star-sim-mainjs-guards-chokepoint
description: main.js's shared mechanisms — the makeLatest() fetch guard, the registered living-only chokepoint, and the per-control wire*() split — plus why none took the shape the plan drafted.
metadata:
  type: project
---

# `main.js`: the fetch guard, the living-only chokepoint, the wiring split (2026-09-03)

**Current state.** Two mechanisms that used to be copy-paste now exist once each in
`frontend/src/main.js`:

- **`makeLatest()`** — the latest-request-wins guard. 13 named guards
  (`trackLatest`, `endgameLatest`, `endgameMetaLatest`, `snLatest`, `strippedLatest`,
  `heliumLatest`, `alphaLatest`, `populationLatest`, `isoLatest`, `observerLatest`,
  `obsTrackLatest`, `binaryLatest`, `coBinaryLatest`) over one factory.
  `const req = xLatest.begin()` before the fetch; `if (!req.current || mode !== "…")
  return` after each await; `xLatest.invalidate()` to kill whatever is in flight.
  21 `begin()` / 41 `.current` / 30 `invalidate()` sites.
- **`dropLivingOnlyPanels()`** — the mode-switch chokepoint, a `livingOnly[]` list.
  Eight drops join it by calling `registerLivingOnly(theirDrop)` next to their own
  definition. Called by every non-live mode entry **and** by `exitEndgame`.
- **23 `wire*()` functions** — the old 650-line `init` is 31 lines:
  `loadRangesAndSeedControls()`, then one call per control group, then the first fetch.
  A new control adds a `wireX()` and one call; it never grows `init` again. Nothing in
  a `wire*()` paints. Their arithmetic lives in `frontend/src/controls.js`
  (see [[star-sim-js-test-harness]] — that module is why the split is testable at all).

Plan rows: [[structure-refactor]] §2.1 moves 1–3 (all shipped 2026-09-03); measured
payoff in `docs/plans/SHIPPED.md` §6.

## The four decisions worth not re-litigating

1. **The guard is a handle, not `fetchLatest(key, path) → null`** (what the plan
   drafted). Two reasons found by reading the call sites: a `catch` block has to know
   whether it is still latest — `fetchEndgamePreview` clears `endgameLoading` and
   repaints *only* if it is, so a stale failure can't blank a newer pending fetch — and
   `tryWDResnap`/`trySNResnap` hold one guard across **two** awaits (the rotation-status
   fetch, then `/endgame`). A promise that resolves `null` cannot express either.

2. **Named guards, never a keyed registry** (`latest("sn")`). There is no JS test
   harness here, so the Playwright screenshot pass is the only check — and a mistyped
   string key would silently mint a *fresh* counter, i.e. a guard that never fires
   stale, which no screenshot can see. A mistyped identifier is a `ReferenceError` on
   first paint, which that pass does catch. Pick the failure mode your verification
   catches.

3. **`fetchJSON` stays unguarded.** `init` calls it fire-once for `/ranges`, `/health`,
   `/mass_range`, `/helium_status`, `/alpha_status`, `/population_status`,
   `/isochrone_status`, `/photometry`. Those must not acquire counters — putting the
   guard inside the fetch helper would have swept them in.

4. **Registration order is teardown order, and that is fine** — but it was settled by
   grepping for cross-reads (`lastPainted` is written only by the cliff-caption drop,
   `obsTrackKey` only by the observer drop), not by reasoning about it. If a future drop
   reads state another one writes, that pair needs explicit sequencing, not a registry.

## The hazard this closed

`exitEndgame` never called the chokepoint. On a clean WD → Back that is harmless (entry
already dropped everything and nothing inside an endgame turns a living-only panel back
on) — the exposure was a fetch that landed *mid-endgame* and repopulated an overlay,
which would then survive into the restored live view as a stale caption. The call sits
at the top of `exitEndgame`, before `mode = "live"`, so the drops still see the endgame
mode and `refreshMassRangeThenTrack()` repaints after them.

## How this was verified (the pattern to reuse)

Not a screenshot comparison — an **A/B of the served app's state**. One Playwright
script drives the real runtime (fast mass drag through five values → HZ + isochrone +
population overlays on → WD enter/back → 20 M☉ SN enter/back → 390 px) and prints a
JSON panel-state row at each step. Run it against `git show HEAD:…/main.js` and against
the working tree: the two logs are identical, zero console errors on both. That is what
makes a 340-line mechanical diff safe to believe when there are no unit tests. The
script itself was a throwaway (a scratch file, not committed — a real harness is plan
§2.3); the reusable part is the *shape*: drive the served app, print a small JSON state
row per step, and diff the log against `git show HEAD:<file>`.

**One follow-up this pass nearly missed**, worth knowing before touching the chokepoint
again: `dropCliffCaptionForModeSwitch` nulls `lastPainted`, and calling it from
`exitEndgame` therefore nulls it on the way back to live too. That is safe *only*
because `paintState` repaints the He-ignition caption from its own `s`, not from
`lastPainted` — the two `updateCliffCaption(lastPainted)` calls in `refreshTrack` would
otherwise have left the second honesty gate silently off after a WD → Back in the
1.65–2.10 M☉ band. Verified in the real app: visible at 1.83 M☉ in core-helium burning →
hidden in the WD endgame → hidden at the end-of-life age the exit pins to (correct: the
phase gate) → visible again on scrubbing back into CHeB. See [[star-sim-he-ignition-cliff]].

Related: [[star-sim-api-routers]] (the backend half of the same track),
[[star-sim-frontend-ux]] (what the panels actually draw).

## Move 3: why the `wire*()` functions did NOT go into the panel modules

The plan drafted `wireRotationControl(ctx)` etc. **inside** `rot`/`sed`/`hr`, each
taking a shared `ctx`. Read the listeners and that seam collapses: a listener's whole
job is to mutate the ~170 module-level `let`s in `main.js` and re-run the paint
pipeline, so `ctx` would have to expose dozens of *mutable* slots — a wider interface
than the `init` it replaces, and one no test could pin. Worse, three of the toggles
exist to enforce **cross-panel** exclusivity (helium / α / isochrone all own the one
HR slot and clear each other), which is not any single panel's business. §3's own
framing agrees: a panel is a *consumer* of a `StellarState`, not an owner of app state.

So the wiring stayed in `main.js` and only the **arithmetic** moved out. That split is
the reusable lesson: in a module this size, the part worth extracting is the part with
no state, and the part worth leaving is the part that is nothing but state.

## `controls.js` — the three shapes every control had re-implemented

| Helper | Replaced | Watch out for |
|---|---|---|
| `nearestWithin` / `snapWithin` | **7** snap-to-landmark loops (mass ticks, [Fe/H], age rows, WD, WR, SN, ⁵⁶Ni) + the SN day→sample lookup | The tolerance is **strict** (`d < tol`) and ties go to the **first** target in scan order — both were properties of the hand-written loops, and the age strip depends on the tie rule (a late landmark row can sit exactly as far from the drag as the 1.0 endpoint) |
| `logValueAt` / `logPosOf` | **6** log-position pairs (⁵⁶Ni, observer distance, M_star/M_co/P, M1/P) | Bounds are read at call time from `binaryMeta`/`coBinaryMeta`, never captured — a [Fe/H] or grid-kind change swaps in a different baked grid with a different span |
| `commitNumber` | **9** number-box preambles | Returns `null` for blank/unparseable = "leave the model alone"; `"0"` must still commit (A_V = 0 and [Fe/H] = 0 are real values) |

**Two sites deliberately stayed hand-written**, each with a comment saying why:
`massFromSliderPos` (its bounds are already log10 and `massValue` is the source of
truth for every fetch — a pow/log round trip risks drift on the one number that must
not drift) and the inclination number box (a cleared angle box means 0°, not "leave
the view alone", so it is not a `commitNumber` site).

## The acceptance test that has now been run three times

Not a screenshot: a **scripted A/B through the served app**. `pass.py`/`pass2.py`
(kept under `M:\claud_projects\temp\star-sim-wire`, regenerable) drive the real UI and
dump a panel-state snapshot after each step — slider values, notes, captions, body
classes, panel visibility, tick labels — then the same pass runs against `git stash`ed
HEAD and the two JSON logs are diffed. Move 3 ran 60 steps over two passes (all six
number boxes including blank/out-of-range, every offered toggle, WD + SN endgames with
an in-endgame re-snap, stripped mode + both binary movies + both CO grid pickers,
390 px): identical at every step, zero console errors both sides. Two lessons for the
next run: the endgame gateway buttons need **~12 s** after a mass change before they
are clickable (the fate + preview fetches gate them), and the mass has to sit inside
each feature's band (the stripped-mode button is 2.0–18.2 M☉, so a 25 M☉ star silently
skips that whole branch).
