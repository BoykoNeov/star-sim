# data/

Downloaded stellar grids live here. **Nothing in this directory is committed**
(see `.gitignore`); grids are fetched at build time.

Currently empty — the running app uses `StubProvider`, which needs no data.

When `MISTProvider` lands (the first real Phase 0 step), MIST `.track.eep`
files go here. Per `STAR_SIM_SPEC.md` §6, fetch the **current** MIST download
location at build time rather than trusting a hard-coded URL, and parse the
files with MIST's own `read_mist_models.py` instead of reinventing the format.
