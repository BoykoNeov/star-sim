# Star Simulator

An interactive stellar simulator built for **teaching and beauty**: pick a
star's mass and metallicity and watch it live — an HR diagram tracks where it
is, a composition panel shows its changing interior, and a real-time 3D
rendering shows a plausible stellar surface and corona.

Guiding value: **real data and real science, with approximation only where
necessary.** See [`STAR_SIM_SPEC.md`](./STAR_SIM_SPEC.md) for the full design;
[`CLAUDE.md`](./CLAUDE.md) for the short operational notes.

> **Status: Phase 2 — physically-driven 3D star (shader beauty).**
> The data layer is the live `MISTProvider`: real MESA/MIST v2.5 tracks over a 2D
> **(mass × [Fe/H])** grid (currently [Fe/H] −0.5…+0.5), interpolated **at fixed
> evolutionary point** (EEP, not age — spec §6). Drag mass or [Fe/H], or scrub
> age, and the star evolves: ZAMS Sun → subgiant → ~154 R☉ red giant. On top of
> that, the 3D star is now a fragment shader where every visual is a real number
> from the state (spec §7): true blackbody **color** (Planck → CIE → sRGB),
> **granulation** whose cell size comes from the pressure scale height (fine for a
> dwarf, a handful of huge cells for a giant), **limb darkening**, a gently
> rotating surface, and an additive **corona** that scales with the activity proxy
> (near-glowless for hot stars — evocative, not predictive). The composition panel
> shows core & surface H/He/metals vs EEP; the HR diagram draws the full track
> with a marker at the current age. `StubProvider` remains a data-free fallback;
> the MIST grids are fetched at build time (see *Run it*). Next: Phase 3 — the
> Lane-Emden interior-structure panel (spec §8) — see `CLAUDE.md`.

## Architecture in one sentence

Everything the user sees is a function of a single `StellarState`, produced only
through a `StellarStateProvider`. Swapping the data source (Stub → MIST → live
solver) changes nothing downstream. This boundary is non-negotiable (spec §3).

```
controls ─▶ FastAPI /state ─▶ Provider.state_at() ─▶ StellarState ──┐
         └▶ FastAPI /track ─▶ Provider.track()    ─▶ [StellarState] ─┤
                                                                     ├─▶ HR diagram (track + marker)
                                                                     ├─▶ 3D star
                                                                     └─▶ composition panel
```

Both endpoints emit the *same* `StellarState` shape; `/track` is just the whole
evolutionary curve (age-independent), so the HR diagram and composition panel
fetch it once per (mass, [Fe/H]) and move their marker as age scrubs.

## Run it

Requires Python 3.11+ and a browser.

### One click (easiest)

- **Windows:** double-click **`start.bat`**.
- **macOS / Linux:** run **`./start.sh`** from the repo root.

That's it. The first run creates the Python environment, installs the
dependencies, and downloads the MIST stellar grids (~180 MB) — so it takes a
couple of minutes and needs internet. Every run after that starts in a second or
two. Your browser opens to the app automatically; **close the launcher window
(or press Ctrl+C) to stop the server.** Double-clicking again while it's already
running just reopens the browser tab.

### Manual (if you prefer the terminal)

From the repo root:

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate          # Windows;  on macOS/Linux: . .venv/bin/activate
pip install -e ".[dev]"
python -m star_sim.fetch_mist     # one-time: discover + fetch MIST grids (~180 MB) into data/
uvicorn star_sim.api:app --reload
```

Either way, open **http://127.0.0.1:8000**. FastAPI serves both the JSON API and
the frontend. Drag the **mass** slider — color and size should transform
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
start.bat              # one-click launcher (Windows)
start.sh               # one-click launcher (macOS / Linux)
backend/
  star_sim/
    state.py           # StellarState dataclass (the §3 spine)
    provider.py        # StellarStateProvider Protocol + ProviderDataMissing (the boundary)
    providers/
      mist.py          # live provider: real MIST v2.5 tracks, EEP-fixed 2D (mass × [Fe/H]) interp; state_at + track
      stub.py          # data-free fallback: physically-flavored, no external data
      _vendor/         # MIST's own read_mist_models.py parser (vendored, §6)
    fetch_mist.py      # build-time grid fetch (discovers the download URL, §6)
    api.py             # FastAPI (/state, /track, /ranges, /mass_range, /age_range); PROVIDER is the single swap point
  tests/               # §10 sanity checks (MIST tests skip when grids absent)
frontend/
  index.html
  src/{main,star,hr,comp,color,canvas}.js  # star.js = §7 shader (color×granulation×limb×rotation + corona); color.js = Planck→CIE→sRGB; HR diagram, composition panel, HiDPI canvas helper
data/                  # downloaded grids (gitignored; fetched at build time)
```
