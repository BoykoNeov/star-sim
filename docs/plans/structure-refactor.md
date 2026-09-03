# Project-structure plan — keeping a 53 kLOC single-author codebase steerable

**Why now.** Phases 1–5 are built; the code is feature-complete for its scope. The
next cost is not a missing feature but *steering* cost: a 4,985-line `main.js`, a
971-line `api.py` with 33 hand-written routes, twelve near-identical cache
globals, a 74 KB roadmap that is 90 % build log, and — until this branch — no
automated check of anything. This plan lists the structural debts with measured
sizes, orders them by payoff-per-risk, and records what this branch already did.

Ground rules that do not move: the §3 `StellarState` spine, `PROVIDER` in `api.py`
as the one swap point, siblings that bypass the provider, no bundler, no deploy
concerns (spec §2). Every step below is a *mechanical* refactor with the existing
test suite (and the new architecture table) as the safety net.

---

## 0. Done on this branch (`claude/project-structure-planning-nons2j`)

| Change | Why |
|---|---|
| `.github/workflows/ci.yml` — ruff + data-free pytest on 3.11/3.12 | Nothing was checked automatically; two tests had been failing on a fresh clone unnoticed. |
| `[tool.ruff]` in `pyproject.toml` — narrow net (`E9 F63 F7 F82 F401 F811 F841`) | A correctness net, not a style regime; 4 real hits fixed (one undefined-name bug was in this branch's own patch — the net paid for itself immediately). |
| `tests/test_architecture.py` — the §3 boundary as **one parametrized table** over all 12 siblings, plus "only `api`/fetchers import the live provider" and "`state.py` is stdlib-only" | Five per-file AST tests existed, three of them needlessly data-gated; seven siblings had none. Runs with no data. |
| `requires_mist_raw_tracks` marker; `requires_mist_data` added to two routes' tests | The hosted cache-only MIST download is a working provider with no raw text tracks; nine ground-truth tests failed instead of skipping. |
| `docs/plans/ROADMAP.md` split: shipped rows → `docs/plans/SHIPPED.md`; the roadmap is a thin open-items index again | CLAUDE.md's own rule ("resist re-growing the status section into a build log") had been broken by the roadmap itself. |
| `docs/plans/science-hurdles.md` | The scientific limits were scattered across 37 memory files; no single tiered ledger existed. |

---

## 1. Backend (`backend/star_sim`, 11.1 kLOC)

### 1.1 `api.py` → an `api/` package of routers  · **SHIPPED 2026-09-03**

> Done. Acceptance was the full OpenAPI schema byte-identical before/after (all 35
> paths, every query bound, every docstring), 456 pytest, ruff clean. Three
> deviations from the text below, all recorded in `SHIPPED.md` §6: the `DataMissing`
> base went to its own `star_sim/errors.py` (not `provider.py` — see (b)); the
> mapping became two app-wide exception handlers rather than a decorator, and
> deliberately does **not** cover bare `ValueError`; and `_donor_ms_lifetime` stayed
> in the router (see (c) — it needs `provider()`, which `binary.py` may not import).

971 lines, 33 `@app.get` routes, ~30 copies of the same
`try/except ParameterOutOfRange → 422 / *DataMissing → 503` ladder over eleven
`*DataMissing` exception classes; 51 code-lines of photometry composition and 49
of SN progenitor assembly live *inside* routes.

Target:

```
star_sim/api/__init__.py      # app = FastAPI(); PROVIDER lives HERE (the swap point, unchanged import path star_sim.api:app / star_sim.api.PROVIDER)
star_sim/api/_errors.py       # one decorator: @provider_errors → 422 / 503 mapping; DataMissing base class
star_sim/api/spine.py         # /health /ranges /mass_range /age_range /state /track /endgame /rotation_status /supernova
star_sim/api/interiors.py     # /polytrope /structure
star_sim/api/spectra.py       # /spectrum /alpha_spectrum /wd_spectrum /wr_spectrum /stripped_spectrum
star_sim/api/binaries.py      # /binary /binary_pair /binary_track(_meta) /co_binary_track(_meta)
star_sim/api/ensembles.py     # /population(_hrd,_status) /isochrone(_status) /helium(_status) /alpha(_status)
star_sim/api/observer.py      # /photometry /photometry_track
```

Rules: (a) `PROVIDER` stays a module attribute of `star_sim.api` so tests that
monkeypatch it keep working; (b) a shared `DataMissing` base (all eleven sibling
exceptions subclass it) lets the mapping be written once — **not** under
`provider.py` as first drafted: the §3 sibling denylist contains `provider`
literally, so a base living there could not be subclassed by any sibling. It gets
its own stdlib-only `star_sim/errors.py`; (c) the composition now inline in `/photometry_track`, `/binary_pair`
(`_donor_ms_lifetime`) and `/supernova` moves into the owning sibling as a pure
function — the route becomes ≤ 10 lines. Test: the existing route tests plus
`test_architecture.py` (routers may import siblings; siblings still may not
import `api`).

### 1.2 One `snap()` and one missing-data hint  · **SHIPPED 2026-09-03 (two of four helpers)**

> Done. `star_sim/_grid.py` holds `snap_index` / `snap_value` (13 call sites across
> `alpha` `helium` `bpass` `isochrone` `structure` `spectra` `providers/mesa`) and
> `load_npz` / `require_bake_version` (7 sites across `bpass` `posydon` `posydon_co`
> `spectra`). It is stdlib+numpy only and `test_architecture.py` now pins that as a
> *shared leaf* rule — every sibling imports it, so anything it can reach a sibling
> can reach. Acceptance was the full suite before/after with the real grids on disk
> (not skips): **464 passed / 0 skipped before, 468 passed / 0 skipped after** — the
> four extra are this step's own new architecture assertions. The zero-skip half is
> the load-bearing one: every sibling's grid is on the dev machine, so "the data-gated
> tests are the check" is true here rather than a suite of skips.
>
> **Two of the four planned helpers were measured and rejected — do not re-propose:**
>
> - **`missing_hint(dataset, path, fetch_cmd)`** — the eight `_MISSING_HINT`
>   templates are hand-written *recipes*, not a shape: different format keys
>   (`data_dir` / `baked_dir` / `kind` / none), and genuinely different instructions
>   (a Docker MESA batch · a 1 GB Zenodo download with a pre-baked shortcut · "restore
>   these from version control"). A builder could only take a free-text blob (no
>   reduction) or flatten a user-facing 503 hint (a regression).
> - **`snap_far(values, x, tol)`** — `*_snapped_far` has *three incompatible
>   meanings* in the code: absolute (`isochrone._FEH_SNAP_FAR`), relative-to-the-node
>   (`alpha`/`helium`, `> 0.25 * snapped`), and log-dex (`posydon._M1_FAR_DEX`,
>   `bpass` on `log_age`). One `tol` parameter would silently change one of them, and
>   `abs(a - b) > tol` is not worth a function.
>
> Two further corrections to the counts above: the "22× `argmin`" is **13** genuine
> nearest-node snaps — the rest are `argmin` over a *precomputed distance* array
> (`posydon`, `posydon_co`, the WR (log T*, log Rt) snap) or over a cost curve
> (`providers/mist`, left alone: that is §1.4 and its interpolation core just
> changed). And `allow_pickle=False` was never an inconsistency: it is numpy's own
> default, so the five bare `np.load` calls behaved identically — it is now passed
> explicitly in one place for documentation only.

### 1.3 `spectra.py` → one cube loader  · **SHIPPED 2026-09-03; the directory split DEFERRED**

> Done, the half that carried the payoff. `spectra.py` had five cache globals and
> five near-identical `_load_*()` functions (find the path, `is_file()`, raise with
> this cube's recipe, construct, memoise). They are now one `_CUBE_FILES` table
> (name → filename + recipe) and one `_cube(name, cls)` — 762 → 718 lines, and
> adding a sixth cube is a table row plus one call instead of a sixth copy of the
> plumbing. The three `BAKE_VERSION` checks went to `_grid.load_npz` in §1.2. The
> five public `*_spectrum_data` functions, their signatures and their returned dict
> keys are untouched.
>
> **The directory split is deferred, and the reason is a THIRD hazard** — one the
> `api.py` → `api/` split did not hit and so did not record in
> [[star-sim-api-routers]]: `api.py` had no module-level mutable state that tests
> reached into, but the spectra tests monkeypatch `spectra.SPECTRA_DATA_DIR` and the
> cache from **8 sites across 4 files** to prove "no baked cube → 503 with the
> recipe". Patching a name on a package `__init__.py` does **not** reach a submodule
> that read that name into its own namespace at import time, so the split forces
> either a `_paths` indirection read at call time or a rewrite of all 8 sites — for a
> payoff that, after the loader collapse, is cosmetic. Revisit only if a fifth or
> sixth cube makes the file genuinely hard to navigate.
>
> The cache-reset sites were verified to still test what they tested, not to pass off
> a warm cube: removing the `_LOADED` swap makes both "not baked" tests fail (200
> instead of 503, and DID NOT RAISE).

### 1.4 `providers/mist.py` (1,478 lines)  · **low priority**

Split only along seams that already exist: `_parse` (track parsing + `.npz`
cache + fingerprint), `_grid` (`_Track/_Grid/_Axis`, bracketing, blending), and
the `MISTProvider` class. The interpolation core just changed (log-mass weight,
this branch) and is now covered by a cache-friendly held-out test — a good moment
to split *because* the guard exists. Do not touch `CACHE_VERSION`.

### 1.5 Fetch/bake framework  · **low, do opportunistically**

Ten `fetch_*_baked.py` each re-declare a byte-identical `_fetch_one` wrapper
over `_baked_release.fetch_one`; raw fetchers carry seven distinct user-agent
strings and five have no `main()`. Give `_baked_release` a `run(tag, assets,
dest_of, citation)` entry and collapse each module to its table. Add
`[project.scripts]` entries (`star-sim-fetch`, `star-sim-bake`) once the table
form exists.

### 1.6 `conftest.py` (560 lines)  · **low**

~30 hand-written `*_available()` predicates + 32 markers, all evaluated at import.
A `requires(dataset)` factory over a small registry `{name: (predicate, reason)}`
halves the file and lets `pytest --collect-only` list what is gated by what.

---

## 2. Frontend (`frontend/src`, 11.7 kLOC; pure helpers under `node --test` since §2.3)

### 2.1 `main.js` (4,985 lines; `init` alone 650)  · **highest payoff, medium risk**

170 top-level state variables, 12 hand-rolled "latest-wins" token guards, a
mode-switch chokepoint still called `dropHeliumForModeSwitch` that fans out to six
siblings, and one `init` that wires every listener.

Target, in three safe moves:

1. **One latest-wins guard object.**  · **SHIPPED 2026-09-03**

   > Done, with one deviation. It was 13 counters, not 12, and the plan's
   > `fetchLatest(key, path)` → `null` contract does **not** fit the call sites: a
   > catch block has to know whether it is still the latest (to paint the error and
   > clear `endgameLoading`), and two guards span *two* awaits (`tryWDResnap`,
   > `trySNResnap` fetch the rotation gate before the endgame). So the guard stays a
   > handle — `makeLatest()` → `begin()` / `.current` / `invalidate()` — and
   > `fetchJSON` is untouched: the 8 fire-once status/range probes must not acquire
   > counters. **Named guards (`snLatest`), not a keyed registry (`latest("sn")`)**,
   > because a mistyped string key silently mints a fresh counter — a guard that never
   > fires stale, invisible to the only check this codebase has; a mistyped identifier
   > is a ReferenceError the screenshot pass does catch. 21 `begin()` / 41 `.current` /
   > 30 `invalidate()` sites; zero `Token` identifiers left.

2. **Register the chokepoint.**  · **SHIPPED 2026-09-03**

   > Done as written. `dropHeliumForModeSwitch` → `dropLivingOnlyPanels()` over a
   > `livingOnly[]` list; all **8** drops (not six) call `registerLivingOnly()` next to
   > their own definition, and helium's own teardown is now just one more member rather
   > than the umbrella's tail. Registration order = teardown order, which reverses the
   > old order — checked by grep (`lastPainted`, `obsTrackKey` are each written by one
   > drop only), not by argument. `exitEndgame` now calls it too, at the top, before
   > `mode = "live"`. Acceptance was an **A/B through the served app**: the same
   > scripted pass against HEAD and against the refactor gives identical panel-state
   > logs, zero console errors at 1440 + 390.

3. **`init` → per-panel `wire*()` functions.**  · **SHIPPED 2026-09-03**

   > Done, with one deviation and one addition. The 650-line `init` is now 31 lines:
   > `loadRangesAndSeedControls()` (the /ranges seed + the six data probes, returning
   > false when the backend is unreachable so nothing gets wired over a dead
   > backend), then 23 named `wire*()` calls, then the first fetch. Each `wire*()`
   > owns one control group's listeners and carries the comment block that used to
   > sit mid-`init`.
   >
   > **Deviation: they stay in `main.js`, not the panel modules.** The plan's `ctx`
   > object cannot be small — a listener's whole job is to mutate the ~170 module
   > state variables above it and re-run the paint pipeline, so the seam would have
   > to expose dozens of mutable slots (wider than the one it removes) — and three of
   > these toggles exist to enforce CROSS-panel exclusivity (He / α / isochrone share
   > one HR slot), which is nobody's panel to own. §3 also wants panels to be
   > consumers of a `StellarState`, not owners of app state.
   >
   > **Addition (what the plan asked for in its last line): the arithmetic did move
   > out**, into a new DOM-free `frontend/src/controls.js` with 16 tests under
   > `node --test`. Three shapes had been hand-written once per control:
   > `nearestWithin`/`snapWithin` replaces **7** copies of the snap-to-landmark loop
   > (mass, [Fe/H], age, WD, WR, SN, ⁵⁶Ni) plus the SN day→sample lookup;
   > `logValueAt`/`logPosOf` replaces **6** log-position pairs (⁵⁶Ni, observer
   > distance, M_star/M_co/P, M1/P); `commitNumber` replaces **9** number-box
   > preambles (blank → commit nothing, garbage → commit nothing, else clamp).
   > `massFromSliderPos` deliberately stays hand-written: its bounds are already
   > log10 values and `massValue` is the source of truth for every fetch, so a
   > pow/log round trip there would risk drift on the one number that must not
   > drift. The inclination box also stays as it was — a cleared angle box means 0°,
   > not "leave the view alone", so it is not a `commitNumber` site.
   >
   > **Acceptance was the A/B through the served app again**, widened to 60 scripted
   > steps over two passes (spine sliders + all six number boxes incl. blank/clamp
   > cases, every offered what-if toggle, the iso decouple slider, the observer
   > knobs, WD enter/scrub/back, stripped mode → companion → the HMS-HMS custom
   > orbit → the CO movie with both grid pickers, the SN gateway → ⁵⁶Ni slider +
   > box + an in-endgame mass re-snap, 390 px): panel-state snapshots **identical**
   > against HEAD at every step, zero console errors on both sides.

Playwright screenshot pass (1440 + 390 px, zero console errors) is the regression
check for each move — CLAUDE.md's standing rule. Move 3 was the first one that could
lean on §2.3 as well: the pure helpers it lifted out of `init` got a `node --test`
file rather than only a screenshot.

### 2.2 The `create*` closure factories  · **accept**

`createHR` 1,140 lines, `createSpectrum` 1,219, `createSED` 955, `createStar`
801. These are one-object modules with private state; the size is the size of the
drawing. Do not split for its own sake; extract only pure helpers that a test could
call (the `hz.js` / `seismo.js` / `gravdark.js` precedent).

### 2.3 A minimal JS harness  · **SHIPPED 2026-09-03**

> Done: `frontend/tests/` — 50 tests over the six helpers under `node --test`, a
> second CI job, no npm install. Three deviations from the text below.
>
> **(a) `classify.js` was not pure.** Its only export was `createClassification(el)`,
> which writes `el.innerHTML`; all seven label functions were module-private. The fix
> is the one §2.2 already blesses — extract the pure part as a named export
> (`classifyLabel(state, mode, opts)`) and leave the factory as two DOM writes — *not*
> a fake `el`, which would bake a DOM shim into a harness whose whole point is not
> needing one. **The rule that follows: a helper earns a test by being extracted, never
> by the harness growing a stub to reach it.**
>
> **(b) Invariants first, anchors second.** The plan listed only pinned values. A value
> harvested from the code under test preserves a flipped sign or a wrong exponent
> happily — this project's named defect class. So the first tests are the identities each
> module's own header states: `kEq²·kPol = 1` and flux conservation in `gravdark.js`;
> the seismic relations *inverting* back to the (M, R) put in, which pins four exponents
> at once; CCM89 being **exactly** identity outside 1.1–8 µm⁻¹. The published anchors
> (0.95/1.68 AU, 3090/135 µHz) and the two regressions the headers record (740 nm used
> to render pure green; a 145 R☉ giant used to flatten to a 1.5 axis ratio) sit under
> those. Every number pinned from current output is labeled as such in a comment.
>
> **(c) `reddening.js` parity is now enforced from both ends.** Its header calls it a
> verbatim port of `photometry.py`'s `ccm89` and says to re-run the match by hand. A
> JS-only test catches JS drift and nothing else, so the same three anchors are asserted
> in `backend/tests/test_photometry.py::test_ccm89_matches_the_javascript_port` — a
> change on either side now fails a test.
>
> Invocation: `cd frontend/tests && node --test`, bare, from inside the directory. A
> glob argument needs Node ≥ 22 and a directory argument fails on Node 24; the bare form
> works everywhere and is what CI runs.

The pure helpers (`color.js`, `hz.js`, `seismo.js`, `gravdark.js`, `classify.js`,
`reddening.js`) are ES modules with no DOM. Node ≥ 20 runs them as-is: a
`frontend/tests/*.test.mjs` with `node --test`, invoked from CI. First tests are
the already-measured anchors (Sun → 0.95 / 1.68 AU; ν_max/Δν solar; Planck 5772 K
→ near-white). No bundler, no npm install.

---

## 3. Docs

- **`ROADMAP.md` is an index of open work only** (done on this branch). Shipped
  rows live in `SHIPPED.md`; a row moves there the day it ships, with its
  measured payoff — that is where "chunk N built" narration belongs, not CLAUDE.md
  and not the roadmap.
- **Memory files > 20 KB** (eight of them, up to 55 KB) are recalled on demand, so
  size is tolerable — but each should open with a ≤ 10-line "current state"
  block so a recall doesn't require reading the history. Do it when next touching
  each file, not as a sweep.
- **Spec §11** lists `activity` and "rotation data" as open; **both are now answered**
  and the spec text is simply stale. Rotation = the vvcrit axis; `activity` = the
  Rossby-flavoured proxy shipped 2026-09-03 (`science-hurdles.md` §1.6). The ledger, not
  the spec, carries the verdicts — leave the spec as the historical design document.

---

## 4. Order of work

1. §1.1 routers + error decorator (one PR; unlocks 1.2–1.3 cleanly).
2. ~~§2.1 move 1 (the latest-wins guard) and move 2 (chokepoint registry +
   `exitEndgame`)~~ — **shipped 2026-09-03**.
3. ~~§2.3 `node --test` for the pure helpers; add to CI~~ — **shipped 2026-09-03**.
4. ~~§2.1 move 3 (`init` → `wire*`, + `controls.js`)~~ — **shipped 2026-09-03**.
5. ~~§1.2 shared grid helpers; §1.3 spectra loader collapse~~ — **shipped 2026-09-03**
   (two of §1.2's four helpers measured and rejected; §1.3's directory split deferred —
   see the notes under each).
6. §1.4–1.6 opportunistically.

Each step is independently shippable and leaves the app byte-identical for the
user; the measure of success is that the *next* feature (say, the near-IR bake
from `science-hurdles.md` §6) touches one router, one sibling, one panel — and the
architecture table stays green without being edited.
