# Star Simulator — working notes for Claude

Interactive stellar simulator: pick a star's mass & metallicity, watch it evolve
(HR diagram + composition panel + real-time 3D star). Teaching **and** beauty.

**The full spec is `STAR_SIM_SPEC.md` — read it first.** This file is the short
operational layer on top of it; it does not repeat the spec.

## Where the detail lives (read this before adding to this file)

This file is a **map, not a changelog**. It is loaded into *every* session, so it
stays small on purpose. Per-feature history, gotchas, measured values and the
"why X not Y" rationale live in:

- **`docs/memory/`** — one topic file per subject, recalled **on demand**. This is
  the sink for detail. The wiki-style links below point at them.
- **`docs/plans/`** — designs. **`docs/plans/ROADMAP.md`** is the canonical index of
  everything proposed-but-unbuilt; update it (not a second list) when scope changes.
- **git** — dates, "chunk N built", test counts, per-PR narration.

When you finish work: put the durable knowledge in the topic file, and only touch
this file if the **architecture** changed (a new sibling, a new route, a new rule).
Resist re-growing the status section into a build log.

## The one rule that overrides everything (spec §3)

Everything the user sees is a function of a single `StellarState`, produced **only**
through the `StellarStateProvider` interface. **No consumer may know where the state
came from.**

- `state.py` / `provider.py` define the boundary. `StellarState` is a plain
  dataclass — keep web/data-source concepts out of it.
- The HR diagram, 3D star, and composition panel consume `StellarState` only. A
  consumer (or the API) that imports a provider's internals — MIST columns, file
  formats, interpolation guts — **is a bug**, not a shortcut.
- Provider swaps happen in exactly one place: `PROVIDER` in `api.py`. Going deeper
  (Stub → MIST → live solver) must change nothing downstream.

## The gotcha that bites everyone (spec §6): interpolate on EEP, not age

Two stars of different mass at the *same age* are in different evolutionary phases.
Interpolating raw tracks against age blends a main-sequence star with a red giant →
physical nonsense. **Always interpolate at fixed EEP** (equivalent evolutionary
point), then map age ↔ EEP. The test for it: an interpolated intermediate-mass track
must lie *between* its neighbors on the HR diagram at every phase.

## Recurring patterns (the rules every feature re-learns)

- **Provider vs. sibling.** A `StellarState` on the evolutionary track comes through
  `PROVIDER`. Everything that *isn't* one state of one single star is a **sibling**:
  its own module, its own route that **bypasses `PROVIDER`**, importing at most
  `state.StellarState` and never a provider. Siblings: interiors, spectra, supernova,
  binaries, populations, isochrones, photometry, what-if overlays. Several are tested
  at the **AST level** for exactly this. A view that isn't a star (a magnitude, a
  population) imports not even `StellarState`.
- **Snap, don't interpolate** (§6 again). Off-spine grids (MESA, POSYDON, spectra
  cubes, profiles) **snap to the nearest node** and say so in-band — a `*_snapped_far`
  flag or a visible caption. Never blend across a grid whose axes aren't EEP-aligned.
- **Measure first, then draw.** Before wiring a payoff to a canvas, verify it through
  the **real served runtime**. This project's recurring bug class is *plausible but
  wrong* — a coefficient, an axis, a caption that no test catches. Gate 0 for a
  feature is a measurement, not a screenshot.
- **Never paint a false caption.** The most-repeated defect here: a label that
  overstates the data (a "binary-only" flood of ~1e-10-star cells, a "helium-rich"
  tag on a carbon surface, an evocative color read as a Teff). If the picture can't
  support the sentence, weaken the sentence or gate the feature off.
- **Honesty gates.** Out-of-range → blank the feature and say why; data absent → a
  `*_status` route so the control hides on a fresh clone; regime-inapplicable → grey
  it with an "appears for…" note rather than deleting it (see the three-hide-reasons
  rule in [[star-sim-frontend-ux]]).
- **Mode switches go through the shared chokepoint.** Living-only panels tear down in
  one place (`drop*ForModeSwitch`) — a WD's log g ~8 or an SN's log g ≈ −5 will
  otherwise slip a naive gate and paint garbage.
