---
name: star-sim-helium-overlay
description: Phase 2 initial-helium (Y) what-if overlay — helium.py sibling + /helium + HR overlay (GC 2nd-generation, self-run MESA baseline-vs-enhanced). BUILT.
metadata:
  type: project
---

**Phase 2 of `docs/plans/tempered-lineage-inspiral.md` — the initial-helium (Y) axis.
BUILT end-to-end 2026-07-09 (Chunks 2a/2b/2c); Playwright-verified, 387 pytest.**

The globular-cluster **second-generation** what-if: at fixed mass/[Fe/H] a He-enhanced
star (Y≈0.40, ω Cen / NGC 2808) is **hotter, brighter, and shorter-lived** than a
primordial-Y one (Y≈0.27) — μ rises → L rises → τ_MS=M/L falls (the HB "second-parameter"
effect). A **what-if overlay sibling** like Ap/Bp — bypasses `PROVIDER`, and the load-bearing
honesty rule is it is **NEVER compared against the live MIST spine**: a He-enhanced MESA track
is only shown against a **MESA baseline** (identical inlist, Y the sole difference), because
MESA-vs-MIST would conflate the He effect with the documented MESA-vs-MIST systematic.

**Chunk 2a (data, Claude ran the MESA batch in Docker himself — the user said "docker is on,
bake it yourself").** Six runs (3 masses × 2 comps), image `evbauer/mesa_lean:r24.03.1.01`,
driven by `docker cp`. Inlists differ ONLY in `initial_mass` (1/2/6) and `initial_y` (baseline
**0.2704** / enhanced **0.40**); **`Zbase=initial_z=0.0152` in BOTH** — the Y axis leaves Z
fixed, so the metallicity-axis "change Zbase too" gotcha does NOT apply. Output
`data/mesa_helium/{baseline,enhanced}/<M>Msun/history.data` — **gitignored, MESA-local** (the
hosted-data-assets pattern excludes MESA; tests skip via `requires_helium_data`). **No bespoke
npz bake** (advisor): 4 MB read directly by the reused parser, like `MESAProvider`.
**Gate 2 PASSED emphatically at every mass** (measured through the real runs, matched-phase):
1 M☉ 5752→6559 K / 0.80→1.86 L☉ / τ_MS 8.33→3.03 Gyr (2.7×); 2 M☉ 9491→11152 K / 17.9→33.8 L☉ /
0.86→0.41 (2.1×); 6 M☉ 19611→22312 K / 1069→1839 L☉ / 0.055→0.029 (1.9×). Recipe
`backend/docs/mesa_helium_recipe.md`.

**Chunk 2b (backend).** `star_sim/helium.py` — a §3 sibling (imports only `state.StellarState`
+ the MESA parser's **free** helpers `_build_track`/`_state_from_track`, never `PROVIDER`).
Groups runs by `round(minit,3)`, keys each member by its **ZAMS surface He** `Ys[0]` (NOT dir
name — dir names are human-only), pairs lower-Y=baseline / higher-Y=enhanced, and **asserts
exactly two per mass** so a stray/missing run fails loudly (advisor). `helium_overlay(mass)`
snaps to nearest grid mass, returns both tracks as `StellarState` lists + each's ZAMS Teff/L and
**windowed τ_MS** (`age[-1]-age[0]`). `/helium?mass=` bypasses PROVIDER, snap-always
(`mass_snapped_far` in-band), 422 on mass≤0. **Refactor:** lifted `_state_from_track` out of the
`MESAProvider` class to module level (it used no `self`) so the sibling reuses it; the method
delegates (behavior byte-unchanged, 18 MESA tests green). **+8 tests** `test_helium.py`
(`requires_helium_data`): per-mass Teff/L/τ_MS Gate-2 asserts, observed ΔY range, §3-state
validity, snap honesty, route/422, and an **AST-level** sibling-imports-no-PROVIDER check (the
first `PROVIDER not in text` version FAILED — the word appears in the docstring prose; use AST).

**Chunk 2c (frontend, Playwright 1440+390 zero errors).** A **light HR overlay, not a mode-swap**
(advisor — the plan scopes 2c to HR + a τ_MS/Y readout; 3D/spectrum/comp stay on the current
star, they draw no tracks so no comparison trap). `#helium-toggle` (mass 0.7–7, |[Fe/H]|≤0.25 —
the solar-Z grid) → `refreshHelium()` → new minimal `hr.setHeliumOverlay(baseline, enhanced,
{yBase,yEnh})` (its OWN draw mode — advisor: do NOT bend `setBinaryTrack`, its donor/companion/
reversal/scrubber semantics don't apply): two full Teff-coloured trails (reusing `drawBinaryTrail`
with splitIdx=length), each dot-labeled at its ZAMS, **MIST living track hidden** while on
(`if (!heliumOn) hr.update/setTrack` guards). Static, no marker.
**τ_MS is invisible on an HR diagram (no time axis — the advisor's key catch)** → surfaced in the
`#helium-note` caption with both lifetimes + ratio. Latest-wins refetch on mass change
(`heliumToken`); drifting out of band OR entering any endgame/stripped view tears it down
(`dropHeliumForModeSwitch` at each mode-entry + `heliumMode=false` resets in the other `hr`
mode-entries so the HR panel can't stick). `fmtGyr` Myr-fallback below 0.1 Gyr (6 M☉ enh ≈29 Myr).

**Advisor guidance that shaped it (all followed):** HR-panel-scoped presentation (hide MIST, don't
draw both) is the load-bearing constraint not a style call; the τ_MS-invisible blind spot blocks
feature-complete; pair by Y-ordering + assert 2; new `setHeliumOverlay` not bent `setBinaryTrack`;
static not scrub; import the free parser functions not the class; read raw history.data (no npz).

**Advisor "before-done" review caught a BLOCKING defect my tests couldn't (both pytest AND Playwright
ran with data present):** the **data-absent path**. On a fresh public clone (MESA data is never
hosted — `[[star-sim-hosted-data-assets]]` excludes it), the toggle showed, `/helium` 503'd, and my
catch left `heliumOn` stuck true → the `if(!heliumOn)` guards on `hr.update`/`setTrack` **froze the HR
panel** (marker/track stuck, no overlay to justify it). Fixed two ways: (1) a **data-availability
visibility gate** — `helium_available()` + `/helium_status`→`{has_grid}` (the `/rotation_status`
pattern), probed once at init into `heliumHasGrid`, gating `updateHeliumControl` so the toggle never
appears without local runs; (2) a **fetch-failure teardown** — `heliumOff()` in `refreshHelium`'s
catch (restores the live HR + unchecks), belt-and-suspenders for a race/mid-session removal. +1
UNGATED test (`/helium_status` is 200 with a bool even with no data — the one test exercised on every
checkout). **388 pytest.** Verified via a two-server Playwright run (8014 with data → toggle works;
8015 with `STAR_SIM_HELIUM_DIR` at an empty dir → toggle hidden AND the HR still scrubs, 0 errors).
Lesson: a data-gated feature needs the data-ABSENT path tested too — a green suite with data present
proves nothing about the fresh-clone experience.

**Next = Phase 3** (α-enhanced evolution axis, self-run MESA — heavier: needs an α-enhanced
opacity table + custom mixture, not a single-knob flip; same overlay plumbing, Gate 3 stricter).
[[star-sim-co-hms-rlo]] [[star-sim-phase4-mesa]] [[star-sim-interior-structure-mesa]]
[[star-sim-hosted-data-assets]]
