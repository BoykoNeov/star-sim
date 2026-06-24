---
name: star-sim-phase5-spectra
description: "Phase 5 synthetic-spectrum panel — DONE (solar sg-demo MVP, full vertical slice): MSG/pymsg build-time bake (no MESA SDK) → void-filled flux cube .npz → pure-Python scipy runtime serving /spectrum (bypasses PROVIDER like /polytrope). Axis-generic so CAP18 (3-D [Fe/H]) is a zero-code re-bake. 116 tests. Solar-only because the CAP18 grids host was unreachable."
metadata:
  node_type: memory
  type: project
  originSessionId: da60f50f-c5fc-4f23-bce5-2e8a5e9b3f72
---

**Phase 5 = a synthetic-spectrum panel** (λ vs flux with real absorption lines),
derived from the state's `(Teff, log g, [Fe/H])` — the very spectrum
[[star-sim-phase2-shaders]]' `color.js` already collapses into one pixel. **Status:
DONE — the solar `sg-demo` MVP shipped, full vertical slice (bake → backend →
frontend → tests → screenshots).** Engine = **MSG** (Townsend's *Multidimensional
Spectral Grids*) via `pymsg`.

**Architecture = build-time bake** (mirrors [[star-sim-phase4-mesa]]'s build-time
precedent + [[star-sim-mist-provider]]'s fetch-at-build): MSG built **once in the
`msg_spike` container**; `backend/scripts/bake_spectra.py` (the ONE place that imports
pymsg — deliberately NOT in the `star_sim` package) bakes a dense **void-filled** flux
cube → `data/spectra/spectra_grid.npz` (gitignored, 96 Teff × 11 logg × 2400 λ, 4.7 MB);
the **runtime is pure-Python** `star_sim/spectra.py` (`scipy` `RegularGridInterpolator`
over the `.npz` — NO pymsg/Fortran/Docker at run time, Windows-clean). Panel is a
**SIBLING to the §3 spine, NOT a `StellarState`** (like Lane–Emden): `/spectrum` bypasses
`PROVIDER` like `/polytrope`. `spectrum.js` is a live consumer of the marker's three
numbers (own debounced latest-wins fetch, not the track), wired into `main.js` `refresh()`.

**Shipped solar-only** (`sg-demo.h5`, 3500–49000 K, no `[Fe/H]` axis) because the **CAP18
grids-page host `user.astro.wisc.edu` was UNREACHABLE (ECONNREFUSED)** at build time — so
per the advisor's documented fallback the MVP de-risks the slice. The bake + runtime are
**axis-generic** (read `sg.axis_labels`, store `axis_keys`/`axis_log`), so a future CAP18
(3-D `[Fe/H]`) is a **pure re-bake, ZERO code change**: `bake_spectra.py --grid <cap18>.h5`
produces a 4-D cube, the runtime reads the axis list back, the panel caption keys on
`feh_varies` (honestly says "solar-metallicity grid" until then).

**Key build/bake decisions (advisor-guided, measured):**
- **Log-spaced Teff** (cool-end line resolution; runtime interpolates in `log10(Teff)` via
  a per-axis `axis_log` flag — stored axes stay human-readable K). **Absolute flux stored**,
  normalized per-spectrum in the frontend draw (the story is continuum SLOPE + lines, not
  brightness — that's the 3D star + L readout).
- **Void-fill ALONG logg at fixed Teff**, NOT generic 2-D nearest-neighbour: sg-demo's voids
  (hot + low-gravity, ~38% of nodes) are a contiguous high-logg block, so logg-fill preserves
  the dominant Teff variation exactly (raw-coord NN would be swamped by the 3500–49000 Teff
  scale and pull a wrong-Teff spectrum). MSG cubic interp can undershoot slightly <0 in deep
  line cores → clamp negatives to 0 (1 bin, −26 vs ~1e6 flux).
- **The hot-end seam (advisor-caught, FIXED):** the hottest *draggable* star is **~80000 K**
  (60 M☉ metal-poor — far above the 49000 K grid ceiling), so a too-tight Query ceiling →
  422 → silent panel freeze. Fix: widen `/spectrum` Query bounds to `teff 1000–200000` /
  `logg −2…7` (wider than any real star) and **clamp BOTH ends** in `spectrum_data` (symmetric
  with the cool 3500 K floor) — dragging to a massive star shows the 49000 K spectrum, never a
  freeze. 422 reserved for genuinely absurd inputs.
- **Tests (advisor's insistence): line-depth anchors MEASURED THROUGH THE RUNTIME PATH** (baked
  `.npz` → RGI interpolation at a non-node test star), NOT the recipe's raw-pymsg numbers (a
  few % off). `tests/test_spectra.py` (15): always-on 422/503 contract + the hot-star NO-422
  case; data-gated Balmer-peaks-at-A, Ca-K-strong-cool-gone-hot, cool clamp, void-fill. 116
  pass (was 102). `requires_spectra_data` conftest marker gates the data tests.
- **Frontend honesty + polish:** visible band 3800–7800 Å painted in true per-wavelength
  spectral colour (`color.js` gained `wavelengthToCSS`, reusing the CIE fit); Wien-peak marker
  + Balmer/Ca/Na guides with **collision-skipped labels** (Ca K/Ca H/Hδ cluster at the Balmer
  jump); honest `feh_varies` caption; graceful "spectrum unavailable" when never-loaded (fresh
  checkout / unbaked → 503; first data-dependent sibling — lane.js never had this). Verified via
  **Playwright bundled Chromium** (`chrome --headless` hijacks the user's Chrome) across the
  spectral sequence + the 80000→49000 clamp, no JS errors.

**Durable artifacts:** plan + resume `docs/plans/graceful-toasting-thimble.md`; MSG build +
bake recipe (incl. the §6 bake command) `backend/docs/msg_spectra_build_recipe.md`; reusable
build container `msg_spike` (from `evbauer/mesa_lean:r24.03.1.01`, MSG at `/tmp/msg-2.2`, pymsg
in conda base, lapack95 at `/tmp/LAPACK95`).

**Build gotchas worth keeping (each cost an iteration):** `mesa_lean` SDK gfortran is **9.2 —
too old** (MSG 2.2's `-ftrampoline-impl=heap` is a GCC-14 flag) → use **conda-forge gfortran
15**; **build LAPACK95 from netlib source with the SAME gfortran** (SDK's prebuilt `.mod` are
gfortran-9.2, unreadable by 15); **gawk not mawk** (mawk silently fails MSG's `makedepf08.awk`
POSIX classes → module-build race); **build from a FRESH extract** (failed parallel build
leaves a corrupt `.dep`); **explicit `-I$CONDA_PREFIX/include` for `.mod`** (conda's pkgconf
strips conda-prefix `-I`; `CPATH` does NOT work for Fortran modules); set `MESASDK_ROOT` to any
valid path or `fypp_deps` crashes. **Bake env:** `MSG_DIR=/tmp/msg-2.2`,
`LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$MSG_DIR/lib`, conda base active.

**Why:** records a shipped phase + the non-obvious decisions (axis-generic for the CAP18 swap,
runtime-measured test anchors, void-fill along logg, the 80000 K hot-end clamp) so a future
session swaps in CAP18 without re-deriving them.

**How to apply:** to add CAP18 — reach the grids host, fetch the 3-D grid, re-run
`bake_spectra.py --grid <cap18>.h5`, drop the `.npz` in `data/spectra/`; no code change. Keep
`/spectrum` off `PROVIDER`; never put pymsg in `pyproject.toml` (build-container only); keep the
Query bounds wider than any real star so dragging never 422s.
