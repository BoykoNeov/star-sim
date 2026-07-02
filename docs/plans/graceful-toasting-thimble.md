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

**IMPLEMENTED + CAP18 SWAP DONE (3-D `[Fe/H]` axis live).** Everything in this plan
was first built and verified end-to-end on the solar `sg-demo` MVP; the **CAP18 swap
is now done** — a pure data re-bake (the bake + runtime are axis-generic, **zero code
change**) that lit up a real metallicity axis. What landed:
- **Bake:** `backend/scripts/bake_spectra.py` (axis-generic, void-fill along log g,
  log-spaced Teff, `axis_log` flag, atomic `.npz` + `BAKE_VERSION`) → ran in
  `msg_spike` → `data/spectra/spectra_grid.npz`. Now baked from **`sg-CAP18-coarse.h5`**
  → a **4-D `96 Teff × 12 [Fe/H] × 11 log g × 2400 λ` cube, ~69 MB** (was the solar
  2-D `96×11×2400`, 4.7 MB), gitignored. Void-fill: all 4560 voids along log g, 0
  fallback. Bake procedure + the CAP18 download in the recipe doc §5–§6.
- **Backend:** `backend/star_sim/spectra.py` (pure numpy/scipy sibling — `_load`,
  `RegularGridInterpolator`, `spectrum_data`, `SpectraDataMissing`) + the `/spectrum`
  route in `api.py` (bypasses `PROVIDER` like `/polytrope`). Query bounds widened to
  `teff 1000–200000` / `logg −2…7` (wider than any real star — the hottest draggable
  star is ~80000 K, well above the CAP18 grid's **30000 K** ceiling — the solar MVP
  reached 49000 K; CAP18 trades hot-end coverage for the `[Fe/H]` axis) so dragging
  **never** 422s: `spectrum_data` clamps BOTH ends to grid coverage (symmetric hot
  floor/ceiling — the advisor-caught seam; was a silent freeze above 60000 K).
- **Frontend:** `frontend/src/spectrum.js` (debounced latest-wins `update(state)`,
  flux-vs-λ with the visible band painted in true per-wavelength spectral colour,
  Wien-peak + Balmer/Ca/Na line guides with collision-skipped labels, per-spectrum
  normalization, honest `feh_varies` caption); `color.js` gained `wavelengthToCSS`;
  wired into `main.js` `refresh()`; markup in `index.html` (full-width panel) + CSS.
- **Tests:** `conftest.py` `requires_spectra_data` marker + `tests/test_spectra.py`
  (16 tests — always-on 422/503 contract incl. the hot-star no-freeze case; data-gated
  line physics MEASURED through the runtime path: Balmer peaks at A, Ca K strong-cool/
  gone-hot, clamp, void-fill; **+ the CAP18 payoff `test_feh_axis_deepens_metal_lines`**
  — at a fixed cool Teff, higher `[Fe/H]` deepens Na D / Ca K while Balmer stays ~flat
  as the control; self-skips on a solar cube). **118 tests pass** (was 116).
- **Verified:** Playwright (bundled Chromium) screenshots — the solar MVP across the
  spectral sequence, and post-CAP18 a metal-poor vs metal-rich K/M dwarf pair showing
  the `[Fe/H]` caption live + line response; the ~80000 K clamp (now shows the 30000 K
  spectrum, no freeze), no JS errors.

