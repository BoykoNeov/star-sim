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
  provider), `spectra.py` (the Phase 5 synthetic-spectrum runtime — also a
  sibling), `api.py` (FastAPI, the swap point; also hosts `/polytrope` and
  `/spectrum`, the routes that do NOT go through `PROVIDER`).
- `backend/tests/` — §10 sanity checks: `test_mist_provider.py` (Sun anchor,
  ZAMS spread, EEP-between-neighbors, plus the [Fe/H]-axis tests: lies-between
  metallicities, held-out-grid accuracy, dead-corner exclusion),
  `test_mesa_provider.py`, `test_mesa_vs_mist.py` (the **measured** MESA-vs-MIST
  cross-validation, matched on Z + central-Xc via the public `track()` API),
  `test_stub_provider.py`, `test_lane_emden.py` (§8 polytrope validation),
  `test_spectra.py`, `test_endgame.py`. Skip markers in `conftest.py` gate by
  data present (`requires_mist_data`, `requires_mist_multifeh`,
  `requires_mist_heldout_feh`, `requires_mesa_data`, `requires_mist_lowz`,
  `requires_spectra_data`, …).
- `frontend/` — static SPA (no bundler): `index.html`, `styles.css`,
  `src/{main,star,hr,comp,lane,spectrum,sed,scale,classify,color,canvas,layout,tooltip}.js`.
  `layout.js` is the draggable/responsive **dashboard** layer (a reorder-in-flow
  sortable over the flex-wrap panel container, see [[star-sim-draggable-responsive-panels]]).
  `comp.js` is the §5.4 composition panel — **three** views via `setMode` (bulk
  H/He/Z; per-element detail, 14 metals + linear/log `setScale`, `mode="cno"` id
  kept; light-element `mode="light"` Li/Be/F log-forced). `lane.js` is the Phase 3
  §8 Lane–Emden interior panel (a self-contained sibling driven by the polytropic
  index `n` alone, never wired into `refresh()`). `star.js` is the Phase 2 §7
  shader (Teff→color × H_p granulation × limb darkening × streak-proof rotation +
  activity corona quad). `color.js` is the reference Planck→CIE→sRGB color pipeline
  (`teffToLinearRGB` for the shader, `teffToRGB`/`teffToCSS`/`wavelengthToCSS` for
  the 2D UI). `canvas.js` is the shared HiDPI `fitCanvas` helper. Three.js via CDN
  importmap, served by FastAPI. Pedagogy is hover-revealed (a `?` glyph + dotted
  status-line tokens, all via one `tooltip.js` singleton). The age window + snap-tick
  landmarks are derived from the `/track` result itself (single source), not a
  separate `/age_range` fetch.
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

Phases 1–5 are built; the app is feature-complete for the current scope. This is
**current state**, not a changelog — the full per-feature history lives in git, the
`docs/memory/` topic files (detailed, recalled on demand), and `docs/plans/`
(designs). The `[[links]]` below point at the topic file that holds the detail.

### Providers (the §3 spine)
- `PROVIDER` in `api.py` is **`MISTProvider`** — the live provider. Real MIST v2.5
  tracks, EEP-fixed **2D (mass × [Fe/H])** interpolation (blend-then-invert), full
  mass grid **0.1–300 M☉** per metallicity, window **ZAMS → end of early-AGB**
  (TPAGB thermal pulses hard-stopped — §6 "messy, defer"). Non-rectangular valid
  domain (`mass_range(feh)` tightens the floor for [Fe/H]>0). Per-grid
  `_parsed_tracks.npz` parse cache (**`CACHE_VERSION` 9**; ~60–110 s cold reparse on
  a bump, ~0.35 s warm). [[star-sim-mist-provider]], [[star-sim-composition-panel]].
- `MESAProvider` — the **second real provider** (offline MESA `history.data`, a
  different on-disk format behind the same boundary), used to **validate MIST**.
  Discrete-grid, snap-to-nearest, **multi-metallicity by snapping** (no
  cross-mass/feh interp). Two Z buckets on disk: bearums [Fe/H]≈−0.84
  (1/2/4/6/10/14/20 M☉) + a self-run solar Z=0.0152 bucket (1/2/6 M☉, Docker MESA
  r24.03.1). Payoff = **measured** MESA-vs-MIST cross-validation matched on Z +
  central-Xc. **Opt-in** (not the live PROVIDER). [[star-sim-phase4-mesa]]; recipe
  `backend/docs/mesa_solar_recipe.md`.
- `StubProvider` — data-free fallback, physically *flavored* not modeled.

### Composition (§5.4 panel)
- `StellarState` carries `metals_surf`/`metals_core` **dicts** (a breakdown of Z,
  not flat fields — `state.py` was untouched across every element add). Per-element
  set is **sixteen**: Li·Be·C·N·O·F·Ne·Na·Mg·Al·Si·P·S·Ca·Ti·Fe (sum ~0.99 Z).
  Adding more individual metals is a dead end for payoff (Na/Al/P are invisible
  floor-huggers; Cr/Mn/Ni aren't in MIST v2.5's network; boron's only isotope is
  radioactive b8). [[star-sim-phase4-cno]].

