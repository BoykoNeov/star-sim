---
name: star-sim-mist-provider
description: "Star Simulator — MISTProvider: real MIST v2.5 grids, EEP 2D interp, full mass grid (0.1–300 M☉) + .npz parse cache, fetch-at-build. Phase 1 done."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8d890850-1473-43b3-adb1-c7ca0e98ecf7
---

**Split into a package 2026-09-03** (`docs/plans/structure-refactor.md` §1.4). One
1,780-line `providers/mist.py` is now `providers/mist/`: `parsing.py` (521 — file
discovery, the `.track.eep` parse, the fingerprint, the `.npz` cache, and `_Track`)
· `interp.py` (189 — `_Grid`/`_Axis`, `_load_grid`, `_build_axis`, `_bracket` /
`_log_mass_weight` / `_blend_windows`) · `provider.py` (1,029 — the class alone) ·
`__init__.py` (141 — the 115-line physics docstring plus a re-export block that keeps
every `from star_sim.providers.mist import …` working unchanged). Three things a
future edit needs to know:

- **`_Track` is in `parsing.py`, not with the other two dataclasses.** `_load_grid`
  calls `_load_all_tracks`, so `interp` → `parsing` is a real one-way dependency;
  putting the parse *output* type in `interp` would make it circular.
- **The grid module is `interp.py` on purpose.** `star_sim/_grid.py` already exists as
  the shared leaf one package up ([[star-sim-shared-grid-leaf]]), and two `_grid`s in
  scope is one typo away from importing the wrong one.
- **The acceptance check is the warm cache, not the test suite.** `_TRACK_COLS`' order
  and `_grid_fingerprint` are the `.npz` cache's identity: change either and every grid
  silently re-parses (~20 s each) with the tests still green. After the split all 10
  grids on disk reported a cache HIT. `CACHE_VERSION` is the *deliberate* way to
  invalidate; nothing else may.

Star Simulator (M:\claud_projects\star-sim): `MISTProvider` is now the live
provider (`PROVIDER` in `backend/star_sim/api.py`), replacing the stub as the
default. Landed 2026-06-20. Follows [[star-sim-init-scope]]; §3 boundary held —
**zero frontend changes** were needed for the swap.

**What it is:** real MIST v2.5 `.track.eep` tracks, EEP-fixed **2D (mass × [Fe/H])**
interpolation, parsed with MIST's own `read_mist_models.py` (vendored, committed,
under `providers/_vendor/` — needs `matplotlib`, added as a dep). Interpolation in
log space (logL/logT/logR/logg), age↔EEP via the interpolated age(row) relation
inverted. **Exposed window = ZAMS→end of early-AGB (EAGB, FSPS phase 4), widened
2026-06-22** (was CHeB 2026-06-21, was RGB-tip originally — see "Widened window"
and "Early-AGB extension" below). `age=0` clamps to ZAMS (EEP 202).

**[Fe/H] axis (landed 2026-06-21):** provider loads N per-metallicity `_Grid`s
(discovers every `feh_*` dir on disk; currently m050/p000/p050 → −0.5…+0.5).
Optional `fehs=(...)` ctor filter restricts which load (tests hold the solar grid
out as ground truth). **Method = blend-then-invert:** build the fully
(mass,[Fe/H]) interpolated window, *then* one age→EEP inversion — this is
deliberate and consistent with how the mass axis already worked; do NOT "fix" it
to per-grid invert-then-blend (the spec §6 wording is conceptual, not a mandate).
Physics direction it must reproduce: lower [Fe/H] → lower opacity → hotter &
brighter. **Non-rectangular valid domain:** super-solar low-mass M-dwarfs have no
evolved tracks (MIST caps them at ZAMS, 202 rows, phase never reaches 2), so
`mass_range(feh)` (new provider method + Protocol member + `/mass_range`
endpoint) tightens the mass floor to ~0.5 M☉ for [Fe/H]>0; `frontend/src/main.js`
fetches it on every feh change and clamps the mass slider (a soft floor that snaps
the thumb). The §10 red dwarf (0.1 M☉, ~2800 K) survives at solar/sub-solar [Fe/H]
where it does exist. This was a user product-call (centered axis + dead corner,
vs the simpler lopsided −0.5…0 with full mass range).

