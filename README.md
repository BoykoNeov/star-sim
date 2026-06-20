# Star Simulator

An interactive stellar simulator built for **teaching and beauty**: pick a
star's mass and metallicity and watch it live — an HR diagram tracks where it
is, a composition panel shows its changing interior, and a real-time 3D
rendering shows a plausible stellar surface and corona.

Guiding value: **real data and real science, with approximation only where
necessary.** See [`STAR_SIM_SPEC.md`](./STAR_SIM_SPEC.md) for the full design;
[`CLAUDE.md`](./CLAUDE.md) for the short operational notes.

> **Status: Phase 0 complete — real MIST tracks.** `MISTProvider` is the live
> provider: it serves real MESA/MIST v2.5 stellar evolution tracks (one [Fe/H],
> solar), interpolating across mass **at fixed evolutionary point** (EEP, not
> age — spec §6). Drag the mass slider *or* scrub age and the star evolves:
> ZAMS Sun → subgiant → 146 R☉ red giant. `StubProvider` remains as a data-free
> fallback. The MIST grids are fetched at build time (see *Run it*). Next: a
> second [Fe/H] axis + the composition panel (Phase 1) — see `CLAUDE.md`.

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
python -m star_sim.fetch_mist     # one-time: discover + fetch MIST grids (~180 MB) into data/
uvicorn star_sim.api:app --reload
```

Then open **http://127.0.0.1:8000**. FastAPI serves both the JSON API and the
frontend. Drag the **mass** slider — color and size should transform
dramatically (cool red dwarf → hot blue giant) — and scrub **age** to walk the
star along its evolutionary track.

The `fetch_mist` step *discovers* the current MIST download location rather than
hard-coding it (spec §6 — the host and version have already drifted). Without
the grids, `/state` answers `503` pointing back at that command and `/health`
still reports liveness; swap `PROVIDER` to `StubProvider()` in `api.py` for a
fully data-free run.

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
    state.py           # StellarState dataclass (the §3 spine)
    provider.py        # StellarStateProvider Protocol + ProviderDataMissing (the boundary)
    providers/
      mist.py          # live provider: real MIST v2.5 tracks, EEP-fixed mass interpolation
      stub.py          # data-free fallback: physically-flavored, no external data
      _vendor/         # MIST's own read_mist_models.py parser (vendored, §6)
    fetch_mist.py      # build-time grid fetch (discovers the download URL, §6)
    api.py             # FastAPI; PROVIDER is the single swap point
  tests/               # §10 sanity checks (MIST tests skip when grids absent)
frontend/
  index.html
  src/{main,star,hr,color}.js   # Three.js star, canvas HR diagram, Teff→color
data/                  # downloaded grids (gitignored; fetched at build time)
```
