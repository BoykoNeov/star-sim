---
name: star-sim-mainjs-guards-chokepoint
description: main.js's two shared mechanisms — the makeLatest() fetch guard and the registered living-only chokepoint — plus why neither took the shape the plan drafted.
metadata:
  type: project
---

# `main.js`: the fetch guard + the living-only chokepoint (shipped 2026-09-03)

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

Plan row: [[structure-refactor]] §2.1 moves 1–2; measured payoff in
`docs/plans/SHIPPED.md` §6. Move 3 (`init` → per-panel `wire*()`) is still open, and
§2.3 (the `node --test` harness) is the item that would have made this change checkable
by something other than screenshots.

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
