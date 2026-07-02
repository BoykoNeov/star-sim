---
name: star-sim-phase5-spectra
description: "Phase 5 synthetic-spectrum panel — DONE + CAP18 SWAP (3-D [Fe/H]) + OSTAR2002 HOT SPLICE (→55000 K, He lines) + HOT-END NO-MODEL NOTICE + GÖTTINGEN COOL SPLICE (<3500 K, TiO bands) DONE: MSG/pymsg build-time bake (no MESA SDK) → void-filled flux cube .npz → pure-Python scipy runtime serving /spectrum (bypasses PROVIDER like /polytrope). Axis-generic runtime unchanged through CAP18 swap AND both splices (NO BAKE_VERSION bump) — real new code is the bake going single-grid→multi-grid (--hot-grid / --cool-grid). He I/He II guides (minTeff-gated, hot) + TiO bandhead guides (maxTeff-gated, cool). Cool splice = Göttingen/PHOENIX sg-Goettingen-MedRes-A.h5 (Husser+2013, 1.7GB, EXACTLY 3-axis Teff/[Fe/H]/logg, log [Fe/H] like CAP18 → no Z/Zo conv, log g 0-6 covers dwarfs+giants → floor 3500→2300 K, the 2809 K coolest star now a REAL spectrum). Above the 55000 K ceiling (hottest draggable ≈78500 K) the panel BLANKS + shows 'no spectral model … reach {teff_max} K'; HOT end only (cool now real-data-covered to 2300). 121 tests. PLUS a separate BROADBAND SED PANEL (gamma→radio) — FRONTEND-ONLY Planck blackbody SED (sed.js, sibling like lane.js, Teff-only, no fetch/backend/re-bake): user wanted 'wider range, gamma and radio' but real gamma/X-ray+radio is non-thermal coronal emission with NO model grid → only honest object is the blackbody; log-log Fλ over 14 decades, 7 EM bands, Wien peak sweeps UV→vis→IR, gamma/radio floor honestly (clamp-to-floor like Li). Exported color.js planck. Verified Playwright, no JS errors, pytest unchanged."
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

**GÖTTINGEN COOL SPLICE — DONE (this session, the symmetric mirror of OSTAR).** Trigger was the user's
question "is the clamped low-T data plausible?" — answer (MEASURED via live provider): the coolest
draggable stars reach **~2809 K** (0.1 M☉ M-dwarf) and most low-mass RGB/AGB tips (incl. the **Sun's own
giant tip ~3278 K**) sit below CAP18's 3500 K floor, where **TiO molecular bands** dominate and the 3500 K
clamp understated them badly (in-grid 3500→4000 K the blue/red continuum ratio already ~triples). Spliced
**`sg-Goettingen-MedRes-A.h5`** (Husser+2013 PHOENIX, the canonical cool-star library, ~1.7 GB,
`…/grids/Goettingen/MedRes-A/v3/…`) onto the cool Teff end. **Why this grid** (verified vs the live grids
page, NOT assumed): **exactly 3-axis `Teff/[Fe/H]/log g`**, **log [Fe/H] like CAP18 → NO Z/Zo conversion**
(simpler than the hot splice), **Teff [2300,12000]**, **log g [0,6] covers dwarfs AND giants** (decisive —
**ruled out SPHINX**, a 2000–4000 K cool grid but **dwarf-gravity-only log g 4.0–5.5** → would clamp every
cool giant; also Coelho14 only-to-3000, C3K voids-warning, NewEra 4.9 GB-no-benefit). Real new code =
`bake_spectra.py --cool-grid` (`_prepend_cool_teff`/`_cool_grid_info`, mirror of the hot helpers): prepends
**19 log-spaced Teff nodes** below 3500 at the cool axis' own log-step (96 CAP18 nodes NOT re-spread).
Axis = `[19 cool][96 CAP18][27 hot]` = **142 nodes [2300..55000]**, cube `142×12×11×2400` **~98 MB**.
**Runtime+frontend axis-generic, NO BAKE_VERSION bump**; `teff_min` auto-dropped to 2300 → the 2809–3500 K
stars are now **real spectra, not the frozen clamp** (cool clamp no longer fires for any reachable star).
**≥3500 K block BIT-IDENTICAL** (verified: 123 CAP18/OSTAR nodes+flux byte-for-byte unchanged — splice purely
ADDED sub-3500). **Payoff = maxTeff-gated TiO bandhead guides** (5167/6159/7053 Å, mirror of the He II
minTeff gate) lighting up in the M regime. **Honesty (advisor — the recurring "don't label a non-feature"
trap):** all 3 TiO heads verified through the runtime path with a **slope-minimal narrow-window** measure
(step **0.55–0.75 at 2809 K vs ~0.03 in Sun**), but **VO 7400 DROPPED** (reads ~0/flat like a control λ — no
clean bandhead at reachable Teff; the **boron-b8 / invisible-Na lesson AGAIN** — verify a feature is real
before labeling it). **Seam graceful** (measured): TiO 6159 essentially continuous across 3500 (0.361→0.356),
the bigger PHOENIX-vs-ATLAS TiO 7053 difference a smooth interpolated ramp not a discontinuity. Void-fill **0
fallback**; neg-flux clamp 8840→**14120** (PHOENIX deep cores, 0.03%, depths still sane). New test
`test_cool_grid_extends_below_3500_with_molecular_bands` (TiO deep-in-M/gone-in-Sun/deepens-as-cools + off-grid
feh ±0.5 bounded — the recurring feh=0 short-circuit gap; self-skips on a no-cool-grid cube). **Stale "3500
floor" rationale fixed** (`teffAboveGrid()`'s "3300 K red dwarf as 3500 K" was now false). **121 tests.**
Playwright: 3145 K M-dwarf → 3 TiO guides on deep troughs (real Göttingen spectrum, would've clamped to 3500
before); Sun → no TiO guides; no JS errors. Recipe §5b (fetch + rationale + findings) + §6 (3-grid bake).

