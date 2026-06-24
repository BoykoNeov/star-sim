---
name: star-sim-phase5-spectra
description: "Phase 5 synthetic-spectrum panel — DONE + CAP18 SWAP (3-D [Fe/H]) + OSTAR2002 HOT SPLICE (→55000 K, He lines) + HOT-END NO-MODEL NOTICE DONE: MSG/pymsg build-time bake (no MESA SDK) → void-filled flux cube .npz → pure-Python scipy runtime serving /spectrum (bypasses PROVIDER like /polytrope). Axis-generic runtime unchanged through CAP18 swap AND OSTAR splice (NO BAKE_VERSION bump) — real new code is the bake going single-grid→multi-grid (--hot-grid). He I/He II guides (minTeff-gated). Above the 55000 K ceiling (hottest draggable ≈78500 K) the panel BLANKS + shows 'no spectral model … reach {teff_max} K' instead of the fake clamped spectrum — backend reports teff_requested/teff_min/teff_max, policy in spectrum.js, HOT end only (cool floor keeps honest clamp), keyed off teff_max not a literal. 120 tests."
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

**First shipped solar-only** (`sg-demo.h5`, 3500–49000 K, no `[Fe/H]` axis) because the
**CAP18 grids-page host `user.astro.wisc.edu` was UNREACHABLE (ECONNREFUSED)** at build time
— per the advisor's documented fallback the MVP de-risked the slice. The bake + runtime are
**axis-generic** (read `sg.axis_labels`, store `axis_keys`/`axis_log`), so CAP18 was a **pure
re-bake, ZERO code change**.

**CAP18 SWAP — DONE (this session, the axis-generic payoff realized).** The host came back up.
Fetched **`sg-CAP18-coarse.h5`** (~339 MB, the right variant — smallest with **exactly 3 axes
`Teff/[Fe/H]/log(g)`**; `large` adds α/ξ at 73 GB, `high`/`ultra` are 3-axis but higher-res we
resample away) from `…/grids/CAP18/coarse/sg-CAP18-coarse.h5`; re-baked in `msg_spike` → a
**4-D `96 Teff × 12 [Fe/H] × 11 logg × 2400 λ` cube, ~69 MB** (`feh` nodes −5…+0.5 @ 0.5);
dropped into `data/spectra/`. The runtime read `axis_keys`, lit up the `feh` axis, the caption
flipped to show `[Fe/H]` automatically — **no runtime/frontend code change**. **NO `BAKE_VERSION`
bump** (schema axis-generic & unchanged; only axis count + `grid_name` differ). Verified via curl
(Na D depth 0.24→0.48 as `[Fe/H]` −1→+0.5) + Playwright (metal-poor vs metal-rich K/M dwarf, the
`[Fe/H]` caption live). Grid facts: `Teff∈[3500, 30000]`, `[Fe/H]∈[−5, 0.5]`, `log(g)∈[0, 5]`;
void-fill **4560 along logg, 0 fallback** (no reachable-box void got a wrong-Teff/feh spectrum —
the advisor's flagged risk, checked & clean); **8840** negative-flux bins clamped to 0 (cubic
undershoot in deep cores — far more than the solar bake's **1** bin, since CAP18's R=10000 lines
ring harder, but only 0.029% of bins and reachable-corner depths are sane: Na D 0.48, Ca K 0.85).
**The one real trade-off:** CAP18 caps at **30000 K** (the recipe's old "~50000 K" claim was
WRONG — verified) vs the solar MVP's 49000 K, so hot O/B stars clamped lower — **now CLOSED by
the OSTAR2002 splice (next section).**

**OSTAR2002 HOT SPLICE — DONE (this session, >30000 K closed).** Spliced
**`sg-OSTAR2002-low.h5`** (Lanz & Hubeny 2003 TLUSTY O-star grid, ~50 MB, 27500–55000 K) onto the
hot end of the Teff axis → baked cube now reaches **55000 K** (`123 × 12 × 11 × 2400`, ~76 MB).
**The real new code is `bake_spectra.py` going single-grid → multi-grid (`--hot-grid`); runtime +
frontend stayed axis-generic, NO `BAKE_VERSION` bump** (only Teff axis length + `grid_name` differ).
- **Method:** *append* log-spaced Teff nodes above 30000 at the cool axis' OWN log-step (the 96 cool
  CAP18 nodes are **NOT re-spread** — advisor: bumping `hi` would coarsen the tuned cool end; 27 hot
  nodes added). Nodes >30000 sampled from OSTAR, reconciling its **linear `Z/Zo`** (0–2) to CAP18's
  **log `[Fe/H]`** via `Z/Zo = 10**[Fe/H]`; log g clamped to OSTAR's 3.0–4.75 (honest edge).
