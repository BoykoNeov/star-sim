# data/

Downloaded stellar grids live here. **Nothing in this directory is committed**
(see `.gitignore`); grids are fetched at build time.

Fetch the MIST grids once after checkout:

```bash
python -m star_sim.fetch_mist                       # solar [Fe/H]=0, non-rotating (default)
python -m star_sim.fetch_mist --feh m050,p000,p050  # the [Fe/H] axis (3 grids, ~540 MB)
```

That script *discovers* the current MIST download location (spec §6 — the host
and version are not hard-coded; MIST has already moved
`waps.cfa.harvard.edu`→`mist.science` and `v1.2`→`v2.5`), downloads each EEP
tarball (~180 MB), and extracts the `.track.eep` files into per-metallicity
`feh_<code>_afe_p0_vvcrit0.0/eeps/` subdirectories here. `MISTProvider`
discovers *every* grid present and interpolates across [Fe/H]; with a single grid
the metallicity slider is pinned to that one point. Tracks are parsed with MIST's
own `read_mist_models.py` (vendored under `backend/star_sim/providers/_vendor/`).

Note the valid domain isn't rectangular: super-solar low-mass M-dwarfs have no
evolved tracks (they outlive the grid), so `mass_range(feh)` tightens the mass
floor above ~0.5 M☉ for `[Fe/H] > 0`. The UI clamps to it (`/mass_range`).

Without these grids the API answers `/state` etc. with a 503 pointing back at
the fetch command; `/health` still reports liveness (`data_ready: false`). Swap
`PROVIDER` to `StubProvider()` in `api.py` for a fully data-free run.