### Spectra (synthetic-spectrum panel — a **sibling**, not a provider)
- `/spectrum` bypasses `PROVIDER` (like `/polytrope`). Engine = MSG/pymsg
  **build-time bake** → void-filled flux cube `data/spectra/spectra_grid.npz`
  (gitignored) → pure-Python scipy runtime `spectra.py`. Current cube: 3-grid Teff
  axis **2300–55000 K**, **142×12×11×2400** (Göttingen cool <3500 + CAP18
  Teff/[Fe/H]/logg + OSTAR2002 hot >30000). The bake is axis-generic (single→
  multi-grid via `--cool-grid`/`--hot-grid`, **no `BAKE_VERSION` bump**). Payoffs:
  [Fe/H] deepens metal lines; He I/II `minTeff`-gated; TiO `maxTeff`-gated;
  past-ceiling no-model notice keyed off `teff_max`. [[star-sim-phase5-spectra]];
  recipe `backend/docs/msg_spectra_build_recipe.md`; plan
  `docs/plans/graceful-toasting-thimble.md`.

### Endgame (WR/WD — `/endgame` goes **through** PROVIDER; an endgame state IS a StellarState)
- Both endgames are already on disk in the MIST tracks (clipped by the `phase>=5`
  window). `endgame()` is on the Protocol (MESA/Stub → `type="none"`),
  `EndgameResult` dataclass, snaps both mass+feh, data-derived classify (φ9→WR /
  φ6-or-logg>7→WD / φ5-onset→SN / else none). WD path = a reversible gateway button
  at the slider limit → log-cooling-age scrubber + WD 3D shader + structure panel +
  mass–radius re-snap. WR path (Chunk 4) = the matching `→ Continue: Wolf–Rayet` button
  → reversible `wr-mode`: index-linear scrub over the φ9 sub-track (WN→WC→WO landmark),
  HR axes to ~316 kK / logL 7, the **normal comp views** (the stripped surface IS the
  story — no custom cross-section), WN/WC/WO subtype from surface composition, mass-stays-
  live re-snap, end caption narrates the un-modeled core-collapse. WR 3D (Chunk 5) = the
  **optically-thick-wind shader** (`star.js` `WIND_FRAG` + `wind` mesh): an additive halo
  over the opaque hot sphere — electron-scattering haze brightest at the limb (pseudo-
  photosphere) + outward-advected value-noise filaments; reach/density read from `Z_surf`
  (smooth WN → clumpy WC/WO), color = honest Teff blackbody (no chemistry hue — it'd
  contradict the spectrum placeholder), intensity a gentle clamped `L` tie (NOT a measured
  Ṁ). **Fit-to-frame extent** (`applyWindScale`, recomputed each frame) — the WR scrub opens
  on a huge R≈33 R☉ star, so a constant extent would clip the viewport. WD spectra (Chunk
  **6a**) = a **second** spectrum sibling `/wd_spectrum`: a separate rectangular Koester DA
  cube (82 Teff × 13 log g, pure-H so no [Fe/H], host-baked — no Docker/pymsg via
  `fetch_koester.py` + `scripts/bake_wd_spectra.py`), `spectrum.js` `updateWD` switched in by
  surface gravity (`refreshWD`: log g ≥ 6.0 → WD cube, else main cube, so TPAGB-giant rows
  show their real spectrum). Two honest edges: **DC** Planck continuum below the ~5000 K
  floor (no Balmer painted on a cold cinder), **no-model frame** above the 80 kK ceiling (the
  gap TMAP fills in 6b). **Chunks 1–5 + 6a built; WR spectra (Chunk 7) and TMAP hot-WD/CSPN
  (Chunk 6b) are later chunks.** [[star-sim-wr-wd-endgame-plan]]; plan
  `docs/plans/smoldering-cinder-gateway.md`, WD-spectra recipe
  `backend/docs/msg_spectra_build_recipe.md §8`.

### SED (broadband panel — **sibling**, Teff-driven, frontend-only)
- `sed.js` plots the Planck blackbody γ→radio (~14 decades), Wien peak, optical
  bracket. Non-thermal overlay: a cool-star coronal X-ray band + Güdel–Benz radio
  (Chunk 1) that **collapses to a rotation→X-ray line** when rotation is supplied
  (age-gyrochronology or a user slider; Chunk 3). **Chunks 1 & 3 built; Chunk 2
  (wind free–free radio, the spine touch) remains.** [[star-sim-nonthermal-sed-plan]];
  plan `docs/plans/magnetic-ember-broadcast.md`.

### Frontend & UX
- Other panels/features: Lane–Emden interior (§8), true-size scale bar, MK
  classification, instability-strip HR overlay, tooltip singleton, age-slider
  landmark ticks, responsive draggable dashboard. **No JS test harness → the
  Playwright screenshot pass IS the regression check** (use Playwright's bundled
  Chromium — `chrome --headless` hijacks the user's running Chrome).
  [[star-sim-frontend-ux]], [[star-sim-draggable-responsive-panels]],
  [[star-sim-true-size-scale-bar]], [[star-sim-instability-strip-overlay]],
  [[star-sim-tooltip-singleton]], [[star-sim-ux-four-fixes]],
  [[star-sim-ux-age-tick-fixes]], [[star-sim-phase2-shaders]],
  [[star-sim-phase3-lane-emden]].

### Tests
- **153 pytest** (gated by data present via `conftest.py` markers; MIST tests skip
  if grids absent). The §10 anchors are the regression gate (Sun: L≈1.07,
  Teff≈5834 K at 4.6 Gyr).

### Next
- **`docs/plans/ROADMAP.md`** is the canonical cross-plan index of everything
  proposed-but-unbuilt (SED Chunk 2, WR/WD endgame Chunks 4–7, the
  rotation/subpopulation atlas, spectra-density stragglers). Update it (not a second
  list) when scope changes. [[star-sim-rotation-subpop-atlas]].

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