**BROADBAND SED PANEL (gamma → radio) — DONE (this session, FRONTEND-ONLY, the "wider range" view).**
User asked to see the spectrum "not only near visible" → clarified **"extend to gamma and radio."** The
honest answer (advisor-confirmed) is **NOT more grid data**: (1) the baked MSG cube is only ~3000–9000 Å
(the three grids barely reach ~10000 Å — Göttingen MedRes-A is the binding limit), and (2) **gamma/X-ray +
radio emission of a real star is NOT photospheric** — it's coronal/chromospheric/flare/wind emission
(activity-driven), which has **no model grid** and which the project already treats as "evocative, not
predictive." So the only physically honest object spanning the whole EM spectrum is the **Planck blackbody
SED** (defined at all λ; the textbook idealization of the photospheric continuum). New `frontend/src/sed.js`
+ panel in `index.html` + `.sed-panel` full-width CSS + wired into `main.js refresh()` — a **sibling like
`lane.js`** but driven by **Teff ALONE** (a blackbody ignores log g & [Fe/H]) → **no fetch, no backend, no
re-bake, pure frontend.** Plots **log–log Fλ over ~14 decades** (1e-4 nm γ → 1e10 nm radio), normalized to
the blackbody peak, **seven EM bands shaded** (γ-ray·X-ray·UV·visible·IR·microwave·radio; visible painted
the true rainbow via `wavelengthToCSS`, reads as the **thin sliver it is**), a **Wien-peak marker** (sweeps
UV→visible→IR as Teff drops — verified O-star 64.6 nm / Sun 497 nm / M-dwarf 871 nm), and a **gold bracket**
on the 300–900 nm window the detail panel covers ("this detail view is this slice of the whole SED").
**Advisor's key points, both addressed:** (a) **the gamma half is empty by physics** — at X-ray/γ λ the
exponent overflows → `planck()→0` → `log10(0)=−∞`; handled **exactly like Li in [[star-sim-phase4-cno]]'s
`comp.js`** (decade-capped axis `FLOOR_DECADES=14` + clamp-to-floor → curve runs flat along the bottom, no
NaN gaps), labeled coronal/flare (activity), not photospheric; (b) **symmetric on radio** — the
Rayleigh–Jeans λ⁻⁴ tail is a **floor, NOT** the real radio flux (chromosphere/corona sit orders of magnitude
above). Both caveats in the caption + a legend "non-thermal edges" tooltip. **Representation = Fλ
deliberately** (advisor) — same quantity as the detail panel (genuinely "the same curve zoomed out") +
reuses the Fλ Wien constant `2.8977719e7 Å·K` (λFλ/νFν would move the peak, need 3.67e7 — not used).
`color.js`'s private `planck`/`HC_OVER_K_NM` **exported** (only code touch outside the new file). **NO
AskUserQuestion** (advisor: "blackbody vs data" is a choice that doesn't exist — gave a one-line
reality-check, then built). Verified via Playwright (bundled Chromium) across Sun/60 M☉ O/0.2 M☉ M-dwarf +
full-page layout: Wien peak sweeps right, both tails floor honestly, no JS errors. **pytest unchanged (137
— [[star-sim-wr-wd-endgame-plan]] count) since frontend-only.** The screenshot pass IS the regression check.

