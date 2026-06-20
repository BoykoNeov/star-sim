# Star Simulator

An interactive stellar simulator built for **teaching and beauty**: pick a
star's mass and metallicity and watch it live — an HR diagram tracks where it
is, a composition panel shows its changing interior, and a real-time 3D
rendering shows a plausible stellar surface and corona.

Guiding value: **real data and real science, with approximation only where
necessary.** See [`STAR_SIM_SPEC.md`](./STAR_SIM_SPEC.md) for the full design;
[`CLAUDE.md`](./CLAUDE.md) for the short operational notes.

> **Status: Phase 0 — the spine.** The architecture runs end to end on a
> `StubProvider` (no external data). Mass/[Fe/H]/age controls drive one
> `StellarState`; the star colors & resizes and a point moves on the HR diagram.
> The next step is `MISTProvider` (real MESA/MIST tracks) behind the same
> interface — see `CLAUDE.md`.

## Architecture in one sentence

Everything the user sees is a function of a single `StellarState`, produced only
through a `StellarStateProvider`. Swapping the data source (Stub → MIST → live
solver) changes nothing downstream. This boundary is non-negotiable (spec §3).

```
controls ──▶ FastAPI /state ──▶ Provider.state_at() ──▶ StellarState ──▶ HR diagram
                                                                      ├─▶ 3D star
                                                                      └─▶ composition
```

## Run it

Requires Python 3.11+ and a browser. From the repo root:

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows;  on macOS/Linux: . .venv/bin/activate
pip install -e ".[dev]"
uvicorn star_sim.api:app --reload
```

Then open **http://127.0.0.1:8000**. FastAPI serves both the JSON API and the
frontend. Drag the **mass** slider — color and size should transform
dramatically (cool red dwarf → hot blue giant).

## Test

```bash
cd backend
pytest
```

The tests encode the spec's §10 sanity checks (the Sun renders at 1 M☉; the
ZAMS luminosity spread covers ~9 orders of magnitude). Keep them when you swap
in a real provider — they become the regression test for that swap.

## Layout

```
backend/
  star_sim/
    state.py          # StellarState dataclass (the §3 spine)
    provider.py       # StellarStateProvider Protocol (the boundary)
    providers/stub.py # v1 provider: physically-flavored, no external data
    api.py            # FastAPI; PROVIDER is the single swap point
  tests/              # §10 sanity checks
frontend/
  index.html
  src/{main,star,hr,color}.js   # Three.js star, canvas HR diagram, Teff→color
data/                 # downloaded grids (gitignored; empty for now)
```