- **Seam is CLEAN (measured):** OSTAR/CAP18 mean flux ≈0.97–0.99 at the 28000–30000 overlap,
  continuum slope continuous, only a small honest two-code Balmer-depth step (0.347→0.307) — and the
  panel normalizes per-spectrum so even that is subtle; non-solar `[Fe/H]=−0.5` seam equally smooth.
- **`BSTAR2006` deliberately NOT used (advisor):** 15000–30000 K sits *entirely inside* CAP18 → adds
  nothing >30000; its only role would be replacing CAP18's hot LTE end with NLTE (bigger change,
  WORSE seam — BSTAR/CAP18≈0.94 vs OSTAR≈0.97–0.99). User confirmed OSTAR-only via AskUserQuestion.
- **TWO bake gotchas (found by measurement, not assumed):** (1) **floor `Z/Zo` at the smallest
  *positive* node 0.001** ([Fe/H]=−3), NOT 0.0 — a query between 0.0 (metal-free) and 0.001 needs the
  metal-free bracket, masked at hot/high-g points, so MSG raises `ValueError('invalid argument')` (a
  partial-cell void) not the clean `LookupError` the bake catches (8 such nodes; read the smallest
  positive node from the grid's own axis via h5py). (2) The old void-fill fallback pulled the
  **30000 K cool spectrum** for the metal-poor+hot corner (nearest in *index* space) — a wrong-Teff
  fill, exactly the advisor's flagged risk — so the bake gained a **same-Teff fill pass** before the
  global fallback: **6390 along logg, 990 same-Teff, 0 fallback** (no Teff-crossing fill). 8840
  neg-flux bins clamped (UNCHANGED — OSTAR added 0; confirms the cool region re-baked bit-identically).
- **PAYOFF = He lines (the advisor's "invisible-addition" bar):** the defining >30000 K feature is
  **He II 4686** (+ He I 4471), NOT the Balmer/Ca/Na the panel drew → `spectrum.js` gained He I/He II
  guides with a **`minTeff` gate** (He I ≥10000 K, He II ≥25000 K) in a cool-blue tint: they appear
  ONLY when the star is hot enough, so dragging into the O-star regime literally lights up He II 4686.
  He physics correct & measured: He II deepens monotonically with Teff (0.034→0.164 over 30000→45000),
  He I PEAKS ~35000 then weakens as He doubly ionizes. New test
  `test_hot_grid_extends_above_30000_with_helium`; existing 40000 K "clamp" tests still pass (now real
  OSTAR samples; orderings robust), stale "clamps to 30000 K" comments fixed. **119 tests** (was 118).
  Verified via Playwright (Sun → no He guides; 42673 K O star → He II labelled cool-blue, blue
  continuum). Recipe §5a (fetch + gotchas) + §6 (splice bake cmd).

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
  (60 M☉ metal-poor — far above the grid ceiling: 49000 K on the solar MVP, **30000 K on
  CAP18**), so a too-tight Query ceiling → 422 → silent panel freeze. Fix: widen `/spectrum`
  Query bounds to `teff 1000–200000` / `logg −2…7` (wider than any real star) and **clamp BOTH
  ends** in `spectrum_data` (symmetric with the cool 3500 K floor) — dragging to a massive star
  shows the ceiling spectrum (30000 K with CAP18), never a freeze. 422 reserved for genuinely
  absurd inputs. (This generic clamp is exactly why the CAP18 swap — with its *lower* ceiling —
  needed no code change.)
- **Tests (advisor's insistence): line-depth anchors MEASURED THROUGH THE RUNTIME PATH** (baked
  `.npz` → RGI interpolation at a non-node test star), NOT the recipe's raw-pymsg numbers (a
  few % off). `tests/test_spectra.py` (16): always-on 422/503 contract + the hot-star NO-422
  case; data-gated Balmer-peaks-at-A, Ca-K-strong-cool-gone-hot, cool clamp, void-fill. **118
  pass** (was 116). `requires_spectra_data` conftest marker gates the data tests. **The CAP18
  payoff test `test_feh_axis_deepens_metal_lines`** (advisor's headline): a "feh changed the
  flux" assert is too weak — instead, at a fixed COOL Teff (~5000 K) assert higher `[Fe/H]`
  **deepens the METAL lines (Na D ~+0.24, Ca K ~+0.05 — near-saturated)** while **Balmer stays
  ~flat as the CONTROL** (proves the axis carves real metal features, not a global rescale).
  Self-skips on a solar cube (`feh_varies` false), mirror of `test_solar_grid_ignores_feh` —
  one of the pair runs per cube, suite green either way.
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

**Hot-end "no model" notice — DONE** (above the grid ceiling, blank not clamp). Past the spliced
**55000 K** ceiling there is **no model atmosphere at all** (hottest draggable star ≈78500 K — a
60 M☉ metal-poor O star, verified via live `/track`), so the old clamp showed a *fake* boundary
spectrum there. The panel now **blanks + says so**. **Layering (advisor):** backend still clamps +
returns a spectrum (so `test_cool_params_clamp_to_grid_floor` is untouched — the clamp IS the
backend's honest behavior), but `spectrum_data` now also returns `teff_requested` + grid
`teff_min`/`teff_max`; the **blank-vs-draw policy lives in `spectrum.js`** (`teffAboveGrid()` =
`teff_requested > teff_max` → `drawNoModel()`: faint frame + centred "No spectral model … reach
{teff_max} K — this star ≈ {teff_requested} K", caption mirrors). **HOT end only** — cool floor keeps
its honest small-extrapolation clamp (3300 K dwarf shown as 3500 K), so flagship cool stars (M-dwarfs,
RGB/AGB tips ~2900–3200 K) are **not** regressed (strict `>` → cool never blanks); symmetric cool-end
notice considered + **rejected**. Message keys off `teff_max` from the response, **never a literal
55000** → auto-tracks a hotter re-bake. **Distinct from the 503 "grid not baked" empty-state.** Test
`test_response_reports_teff_coverage_for_no_model_notice` pins the contract. **120 tests.** Verified
via Playwright on the **real UI** (drove mass/feh/age number inputs — they commit-on-change, bypassing
snapping): 78453 K → message w/ dynamic ceiling, no JS errors; in-range 53656 K → normal draw.

**Why:** records a shipped phase + the non-obvious decisions (axis-generic for the CAP18 swap,
runtime-measured test anchors, void-fill along logg, the 80000 K hot-end clamp NOW a "no model"
notice, CAP18's 30000 K ceiling) — and that the CAP18 swap *did* pay off as a zero-code re-bake
exactly as designed.

**How to apply:** the CAP18 swap AND the OSTAR2002 hot-end splice are **done** (cube reaches 55000 K,
He lines live). To go further (more line detail, or NLTE B-star spectra): re-bake from
`sg-CAP18-high.h5`/`ultra` or OSTAR `medium`/`high` for finer spectra, or splice **`BSTAR2006`**
(15000–30000 K, NLTE) if CAP18's LTE hot end is ever a concern — all re-bakes/data work, the runtime
stays axis-generic. **Splice mechanics that paid off (reuse for BSTAR):** `bake_spectra.py --hot-grid`
appends Teff nodes at the cool axis' own log-step (never re-spread); translate any `Z/Zo`-axis grid via
`Z/Zo=10^[Fe/H]` floored at the smallest *positive* node (dodge the metal-free `ValueError` cliff);
keep the same-Teff void-fill pass (preserves the dominant Teff axis). General rules that still hold:
keep `/spectrum` off `PROVIDER`; never put pymsg in `pyproject.toml` (build-container only); keep Query
bounds wider than any real star so dragging never 422s; bake the cube into the build container
(`msg_spike`) and `docker cp` the `.npz` out — never import pymsg at run time. **chrome --headless
hijacks the user's running Chrome → use Playwright's bundled Chromium for headless shots.**
