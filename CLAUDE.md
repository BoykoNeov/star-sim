# Star Simulator — working notes for Claude

Interactive stellar simulator: pick a star's mass & metallicity, watch it evolve
(HR diagram + composition panel + real-time 3D star). Teaching **and** beauty.

**The full spec is `STAR_SIM_SPEC.md` — read it first.** This file is the short
operational layer on top of it; it does not repeat the spec.

## The one rule that overrides everything (spec §3)

Everything the user sees is a function of a single `StellarState`, produced
**only** through the `StellarStateProvider` interface. **No consumer may know
where the state came from.**

- `state.py` / `provider.py` define the boundary. `StellarState` is a plain
  dataclass — keep web/data-source concepts out of it.
- The HR diagram, 3D star, and composition panel consume `StellarState` only.
  A consumer (or the API) that imports a provider's internals — MIST columns,
  file formats, interpolation guts — **is a bug**, not a shortcut.
- Provider swaps happen in exactly one place: `PROVIDER` in `api.py`. Going
  deeper (Stub → MIST → live solver) must change nothing downstream.

## The gotcha that bites everyone (spec §6): interpolate on EEP, not age

Two stars of different mass at the *same age* are in different evolutionary
phases. Interpolating raw tracks against age blends a main-sequence star with a
red giant → physical nonsense. **Always interpolate at fixed EEP** (equivalent
evolutionary point), then map age ↔ EEP. The test for it: an interpolated
intermediate-mass track must lie *between* its neighbors on the HR diagram at
every phase. This matters the moment `MISTProvider` lands; the stub sidesteps it.

## Where things are

- `backend/star_sim/` — `state.py`, `provider.py` (the §3 boundary),
  `providers/mist.py` (the real v1 provider), `providers/mesa.py` (the **second**
  real provider — offline MESA `history.data`, a different on-disk format behind
  the same boundary; **multi-metallicity by snapping** — `[Fe/H]` buckets, snap
  feh-then-mass, no cross-mass/cross-feh interp; used to **validate MIST**),
  `providers/stub.py` (data-free fallback),
  `providers/_vendor/read_mist_models.py` (MIST's own parser, §6),
  `fetch_mist.py` / `fetch_mesa.py` (build-time grid fetches), `lane_emden.py`
  (the Phase 3 §8 polytrope solver — a **sibling** to the §3 spine, not a
  provider), `api.py` (FastAPI, the swap point; also hosts `/polytrope`, the one
  route that does NOT go through `PROVIDER`).
- `backend/tests/` — §10 sanity checks: `test_mist_provider.py` (Sun anchor,
  ZAMS spread, EEP-between-neighbors, plus the [Fe/H]-axis tests: lies-between
  metallicities, held-out-grid accuracy, dead-corner exclusion),
  `test_mesa_provider.py` (parser/dedup/window unit tests on a committed
  synthetic fixture + full provider API on a tmp copy — both always run — and
  gated physical-sanity on the real grid), `test_mesa_vs_mist.py` (the **measured**
  MESA-vs-MIST cross-validation, matched on Z + central-Xc via the public
  `track()` API), `test_stub_provider.py`, and `test_lane_emden.py` (§8 polytrope
  validation — closed forms n=0/1/5 pointwise + Chandrasekhar table; needs no MIST
  data, so always runs). Skip markers in `conftest.py` gate by data present:
  `requires_mist_data` (≥1 grid), `requires_mist_multifeh` (≥2),
  `requires_mist_heldout_feh` (the m050/p000/p050 trio), `requires_mesa_data`
  (≥1 MESA run), and `requires_mist_lowz` (the m100/m075 grids bracketing the
  MESA sample Z).
- `frontend/` — static SPA (no bundler): `index.html`, `styles.css`,
  `src/{main,star,hr,comp,lane,color,canvas}.js` (`comp.js` is the §5.4 composition
  panel — **three** views toggled by `setMode`: a **bulk H/He/metals** view, a Phase 4
  **per-element detail** view (fourteen metals Li·C·N·O·Ne·Na·Mg·Al·Si·P·S·Ca·Ti·Fe;
  `mode="cno"` id kept) with independent core/surface scales **and a linear/log y-axis
  toggle (`setScale`)**, and a **light-element** view (`mode="light"` — Li·Be·F, log
  forced, scale toggle hidden). Log is what makes the trace elements visible (Li at
  ~1e-10 is sub-pixel on linear; on log its surface depletion plunges off the bottom);
  the light view is the *panel* (not floor-hugger lines in the cno view) where the
  fragile light elements' depletion shows. `region()` is shared by both line views,
  parameterized by element list + a `useLog` flag; `lane.js` is the
  Phase 3 §8 Lane–Emden interior panel — a self-contained
  sibling, driven by the polytropic index `n` alone, that `main.js` instantiates
  but never wires into `refresh()`/`refreshTrack()`; `canvas.js` is the shared
  HiDPI `fitCanvas` helper the HR, composition & Lane–Emden panels all use).
  `star.js` is the Phase 2 §7 shader (a `ShaderMaterial`:
  Teff→color × H_p granulation × limb darkening, streak-proof rotation, + an
  activity-driven corona quad); `color.js` is the reference Planck→CIE→sRGB color
  pipeline (`teffToLinearRGB` for the shader, `teffToRGB`/`teffToCSS` for the 2D
  UI). Three.js via CDN importmap. Served by FastAPI. The pedagogy
  is hover-revealed: a `?` glyph (panel headings, control labels, each readout
  row) and glyph-free dotted-underline hovers on the status-line tokens, all via
  one CSS `data-tip` tooltip. The age window + the snap-tick landmarks are
  derived from the `/track` result itself (single source — the slider domain and
  the composition's EEP span can't drift), not a separate `/age_range` fetch.
- `data/` — downloaded grids (gitignored). Fetch once: `python -m star_sim.fetch_mist`.

## Commands

```bash
# backend (from backend/)
python -m venv .venv && . .venv/Scripts/activate   # Windows; or .venv/bin/activate
pip install -e ".[dev]"
python -m star_sim.fetch_mist                      # one-time: fetch MIST grids (~180 MB) into data/
uvicorn star_sim.api:app --reload                  # serves API + frontend at :8000
pytest                                             # run sanity tests (MIST tests skip if grids absent)
```

Open http://127.0.0.1:8000 — drag the mass slider; the whole UI transforms.

## Current status & what's next

- **Done:** the §3 spine; `MISTProvider` is the live provider (`PROVIDER` in
  `api.py`) — real MIST v2.5 tracks, EEP-fixed **2D (mass × [Fe/H])**
  interpolation over the ZAMS→RGB-tip window. `fetch_mist.py` *discovers* the
  current download URL by scraping MIST's model-grids page (the host moved
  waps.cfa.harvard.edu→mist.science and version v1.2→v2.5 since the spec — §6
  vindicated). `StubProvider` stays as a data-free fallback. The §10 anchors are
  the regression test for the swap (Sun: L≈1.07, Teff≈5834 K at 4.6 Gyr).
