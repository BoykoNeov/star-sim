# Plan: Synthetic-spectrum panel (Phase 5)

## Context

The user asked to "add spectra to the displayed characteristics." After two
clarifying choices they picked **real synthetic spectra with absorption lines**
(not a bare blackbody continuum), interpolated on the `(Teff, log g, [Fe/H])`
the `StellarState` already carries — and pointed at **MSG** (Townsend's
Multidimensional Spectral Grids) as the engine. A third choice settled the
hosting model: **build-time bake** — build MSG once, use `pymsg` offline to bake
a dense spectrum grid into compact arrays, and have the runtime backend do
pure-Python interpolation (no MSG/Fortran/Docker dependency at run time, fully
Windows-clean). This matches the project's existing "MESA as a build-time data
step feeding a pure-Python backend" precedent.

**The build is already proven** (the spike): MSG 2.2 + pymsg builds on a lean
conda-forge stack (gfortran 15 + conda lapack/hdf5 + netlib lapack95, **no MESA
SDK**), and `sg.flux(x, z, lam)` returns physically-correct lined spectra across
the full O→M range (Balmer lines peak at A stars; Ca K strong in cool stars,
gone when hot). The full reproducible recipe + every gotcha is captured in
**`backend/docs/msg_spectra_build_recipe.md`**.

Outcome: a new **Spectrum panel** that, whenever the star changes, fetches a
synthetic spectrum (λ vs flux, with the visible band shaded and the principal
absorption lines visible) from a new `/spectrum?teff=&logg=&feh=` endpoint —
making visible the very spectrum that `color.js` already collapses into the
star's one-pixel color.

## Architecture (mirrors the Lane–Emden sibling, spec §3/§8)

The spectrum is a **sibling to the StellarState spine, not a `StellarState`** —
exactly like the Lane–Emden polytrope. `/spectrum` is, like `/polytrope`, the
*other* route that does **not** go through `PROVIDER`. It is a derived view of
the state's `(Teff, logg, [Fe/H])`, just as the star's color already is.

```
BUILD-TIME (once, in the MSG Docker container — see the recipe doc):
  build MSG  ->  pymsg.flux over a dense (Teff,logg,[Fe/H]) grid, voids filled
             ->  data/spectra/spectra_grid.npz   (axes + flux cube; gitignored)

RUNTIME (Windows backend, pure-Python — no pymsg):
  GET /spectrum?teff=&logg=&feh=
    -> spectra.spectrum_data()  (RegularGridInterpolator over the .npz)
    -> { wavelength[], flux[], teff, logg, feh }
  frontend spectrum.js reads Teff/logg/[Fe/H] off the current StellarState
    -> draws λ vs flux, visible band shaded
```

## Build-time bake (the novel part)

A standalone **`backend/scripts/bake_spectra.py`** (NOT in the `star_sim`
package, so importing the package never pulls in pymsg) runs **inside the MSG
container** built per the recipe. It:

1. Loads a `pymsg.SpecGrid` from a downloaded grid file.
2. Defines regular axes: `Teff` (e.g. ~80 steps over the grid's range),
   `log g` (the grid's ~0–5 in 0.5 steps), `[Fe/H]` (the grid's metallicity
   points), and a `lam` wavelength array (~3000–9000 Å at teaching resolution,
   ~2–3 Å bins → a few thousand points).
3. Evaluates `sg.flux({...}, 0.0, lam)` at every grid node; on `LookupError`
   (a grid void) fills from the nearest valid neighbour so the stored cube is
   **fully regular** (advisor's "dense, void-filled bake" — trilinear at this
   spacing is sub-percent vs pymsg's cubic, invisible on the panel).
4. Saves `spectra_grid.npz` atomically: `teff[]`, `logg[]`, `feh[]`, `lam[]`
   (bin centres), `flux` cube `(nTeff, nlogg, nfeh, nlam)`, plus metadata
   (grid name, units, a `BAKE_VERSION`). Copied to host `data/spectra/`.

**Grid choice (decision below):** the spike's bundled `sg-demo.h5` (Kurucz
`ap00`) already spans **3500–49000 K** but is **solar-only** (no `[Fe/H]` axis).
**CAP18** (Allende Prieto 2018, from MSG's grid-files page) adds the `[Fe/H]`
axis and reaches ~50000 K. The bake script and `.npz` format are
dimensionality-agnostic (2-D solar or 3-D); start on whichever the grid offers.

## Backend changes

- **`backend/star_sim/spectra.py`** (new, mirrors `lane_emden.py` — a standalone
  sibling module, pure numpy/scipy, **no pymsg**):
  - `SPECTRA_DATA_DIR` = `data/spectra/` via `STAR_SIM_SPECTRA_DIR` env override
    (same idiom as `mist.py`'s `DATA_DIR`).
  - Lazy-load `spectra_grid.npz` once; build a
    `scipy.interpolate.RegularGridInterpolator((teff,logg,feh), flux_cube)`
    (vector-valued — returns the full flux array per point). If the grid is
    solar-only, the `[Fe/H]` axis is degenerate and `feh` is clamped.
  - `spectrum_data(teff, logg, feh, *, n_display=None) -> dict` returns
    `{ "wavelength": [...], "flux": [...], "teff":…, "logg":…, "feh":… }`
    (`.tolist()` for JSON, like `polytrope_profile`). Clamp inputs to grid
    bounds (cool M-dwarf logg etc.); raise `ValueError` only if truly outside.
  - If the `.npz` is absent, raise a clear "spectra not baked" error
    (analogue of `ProviderDataMissing`) so the route returns 503.
- **`backend/star_sim/api.py`**: add `from .spectra import spectrum_data` and a
  `/spectrum` route mirroring `/polytrope` (lines ~142–159) — `Query(...)` with
  bounds for `teff`/`logg`/`feh` (422 on violation), `try/except` mapping
  "not baked" → 503. Returns the dict directly.
- **`backend/pyproject.toml`**: no new runtime deps — `numpy`/`scipy` already
  present. (pymsg lives only in the build container, never in `pyproject.toml`.)

## Frontend changes (mirror `lane.js` + `comp.js`)

- **`frontend/src/spectrum.js`** (new): `createSpectrum(canvas, { api })` — a
  self-contained panel like `lane.js`, but with an `update(state)` method like
  `comp.js`:
  - `update(state)` reads `state.Teff_K`, `state.logg`, `state.feh_init` and
    kicks a **debounced latest-wins** fetch (the `lane.js` `token`/`debounce`
    idiom) to `/spectrum?teff=&logg=&feh=`.
  - `draw()` plots flux vs wavelength on a `fitCanvas` canvas: axes + grid (the
    `comp.js`/`lane.js` `xOf`/`yOf` idiom), the flux curve, and the **visible
    band (3800–7800 Å) shaded with per-wavelength spectral colour** (small
    wavelength→sRGB helper, reusing the CIE machinery already in `color.js`;
    fall back to `teffToCSS(Teff)` if simpler). Nice-to-have: a Wien-peak marker
    and faint Hα/Hβ/Ca K line labels — the pedagogy.
- **`frontend/src/main.js`**: `import { createSpectrum }`, instantiate it next
  to the other panels (~line 38), and call `spectrum.update(s)` inside
  `refresh()` right after `comp.update(s)` (line ~404) so it tracks the current
  star on mass/[Fe/H]/age change.
- **`frontend/index.html`**: a `<section class="panel spectrum-panel">` with an
  `<h2>` + `?` `data-tip` help tooltip, `<canvas id="spectrum-canvas">`, and a
  legend (the spec's hover-pedagogy convention). Place it near the composition
  panel (or full-width like `lane-panel`).
- **`frontend/styles.css`**: `.spectrum-panel` + `#spectrum-canvas` rules
  (copy the `#comp-canvas` / `.lane-panel` conventions).
- No backend/API concepts leak into the frontend beyond the three physical
  numbers already on the state (§3 respected).

## Tests (`backend/tests/`, data-gated like MIST/MESA)

- **`conftest.py`**: add `requires_spectra_data` skip marker (checks
  `SPECTRA_DATA_DIR` for `spectra_grid.npz`), mirroring `requires_mist_data`.
- **`tests/test_spectra.py`** (new):
  - Always-on (no data): `/spectrum` returns 422 for out-of-range params; the
    "not baked" path returns 503 cleanly.
  - Data-gated (`requires_spectra_data`): endpoint 200 with
    `len(wavelength)==len(flux)`; flux all-finite, positive; **physical-sanity
    line checks** — Balmer Hα/Hβ absorption deeper at ~9500 K than at the Sun;
    Ca K (3933 Å) deep in cool stars and shallow when hot (the spike's measured
    signatures, pinned as the regression test, à la the MIST Sun anchor).
- Frontend has no JS harness — a headless Playwright screenshot of the panel
  rendering real `/spectrum` data is the regression check (as in Phases 2–4).

## Decisions to confirm before/while implementing

1. **Grid:** bake from **CAP18** (3-D, gives the `[Fe/H]` axis) vs. ship a
   solar-only MVP from the proven **`sg-demo.h5`** first and add CAP18 later.
   Recommendation: try CAP18 (verify its download/size from MSG's grid page); if
   it fights, ship the `sg-demo` MVP and swap the `.npz` in later — the runtime
   code is unchanged.
2. **Grid/wavelength density:** the `.npz` size knob (~80 Teff × 11 logg × N feh
   × ~3000 λ ≈ tens of MB compressed). Tunable in the bake script; default to
   "dense enough that trilinear ≈ cubic."

## Verification (end-to-end)

1. **Build + bake** (in the MSG container, per `backend/docs/msg_spectra_build_recipe.md`):
   build MSG, run `scripts/bake_spectra.py`, copy `spectra_grid.npz` →
   `data/spectra/`.
2. **Backend**: `pytest backend/tests/test_spectra.py` — always-on tests pass
   without data; data-gated line-physics tests pass with the baked grid.
   `curl 'http://127.0.0.1:8000/spectrum?teff=9500&logg=4&feh=0'` → JSON with
   matching-length `wavelength`/`flux`, a visible Hα/Hβ dip.
3. **Frontend**: `uvicorn star_sim.api:app --reload`, open the app, drag the
   mass slider — the Spectrum panel transforms (cool red star → line-rich;
   hot star → smooth blue continuum). Headless Playwright screenshot at a few
   masses as the regression check.
4. Confirm the §3 boundary: nothing downstream imports pymsg or grid internals;
   `/spectrum` is the only new route and it bypasses `PROVIDER` (like
   `/polytrope`).

---

## Status & how to resume (session handoff)

**Done this session (durable):**
- **Spike proven** — MSG 2.2 + pymsg builds on a lean conda-forge stack (gfortran
  15 + conda lapack/hdf5 + netlib lapack95, **no MESA SDK**); `sg.flux(x,z,lam)`
  returns physically-correct lined spectra across 3500–49000 K (Balmer peak at A;
  Ca K strong in cool stars, gone when hot).
- **Recipe written** → `backend/docs/msg_spectra_build_recipe.md` (full build
  procedure + every gotcha: gawk-not-mawk, lapack95-from-source, pkgconf `-I`
  stripping, `MESASDK_ROOT` for `fypp_deps`, fresh-tree builds, runtime env).
- **Hosting decided** = build-time bake (this plan).
- **This plan** written.
- **Now committed & tracked:** this plan + the recipe doc are in the repo; the WIP is
  recorded in memory (`docs/memory/star-sim-phase5-spectra.md`) and in CLAUDE.md's
  "Current status" (the Phase-5 in-progress bullet). Still **no implementation code** —
  the spike + these docs are all that exists; resume from "Resume order" below.

**Build container left for reuse:** Docker container **`msg_spike`** (from
`evbauer/mesa_lean:r24.03.1.01`) is left running with a complete working build:
MSG at `/tmp/msg-2.2`, `pymsg` installed in conda base (`/opt/conda`), lapack95 at
`/tmp/LAPACK95`. Reuse it for the bake; to drive it set the runtime env from the
recipe (`MSG_DIR=/tmp/msg-2.2`, `MESASDK_ROOT=$CONDA_PREFIX`,
`LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$MSG_DIR/lib`, conda base active). If it's gone,
rebuild via the recipe (~10 min). It is separate from the user's `mesa_dock`
container; `docker rm -f msg_spike` to discard.

**Resume order (implementation):**
1. Grid decision + fetch (CAP18 3-D vs `sg-demo.h5` solar MVP — see "Decisions").
2. `backend/scripts/bake_spectra.py` → run in `msg_spike` → `data/spectra/spectra_grid.npz`.
3. Backend: `spectra.py` + `/spectrum` route in `api.py`.
4. Frontend: `spectrum.js` + `main.js` wiring + `index.html` + `styles.css`.
5. Tests (`conftest` marker + `test_spectra.py`); screenshot verify.
6. Session-end ritual: update memory, commit + push.

**flux() API recap:** `sg.flux(x={'Teff':…,'log(g)':…}, z=0.0, lam=<Å bin edges>)`
→ erg/cm²/s/Å, length `len(lam)-1`. Grid axes: `sg.axis_labels`,
`sg.axis_x_min/x_max`, `sg.lam_min/lam_max`.
