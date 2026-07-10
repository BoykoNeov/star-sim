---
name: star-sim-isochrone-cluster
description: Isochrone/cluster HR overlay (Axis B of the outward quartet) — isochrone.py + /isochrone sibling over the published MIST v2.5 .iso grid, baked to per-[Fe/H] npz; turnoff-dating overlay. BUILT 2026-07-10.
metadata:
  type: project
---

**Axis B of the outward quartet (`docs/plans/outward-quartet-atlas.md`) — BUILT end-to-end
2026-07-10 (B1 backend + B2 frontend). 412 pytest, Playwright 1440+390 zero console errors.**
The transpose of a track: all masses at ONE age, a coeval-cluster locus on the HR panel,
the **main-sequence turnoff ringed** (the age clock — how clusters are dated), the user's
star sitting on it. Distinct from the BPASS coeval-ensemble overlay
([[star-sim-coeval-ensemble-bpass]]): that is integrated light + number density; this is the
individual-star locus you fit to a real cluster's photometry.

## Architecture (the sibling idiom, like [[star-sim-interior-structure-mesa]] / bpass)
- `isochrone.py` bypasses `PROVIDER`, imports only `state.StellarState` + numpy/stdlib
  (AST-tested: no `api`, no `provider`; DOES import `state` — a §3-clean locus, unlike bpass
  whose payload is a population). Reads the **published MIST v2.5 `.iso` grid** → returns
  `list[StellarState]` + `turnoff` + snapped-far flags. `/isochrone` (snap-always, 503 unbaked,
  422 on age≤0) + `/isochrone_status` (has_grid honesty gate — mirrors `/population_status`).
- **Data source = MIST's PUBLISHED `.iso`, NOT a from-tracks reconstruction.** The plan's
  from-tracks EEP cross-check was **dropped (advisor)** — reconstructing the isochrone from the
  tracks by inverting age-at-fixed-EEP IS the interpolation-of-interpolation / EEP hazard the
  `lies-between-neighbors` test exists to guard against; reading the published grid keeps it
  cleanly Tier-1. **Version-consistent with the live tracks (both v2.5)** so the marker lands
  EXACTLY on the MS locus — the Sun-anchor test (4.6 Gyr solar iso contains a 1 M☉ star at
  L≈1/Teff≈5772) is the version-consistency check that justified the v2.5 download over v1.2.

## The size surprise → a bake (measure-first pivot from "read raw")
Each `.iso` is **~550 MB of 170-column text**, and the v2.5 iso grid ships as **ONE ~6.7 GB
tarball per vvcrit holding ALL metallicities+[a/Fe]** (no per-[Fe/H] download — verified on
mist.science; v1.2 has a 207 MB basic option but is a DIFFERENT model version). So the advisor's
"probably no parse cache, read raw" was overturned by the measurement: `fetch_mist_iso.py`
**streams the tarball once** (`r|xz`, member-by-member, never a whole-archive list) and **bakes**
each solar-scaled (`afe_p0`) node in the track [Fe/H] domain [−1.05,+0.55] to a compact
**per-(feh,vvcrit) `.npz`** (~2.6 MB, only ~11 columns: eep/mass/logT/logL/logg/logR/phase/
h1/he4/ch1/che4, CSR-flattened across all ~107 ages). `BAKE_VERSION` discipline (the tracks'
`_parsed_tracks.npz` precedent). Result: **7 nodes −1.0…+0.5** (~18 MB total) — DENSER than the
tracks' 5 nodes (the iso grid has ±0.25 steps). Streaming parse ≈5 s/550 MB file. Data gitignored
under `data/mist_isochrones/` (`requires_isochrone_data`). The 6.7 GB download is fetched to
`M:\claud_projects\temp` and pruned after baking (per the global temp rule).

## Turnoff = bluest MS-phase row, NOT global max Teff (the load-bearing advisor catch)
Old/metal-poor isochrones carry **hot post-AGB + WD stars far bluer than the MSTO** — measured
**global max Teff 116k–354k K vs the true MSTO ~6000–17000 K** (a naive `max(Teff)` off by 20–50×).
`_turnoff()` filters to `phase == "MS"` (FSPS code 0) then takes the hottest. The test
`test_turnoff_is_ms_only_not_global_hottest` asserts both (turnoff == hottest MS row AND a hotter
non-MS star exists so the test has teeth). **Gate 0 (measured through the real path):** turnoff
drops monotonically cooler+fainter+lighter 0.1→1→4→12 Gyr (16685K/1350L/4.7M → 6053K/1.9L/0.89M).

## B2 frontend (a LIGHT HR overlay that OWNS the panel, like He/α — mutually exclusive with them)
`#isochrone-toggle` (gated on `/isochrone_status has_grid`, living-only, NOT mass-gated — reads
only the marker's age+[Fe/H]). `hr.js setIsochroneOverlay(states, turnoff, current)` /
`drawIsochrone`: auto-fits to the locus, draws the Teff-coloured trail (reuses `drawBinaryTrail`),
rings the turnoff (gold + "turnoff" label), drops the user's marker ON the locus (`drawMarker`).
The **cluster ages with the age slider** (paintState → `refreshIsochrone(s)`, node-bucketed so a
same-node scrub repaints the moved marker without a refetch — the marker is drawn INSIDE the
overlay, so unlike the BPASS cloud a skipped repaint would freeze it). Suppresses the normal
`hr.update`/`hr.setTrack` while on (extended the `!heliumOn && !alphaOn` gate to `&& !isoOn`);
`dropIsochroneForModeSwitch` in the mode-switch hook. Playwright-verified: the aging-cluster movie
works (turnoff 6239K/1.21M☉ at 4.5 Gyr → 5710K/0.95M☉ at 11 Gyr), 0 console errors 1440+390.

## Follow-ups (unbuilt)
- **B3** (plan-optional): a decoupled cluster-age slider (age the cluster independent of the star).
- **Hosting**: the ~18 MB baked npz set as a GitHub Release (the `fetch_*_baked.py` /
  [[star-sim-hosted-data-assets]] pattern) — the 6.7 GB fetch is painful on a fresh clone. Would
  need a Release upload (outward-facing → confirm with the user first). MIST is public-domain-ish
  (its own license); check before hosting.
- The **full locus includes the post-AGB→WD sequence** (the blue sweep across the top + the faint
  hot WD tail) — honest (it's the real published isochrone), Teff-coloured + thin/context; clip at
  the AGB if it ever reads as too busy (not done — the turnoff is clearly the focus).

Files: `backend/star_sim/isochrone.py`, `fetch_mist_iso.py`, `tests/test_isochrone.py`,
`/isochrone`+`/isochrone_status` in `api.py`; `frontend/src/hr.js`, `main.js`, `index.html`
(`#isochrone-control`). Plan `docs/plans/outward-quartet-atlas.md` §Axis B.