**Why:** records a shipped phase + the non-obvious decisions (axis-generic for the CAP18 swap,
runtime-measured test anchors, void-fill along logg, the 80000 K hot-end clamp NOW a "no model"
notice, CAP18's 30000 K ceiling) — and that the CAP18 swap *did* pay off as a zero-code re-bake
exactly as designed.

**How to apply:** the CAP18 swap, the OSTAR2002 hot splice AND the **Göttingen cool splice** are **done**
(cube spans **2300–55000 K**: TiO bands at the cool end, He lines at the hot end). **The "spectra density
bump" (higher-res re-bake) was investigated 2026-07-02 → SKIP, measured real-but-invisible:** CAP18
`coarse`→`high`/`ultra` differ *only* in spectral R (same Teff/logg/feh node count), which THIS bake
**resamples away** to the fixed 2.5 Å / 2400-bin λ grid; and the panel draws the full ~6000 Å over ~1200 px
≈ **5 Å/px** with no zoom (≈2.7 Å/px even at 2560 px), so the current 2.5 Å bins are already ≈1 bin/px —
higher source R cannot render at any display width. Same skip as VO-7400 / boron-b8 / 0.6 M☉ structure. Docker
NOT brought up (baking-to-confirm would spend the exact GB+Docker cost the gate exists to prevent). **The
honest payoff path was a frontend spectrum *zoom / detail sub-band view* first** (Ca H&K, Mg b) — a finer bake
becomes worthwhile *only after* that view exists — **and that view is now BUILT (2026-07-02, frontend-only, no
re-bake, no backend touch).** Recorded in `ROADMAP.md` + `graceful-toasting-thimble.md`
§Next.

**SPECTRUM ZOOM / DETAIL SUB-BAND VIEW — DONE (2026-07-02, frontend-only, the density-skip's prerequisite).**
Preset band buttons under the canvas (`#spectrum-zoom` in `index.html`; **Full · Ca H&K · Mg b · Na D · Hα ·
He 4686**) reframe the x-axis onto a ~120–150 Å window. It is a **pure client-side reframe of the SAME served
`data`** (no refetch, no `n_display` — `/spectrum` already serves the full native grid: **2400 samples,
3001–8999 Å, 2.5 Å step**, confirmed via curl), so the grid's already-present 2.5 Å sampling — sub-pixel across
the ~660 px full panel (~0.11 px/Å) — becomes ~11 px/bin and the line cores resolve. `spectrum.js` gained a
`viewBand={lo,hi}|null` state + `viewWindow(lam)` (clamps the band to the data range), and the draw path:
window-local vertical normalization (fmax over the framed window → band continuum ≈1, a flat band renders flat
at the top — honest local-continuum norm, advisor-approved), a clip to the plot rect around shading+curve so
out-of-window samples don't spill, **adaptive nm ticks** (`niceNmStep`, ≥~2.5 intervals) + a "flux (band max=1)"
y-label — **all gated behind `viewBand != null` so the FULL view is byte-identical** (advisor point 4: my
`firstNm` would otherwise add a stray 300 nm tick). **The load-bearing honesty (advisor point 2): native sample
points are marked as dots** (`drawSamplePoints`, only when zoomed) — a smooth polyline hides the 2.5 Å sampling,
the dots show exactly how finely the model is resolved, so you can judge whether a finer bake would help; the
caption leads with the invariant "2.5 Å sampling" (**not** R — Δλ is constant so R runs ~1200 blue → ~3600 red).
Applies to the **main cube AND the [α/Fe] overlay** (both curves get dots — the α Mg b/Ca deepening made legible
at native res; Coelho grid confirmed same 3001–8999 range). Reset-to-Full + row `.hidden` in WD/WR/SN endgames
(mirrors the α-toggle-row idiom; the endgame cubes span other λ ranges — **verified on-screen: zoomed to Mg b →
enter WD mode → row hidden + reset to Full + zoom-caption gone → exit → row back, Full active**). **Added
`{lam:5175,"Mg b",maxTeff:8000}` to the main `LINES`** (advisor point 1 — it was α-only, so the "Mg b" button in
the normal view would have zoomed to an unlabeled band). **Playwright-verified 1440 + 390 px** (the responsive bar
— the new 7-item button row wraps cleanly at 390 px, Ca H&K still legible at ~2px/Å), **zero console errors** (the WebGL ReadPixels stalls are the
pre-existing Three.js-canvas-screenshot noise, not errors): Ca H&K splits cleanly into K 3933 + H 3968; **Na D
shows a marginal double-dip right at the 2.5 Å limit** (6 Å ≈ 2.4 bins — so the caption stays GENERIC, never
claims "resolves into two"; this band is actually the best on-screen argument for *why* a finer bake could pay
off, exactly the view's purpose — advisor point 3, verify-before-claiming); He 4686 lights up on a 34 kK O star
(in-grid; a 40 M☉ ZAMS star is 61 kK > the 55 kK ceiling → the no-model frame, so pick an in-grid O star);
M-dwarf blue band legible. Backend byte-unchanged (no `.py` touched → pytest unaffected). Plan
`graceful-toasting-thimble.md` §Next; ROADMAP row promoted from skip→done. (Splice-for-coverage — new Teff/λ *range* — is still real data work; splice **`BSTAR2006`** only if
NLTE B-star fidelity 15–30 kK is ever specifically wanted, not as a density bump.) The runtime stays
axis-generic for any such re-bake. **Splice mechanics
that paid off (reuse for BSTAR / any future grid):** `bake_spectra.py --hot-grid` *appends* Teff nodes above
the ceiling, `--cool-grid` *prepends* below the floor — both at the primary axis' own log-step (never
re-spread the CAP18 nodes; the ≥-/≤-overlap block stays bit-identical); translate any `Z/Zo`-axis grid via
`Z/Zo=10^[Fe/H]` floored at the smallest *positive* node (a log-[Fe/H] grid like Göttingen needs NO
conversion); keep the same-Teff void-fill pass (preserves the dominant Teff axis). **For a cool grid, pick
one with broad log g (dwarfs AND giants) — a dwarf-only grid (SPHINX) clamps cool giants.** **Verify every UI
guide is a REAL feature** (slope-minimal narrow-window step through the runtime path) before labeling it — VO
7400 was dropped for reading flat (boron-b8 lesson). General rules that still hold:
keep `/spectrum` off `PROVIDER`; never put pymsg in `pyproject.toml` (build-container only); keep Query
bounds wider than any real star so dragging never 422s; bake the cube into the build container
(`msg_spike`) and `docker cp` the `.npz` out — never import pymsg at run time. **chrome --headless
hijacks the user's running Chrome → use Playwright's bundled Chromium for headless shots.**

**Done (UX, rainbow far-red fix + nm axis — frontend-only, pytest unchanged 137).** User: the
spectrum panel's per-λ rainbow was true only to ~7000 Å, then swung back to **yellow→green** instead
of staying red; also wanted the axis in **nm**. ROOT CAUSE (node-measured the CIE fit, not guessed):
`color.js` `wavelengthToCSS` **normalizes every λ to full brightness**, and the Wyman CMF fit's
chromaticity drifts in the far tails (its lobes decay at different rates → past ~690 nm `cieY`
outlives `cieX`, so 740 nm rendered **pure (0,255,0) green**; below ~390 nm → cyan) — full-brightness
norm then amplifies the wrong ratio into a vivid wrong hue. FIX = two tail corrections **confined to
`wavelengthToCSS`** (advisor's key guard: leave the CMFs + `planckToXYZ` UNTOUCHED → star color + §10
Sun anchor unchanged, since there the same tail error averages out in the integral): (1) **hue
clamp** the wavelength feeding the CMFs to **[410, 680] nm** (645–680 nm are an identical saturated
red; past it the hue no longer changes, only brightness does — also fixes the 690–700 orange drift);
(2) **edge luminance falloff** to a 0.35 floor near violet (380→420) + red (700→780), multiplied in
**LINEAR light BEFORE the sRGB gamma** (NOT Bruton's 0.8-gamma — the pipeline already has proper
gamma). Net: far red deep-red→dark (720 nm 236,0,0 → 780 nm 160,0,0), violet deep, core unchanged.
SHARED with `sed.js` (same fn) → fixes its visible-band edge too. **nm axis = display-only,
spectrum.js only** (data stays Å, the existing `lam[i]/10` pattern; only x-tick labels via
`xOf(nm*10)` + axis title + comments changed; line-feature λ's stay in Å). **VERIFY WITH A COOL STAR**
(advisor): its flux peaks in the red so far-red columns are *tall* and actually exercise the fix — a
hot star's near-zero far-red columns wouldn't. Verified Playwright bundled Chromium, 0.2 M☉ M-dwarf
(3258 K): clean rainbow, far red solid-red-not-green, nm ticks, no JS errors. Cross-refs
[[star-sim-frontend-ux]].
