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

### 1.2 One `snap()` and one missing-data hint  · **medium payoff, low risk**

`int(np.argmin(np.abs(grid - x)))` appears 22× across 8 files; the
`_MISSING_HINT.format(data_dir=…)` template 8×; the `bake_version` mismatch check
8×; `np.load(..., allow_pickle=False)` is inconsistent (5 of 10 sites). Add
`star_sim/_grid.py` with `snap_index(values, x)`, `snap_far(values, x, tol)`,
`load_npz(path, expected_bake_version, tag)` and a `missing_hint(dataset, path,
fetch_cmd)` builder. Replace call sites one sibling per commit; behaviour is
bit-identical, so the data-gated tests are the check.

### 1.3 `spectra.py` (761 lines) → a `spectra/` package  · **medium**

Five parallel `*_spectrum_data` loaders, five cache globals, three
`BAKE_VERSION` checks. One `_Cube` class (axes, flux, bake version, snap rules)
and one `@functools.cache` loader per cube file; the five public functions stay
as the API. Removes the "add a sixth cube by copy-paste" path.

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

## 2. Frontend (`frontend/src`, 11.7 kLOC, no harness)

### 2.1 `main.js` (4,985 lines; `init` alone 650)  · **highest payoff, medium risk**

170 top-level state variables, 12 hand-rolled "latest-wins" token guards, a
mode-switch chokepoint still called `dropHeliumForModeSwitch` that fans out to six
siblings, and one `init` that wires every listener.

Target, in three safe moves:

1. **`fetchJSON` grows the token guard.** `fetchLatest(key, path)` keeps one
   counter per key and resolves `null` for stale responses. Replace the 12
   copies one at a time (each is ~6 lines).
2. **Rename and register the chokepoint.** `dropHeliumForModeSwitch` →
   `dropLivingOnlyPanels()`, with the six `drop*ForModeSwitch` callbacks pushed
   onto a `livingOnly[]` list *by the panel that owns them* — a new overlay
   registers itself instead of editing the umbrella. Then call it from
   `exitEndgame` too (today it is not — a latent WD→Back→stale-overlay hazard).
3. **`init` → per-panel `wire*()` functions** in the panel modules
   (`wireRotationControl`, `wireObserverControls`, …), each taking the shared
   `ctx` object. `main.js` keeps state + the paint pipeline; wiring moves to where
   the DOM ids are used.

Playwright screenshot pass (1440 + 390 px, zero console errors) is the regression
check for each move — CLAUDE.md's standing rule.

### 2.2 The `create*` closure factories  · **accept**

`createHR` 1,140 lines, `createSpectrum` 1,219, `createSED` 955, `createStar`
801. These are one-object modules with private state; the size is the size of the
drawing. Do not split for its own sake; extract only pure helpers that a test could
call (the `hz.js` / `seismo.js` / `gravdark.js` precedent).

### 2.3 A minimal JS harness  · **medium, cheap**

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
2. §2.1 move 1 (`fetchLatest`) and move 2 (chokepoint registry + `exitEndgame`).
3. §2.3 `node --test` for the pure helpers; add to CI.
4. §1.2 shared grid helpers; §1.3 spectra package.
5. §2.1 move 3 (`init` → `wire*`).
6. §1.4–1.6 opportunistically.

Each step is independently shippable and leaves the app byte-identical for the
user; the measure of success is that the *next* feature (say, the near-IR bake
from `science-hurdles.md` §6) touches one router, one sibling, one panel — and the
architecture table stays green without being edited.