**CAP18 swap — DONE (this session).** The grids-page host (`user.astro.wisc.edu`)
came back up. Fetched `sg-CAP18-coarse.h5` (~339 MB, 3 axes `Teff/[Fe/H]/log(g)`),
re-baked in `msg_spike` → a 4-D `.npz`, dropped it into `data/spectra/`; the runtime
read `axis_keys` and lit up the `feh` axis, the caption flipped automatically. **Zero
code change** to runtime/frontend — only a new `[Fe/H]`-physics test + stale-`49000`-ref
fixes. The one real trade-off: CAP18 caps at **30000 K** (vs the solar MVP's 49000 K),
so hot O/B stars clamp lower — accepted, the clamp is honest and the metallicity axis
was the goal.

**OSTAR2002 hot-end splice — DONE (this session).** The CAP18 30000 K ceiling is closed:
`sg-OSTAR2002-low.h5` (a TLUSTY O-star grid, 27500–55000 K) is spliced onto the Teff axis,
so the baked cube now reaches **55000 K** (`123 × 12 × 11 × 2400`, ~76 MB). The bake
(`bake_spectra.py --hot-grid`) appends log-spaced Teff nodes above 30000 (the 96 cool nodes
are NOT re-spread), samples OSTAR for them via `Z/Zo = 10**[Fe/H]` (floored at OSTAR's
smallest positive node 0.001 to dodge a `ValueError` cliff near the metal-free node) with
log g clamped to 3.0–4.75, and a new **same-Teff void-fill pass** keeps the metal-poor hot
corner from pulling a wrong-Teff cool spectrum (990 same-Teff, **0 fallback**). The seam at
30000 K is clean (OSTAR/CAP18 mean flux ≈0.97–0.99, continuum slope continuous, a small
honest two-code Balmer step). **BSTAR2006 was deliberately not used** (15000–30000 K sits
entirely inside CAP18; adds nothing >30000). Frontend: He I 4471 / He II 4686 line guides
with a `minTeff` gate (appear only when the star is hot enough — He II lights up in the
O-star regime, the payoff). New test `test_hot_grid_extends_above_30000_with_helium` (He II
deepens 30000→45000 K, far deeper than the Sun; 45000 K is a real sample, not the old clamp).
**119 tests pass.** Verified via Playwright (Sun → no He guides; 42673 K O star → He II
labelled in cool-blue). Recipe §5a + §6. Runtime/frontend stayed axis-generic — no
`BAKE_VERSION` bump.

**Hot-end "no model" notice — DONE (this session).** Above the spliced grid's 55000 K
ceiling there is **no model atmosphere at all** (the hottest draggable star, a 60 M☉
metal-poor O star, reaches ~78500 K — verified through the live `/track`). Showing the
clamped 55000 K spectrum there would be a fake, so the panel now **blanks and says so**
instead. Implementation keeps the layering honest: the backend still clamps + returns a
spectrum (no change to `test_cool_params_clamp_to_grid_floor`), but `spectrum_data` now
also reports `teff_requested` + the grid's `teff_min`/`teff_max`; `spectrum.js` blanks the
curve and draws a centred "No spectral model for this temperature / our model atmospheres
reach {teff_max} K — this star is ≈ {teff_requested} K" message (faint frame so it reads as
intentionally empty, distinct from the 503 "grid not baked" state). **Hot end only** — the
cool floor keeps its honest small-extrapolation clamp (a 3300 K red dwarf as 3500 K), so
common cool stars (M-dwarfs, RGB/AGB tips) are not regressed; the message text is keyed off
the grid's real ceiling (`teff_max` from the response), never a literal 55000, so it
auto-tracks a hotter re-bake. New test `test_response_reports_teff_coverage_for_no_model_notice`
pins the contract (`teff_requested > teff_max` while `teff == teff_max`). **120 tests pass.**
Verified via Playwright on the real UI: 78453 K star → message with dynamic 55000 K ceiling,
no JS errors; in-range 53656 K O star → normal spectrum still draws right up to the ceiling.
(At the time the cool floor was 3500 K and kept its honest clamp — *since extended to 2300 K
by the cool splice below*, so the hot end is now the only model gap; the notice stays hot-only.)