- **Done (Phase 1, [Fe/H] axis):** the provider loads N per-metallicity grids
  (currently m050/p000/p050 → [Fe/H] −0.5…+0.5) and does the §6 outer-loop
  metallicity blend. Method: **blend-then-invert** — build the fully (mass,[Fe/H])
  interpolated track window, *then* one age→EEP inversion (consistent with how the
  mass axis already worked; do not "fix" it to per-grid invert). The valid domain
  is **non-rectangular**: super-solar low-mass M-dwarfs have no evolved tracks, so
  `mass_range(feh)` (new provider method + `/mass_range` endpoint) tightens the
  mass floor for [Fe/H]>0; the frontend clamps the mass slider to it. The §10 red
  dwarf survives at solar/sub-solar [Fe/H].
- **Done (Phase 1, composition panel):** the §5.4 panel — stacked-area surface &
  core X/Y/Z vs **EEP** (`comp.js`). EEP not age on the x-axis on purpose: the
  core-H→He transition near TAMS is an invisible sliver on a linear-age axis. Fed
  by a new `track(mass, feh)` provider method + `/track` endpoint returning a list
  of `StellarState` (same §3 dataclass, ordered by EEP — never the raw interp
  window, which would leak provider internals). The same `/track` also draws the HR
  diagram's full-track polyline (§5.2). Track is age-independent: fetched on
  mass/[Fe/H] change (own latest-wins token), the marker moves on age scrub.
  Provider-side, `state_at` and `track` share one `_state_from_row` helper so they
  can't drift (the unchanged Sun anchor proves the refactor).
