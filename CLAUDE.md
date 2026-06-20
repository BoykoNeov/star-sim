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
  `providers/stub.py` (v1 provider), `api.py` (FastAPI, the swap point).
- `backend/tests/` — sanity checks wired from spec §10 (Sun anchor, ZAMS spread).
- `frontend/` — static SPA (no bundler): `index.html`, `src/{main,star,hr,color}.js`.
  Three.js via CDN importmap. Served by FastAPI.
- `data/` — downloaded grids (gitignored, currently empty; stub needs no data).

## Commands

```bash
# backend (from backend/)
python -m venv .venv && . .venv/Scripts/activate   # Windows; or .venv/bin/activate
pip install -e ".[dev]"
uvicorn star_sim.api:app --reload                  # serves API + frontend at :8000
pytest                                             # run sanity tests
```

Open http://127.0.0.1:8000 — drag the mass slider; the whole UI transforms.

## Current status & what's next

- **Done:** the §3 spine, `StubProvider`, FastAPI `/state` `/ranges` `/age_range`
  `/health`, and a runnable end-to-end frontend shell (Teff→color, R→size, point
  on the HR diagram). The stub returns Sun values at 1 M☉ (spec §10).
- **Next (first real Phase 0 step):** `MISTProvider` behind the same interface —
  fetch the **current** MIST download location at build time (do not hard-code a
  URL, spec §6), reuse MIST's `read_mist_models.py`, start with one [Fe/H].
- Then Phase 1 (full EEP 2D interpolation, composition panel), Phase 2 (shader
  beauty: granulation from H_p, limb darkening, corona from `activity`).

## Conventions

- Keep the stub honest: it is physically *flavored*, not a model. Label
  approximations in comments (the corona/activity layer is "evocative, not
  predictive" per spec §7).
- Don't let scope creep in: no live structure solve, no nuclear network, no
  deploy/bundle concerns (spec §2). This runs locally.
