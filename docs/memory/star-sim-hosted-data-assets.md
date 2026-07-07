---
name: star-sim-hosted-data-assets
description: Pre-baked data hosted via GitHub Releases (POSYDON, MIST, Koester+TMAP, PoWR, Coelho, Gotberg) so casual users skip raw multi-GB source fetches; the license-audit restriction was explicitly overridden by the user.
metadata:
  type: project
  originSessionId: 614a40b0-c4a6-4698-a4c9-e486917bf270
---

Star Simulator hosts **pre-baked derived data artifacts as GitHub Release
assets** on repo `BoykoNeov/star-sim`, one release tag per dataset, so a user can
run a `python -m star_sim.fetch_<dataset>_baked` command (plain HTTPS + sha256
verify) instead of running each feature's raw-source recipe (a multi-GB
tarball/API-scrape fetch, then a host-side bake step). Six tags exist:
`posydon-baked-v1`, `mist-baked-v1`, `koester-baked-v1`, `powr-baked-v1`,
`coelho-baked-v1`, `gotberg-baked-v1`. Plans: `docs/plans/lantern-grid-waystation.md`
(POSYDON, the original).

**Why GitHub Releases, not the repo tree:** committed repo files cap at 100 MB
and bloat clone size forever; release assets cap at 2 GB, live outside git
history, and need no API auth to download publicly.

**Scope history — the license audit, then the user's explicit override.** The
original build (POSYDON only) was scoped by a per-dataset license audit of every
`fetch_*.py`'s redistribution terms:
- **POSYDON** (Zenodo DR2): explicit **CC-BY** → the only one with a clean grant.
- **MIST, Koester, TMAP, PoWR, Coelho, Gotberg**: all "cite on use" (academic
  norm) but **no explicit redistribution grant found** in any fetch script.
- **MESA** (bearums repo): explicitly all-rights-reserved.

That audit is still accurate — nothing changed about the underlying terms. What
changed: the user explicitly asked ("add also MIST/Koester/TMAP/PoWR/Coelho/
Gotberg baked data with attribution — my call") to host the remaining five
anyway, taking the redistribution-license judgment call themselves, with
attribution required in every fetch script's docstring + release notes (each
cites the source paper(s) — see the modules for exact citations). **MESA stays
excluded** (explicitly all-rights-reserved, categorically different from "no
grant found") — it was not part of the override request.

**The MIST case needed a real code change, not just an upload — the size story.**
MIST's raw `.track.eep` files are ~1.2 GB per [Fe/H]×rotation bucket (~12 GB for
the full 5×2 axis) because they carry MIST's full ~80-column text format; the app
only reads a windowed ~40. `providers/mist.py` already caches a parsed,
column-trimmed `_parsed_tracks.npz` per bucket (43-47 MB, ~27x smaller, **every
row preserved** — confirmed empirically before trusting this: `_write_cache`
concatenates full unsliced arrays, so TPAGB/WD/WR/SN endgame rows survive, not
just the living-state window). But that cache is normally *validated against its
raw source* (`_grid_fingerprint` hashes every `.track.eep` file's name/size/mtime),
so shipping the small cache alone wouldn't load on a fresh checkout with no raw
files.

The fix (small, narrow, in `providers/mist.py`): `_grid_fingerprint` already
degrades gracefully to a stable, content-free hash (`sha256(f"v{CACHE_VERSION}")`)
when a directory has zero `.track.eep` files — nothing to fold in. So a cache
baked with *that* fingerprint validates on any machine with no raw source
running the same code version. The only code change needed was discovery:
`_find_eep_dirs` now also recognizes a directory holding just `_parsed_tracks.npz`
(no raw files) as a valid grid. The raw-files path is untouched (its fingerprint
still includes real per-file stats). Gated by a new regression test
(`test_cache_only_grid_directory_loads_and_matches_raw` in `test_mist_provider.py`)
that round-trips `state_at` + `endgame()` (WD/SN/WR masses) from a cache-only
directory against the normal provider — bit-identical. Full 311-test suite green.

`backend/scripts/bake_mist_standalone.py` produces the source-less-fingerprinted
`.npz` per bucket (reuses `providers/mist.py`'s real parse/cache functions, so the
bake can never drift from the runtime's own logic). Result: MIST hosting is ~450
MB for the **entire** [Fe/H]×rotation axis (10 buckets), not a scoped-down subset —
the "solar-only vs full axis" tradeoff dissolved once the size was fixed.

**The four spectra siblings (Koester+TMAP combined into one WD cube, PoWR, Coelho,
Gotberg) needed no code change at all.** `spectra.py` already loads each baked
`.npz` cube directly with no raw-source fingerprint dependency (unlike MIST) —
and each bake script (`bake_wd_spectra.py`/`bake_wr_spectra.py`/
`bake_alpha_spectra.py`/`bake_stripped_spectra.py`) already resamples/trims to
just what the app reads, so the existing `data/spectra/*.npz` files (9.7-26 MB
each, vs 150 MB-17 GB raw depending on source) were hosted as-is.

**Shared plumbing:** `star_sim/_baked_release.py` factors the download/sha256/
verify mechanics out of what was five near-duplicate scripts (the original
`fetch_posydon_baked.py` was refactored onto it too, behavior-identical — verified
by re-running it, "skip" on the already-present asset). Each `fetch_*_baked.py`
module owns only its release tag, asset list, destination path(s), and citation
text.

**Verified end-to-end**, not just unit-tested: a real `gh release create` publish
of all 5 new tags, then a real fetch (via `STAR_SIM_DATA_DIR`/`STAR_SIM_SPECTRA_DIR`
pointed at a clean scratch directory) of every asset, then a real load through
`MISTProvider` and all four `spectra.py` loader functions (`wd_spectrum_data`/
`wr_spectrum_data`/`alpha_spectrum_data`/`stripped_spectrum_data`) — all succeeded
from nothing but the freshly-downloaded files.

**How to apply — hosting another dataset/bucket in the future:** check the
license situation, but remember the user has already made the call for
"cite on use, no explicit grant" sources in this project (MIST/Koester/TMAP/PoWR/
Coelho/Gotberg already cleared) — MESA remains the one hard exclusion
(all-rights-reserved). If it's a new MIST bucket: `bake_mist_standalone.py`, sha256,
`gh release upload mist-baked-v1 <file>`, add the bucket+hash to
`fetch_mist_baked.py`'s `_ASSETS`. If it's a new/updated spectra cube: bake it with
the existing `scripts/bake_*.py`, sha256, `gh release upload <tag> <file>`, update
the matching `fetch_*_baked.py`. If it's a genuinely new dataset: check whether its
`spectra.py`/provider-style loader has a raw-source fingerprint dependency like
MIST (needs the same source-less-fingerprint trick) or is self-contained like the
spectra cubes (ship as-is).

See [[star-sim-binary-stripped]] for the POSYDON co-evolving-binary feature that
data backs, [[star-sim-mist-provider]] for the provider MIST hosting touches,
[[star-sim-rotation-subpop-atlas]] for the rotation axis MIST's bucket set spans.
