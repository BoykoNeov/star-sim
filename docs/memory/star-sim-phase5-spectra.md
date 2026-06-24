---
name: star-sim-phase5-spectra
description: "Phase 5 synthetic-spectrum panel — WORK IN PROGRESS (spike proven + planned, NO code yet): MSG/pymsg builds lean on conda-forge with NO MESA SDK; architecture decided = build-time bake → pure-Python runtime; panel is a sibling to the §3 spine (/spectrum bypasses PROVIDER like /polytrope)."
metadata:
  node_type: memory
  type: project
  originSessionId: da60f50f-c5fc-4f23-bce5-2e8a5e9b3f72
---

**Phase 5 = a synthetic-spectrum panel** (λ vs flux with real absorption lines),
derived from the state's `(Teff, log g, [Fe/H])` — the very spectrum
[[star-sim-phase2-shaders]]' `color.js` already collapses into one pixel.
**Status: planning + spike done, NO code written yet.** Engine = **MSG** (Townsend's
*Multidimensional Spectral Grids*) via its `pymsg` Python wrapper.

**Spike proven (durable):** MSG 2.2 + `pymsg` builds on a **lean conda-forge stack —
NO MESA SDK, no ~1.2 GB download** (gfortran 15 + conda libblas/liblapack/hdf5 +
netlib LAPACK95 built from source). `sg.flux(x={'Teff':…,'log(g)':…}, z=0.0, lam=<Å
bin edges>)` returns physically-correct lined spectra across **3500–49000 K**: Balmer
Hα/Hβ absorption peaks at A stars, Ca K (3933 Å) strong in cool stars and gone when
hot. Reusable build container **`msg_spike`** (from `evbauer/mesa_lean:r24.03.1.01`)
left running with the complete build (MSG at `/tmp/msg-2.2`, pymsg in conda base,
lapack95 at `/tmp/LAPACK95`) — separate from the user's `mesa_dock`.

**Architecture decided = build-time bake** (mirrors the MESA build-time precedent of
[[star-sim-phase4-mesa]] and the fetch-at-build of [[star-sim-mist-provider]]): MSG is
built **once in the container**, `pymsg` bakes a **dense void-filled `(Teff, logg,
[Fe/H])` flux cube** → `data/spectra/spectra_grid.npz` (gitignored, like `data/mist`
& `data/mesa`); the **runtime backend is pure-Python** (`scipy`
`RegularGridInterpolator`) — **no pymsg/Fortran/Docker at run time, Windows-clean**.
The panel is a **SIBLING to the §3 spine, NOT a `StellarState`** — exactly like the
Lane–Emden polytrope: `/spectrum?teff=&logg=&feh=` is, like `/polytrope`, the *other*
route that does **not** go through `PROVIDER`. No backend/grid internals leak to the
frontend beyond the three physical numbers already on the state (§3 respected).

**Durable artifacts (read these to resume):**
- Plan (full design + resume order + open decisions): `docs/plans/graceful-toasting-thimble.md`.
- MSG build recipe + every gotcha: `backend/docs/msg_spectra_build_recipe.md`.

**Resume order:** (1) grid decision — **CAP18** (Allende Prieto 2018, 3-D, gives the
`[Fe/H]` axis, ~50000 K) vs ship a **solar-only MVP** from the proven bundled
`sg-demo.h5` first (runtime code is identical; swap the `.npz` later). (2)
`backend/scripts/bake_spectra.py` (standalone, NOT in the `star_sim` package, runs in
`msg_spike`). (3) `backend/star_sim/spectra.py` (mirrors `lane_emden.py`) +
`/spectrum` route in `api.py` (mirrors `/polytrope`). (4) frontend `spectrum.js`
(mirrors `lane.js`+`comp.js`) + `main.js`/`index.html`/`styles.css` wiring. (5)
`conftest` `requires_spectra_data` gate + `test_spectra.py` (always-on 422/503 +
data-gated line-physics anchors); Playwright screenshot as the frontend regression check.

**Build gotchas worth keeping (from the recipe, each cost an iteration):** the
`mesa_lean` SDK gfortran is **9.2 — too old** (MSG 2.2's `-ftrampoline-impl=heap` is a
GCC-14 flag) → use **conda-forge gfortran 15**; **build LAPACK95 from netlib source
with the SAME gfortran** (the SDK's prebuilt `.mod` are gfortran-9.2, unreadable by
15); **gawk not mawk** (mawk silently fails MSG's `makedepf08.awk` POSIX classes →
module-build race); **build from a FRESH extract** (a failed parallel build leaves a
corrupt `.dep`); **explicit `-I$CONDA_PREFIX/include` for `.mod`** (conda's pkgconf
strips conda-prefix `-I`; `CPATH` does NOT work for Fortran modules); set
`MESASDK_ROOT` to any valid path or `fypp_deps` crashes (`'{}/lib/python'.format(None)`).

**Why:** captures a proven-but-uncommitted spike + a chosen architecture so a future
session resumes without re-discovering the build (which is genuinely fiddly), and
records the §3-sibling decision so nobody tries to make the spectrum a `StellarState`.

**How to apply:** read the plan + recipe first; reuse the `msg_spike` container for
the bake (or rebuild via the recipe, ~10 min); keep `/spectrum` off `PROVIDER` like
`/polytrope`; never put pymsg in `pyproject.toml` (it lives only in the build container).