**§6 vindicated — do not hard-code MIST URLs:** the host moved
`waps.cfa.harvard.edu`→`mist.science` and version `v1.2`→`v2.5` since the spec
was written. `backend/star_sim/fetch_mist.py` *discovers* the tarball by scraping
the model-grids page (follows the redirect, picks the highest version matching
feh/afe/vvcrit). Run once: `python -m star_sim.fetch_mist` (~180 MB into
`data/`, gitignored). Provider raises `ProviderDataMissing`→503 if absent;
`/health` stays up with `data_ready: false`.

**Widened window (2026-06-21):** `_phase_window` now caps at the last row before
the early-AGB (FSPS `phase >= 4`), i.e. end of CHeB — adding the He flash +
horizontal branch / blue loop past the RGB tip, stopping short of the AGB thermal
pulses (§6's "messy, defer"). `_Track.rgb_end` renamed → `track_end`. Verified
safe: age is *strictly monotonic* across the whole span incl. the He flash (MIST
resamples it into increasing-age rows), so the age→EEP inversion never folds; and
`lies_between` is convexity-guaranteed so it can't break from widening. **Two
consequences:** (1) the age scrubber's far end is now a red-clump/early-AGB star
(~13 R☉) and the RGB-tip giant (~154 R☉) is a *mid-track* transient — so
`test_evolves_off_main_sequence` pulls the tip via `max(track, key=R)`, not the
age endpoint. (2) **Documented, accepted caveat:** at the He-ignition transition
(~2.0–2.1 M☉) cross-mass CHeB interp is poor even at 0.1-M☉ spacing (~12% median,
>300% peak L-err — *intrinsic*, not grid density; measured). The deferred full
grid is the fix, NOT denser `DEFAULT_MASSES`. New test
`test_cheb_interpolation_sampled_by_eep` samples by EEP (CHeB is a ~1% age-sliver
the age-sampled tests skip). The full grid (see "Full grid + parse cache" below)
*reduces but does not eliminate* this — measured, not assumed.

**Early-AGB extension (2026-06-22):** `_phase_window` threshold `phase >= 4` →
`>= 5`, so the window now runs ZAMS→end of EAGB (the second giant ascent), the
last row before the thermally-pulsing AGB (TPAGB, phase 5). **`CACHE_VERSION` 3→4**
(track_end ~705→~806 is cached; arrays unchanged → one ~60 s reparse). Decision was
**data-driven** (4 throwaway probes + advisor, not assumed): full-grid phase-4 onset
is the *same* EEP row ~706 for every mass with a real AGB (EEP-aligned like CHeB),
age strictly increasing (inversion never folds), EAGB smooth (2–4 logL/logR
reversals/track). **TPAGB hard-stopped** because it's 30–100 reversals/track (thermal
pulses survive resampling at different EEP rows per mass → cross-mass interp blends
incoherent pulses — §6's "messy, defer"), and MIST v2.5's third dredge-up is too weak
to even pay off as a carbon star (surface C/O stays ~0.3). **This supersedes two
"Widened window" consequences:** (1) the age-scrubber far end is now a luminous
low-gravity EAGB giant (R up to a few hundred R☉, logg ~0.6–1.2 — the §7
enormous-granule payoff), NOT a ~13 R☉ red clump; (2) for intermediate masses EAGB
radius can exceed the RGB tip, so the dredge-up/inert tests and the frontend "RGB tip"
landmark now pull the first-ascent tip from **`phase=="RGB"` rows**, not global max-R
(anchors unchanged: N ×3.14, C ×0.63). **Honesty notes:** the `"EAGB"` label is
*nominal* for ~15–40 M☉ (MIST tags phase-4 pre-collapse supergiant rows there — we
report FSPS's code, don't mass-relabel); massive >~8 M☉ stars have *zero-width* phase
4 (window untouched); the 6.5→7 M☉ boundary loses the *TPAGB* not the EAGB, so EAGB
interp across it is accurate (~0.6% median L-err, held-out 6.5). New tests:
`test_eagb_extends_window_and_tpagb_is_excluded`, `test_eagb_interpolation_sampled_by_eep`,
`test_eagb_interpolation_across_tpagb_boundary`. 63 tests pass. TPAGB remains the
next deferred phase (would need explicit per-grid handling, never cross-mass interp).

**Gotchas hit & fixed:** MIST's `phase` column is FSPS-coded and caps tracks
with a `-9` sentinel row (and pre-MS `-1`) — so the window end is the last real
row *before* the next primary phase, NOT a naive `phase<=N` (which wrongly grabbed
the -9 row at 27.7 Gyr). Z computed as 1−X−Y for exact sum-to-one. Row index ≡
EEP−1 ≡ same phase across masses (the load asserts all tracks agree on the ZAMS
row, else it refuses to interpolate).

**Empirical anchors (the stub→MIST regression, tests/test_mist_provider.py):**
Sun at (1.0, 0.0, 4.6e9) = L 1.07, Teff 5834 K, R 1.01, logg 4.43 (MIST runs
slightly hot/luminous vs the 5772/1.0 reference — tolerances are empirical, not
the stub's rel=1e-6). ZAMS spread 0.1→40 M☉ = 8.4 orders in L. Interpolated
1.5 M☉ vs real 1.5 track: median |dL|/L ~1% at fixed EEP. RGB tip 1 M☉ ≈ 154 R☉
(max radius across the now-CHeB-inclusive track).
**[Fe/H] interp accuracy is looser than mass** — a 1-dex bracket has real
curvature: held-out [Fe/H]=0 from m050/p050 vs real p000 = L median ~3.3% (max
~11%), Teff ~0.7%. So the held-out test tolerance is empirical (~6%), while
lies-between (convexity-guaranteed) stays tight. Don't import the mass test's 5%.

**Full grid + parse cache (landed 2026-06-21):** the provider now loads the
**full** mass grid per metallicity — every track on disk, **0.1…300 M☉** (was the
curated 27-mass `DEFAULT_MASSES`). So the mass axis reaches the spec's massive-O-star
end (~10⁶ L☉; `/ranges` max 40→300, user-confirmed) and the ~2 M☉ He-ignition cliff
is **reduced, not eliminated** by *density* — tight 1.9/2.0/2.1 bracketing (vs old
1.8/2.0/2.5) ~halves the CHeB median L-err (measured ~23%→~8%) and drops whole-window
median <1%, but the steepest CHeB rows at the transition stay rough (peak still 100s%
— intrinsic morphology change, NOT grid density; `lies_between` convexity still holds).
`test_transition_mass_interpolation_reduced_not_eliminated` pins this honestly.
Parsing ~170 text tracks/grid is slow (~20 s), so windowed per-track arrays are
cached to a per-grid `_parsed_tracks.npz` (under `data/`, gitignored) keyed by a
source-file fingerprint (name+size+mtime + `CACHE_VERSION`): **62 s cold → 0.35 s
warm**. Architecture = **parse-all → cache-all → select subset**
(`_load_all_tracks`/`_load_grid`): the cache always holds the full grid, decoupled
from any `masses=` subset. `DEFAULT_MASSES` survives as an opt-in curated constant —
the two EEP-interpolation tests now pin `masses=(1.4, 1.6)` so 1.5 M☉ stays
*interpolated* now that it's a real grid point (Sun anchor unchanged: 1.0 is a grid
point either way). Storage is pure numeric arrays (concat + `lengths` index, no
pickle); writes atomic (temp + `os.replace`); `fetch_mist` warms the cache after
download. New tests: `test_full_grid_loaded_by_default`,
`test_parsed_track_cache_roundtrip_fidelity` (bit-for-bit fresh-parse vs cache),
`test_cache_fingerprint_rejects_stale_source`,
`test_transition_mass_interpolation_reduced_not_eliminated` (the honest cliff
regression). Frontend needed no slider-logic change (log-scaled, reads `/ranges`);
only added 60/100/200/300 snap-tick landmarks. **All 35 tests pass.** This completes
Phase 1.

**TPAGB is exposed, not lost — + a showcase (2026-07-02):** the LIVING window still
hard-stops at φ5 (above), but `endgame()` **snaps to one real grid track** (no cross-mass/
[Fe/H] interp — the §6 hazard sidestepped) and its clipped slice INCLUDES the ~601 TPAGB
rows. So the He-shell-flash loops already shipped via the WD gateway's cooling scrub — just
**compressed into 12% of the slider** (`WD_FP` in `main.js`) to protect the ~100 kK central-
star spike. **Measured faithful** (1–3 M☉ ≈ 0.26–0.34 dex/loop, metallicity-tracking; 5 M☉
collapses to ~0.02 dex — real hot-bottom burning, verified not a resampling artifact via a
local-extrema amplitude probe). **The thermal-pulse showcase (frontend-only):** an opt-in
"🔍 Thermal pulses" toggle inside wd-mode (`.pulse-toggle`, `hr.setThermalPulses()` +
`pulseMode` mirroring the `setSupernova`/`snMode` pattern) gives the TPAGB slice the WHOLE
HR panel + slider — surface **log L vs LINEAR kyr-since-TPAGB-onset** (~6× vertical
decompression → the classic sawtooth: slow quiescent rise, brief flash, deep dip). A
**data-derived visibility gate** (`tpMedianPulseAmplitude ≥ 0.15 dex`) hides the toggle for
the ≥5 M☉ near-flat pulses (the honesty gate — only offer it where there's something to
see). Marker rides with the past/future split; x-origin honestly labeled "TPAGB onset" (row
0 = phase onset, ~½ Myr before the first actual flash — advisor-caught). Playwright-verified
1440 + 390 px (`flex-wrap` on `.endgame-bar-top`), zero console errors. This retires the old
"TPAGB remains the next deferred phase" note above. See [[star-sim-wr-wd-endgame-plan]].

**Next:** Phase 2 (shader beauty: granulation from H_p, limb darkening, corona from
`activity`). See [[star-sim-init-scope]] and [[star-sim-composition-panel]].


**Log-mass interpolation weight (2026-09-02).** `_grid_window` now blends the two
bracketing tracks with a weight linear in **log M** (`_log_mass_weight`), not M.
Measured on the full solar grid with every interior node held out (rebuilt from its
two neighbours, compared row-by-row at fixed EEP against the real track, 169 nodes):
mean median |Δlog L| 0.0033 → 0.0021 dex, better on 126/169 nodes; the coarse ends
win most (0.2 M☉ 0.036 → 0.0095; 25 M☉ 0.025 → 0.0067; 30 M☉ 0.019 → 0.0074).
Exact grid hits are w=0 so the Sun anchor and every snapped endgame are byte-identical;
no `CACHE_VERSION` bump (parse unchanged). The 0.35–0.45 M☉ nodes are slightly worse
(fully-convective transition — grid density, not weighting). Pinned by
`test_mass_interpolation_held_out_grid_nodes`, a **cache-friendly** held-out test
(truth = the full provider's own node) whose bounds sit between the two measurements.

**Sun-anchor cause corrected (2026-09-02).** The header docstring used to blame an
"interpolated request's leftover composition offset". Wrong: (1.0, [Fe/H]=0) is an
exact grid node, no blend. The 1.067 L☉ / 5834 K / 1.012 R☉ residual at 4.567 Gyr is
MIST v2.5's own p000 1.00 M☉ track (ZAMS X/Y/Z 0.7135/0.2702/0.0164); the grid puts
L=1.00 at [Fe/H]≈+0.07 or M≈0.99 M☉. Verdict unchanged: never retune. The
seismology panel's 3 % low ring is the same root.

**Cache-only clones need a second gate.** The hosted `fetch_mist_baked` buckets are
`.npz`-only; nine tests that read a raw `.track.eep` as ground truth (`_real_track`)
were failing, not skipping, there. They now carry `requires_mist_raw_tracks`
(conftest `mist_raw_tracks_available`). New accuracy tests should use the
cache-friendly form.
