---
name: star-sim-api-routers
description: The api/ router package — the swap point, the app-wide 422/503 handlers, and the two hazards any future file→package split will hit again.
metadata:
  type: project
---

# `api.py` → `api/` routers (shipped 2026-09-03)

**Current state.** `backend/star_sim/api/` is a package: `__init__.py` (app,
middleware, `PROVIDER`, `include_router` ×6, StaticFiles mounted **last**),
`_deps.py`, `_errors.py`, and six routers — `spine` (everything through
`PROVIDER`, plus the hybrid `/supernova`) · `interiors` · `spectra` ·
`binaries` · `ensembles` · `observer`. A route body is the sibling call and
nothing else. Detail + the measured payoff: `docs/plans/SHIPPED.md` §6;
the plan row is [[structure-refactor]] §1.1.

## The three rules this split established

1. **`PROVIDER` is still one line in one file** — `api/__init__.py`. Routers
   never import it; they call `_deps.provider()`, which resolves the package
   attribute at *request* time. A module-scope `from . import PROVIDER` is
   impossible anyway (the routers are imported *by* that `__init__`), and a
   snapshot would defeat the swap. Two tests pin it: no router names a concrete
   provider, and `PROVIDER` is assigned in exactly one module.
2. **The 422/503 ladder is app-wide, not per route.** `star_sim/errors.py` holds
   `DataMissing`, subclassed by all eleven sibling `*DataMissing` exceptions
   *and* by `provider.ProviderDataMissing`; `api/_errors.py` maps that family →
   503 and `ParameterOutOfRange` → 422, both as `{"detail": str(exc)}`.
   - The base **cannot** live on `provider.py` (where the plan first put it): the
     §3 sibling denylist names `provider` literally, so nothing a sibling
     subclasses may live there. Hence its own stdlib-only module.
   - **Never add a blanket `ValueError` handler.** `ParameterOutOfRange` *is* a
     `ValueError`, so an app-wide rule would relabel every genuine bug — a bad
     dict key, a numpy conversion — as a client error across all 35 routes. The
     two CO-binary routes keep a *local* arm for an unknown `kind` (an unbounded
     str Query); `/isochrone`'s was dropped as unreachable.
   - `/health` keeps its own inline catch on purpose: 200 with
     `data_ready: false` is the question it exists to answer.
3. **The router is the composition layer.** Anything that needs *both* the
   provider and a sibling lives in the router, because the sibling may not
   import the provider: `_donor_ms_lifetime` (`/binary_pair`), and the array
   extraction in `/photometry_track`. What moved *out* takes plain
   scalars/arrays only — `supernova.supernova_payload(fate=…, co_core_msun=…)`
   never sees an `EndgameResult`, and `photometry.track_band_mags(teffs, loggs,
   fehs, radii)` never sees a `StellarState` (a magnitude is not a star).

## Three hazards the next file→package split will hit

`providers/mist.py` is the remaining queued split ([[structure-refactor]] §1.4).
`spectra.py` → `spectra/` was **abandoned** on hazard 3 below — see
[[star-sim-shared-grid-leaf]]; its loader duplication was solved inside the one file
instead. Any future split re-runs into:

- **`test_architecture.py` goes quietly vacuous.** Its checks globbed
  `star_sim/*.py`, which stops seeing a module the moment that module becomes a
  directory — the test keeps passing while enforcing nothing. `_package_modules()`
  now walks subpackages; extend it, don't trust a green run after a split.
- **Relative-import depth.** `_imports()` used to normalise every relative
  import to `star_sim.{mod}`, which is only right at top level. Inside a
  subpackage a `from ..spectra import …` is level 2 and must resolve against the
  importing module's own package, or the AST boundary test reads the wrong name.
- **Module-level state that tests reach into — the one `api.py` did NOT hit, and
  the reason the spectra split was dropped.** `api.py` had none; `spectra.py` has a
  data-dir constant and (then) five cache globals, monkeypatched from **8 sites
  across 4 test files** to prove "no baked cube → 503 with the recipe". Patching a
  name on a package `__init__.py` does **not** reach a submodule that read that name
  into its own namespace at import time, so a split forces either a `_paths`
  indirection read at call time or a rewrite of every patch site. Count those sites
  *before* deciding a split is cheap.

## What made a 1,000-line move safe to believe

Not the test suite and not a screenshot: the **full OpenAPI schema, dumped
before and after and diffed byte-for-byte** — all 35 paths, every `Query` bound,
every docstring as its description, every operationId. Route functions kept
their original names so even operationIds match. That is the acceptance check
for any future pure move here; `app.routes` is *not* usable for it (this FastAPI
version puts `_IncludedRouter` objects in the list, which have no `.path`).