**Cool-end splice (Göttingen/PHOENIX, <3500 K) — DONE (this session).** CAP18's 3500 K
floor was a poor stand-in for the coolest stars (measured: a 0.1 M☉ M-dwarf reaches **2809 K**,
and most low-mass RGB/AGB tips — incl. the **Sun's own giant tip ~3278 K** — sit below 3500 K;
below ~3000 K the spectrum is dominated by **TiO molecular bands** the 3500 K clamp badly
understated). Spliced in the **Göttingen grid** (Husser+2013 PHOENIX, `sg-Goettingen-MedRes-A.h5`,
1.7 GB) onto the cool end — chosen because it is **exactly 3-axis `Teff/[Fe/H]/log g`** (log
[Fe/H] like CAP18, *no* Z/Zo conversion — simpler than the hot splice), **2300–12000 K**, and
**log g 0–6** covering cool dwarfs *and* giants (ruling out SPHINX, whose log g is dwarf-only).
`bake_spectra.py --cool-grid` prepends 19 log-spaced Teff nodes below 3500 K (mirror of
`_append_hot_teff`); the ≥3500 K block stays **bit-identical**. The cool floor is now 2300 K,
below every reachable star, so the cool clamp no longer fires. **Payoff** (mirror of the He II
guides): `maxTeff`-gated **TiO bandhead guides** (5167/6159/7053 Å) light up dragging into the
M regime — all three verified real through the runtime path (step ~0.55–0.75 at 2809 K vs ~0.03
in the Sun); **VO 7400 was DROPPED** (reads ~0/flat — no clean bandhead at reachable Teff, the
boron-b8 "don't label a non-feature" rule). New test `test_cool_grid_extends_below_3500_with_molecular_bands`
(self-skips on a no-cool-grid cube). **121 tests pass.** Verified via Playwright: 3145 K M-dwarf
→ TiO guides lit + deep molecular troughs; Sun → no TiO guides; no JS errors.

**Next — spectra density bump investigated → SKIP (measured real-but-invisible, 2026-07-02).**
The idea was to re-bake at higher source resolution (CAP18 `high`/`ultra`, a `medium`/`high`
OSTAR tier) or splice **BSTAR2006**. It was gated with the project's measure-first rule and
came back negative on **two independent supports**:

1. **The recipe itself (§5):** CAP18 `coarse`→`high`/`ultra` differ *only* in spectral
   resolution R (same Teff/log g/[Fe/H] node count), and this bake **resamples that R away**
   to the fixed 2.5 Å / 2400-bin λ grid — "we resample away anyway."
2. **Display physics (independent of the recipe author's judgment):** the panel draws the
   full ~6000 Å over ~1200 px ≈ **5 Å/px** with no zoom (≈2.7 Å/px even on a 2560 px monitor).
   The current **2.5 Å bins are already ≈1 bin/px** at the largest realistic width, so any line
   narrower than a screen pixel is sub-pixel *regardless of bin size*. Higher source R only
   manifests at finer λ bins, which cannot render at any display width.

So a GB-scale download + Docker + re-bake would yield a cube **indistinguishable on screen**
from the current one — the same skip already given to VO-7400 / boron-b8 / the 0.6 M☉ structure
slice. Not baked; Docker not brought up (baking-to-confirm would spend the exact cost the gate
exists to prevent). **BSTAR2006** stays dismissed (§5a: LTE→NLTE only, inside CAP18's range,
adds nothing >30000 K).

**The one honest payoff path — a frontend feature, not a bake: BUILT (2026-07-02, frontend-only).**
The **spectrum zoom / detail sub-band view** (preset bands Full · Ca H&K · Mg b · Na D · Hα · He 4686)
reframes the x-axis onto a ~120–150 Å window — a pure client-side reframe of the already-full-res served
data (2400 samples, 3001–8999 Å, 2.5 Å step; `/spectrum` serves no `n_display` downsample), so the native
2.5 Å sampling stops being sub-pixel and the line cores resolve, with the **sample points marked as dots**
so you can judge whether a finer bake would help. `spectrum.js` `viewBand`/`viewWindow()` + window-local
normalization + adaptive ticks (all gated behind `viewBand` so full view is byte-identical); applies to the
main cube AND the [α/Fe] overlay; reset+hidden in WD/WR/SN. Added `Mg b` to the main `LINES`. Playwright-
verified (Ca H&K splits cleanly; Na D shows a double-dip *at* the 2.5 Å limit — the best on-screen argument
for a finer bake; He 4686 lights up on a 34 kK O star), zero console errors, backend byte-unchanged.
**So the density-bump re-bake is now *reconsiderable*** — but only per-band where the zoomed dots visibly
under-sample a line (e.g. Na D). Recorded here + in `ROADMAP.md` + memory `star-sim-phase5-spectra.md`.

**Done (original spike session, durable):**
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
