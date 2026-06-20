# data/

Downloaded stellar grids live here. **Nothing in this directory is committed**
(see `.gitignore`); grids are fetched at build time.

Fetch the MIST grids once after checkout:

```bash
python -m star_sim.fetch_mist            # solar [Fe/H]=0, non-rotating (default)
```

That script *discovers* the current MIST download location (spec §6 — the host
and version are not hard-coded; MIST has already moved
`waps.cfa.harvard.edu`→`mist.science` and `v1.2`→`v2.5`), downloads the EEP
tarball (~180 MB), and extracts the `.track.eep` files into a
`feh_p000_afe_p0_vvcrit0.0/eeps/` subdirectory here. `MISTProvider` parses them
with MIST's own `read_mist_models.py` (vendored under
`backend/star_sim/providers/_vendor/`).

Without these grids the API answers `/state` etc. with a 503 pointing back at
the fetch command; `/health` still reports liveness (`data_ready: false`). Swap
`PROVIDER` to `StubProvider()` in `api.py` for a fully data-free run.
