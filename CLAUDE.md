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
  `providers/mist.py` (the real v1 provider), `providers/stub.py` (data-free
  fallback), `providers/_vendor/read_mist_models.py` (MIST's own parser, §6),
  `fetch_mist.py` (build-time grid fetch), `api.py` (FastAPI, the swap point).
- `backend/tests/` — §10 sanity checks: `test_mist_provider.py` (Sun anchor,
  ZAMS spread, EEP-between-neighbors, plus the [Fe/H]-axis tests: lies-between
  metallicities, held-out-grid accuracy, dead-corner exclusion) and
  `test_stub_provider.py`. Skip markers in `conftest.py` gate by data present:
  `requires_mist_data` (≥1 grid), `requires_mist_multifeh` (≥2), and
  `requires_mist_heldout_feh` (the m050/p000/p050 trio).
- `frontend/` — static SPA (no bundler): `index.html`, `styles.css`,
  `src/{main,star,hr,comp,color,canvas}.js` (`comp.js` is the §5.4 composition
  panel; `canvas.js` is the shared HiDPI `fitCanvas` helper the HR & composition
  panels both use). Three.js via CDN importmap. Served by FastAPI. The pedagogy
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
- **Next:** Phase 2 (shader beauty: granulation from H_p, limb darkening, corona from
  `activity`).

## Conventions

- Keep the stub honest: it is physically *flavored*, not a model. Label
  approximations in comments (the corona/activity layer is "evocative, not
  predictive" per spec §7).
- Don't let scope creep in: no live structure solve, no nuclear network, no
  deploy/bundle concerns (spec §2). This runs locally.