- **Done (Phase 1, widened window):** the exposed track now runs **ZAMS → end of
  core-He burning (CHeB)**, not just to the RGB tip. `_phase_window` caps at the
  last row before the early-AGB (FSPS `phase >= 4`); `_Track.rgb_end` → `track_end`.
  This adds the He flash + horizontal branch / blue loop — real post-tip drama —
  while stopping short of the AGB thermal pulses (§6's "messy, defer" phases). The
  He flash is *inside* the window but safe: MIST resamples it into strictly-
  increasing-age rows, so the age→EEP inversion never folds. **Consequence to know:**
  the age scrubber's far end is now a red-clump/early-AGB star (~13 R☉), and the
  RGB-tip giant (~154 R☉) is a *mid-track* transient — the tests pull the tip via
  `max(track, key=R)`, not the age-window endpoint. **Documented caveat:** right at
  the He-ignition transition (~2.0–2.1 M☉) cross-mass CHeB interpolation is poor
  even at fine spacing (intrinsic, not grid density — `lies_between` still holds);
  the deferred full grid is the real fix, *not* denser `DEFAULT_MASSES`. New test:
  `test_cheb_interpolation_sampled_by_eep` (samples by EEP, since CHeB is a ~1%
  age-sliver the age-sampled tests miss).
- **Done (Phase 1, full grid + parse cache):** the provider now loads the **full**
  mass grid per metallicity (every track on disk, **0.1…300 M☉** — was a curated
  27-mass `DEFAULT_MASSES` subset), so the mass axis reaches the spec's massive-O-star
  end (§10, ~10⁶ L☉) and the ~2 M☉ He-ignition cliff is **reduced (not eliminated)**
  by tight bracketing (1.9/2.0/2.1 vs the old 1.8/2.0/2.5): measured CHeB median
  L-error ~halves (~23%→~8%) and whole-window median drops <1%, but the steepest CHeB
  rows at the transition stay rough (intrinsic morphology change — `lies_between` still
  holds; `test_transition_mass_interpolation_reduced_not_eliminated` pins it honestly).
  Parsing ~170 text tracks/grid is slow (~20 s), so the windowed
  per-track arrays are cached to a per-grid `_parsed_tracks.npz` (under `data/`,
  gitignored) keyed by a source-file fingerprint (name+size+mtime + `CACHE_VERSION`):
  **62 s cold → 0.35 s warm**. Architecture is **parse-all → cache-all → select
  subset** (`_load_all_tracks`/`_load_grid`): the cache always holds the full grid,
  independent of any `masses=` subset. `DEFAULT_MASSES` survives as an opt-in curated
  constant (the two interpolation tests now pin `masses=(1.4, 1.6)` so 1.5 M☉ stays
  *interpolated* now that it's a real grid point). `fetch_mist` warms the cache after
  download. Storage is pure numeric arrays (concat + `lengths` index, no pickle);
  writes are atomic (temp + `os.replace`). New tests: `test_full_grid_loaded_by_default`,
  `test_parsed_track_cache_roundtrip_fidelity` (bit-for-bit fresh-parse vs cache),
  `test_cache_fingerprint_rejects_stale_source`.
- **Done (Phase 2, shader beauty — frontend-only):** `star.js` is now a
  `ShaderMaterial` and `color.js` the reference color pipeline; **no backend / API
  change, and the `activity` proxy was left untouched** (a §11 open question, not
  Phase 2). Layers (spec §7): **color** = Planck blackbody → CIE 1931 (Wyman CMF
  fit) → linear sRGB, gamma last, max-channel normalized (§10 holds: Sun warm
  near-white, not yellow); **granulation** = animated 3D Worley whose cell
  frequency is the pressure scale height `Q = R·10^logg/Teff` (Sun ≈22 cells,
  clamped [2.5, 90] — the floor *is* the giant's "handful of enormous cells");
  **limb darkening** = quadratic law; **rotation** = a continuous rigid spin
  (latitude-independent → no shear) + a **bounded, per-lifetime-reset** differential
  shear cross-faded across two reforming granule generations — this is the fix for
  the real bug where naive `omega(lat)·t` winds granulation into longitudinal
  **streaks** by ~60 s (don't revert it); **corona** = a camera-facing additive
  quad (a back-shell gave a detached ring) whose intensity+extent scale with
  `activity`, near-glowless for hot O/B stars on purpose, labelled "evocative, not
  predictive" in code + UI. `uTime` comes from a `THREE.Clock` (frame-rate
  independent). Verified with headless Chromium/SwiftShader screenshots (Sun / hot
  15 M☉ / RGB-clump giant / 0.2 M☉ dwarf + a t=0/30/60 s wind-up check); there is
  no JS test harness, so that screenshot pass *is* the regression check.
- **Done (Phase 3, Lane–Emden interior panel — §8):** a live-computed **static
  polytrope** (`P = K ρ^(1+1/n)`), built as a **sibling to the §3 spine, not a
  provider** — the spec is emphatic it is "never the evolution engine," so it is
  **not** a `StellarState` and `/polytrope?n=` is the one route that does **not**
  touch `PROVIDER`. Backend `lane_emden.py` integrates θ″+(2/ξ)θ′=−θⁿ with a
  series start off the ξ=0 singularity, DOP853 (rtol 1e-10), a **terminal event at
  θ=0** for ξ₁, and `f=−max(θ,0)ⁿ` clamping in the RHS (a non-integer power of a
  trial-point negative θ is NaN and would poison the step). Validation is the
  point (§10): closed forms n=0 (√6, 2√6), n=1 (π, π), n=5 (no finite surface)
  checked **pointwise across the domain**, plus both invariants ξ₁ **and**
  −ξ₁²θ′(ξ₁); Chandrasekhar (1939) Table 4 n=1.5/2/3/4 as looser secondary
  cross-checks (recited digits, so a mistyped table value can't impersonate an
  integrator bug). Search cap is **ξ=100** (not 50): ξ₁ diverges as n→5
  (n=4.7→54.8), and a too-small cap would mislabel a real-but-distant surface as
  "no finite surface" — `test_high_n_finite_surface_found_past_old_cap` pins that.
  The no-surface case (n≥5) plots against **raw ξ** out to a readable 20.
  Frontend `lane.js` is **self-contained and decoupled** from the spine: its own
  n-slider (snap presets 0/1/1.5/3/5, each carrying the physics as a *label* —
  n=1.5≈fully convective, n=3≈Eddington/radiative core), own debounced latest-wins
  fetch, never wired into `refresh()`. It plots **ρ/ρc=θⁿ prominently** (the §8
  payoff — central concentration jumps 1→54 from n=0→3) with θ as a fainter line,
  x normalized to r/R=ξ/ξ₁, and a readout of ξ₁, −ξ₁²θ′(ξ₁), and **ρc/ρ̄** (=1
  uniform at n=0, ~54 at n=3). Auto-deriving n from the star was **rejected as
  dishonest** — MIST gives no convective/radiative split, so it would fake a fit;
  n is the user's to set. Verified via headless SwiftShader screenshots
  (n=0/1.5/3/4.7/5); no JS test harness, so that screenshot pass is the regression
  check (the pytest suite is the real gate on the math).
- **Done (Phase 4, per-element CNO composition):** `StellarState` gained
  `metals_surf`/`metals_core` — `dict[str, float]` of element symbol → mass
  fraction (a **breakdown** of the lumped `Z`, not a replacement; X/Y/Z stay).
  Chosen as a **dict, not flat fields**, because the element set is open-ended
  (Fe/Ne/Mg are a one-line add later) and element symbols are a pure physics
  concept, not provider columns (§3). v1 exposes **C, N, O** (the CNO-cycle +
  first-dredge-up payoff), each summed over its isotopes (C=c12+c13,
  N=n13+n14+n15, O=o14…o18) from the MIST `surface_`/`center_` columns. Threaded
  through the whole §6 pipeline: `_Track` arrays Cs/Ns/Os/Cc/Nc/Oc, added to
  `_TRACK_COLS` with **`CACHE_VERSION` 1→2** (old `.npz` rejected → one ~60 s
  reparse), mixed linearly in `_grid_window`/`_blend_windows` (convex → lies-
  between preserved), emitted float-wrapped (JSON-safety) by `_state_from_row`.
  The stub fills a **flat solar-ratio C/N/O split of Z** (no processing →
  surface==core, honest "flavor"). The API is unchanged (`asdict` carries the new
  keys for free; `EXPECTED_KEYS` updated). New §10 tests (the proof): CNO bounds
  (0≤elem≤Z, ΣCNO≤Z), Sun surface solar-ballpark, **first dredge-up** (3 M☉ grid
  point, ZAMS→max-R tip: surface N ×3.15, C ×0.63 — assert N↑/C↓ only, O barely
  moves), core CNO-equilibrium (core N≫surface N, core C≪surface C). **Verified
  the feh-blend path by curl** (all tests use feh=0, which short-circuits the
  blend): off-grid mass×[Fe/H] returns bounded CNO, no KeyError. Frontend:
  `comp.js` has a **bulk ↔ CNO toggle** (`setMode`); the CNO view draws C/N/O as
  lines with **independent core/surface y-scales** — core C/O reach tens of % in
  CHeB while surface stays ~1%, so a shared scale would erase the dredge-up. The
  toggle + swapping legends live in `index.html`/`styles.css`/`main.js`; verified
  via headless SwiftShader screenshots (the screenshot pass is the frontend
  regression check, as in Phases 2–3).
- **Done (Phase 4, widened element set → Ne/Mg/Fe):** the per-element view now
  exposes **six** elements — C, N, O **+ Ne, Mg, Fe** — vindicating the dict design:
  `state.py` was untouched (open-ended `metals_surf`/`metals_core`). Provider
  threading mirrors the CNO add: `_Track` gained `Nes/Mgs/Fes` + `Nec/Mgc/Fec`
  (Ne=ne18…ne22, Mg=mg23…mg26, **Fe=fe56**, a single isotope), `_TRACK_COLS` +
  **`CACHE_VERSION` 2→3** (old `.npz` rejected → one ~60 s reparse), linear mixing in
  `_grid_window`/`_blend_windows`, six entries each in `_state_from_row`'s dicts. The
  stub's `CNO_OF_Z` became `METALS_OF_Z` (added Ne 0.112 / Mg 0.047 / Fe 0.085, solar
  fractions-of-Z; the six sum to ~0.82 Z so the per-element sum stays under Z). **The
  physics caught a wrong assumption** (advisor): Fe is *not* flat on the MS — MIST
  models gravitational settling, so the **Sun's surface Fe dips ~10% ZAMS→4.6 Gyr**
  (measured ×0.90). So the "inert tracer" test is at **3 M☉** (diffusion suppressed:
  Fe ×1.00, Ne ×0.99, Mg ×1.00 while N ×3.15) and asserts a *relative* bound, not
  flatness. Fe doubles as the **[Fe/H]-axis validator**: surface Fe at ZAMS scales
  ~10^Δ[Fe/H] per grid (measured Fe(+0.5)/Fe(0)=2.85, Fe(0)/Fe(−0.5)=3.05 vs 3.16 —
  a touch under, since [Fe/H] is a number ratio vs H; `rel=0.20`, multifeh-gated).
  New/updated §10 tests: `test_metal_breakdown_present_and_bounded` (set is the six,
  sum≤Z margin ~1e-3), `test_heavy_tracers_inert_while_cno_processes`,
  `test_iron_validates_the_feh_axis`; stub `test_stub_metal_breakdown_bounded`.
  Verified the full mass×[Fe/H] blend path via live API curl (off-grid 2.7 M☉ /
  [Fe/H]=0.25 → six bounded keys, no KeyError; all 505 track rows carry the same
  keyset). Frontend: `comp.js` `ELEMS`/`ELEM_COL` → six (atomic-number order; Fe a
  steel-grey iron mnemonic); the drawing loop was already generic. Legend grew 3→6
  (flex-wraps), button "C·N·O detail" → "per-element detail", **both** comp tooltips
  (panel `<h2>` + mode help) updated; internal `mode="cno"` id kept (minimal churn).
  Verified via headless Chrome screenshot of a throwaway probe rendering real 3 M☉
  `/track` data in cno mode (six distinct lines, dredge-up visible, scales intact).
- **Done (Phase 4, early-AGB extension):** the exposed window now runs **ZAMS → end
  of the early-AGB (EAGB, phase 4)** — the second giant ascent — not just to CHeB.
  One-line change at the §6 gate: `_phase_window` threshold `phase >= 4` → `>= 5`
  (`track_end` ~705 → ~806); **`CACHE_VERSION` 3→4** (track_end is cached; old caches
  hold the narrower value → one ~60 s reparse, arrays unchanged). The decision was
  **data-driven, not assumed** (4 throwaway probes + advisor): across the full grid
  the phase-4 onset is the *same* EEP row (~706) for every mass with a real AGB
  (EEP-aligned like CHeB), age stays strictly increasing (inversion never folds), and
  EAGB is smooth (2–4 logL/logR reversals/track) — vs the **TPAGB (phase 5) we
  hard-stop before**: 30–100 reversals/track (thermal pulses survive resampling, at
  different EEP rows per mass → cross-mass interp blends incoherent pulses, the §6
  "messy, defer"), and MIST v2.5's third dredge-up is too weak to even deliver the
  carbon-star payoff (surface C/O stays ~0.3). **Consequence to know:** the age
  scrubber's far end is now a luminous, low-gravity EAGB giant (R up to a few hundred
  R☉, logg ~0.6–1.2 — the §7 enormous-granule payoff), and for **intermediate masses
  EAGB radius can exceed the RGB tip**, so tests (and the frontend "RGB tip" landmark)
  now pull the first-ascent tip from **`phase=="RGB"` rows**, not the global max-R
  (the dredge-up anchors are unchanged: N ×3.14, C ×0.63 at the RGB tip). **Two
  honesty notes (advisor):** (a) the `"EAGB"` label is *nominal* for ~15–40 M☉ (MIST
  tags phase-4 pre-collapse supergiant rows there, no literal AGB) — we report
  MIST/FSPS's code faithfully rather than mass-relabel; massive stars >~8 M☉ have a
  *zero-width* phase 4 so their window is untouched. (b) the 6.5→7 M☉ boundary is
  where the *TPAGB* disappears, but EAGB survives both sides → interpolating across it
  is accurate (measured ~0.6% median L-error for held-out 6.5). New §10 tests:
  `test_eagb_extends_window_and_tpagb_is_excluded` (the scope proof — EAGB present,
  TPAGB/post-AGB never), `test_eagb_interpolation_sampled_by_eep` (1.5 from 1.4/1.6,
  EEP-sampled like the CHeB test), `test_eagb_interpolation_across_tpagb_boundary`
  (the advisor-insisted cross-mass accuracy check at the boundary). Frontend (pure
  pedagogy + one landmark fix): `PHASE_TIP.EAGB` gloss, Phase-readout + age-slider
  tooltip text, `criticalAges` RGB-tip restricted to RGB rows. Verified end-to-end via
  live API curl + a headless Chromium screenshot (3 M☉ at max age → EAGB giant
  renders, status line "EAGB", no JS errors). 63 tests pass (was 60).
- **Done (Phase 4, widened element set → Si/S/Ca/Ti):** the per-element view now
  exposes **ten** elements — the six above **+ Si, S, Ca, Ti** — the dict design's
  third payoff (`state.py` again untouched). Provider threading mirrors the Ne/Mg/Fe
  add exactly: `_Track` gained `Sis/Ss/Cas/Tis` + `Sic/Sc/Cac/Tic` (Si=si27…si30,
  S=s31…s34, **Ca=ca40** and **Ti=ti48**, both single-isotope like Fe — verified
  against the real MIST track header before coding, *not* assumed), `_TRACK_COLS` +
  **`CACHE_VERSION` 4→5** (old `.npz` rejected → one ~60 s reparse), linear mixing in
  `_grid_window`/`_blend_windows`, ten entries each in `_state_from_row`'s dicts.
  Field-name convention: trailing `s`=surface / `c`=core, so **`Sc` is sulfur-core,
  not scandium** (commented). The stub's `METALS_OF_Z` added Si 0.044 / S 0.020 /
  Ca 0.0042 / Ti 0.0002 (solar fractions-of-Z); the ten now sum to ~0.89 Z in the
  stub. **The sum-under-Z headroom shrank as predicted:** measured at the Sun the ten
  MIST elements sum to **~0.98 of Z** (surface 0.982, core 0.976 — headroom only
  ~3e-4, still ≫ the 1e-9 slack). The bound is *physically* guaranteed (named
  elements are a disjoint subset of the metals), so a sum >Z would mean a
  double-counted isotope — re-measuring it is the real correctness check, not the
  green assert. Updated §10 tests: `test_metal_breakdown_present_and_bounded` (set is
  the ten; real sum/Z in the docstring) and `test_heavy_tracers_inert_while_cno_processes`
  (extended to assert Si/S/Ca/Ti also ×1.00 at the 3 M☉ RGB tip — they're genuinely
  inert this side of the AGB); stub `test_stub_metal_breakdown_bounded`. **Verified the
  [Fe/H] blend path** (the real coverage gap — every `feh=0` test short-circuits
  `_blend_windows`; multifeh tests assert only logL/logT, never the metals dict) via a
  direct probe: off-grid 2.7 M☉ / [Fe/H]=0.25 → ten bounded keys, and all 606 track
  rows carry the keyset & stay bounded. Frontend: `comp.js` `ELEMS`/`ELEM_COL` → ten
  (atomic-number order C→Fe; the four new fill the open hue gaps — Si violet, S
  sulfur-chartreuse, Ca red, Ti cyan); the drawing loop was already generic. Legend
  grew 6→10 (still flex-wraps, 4+4+2), both comp tooltips + the panel `<h2>` gloss
  updated; `mode="cno"` id kept. Verified via headless Chrome screenshot (3 M☉ in cno
  mode: ten distinct lines, surface dredge-up + core C/O spike intact, legend wraps
  cleanly, no JS errors). 63 tests pass (unchanged count — extended existing tests).
- **Done (Phase 4, widened element set → Na/Al/P):** the per-element view now exposes
  **thirteen** elements — the ten above **+ Na, Al, P** (the odd-Z light metals). Provider
  threading mirrors the Si/S/Ca/Ti add exactly: `_Track` gained `Nas/Als/Ps` + `Nac/Alc/Pc`
  (Na=na21…na24, Al=al25…al27, P=p30+p31), `_TRACK_COLS` + **`CACHE_VERSION` 5→6** (old
  `.npz` rejected → one ~60 s reparse), linear mixing in `_grid_window`/`_blend_windows`,
  three entries each in `_state_from_row`'s dicts; the stub's `METALS_OF_Z` added Na 0.0020 /
  Al 0.0038 / P 0.0004 (Asplund fractions-of-Z; the thirteen now sum to ~0.90 Z in the
  stub). Field-name convention `s`=surface/`c`=core means **`Pc` is phosphorus-core**
  (commented next to the existing `Sc`=sulfur-core note). **The requested set was Na/Al/P
  *plus Cr/Mn/Ni*, but Cr/Mn/Ni are NOT in MIST v2.5's nuclear network** — verified against
  the real track header (isotopes stop at the Ca40/Ti48/Fe56 region; no chromium/manganese/
  nickel columns exist), so only Na/Al/P could be added. **The physics caught another
  wrong assumption** (advisor + measured): Na is **not inert** — the Ne-Na cycle dredges
  it up, so surface Na rises **×1.41** at the 3 M☉ RGB tip (real Na-O / Na-rich-giant
  physics). So Na gets its *own* dredge-up assertion (`>1.2`), while only Al/P join the
  inert-tracer loop (both ×1.00). **Honesty note (advisor):** the Na enrichment is a
  *data-only* signal — at ~3e-5 of mass vs O's ~7e-3 it's a sub-pixel wiggle on `comp.js`'s
  shared per-region scale, invisible to the user; making it visible (per-line normalize /
  log scale) is a separate rendering decision, not part of "add elements." So this is
  honestly **filler-plus-one-invisible-wrinkle** — Li (lithium depletion) is the visible
  payoff if more elements are wanted (see Next). The sum-under-Z headroom shrank as
  expected but holds: measured at the Sun the thirteen sum to **~0.99 of Z** (surface 0.988,
  core 0.989 — headroom ~2e-4, still ≫ the 1e-9 slack; the bound is physically guaranteed
  by disjointness, so re-measuring is the real check). Updated §10 tests:
  `test_metal_breakdown_present_and_bounded` (set is the thirteen; real surface/core sum/Z
  in the docstring), `test_heavy_tracers_inert_while_cno_processes` (Al/P added to the inert
  loop, Na carved out with its own assertion); stub `test_stub_metal_breakdown_bounded`.
  **Verified the [Fe/H] blend path** via a direct probe (off-grid 2.7 M☉ / [Fe/H]=0.25 →
  thirteen bounded keys; all 606 track rows carry the keyset & stay bounded). Frontend:
  `comp.js` `ELEMS`/`ELEM_COL` → thirteen (atomic-number order, interleaved — Na after Ne,
  Al after Mg, P after Si — *not* appended; the three new fill open hue gaps: Na sodium-D
  yellow, Al aluminium silver, P phosphorus orchid); the drawing loop was already generic.
  Legend grew 10→13 (still flex-wraps), both comp tooltips + the panel `<h2>` gloss updated;
  `mode="cno"` id kept. Verified via headless Chrome screenshot (3 M☉ in cno mode: thirteen
  distinct lines, surface dredge-up + core C/O spike intact, Na/Al/P render as the expected
  floor-huggers, legend wraps cleanly, no JS errors). 90 tests pass (unchanged count —
  extended existing tests; MESA suite already at 90).
- **Done (Phase 4, MESAProvider — the second real provider, validates MIST):**
  `providers/mesa.py` reads offline MESA `history.data` runs — a **completely
  different on-disk format** behind the same §3 boundary, proving the abstraction a
  second time (Stub→MIST showed nothing downstream changes; a second *real* physics
  provider shows it again). Scope is honest and deliberately narrow: a **discrete-grid,
  single-track** provider — `state_at`/`track` **snap to the nearest run** and report
  that run's **true** `mass_init_msun` (never silent extrapolation, §6); the only
  interpolation is the along-track age→row inversion (safe, stays within one track).
  **No cross-mass/[Fe/H] interpolation on purpose**: raw history has no EEP column, and
  identifying EEPs to row-align tracks *is* MIST's `iso` machinery (spec rules out "a
  MESA reimplementation"). So the §10 lies-between test is MIST-specific and N/A here.
  Parser is a self-contained ~40-line `history.data` reader (no `mesa_reader` dep —
  parity with the vendored MIST parser); it **dedups retry/backup rows by
  `model_number`** (keeps the last write, like py_mesa_reader) so `star_age` is
  strictly increasing for the inversion. Honest proxies, all commented: **ZAMS** =
  first row where central H dropped ~0.0015 below initial (skips pre-MS); **eep** = a
  plain monotonic row index (MESA has no EEP → *not* comparable to MIST's; the frontend
  derives its axis from the track itself, so nothing downstream assumes an origin);
  **[Fe/H]** derived from ZAMS surface Z = log10(Z/Z_sun), rounded 2 dp (he3-in-Z
  bias is a few hundredths); **phase** a coarse MS→RGB→CHeB→post-CHeB label from
  central H/He (no FSPS code in raw history). Per-element `metals_*` come back **empty**
  (tutorial runs log no isotopes — `StellarState` defaults handle it gracefully). Data:
  `fetch_mesa.py` pulls a small public grid (`bearums/InteractivePlots`, pinned SHA —
  **no upstream license, so NOT redistributed**: downloaded into gitignored `data/mesa/`
  for local use, like the MIST grids; 1/2/4/6/10/14/20 M☉, single Z≈0.0022 → [Fe/H]≈−0.84).
  **The validation (the upgraded scope) is the payoff — and it is *measured*, not a
  green check with a priori tolerances** (advisor): `test_mesa_vs_mist.py` diffs MESA vs
  MIST through the public `track()` API, controlling **both** confounds — matched on
  **Z** (solve the MIST [Fe/H] whose ZAMS Z = the MESA run's; the sample Z=0.00218 sits
  between MIST m100 Zinit=0.00171 and m075 Zinit=0.00303, so `fetch_mist --feh m075,m100`
  is required) **not** on derived [Fe/H] (different Z_sun/Y(Z) laws → equal "[Fe/H]" ≠
  equal Z), and compared at **shared central Xc** (0.6/0.4/0.2) not each code's ZAMS
  label. Yinit agrees (~0.2518 both) so Y is not a confound. **Measured gaps** (M=1/2/6):
  near ZAMS |ΔlogL|≤0.036, |ΔTeff|≤2.3%, |ΔR|≤8.2%; by late MS |ΔlogL|≤0.126, |ΔTeff|≤4.4%,
  |ΔR|≤20.3% — MESA systematically more luminous/larger, gap **growing off ZAMS**
  (late-MS overshoot/mixing/opacity sensitivity; tutorial inlist ≠ MIST v2.5). Tolerances
  pin those measured numbers with margin (the `test_mist_provider.py` pattern). MESA is
  **opt-in** — `PROVIDER` in `api.py` stays `MISTProvider`. New conftest gates:
  `requires_mesa_data`, `requires_mist_lowz`. 85 tests pass (was 63; +22 MESA, the rest
  are the now-present m075/m100 grids exercising existing [Fe/H]-axis tests).
- **Done (Phase 4, MESAProvider → multi-metallicity by snapping):** the provider
  went from a hard single-Z guard (raised if runs spanned >0.02 dex in [Fe/H]) to
  **multi-metallicity by snapping** — runs group into `[Fe/H]` buckets (key = derived
  feh rounded 2 dp), and a request **snaps feh-then-mass**: nearest grid [Fe/H] bucket,
  then nearest mass within it. `_snap(mass)` → `_snap(mass, feh)` is the single choke
  point (age_range/state_at/track can't disagree); `parameter_ranges`/`mass_range` now
  report a **real feh span** with a **non-rectangular** per-Z mass domain; off-grid feh
  **snaps in-range / raises out-of-range**, reporting the *true* grid feh in `feh_init`
  (mirrors the existing true-mass honesty — never a silent extrapolation, §6). **Still no
  cross-mass/cross-feh interpolation** (raw history has no EEP = MIST's `iso`, out of
  scope — unchanged). The single-Z grid is just the degenerate one-bucket case, so all
  prior behavior is preserved; **no `CACHE_VERSION`** (MESA has no parse cache). Tests:
  5 new **always-on** multi-Z tests on a programmatic two-bucket synthetic fixture
  (deliberately non-rectangular: solar 1.0+2.0 M☉ / metal-poor −0.5 1.0 M☉) exercise
  snap-feh-then-mass, per-feh `mass_range`, true-value reporting, and out-of-grid raises.
  90 tests pass (was 85). The capability was **latent / multi-Z-ready** when written: a
  future grid with a second metallicity drops into `data/mesa/` with **zero code** — at
  the time the provider still loaded only the metal-poor bearums bucket (**now realized**
  — a solar bucket was added; see the solar-grid bullet below). **Drop-in caveat:** buckets
  are keyed by *per-track* `round(derived_feh, 2)`, so when a real second-Z grid lands,
  confirm each physical grid collapses to **exactly one** bucket key (a grid whose
  per-mass derived feh straddles a 2-dp rounding boundary would fragment into two —
  bearums is uniform today, so `feh min==max` holds; the future-proof fix, if ever
  needed, is to bucket by clustering rather than raw rounding).
  **Why no solar grid was added (the deliberate non-action — finding worth keeping):**
  a clean, fetchable, *native* multi-mass **solar** MESA grid with surface composition
  in standard `history.data` format **does not exist publicly** (thorough hunt). The one
  multi-mass solar grid, `konkolyseismolab/mesalab`, is **MIST tracks repackaged** as
  history.data (its inlists literally say "Dummy inlist for MIST data … automatically
  generated") → feeding it through `MESAProvider` makes the MESA-vs-MIST cross-validation
  **circular** (MIST-vs-MIST, a fake green check) — **rejected** (also has no 1 M☉). The
  one genuine *native* solar source, `sai-veeresh/computational-astrophysics`, is real
  MESA (verified sane Sun anchor: MESA ~0.04–0.05 dex brighter / 60–90 K hotter than MIST
  p000 at matched Xc — real independent scatter) **but has no bulk surface composition at
  all** (only `center_*` + `surface_c12/o16`), so `X/Y/Z_surf` — *required* §3 fields —
  would have to be fabricated or the non-negotiable spine mutated, plus a non-standard
  1-line-header format and 1 M☉-only-at-solar. Not worth ingesting. **The real path to a
  clean solar Sun anchor is a one-off MESA-Web solar run** (clean full-column standard
  format → fits the existing parser, zero surgery) — now a pure drop-in thanks to this
  generalization. **Now done — see the next bullet** (run locally in Docker rather than
  via the MESA-Web web form, which never delivered its result email; same idea: a clean
  full-column solar `history.data` straight into the parser).
- **Done (Phase 4, solar MESA grid — the multi-Z capability realized, zero provider code):**
  the latent multi-metallicity-by-snapping is now **real data**: a near-solar
  `[Fe/H]≈0.00` bucket sits alongside bearums (`−0.84`), so `MESAProvider` exposes two Z
  buckets. Made by running **MESA r24.03.1 locally in Docker** (`evbauer/mesa_lean:r24.03.1.01`,
  driven by `docker exec` — no SSH helper, no local MESA build): a 1 M☉ run at
  **`initial_z=0.0152`** (= the project `Z_sun`, so derived `[Fe/H]` rounds to **+0.00**),
  pre-MS→TAMS, `pgstar` off (headless), **`history_interval=1`** for a dense track (297
  models → **129 exposed rows**). **This was a *data* task — no `state.py`/`mesa.py`/
  `CACHE_VERSION` change** (MESA has no parse cache; the provider reads mass/feh from the
  file, not the dir name, so `data/mesa/solar/1Msun/` doesn't collide with bearums
  `data/mesa/1Msun/`). The output is gitignored like all of `data/`, so the **reproducibility
  recipe lives at `backend/docs/mesa_solar_recipe.md`** (image, exact inlist, the
  `history_columns.list` surface-`h1`/`he4` uncomment, placement, measured anchor) — the
  *how* survives even though the file can't be committed. **One test broke as predicted
  (advisor):** `test_real_grid_loads_with_expected_masses` pinned single-Z
  (`assert feh min==max`); adding the solar bucket is exactly what makes the provider
  multi-Z, so the assertion was updated to verify the **bearums bucket** is present +
  metal-poor + carries its 7 masses, *without* assuming it's the only Z (robust whether or
  not the optional solar drop-in is present). **The payoff — measured, the actual reason
  for a solar bucket:** `test_mesa_vs_mist_solar.py` (+ conftest gates `requires_mesa_solar`,
  `requires_mist_solar_bracket`) cross-validates solar MESA vs MIST through the public
  `track()` API, matched on **Z** (the solar ZAMS `Z_surf=0.01523` is **below** MIST p000's
  `0.01635`, so p000 alone can't bracket it — the straddling grids are **m050 + p000**,
  matched MIST `[Fe/H]≈−0.05`; Yinit agrees ~0.269) and compared at shared **Xc=0.6/0.4/0.2**.
  **Measured (masses 1/2/6):** the **1 M☉ Sun is dramatically tight** (|ΔlogL|≤0.014,
  |ΔTeff|≤0.04%, |ΔR|≤1.5% — ~10× under the metal-poor bracket), while the **intermediate
  masses grow off ZAMS** (worst at Xc=0.2: |ΔlogL|≤0.069, |ΔR|≤9.9% — the convective-core-hook
  regime), staying inside but approaching the metal-poor envelope (late-MS |ΔlogL|≤0.13,
  |ΔR|≤20%). **Honest note:** the ΔlogL sign is **not uniform** (MESA brighter at 1 M☉, MIST
  brighter at 2/6), so — unlike the metal-poor grid — there's no "MESA systematically
  brighter" assertion here. **Sun anchor
  (4.6 Gyr): L=1.18, Teff=5894 K, R=1.04, mid-MS** — *not* solar-calibrated (no α_MLT/Y
  tuning to force L=1; the offset is real and honest, on the MESA-brighter trend). MESA
  stays **opt-in** (`PROVIDER` in `api.py` is still `MISTProvider`). **102 tests pass** (was
  92; +10 solar cross-val over 1/2/6 M☉). Gotchas worth keeping (all in the recipe doc):
  `pkill -x star` not `pkill -f .../star` (the `-f` pattern matches its own argv and the kill
  suicides); `docker exec -d` to detach the run from the client; `pgstar_flag=.false.` removes
  the whole Xming/X11 prerequisite. **2 & 6 M☉ added** (same warm container): the solar bucket
  now spans **1/2/6 M☉**, the cross-val parametrizes over all three, and a dedicated
  `test_one_msun_sun_is_exceptionally_tight` pins the Sun-specific ~10× tightness.
- **Done (Phase 4, Li lithium + the log-scale per-element view):** the per-element view
  now exposes **fourteen** elements — the thirteen above **+ Li** (li7, single isotope
  like Ca/Ti/Fe; placed *first* in `ELEMS`, atomic order Z=3). The provider threading is
  the same mechanical mirror of the Na/Al/P add: `_Track.Lis/Lic`, `_TRACK_COLS` +
  **`CACHE_VERSION` 6→7** (old `.npz` rejected → one ~60 s reparse — measured 227 s for
  the full suite cold), linear mixing in `_grid_window`/`_blend_windows`, one entry each
  in `_state_from_row`'s dicts; stub `METALS_OF_Z` Li 3.8e-9 (depleted-photospheric flat
  floor — only MIST shows depletion). **But the headline is that this was NOT a one-line
  dict add** (the spec/Next bullet undersold it — caught by advisor + measurement before
  coding): surface Li is **~1e-10 of mass** (a *million×* smaller than Na, which was
  already "a sub-pixel wiggle"), so on `comp.js`'s shared **linear** per-region scale it
  renders flat on the zero axis — a data-only add would have shipped an invisible 14th
  line, the exact "dishonest green check" the project guards against, defeating the whole
  reason Li was chosen over more heavy elements. The visible payoff *required a rendering
  change*; the **user chose a linear/log toggle** (advisor's lean; linear stays default).
  So `comp.js` gained `setScale("lin"|"log")` and `region()` a log path: a **decade-
  rounded window capped to [4,10] decades** (so a lone ~1e-16 core-Li sample can't stretch
  the axis to 15 decades), values at/below the floor — Li once it burns to ~0 — **clamp to
  the bottom** so the plunge reads as "off the bottom", not a NaN gap, plus faint decade
  gridlines + exponent tick labels. The lin/log buttons live in `.comp-modes` (shown only
  in cno mode via CSS), wired in `main.js` like the existing mode toggle. **Measured Li
  physics grounds the tests** (not assumed): surface Li at 3 M☉ ZAMS 1.0e-8 → RGB tip
  1.35e-10 (a **74× plunge**, tip/zams 0.0135); the Sun is the famous mild case (×0.87
  over the MS, then ×~2400 by the RGB tip); core Li ~1e-16 (burned instantly the whole
  MS). **So Li is NOT inert** — carved out of `test_heavy_tracers_inert_while_cno_processes`
  with its own assertion (like Na), plus a dedicated `test_surface_lithium_depletes` (the
  payoff test: tip/zams<0.05 + core Li ≪ surface Li). Bound test set → fourteen (sum still
  ~0.99 Z — Li adds only ~1e-10); stub set → fourteen. **91 tests pass** (was 90 — the new
  Li test). **Verified the [Fe/H] blend path** (the recurring gap — every feh=0 test
  short-circuits `_blend_windows`) via a direct probe: off-grid 2.7 M☉ / [Fe/H]=0.25 →
  606 blended rows, all fourteen bounded keys incl Li, surface Li depletes (1.93e-8 →
  2.67e-10). **Pedagogy (the user's explicit second ask — "why this happens, where to
  look"):** hover stories on every per-element legend entry (Li: burns low-T, dredged down
  & destroyed, *switch to log to watch it plunge*; C/N/O the dredge-up; Na the Ne-Na
  enrichment; Fe inert + low-mass diffusion dip; Ne/Mg/Al/Si/P/S/Ca/Ti a per-element
  inert-tracer gloss), a `?` on the scale toggle explaining the log rationale + where to
  look, and the panel `<h2>` + mode-help prose updated with Li + the log hint. **Verified
  the visible payoff** via a Playwright screenshot (the user's running Chrome hijacks the
  `chrome --headless --screenshot` CLI — "Opening in existing browser session" — so the
  reliable headless path here is **Playwright's bundled Chromium**, installed in the
  scratchpad; the throwaway `frontend/_li_probe.html` was deleted after): **linear → Li
  flat on the axis (invisible); log → the surface Li line plunges off the bottom at the
  RGB, core Li pinned at the floor**, all fourteen elements legible across the decades, no
  JS errors. (Frontend has no JS test harness — the screenshot pass *is* the regression
  check, as in Phases 2–4.)
- **Done (Phase 4, Li/Be/F light-element panel):** a **third** composition view
  (`mode="light"`) — the fragile light elements **Li, Be, F** on a forced-log scale,
  the *panel* the prior bullets pointed at (not three more floor-hugger lines in the
  fourteen-element cno view, which is the whole point). **The requested set was Be/B/F,
  but boron was DROPPED — measured, not assumed** (advisor + a throwaway probe before
  coding): MIST v2.5's *only* boron isotope is **`b8`, which is radioactive** (β⁺ decay,
  t½≈0.77 s — the pp-III branch that makes the high-energy solar neutrinos), so
  `surface_b8` sits at a numerical-zero **~1e-83** floor, not stable boron (no b10/b11 in
  the network). A flat 1e-83 line is exactly the invisible floor-hugger the panel exists
  to avoid. This is subtler than the Cr/Mn/Ni finding (there the columns didn't exist;
  here the column exists but its one isotope is radioactive). **Be and F are real and
  tell the lesson — fragility tracks burning temperature:** measured surface depletion at
  3 M☉ ZAMS→first-ascent RGB tip — **Li ×0.0135** (~2.5 MK, plunges), **Be ×0.35**
  (~3.5 MK, depletes modestly — *more robust* than Li), **F ×0.91** (preserved this side
  of the AGB — the stable backdrop, the role Fe plays in the cno view; its enrichment
  story is on the excluded TPAGB). be9 dominates Be / f19 dominates F (be7 EC-decays ~53 d,
  f17/f18 short-lived), so the all-isotope sum (project convention) equals the stable
  value. Provider threading mirrors the Li add: `_Track.Bes/Fs` + `Bec/Fc`
  (Be=be7+be9+be10, F=f17+f18+f19), `_TRACK_COLS` (Be after Li, F after O — atomic order)
  + **`CACHE_VERSION` 7→8** (old `.npz` rejected → one ~60 s/grid reparse), linear mixing
  in `_grid_window`/`_blend_windows`, two entries each in `_state_from_row`'s dicts; field
  convention `Fs`/`Fc`=fluorine vs `Fes`/`Fec`=iron (commented). The stub's `METALS_OF_Z`
  added Be 1.0e-8 / F 2.4e-5 (flat floors — only MIST shows Li/Be depleting, F holding).
  Element set → **sixteen** (sum still ~0.99 Z — Be ~1e-8, F ~2e-5; the bound is physically
  guaranteed by disjointness). New/updated §10 tests: `test_metal_breakdown_present_and_bounded`
  (set→sixteen, boron-absence documented), `test_light_elements_deplete_in_burning_temperature_order`
  (the payoff: Be `0.1<r<0.6` AND `be_r>li_r`, F `0.8<r<1.1` — Be/F deliberately NOT in the
  inert loop), stub set→sixteen. **92 tests pass** (was 91 — the new light test). **Verified
  the [Fe/H] blend path** (the recurring feh=0 short-circuit gap) via a direct probe: off-grid
  2.7 M☉ / [Fe/H]=0.25 → 606 blended rows, all sixteen bounded keys, depletion ordering holds
  (Li 0.016, Be 0.40, F 0.93). Frontend: `comp.js` gained `LIGHT_ELEMS=[Li,Be,F]` + a
  `drawLight()` reusing a parameterized `region(...,elems,useLog)`; `setMode` accepts "light";
  third mode button + `legend-light` (with the per-element fragility hover stories) + CSS
  `mode-light` rules (scale toggle stays cno-only — light is log-only); `main.js` toggles
  `mode-cno`/`mode-light` mutually. Panel `<h2>` tooltip notes boron's absence in plain
  language. **Verified via Playwright (bundled Chromium — the user's running Chrome hijacks
  `chrome --headless --screenshot`)** driving the *real* served UI: light button → `mode-light`
  class, legend swap, scale-toggle hidden, no JS errors; screenshot shows surface Li plunging
  on the lower RGB, Be dipping modestly, F flat — and the cno-log view still renders its
  fourteen elements intact after the `region()` refactor. (No JS test harness — the screenshot
  pass *is* the regression check, as in Phases 2–4.)
- **Next:** more Phase 4 paths, each behind the existing §3 provider interface:
  the **solar MESA grid** is **done** (1/2/6 M☉ at Z=0.0152 via local Docker MESA runs →
  a real `[Fe/H]≈0.00` bucket + a measured solar MESA-vs-MIST cross-val over all three
  masses; see the solar-grid Done bullet + `backend/docs/mesa_solar_recipe.md`). The per-element
  view is **done
  through Li** and the light-element panel is **done (Li/Be/F)**, and the lesson holds
  that *adding more individual metals is a dead end for payoff* (Na/Al/P are invisible
  floor-huggers; Cr/Mn/Ni aren't even in MIST v2.5's network; **boron's only isotope is
  radioactive** — so the panel is Li/Be/F, not the originally-imagined Be/B/F). The light
  view is now the home for any further fragile-light-element pedagogy, but the network
  has no other clean candidate (the next nuclides up are the C/N/O the cno view already
  covers). Remaining bigger arcs: the **TPAGB thermal pulses** (still deferred — §6's
  genuinely messy phase; would need explicit per-grid handling, *not* cross-mass
  interpolation), eventually a `LiveSolverProvider` or reduced nuclear network (large,
  explicitly out of scope for now — see spec §9).

## Conventions

- Keep the stub honest: it is physically *flavored*, not a model. Label
  approximations in comments (the corona/activity layer is "evocative, not
  predictive" per spec §7).
- Don't let scope creep in: no live structure solve, no nuclear network, no
  deploy/bundle concerns (spec §2). This runs locally.
- **Claude's auto-memory is tracked in the repo** at `docs/memory/` (`MEMORY.md`
  index + one file per fact). The harness still reads/writes memory from its fixed
  path `~/.claude/projects/M--claud-projects-star-sim/memory`, which is a **directory
  junction** pointing at `docs/memory/` — so every memory write lands in the repo.
  Consequence: after writing or editing memory, **`git add docs/memory` and commit
  it** like any other tracked change (the session-end ritual already covers this). If
  the junction is ever missing (fresh clone on another machine, or it got replaced by
  a real dir), re-create it: `New-Item -ItemType Junction -Path "<that .claude path>"
  -Target "<repo>\docs\memory"` (Windows; no admin needed) — the repo copy is the
  source of truth.
