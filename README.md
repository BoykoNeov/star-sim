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
fully data-free run. Prefer a faster download over discovery? Run
`python -m star_sim.fetch_mist_baked` instead — see below.

### Optional: additional datasets

The MIST fetch above is all the core app needs. Several extra panels use their
own datasets, fetched separately (each panel degrades to an honest "no data"
placeholder if you skip it — nothing crashes). Most have a **pre-baked fast
path** — a plain HTTPS download of a small, sha256-verified derived artifact
from this repo's [GitHub Releases](https://github.com/BoykoNeov/star-sim/releases),
instead of the raw multi-GB source grids each feature is built from:

```bash
python -m star_sim.fetch_mist_baked      # the full MIST [Fe/H]×rotation axis (~450 MB) — an alternative to fetch_mist
python -m star_sim.fetch_posydon_baked   # co-evolving binary tracks (/binary_track) — the full 8-metallicity axis
python -m star_sim.fetch_koester_baked   # white-dwarf spectra (/wd_spectrum) — Koester DA + TMAP
python -m star_sim.fetch_powr_baked      # Wolf-Rayet wind-emission spectra (/wr_spectrum)
python -m star_sim.fetch_coelho_baked    # [alpha/Fe] spectrum what-if (#alpha-toggle)
python -m star_sim.fetch_gotberg_baked   # binary-stripped-star spectra (/stripped_spectrum)
```

Each is a **derived artifact** — a compact, resampled/re-serialized cube or cache
built from that source's public data, not a verbatim copy — hosted under this
project's own redistribution call (only POSYDON carries an explicit CC-BY grant;
the others don't have one, see `docs/memory/star-sim-hosted-data-assets.md` and
each module's docstring for the citation to use). MIST's is the one worth
knowing about even if you don't need speed: MIST's raw EEP tracks carry ~80
text columns of which this app reads ~40, so the baked cache is ~27x smaller
than mirroring the raw grid (43-47 MB per [Fe/H]×rotation bucket vs ~1.2 GB) —
see `backend/scripts/bake_mist_standalone.py`'s docstring for how. MESA
validation doesn't have a pre-baked shortcut (it's a self-run Docker recipe, see
`backend/docs/mesa_solar_recipe.md`); the other `fetch_*.py` modules under
`backend/star_sim/` document the from-source recipe if you'd rather not depend
on this repo's releases.

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

## License

Star Simulator is licensed under the **Apache License, Version 2.0** — you are
free to use, modify, and redistribute it, including in derivative and commercial
works. The one obligation is **attribution**: keep the [`NOTICE`](./NOTICE) file
(which credits the original author, Boyko Neov) in any redistribution or
derivative work, per Section 4(d) of the license. See [`LICENSE`](./LICENSE) for
the full text.

One bundled third-party file, `read_mist_models.py` (the MIST track parser), is
MIT-licensed by Jieun Choi — see [`NOTICE`](./NOTICE). The stellar-evolution and
spectral data grids the app downloads at build time are **not** part of this
repository and carry their own upstream licenses.