- **Evocative vs. modeled.** Corona, wind filaments, fireball boil, Ap/Bp spots and
  the NS dot are *evocative* (spec §7) — label them so. Teff colors, radii and
  tracks are modeled. Never let the two blur in a caption.
- **No JS test harness → the Playwright screenshot pass IS the regression check.**
  Use Playwright's bundled Chromium (`chrome --headless` hijacks the user's running
  Chrome). Check 1440 + 390 px, zero console errors.

## Where things are

**`backend/star_sim/`**
- `state.py`, `provider.py` — the §3 boundary.
- `providers/` — `mist.py` (the live provider), `mesa.py` (second real provider,
  offline `history.data`, used to **validate MIST**), `stub.py` (data-free fallback),
  `_vendor/read_mist_models.py` (MIST's own parser).
- `api.py` — FastAPI; `PROVIDER` is the swap point. Also hosts every sibling route.
- Siblings (each bypasses `PROVIDER`): `lane_emden.py` · `structure.py` · `spectra.py` ·
  `supernova.py` · `binary.py` · `posydon.py` · `posydon_co.py` · `helium.py` ·
  `alpha.py` · `bpass.py` · `isochrone.py` · `photometry.py`.
- `fetch_*.py` — build-time grid fetches; `scripts/bake_*.py` — host-side bakes.

**`backend/tests/`** — §10 sanity checks. Skip markers in `conftest.py` gate by data
present (`requires_mist_data`, `requires_mesa_data`, `requires_spectra_data`,
`requires_structure_data`, `requires_posydon_*`, …), so a fresh clone skips rather
than fails. The Sun anchor is the regression gate.

**`frontend/`** — static SPA, no bundler. `index.html`, `styles.css`, and
`src/{main,star,hr,comp,lane,structure,roche,spectrum,sed,scale,classify,color,canvas,layout,tooltip,sn,hz,hzhist,reddening,cmd,seismo}.js`.
`main.js` owns state and pushes it to panels; most panels are **pushed-data
consumers** (`update()`/`set*()`), not fetchers. `color.js` is the reference
Planck→CIE→sRGB pipeline; `canvas.js` the shared HiDPI `fitCanvas`; `tooltip.js` the
singleton hover layer. Three.js via CDN importmap, served by FastAPI.

**`data/`** — downloaded/baked grids (gitignored). Most are pre-baked as GitHub
Release assets — see [[star-sim-hosted-data-assets]] for the fetch tags.

## Commands

```bash
# backend (from backend/)
python -m venv .venv && . .venv/Scripts/activate   # Windows; or .venv/bin/activate
pip install -e ".[dev]"
python -m star_sim.fetch_mist                      # one-time: MIST grids (~180 MB) into data/
uvicorn star_sim.api:app --reload                  # serves API + frontend at :8000
pytest                                             # sanity tests (skip if grids absent)
```

Open http://127.0.0.1:8000 — drag the mass slider; the whole UI transforms.

## Current state

Phases 1–5 are built and the app is feature-complete for the current scope. What
follows is a one-line-per-subject map; **the topic file holds the detail.**

### The spine (§3)
- **`MISTProvider` is the live `PROVIDER`** — MIST v2.5, EEP-fixed **2D (mass ×
  [Fe/H])** interpolation, 0.1–300 M☉, window ZAMS → end of early-AGB, non-rectangular
  valid domain, `.npz` parse cache (`CACHE_VERSION`). A third axis — **rotation
  `vvcrit`** — is wired end-to-end and **snaps** between MIST's two buckets {0.0, 0.4}
  while interpolating mass×[Fe/H] within one. [[star-sim-mist-provider]],
  [[star-sim-rotation-subpop-atlas]]
- **`MESAProvider`** — second real provider, discrete snap-to-nearest, **opt-in**; its
  payoff is measured MESA-vs-MIST cross-validation. [[star-sim-phase4-mesa]]
- **`StubProvider`** — data-free fallback, physically *flavored*, not modeled.
- **Composition** rides the spine as `metals_surf`/`metals_core` **dicts** (sixteen
  elements; `state.py` never grew a field per element). [[star-sim-phase4-cno]],
  [[star-sim-composition-panel]]

### Fates (endgame)
- **WR / WD** — `/endgame` goes **through** `PROVIDER` (an endgame state *is* a
  `StellarState`, already on the tracks); reversible gateway → cooling scrub, wind
  shader, Koester/TMAP + PoWR spectra. Arc complete. [[star-sim-wr-wd-endgame-plan]]
- **Supernova** — a **hybrid**: classification + progenitor scalars on the spine,
  the light curve computed in the pure sibling `supernova.py`. Fireball → NS/BH/
  failed-SN remnant, pre-collapse onion. Arc complete. [[star-sim-supernova-remnant-endgame]]

### Siblings
- **Interiors** — `structure.py` reads real MESA radial profiles (the honest
  Lane–Emden successor); `lane_emden.py` remains the §8 polytrope panel. Partial 2D
  (mass × [Fe/H]) grid. [[star-sim-interior-structure-mesa]], [[star-sim-phase3-lane-emden]]
- **Spectra** — `spectra.py` over a baked flux cube, plus three more cubes behind
  their own routes (WD, WR, stripped-star). [[star-sim-phase5-spectra]]
- **Binaries** — `binary.py` (Götberg stripped star + Roche geometry), `posydon.py`
  (two-star co-evolution movie), `posydon_co.py` (compact-object tail + DCO
  classifier). [[star-sim-binary-stripped]], [[star-sim-co-hms-rlo]]
- **The outward quartet** (all built) — **A** observer's view / CMD
  ([[star-sim-observer-cmd]]) · **B** cluster isochrone ([[star-sim-isochrone-cluster]]) ·
  **C** asteroseismology ([[star-sim-asteroseismology]]) · **D** habitable zone
  ([[star-sim-habitable-zone]]).
- **Ensembles** — `bpass.py`, the coeval-population overlay (SED wedge + HRD
  number density). [[star-sim-coeval-ensemble-bpass]]

### What-if overlays (never compared against the live MIST spine)
- **Helium (Y)** and **α-enhanced (Z-equivalent)** — self-run MESA, always
  MESA-vs-MESA (a MESA-vs-MIST overlay would conflate the effect with the known
  provider systematic). They share one HR slot, mutually exclusive.
  [[star-sim-helium-overlay]], [[star-sim-alpha-overlay]]
- **Ap/Bp spots**, **gravity darkening / oblateness** — frontend-only, evocative.
  [[star-sim-apbp-peculiarity]], [[star-sim-gravity-darkening]]

### Frontend & UX
- Panels/features: SED ([[star-sim-nonthermal-sed-plan]]), true-size scale bar
  ([[star-sim-true-size-scale-bar]]), instability strip
  ([[star-sim-instability-strip-overlay]]), tooltip singleton
  ([[star-sim-tooltip-singleton]]), draggable dashboard
  ([[star-sim-draggable-responsive-panels]]), shaders ([[star-sim-phase2-shaders]]).
- Layout discipline (reserved heights, anti-jump passes) and the accumulated
  user-reported fix batches: [[star-sim-frontend-ux]], [[star-sim-ux-four-fixes]],
  [[star-sim-ux-nine-fixes]], [[star-sim-ux-age-tick-fixes]].

## Conventions

- Keep the stub honest: physically *flavored*, not a model. Label approximations in
  comments (spec §7).
- Don't let scope creep in: no live structure solve, no nuclear network, no
  deploy/bundle concerns (spec §2). This runs locally.
- **Claude's auto-memory is tracked in the repo** at `docs/memory/` (`MEMORY.md`
  index + one file per fact). The harness reads/writes memory from
  `~/.claude/projects/M--claud-projects-star-sim/memory`, which is a **directory
  junction** pointing at `docs/memory/` — so every memory write lands in the repo.
  Consequence: after writing or editing memory, **`git add docs/memory` and commit**
  like any other change. If the junction is ever missing (fresh clone, or replaced by
  a real dir), re-create it: `New-Item -ItemType Junction -Path "<that .claude path>"
  -Target "<repo>\docs\memory"` (Windows, no admin needed) — the repo copy is the
  source of truth.
- `MEMORY.md` entries are **one line each**: `- [Title](file.md) — hook`. The detail
  belongs in the topic file, not the index.
