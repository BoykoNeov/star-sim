---
name: star-sim-hosted-data-assets
description: Pre-baked data hosted via GitHub Releases (POSYDON — now the full 8-bucket metallicity axis, MIST tracks, MIST isochrones, Koester+TMAP, PoWR, Coelho, Gotberg, self-run helium/alpha MESA, + BPASS — 10 tags) so casual users skip raw multi-GB source fetches; the license-audit restriction was explicitly overridden by the user. "MESA excluded" is ONLY the third-party bearums validation tracks — SELF-RUN MESA output IS hosted.
metadata:
  type: project
  originSessionId: 614a40b0-c4a6-4698-a4c9-e486917bf270
---

Star Simulator hosts **pre-baked derived data artifacts as GitHub Release
assets** on repo `BoykoNeov/star-sim`, one release tag per dataset, so a user can
run a `python -m star_sim.fetch_<dataset>_baked` command (plain HTTPS + sha256
verify) instead of running each feature's raw-source recipe (a multi-GB
tarball/API-scrape fetch, then a host-side bake step). Ten tags exist:
`posydon-baked-v1`, `mist-baked-v1`, `mist-iso-baked-v1`, `koester-baked-v1`,
`powr-baked-v1`, `coelho-baked-v1`, `gotberg-baked-v1`, `mesa-helium-baked-v1`,
`mesa-alpha-baked-v1`, `bpass-baked-v1`.
Plans: `docs/plans/lantern-grid-waystation.md` (POSYDON, the original).

**MIST isochrones (`mist-iso-baked-v1`, 2026-07-10) — the 10th tag.** The
cluster-isochrone HR overlay (Axis B of the outward quartet, see
[[star-sim-isochrone-cluster]]) reads baked per-metallicity `.iso` cubes. The raw source
is ONE ~6.7 GB MIST v2.5 isochrone tarball per rotation rate (all metallicities), so a
fresh clone would otherwise stream 6.7 GB + bake. The tag hosts the **7 baked non-rotating
cubes** (`iso_feh{-1.00…+0.50}_vvcrit0.0.npz`, ~2.6 MB each, ~18 MB total — only the ~11
columns the HR overlay reads). `fetch_mist_iso_baked.py` uses the **flat `{filename:
sha256}` `_ASSETS`** over `_baked_release.fetch_one` (all 7 uniquely named — the BPASS
model, NOT the helium/alpha 2-tuple mapping), dest = `ISO_DATA_DIR`. **No code change to
`isochrone.py`** — the cubes are self-contained `np.load` + a `bake_version` check with no
MIST-track-style raw-source fingerprint (`_IsochroneIndex` just globs `*.npz` and reads
each file's own `bake_version`/`feh`/`vvcrit`), so this is the BPASS/Coelho/spectra
drop-in class, NOT the EEP-track source-less-fingerprint trick. License = the SAME MIST
call the user already authorized for the EEP-track cubes (MIST-derived, "cite on use, no
explicit grant"). Verified end-to-end into a fresh `STAR_SIM_ISOCHRONE_DIR` (7 `ok` +
sha256 → `isochrone_available()` True → the 4.6 Gyr solar iso reproduces turnoff
6239 K/1.21 M☉ from downloaded bytes). Only vvcrit=0.0 baked; add the rotating axis to
`_ASSETS` if/when baked.

**BPASS (`bpass-baked-v1`, 2026-07-10) — the 9th tag; now hosts BOTH population cubes.**
The coeval-population overlay (see [[star-sim-coeval-ensemble-bpass]]) backs two panels,
so the tag carries **two** flat drop-in assets, mapped in one `{GRID_FILENAME: sha256,
GRID_FILENAME_HRD: sha256}` dict over `_baked_release.fetch_one` (NOT the helium/alpha
2-tuple asset-name mapping — both BPASS files are uniquely named):
- `bpass_ssp.npz` (4.1 MB) — the SED integrated-spectrum cube (Chunk 1); hosted so
  users skip the ~1 GB **v2.3** Zenodo sin+bin pair + the h5py bake. **License: BPASS
  v2.3 is CC-BY 4.0.**
- `bpass_hrd.npz` (1.6 MB) — the HR-diagram number-density cube (Chunk 2); hosted so
  users skip the 1.5 GB **v2.2.1** starter-kit Zenodo zip range-extraction + bake.
  **License: the v2.2.1 starter kit (Zenodo 7340797) is ALSO CC-BY 4.0** — confirmed
  from the record before the outward-facing upload, the same explicit redistribution
  grant as v2.3 (both cleaner than the "cite on use, no grant found" MIST/Koester/PoWR/
  Coelho/Gotberg judgment call).

**No code change beyond `fetch_bpass_baked.py`'s `_ASSETS` + docstring** — `_Bpass`/
`_BpassHRD.__init__` are both `np.load` + a `bake_version` check with no raw-source
fingerprint like MIST, so the downloaded npzs load directly. Verified end-to-end into a
fresh `STAR_SIM_BPASS_DIR` (fresh subprocess → both `"ok"`, sha256 verified → `has_grid`
AND `has_hrd` both True → `population_hrd(0.0, 0.04)` reproduces Gate 0 from the
downloaded bytes: single hot-cell count 0.000 vs binary 283.47). The SED cube's earlier
verify (`population_sed` serves the ionizing wedge) still holds.

**Self-run MESA output IS hosted (the helium/alpha carve-out, 2026-07-09).** When
the user asked to make the helium + α what-if overlays "easier for casual users,"
the apparent blocker was the "MESA stays excluded" rule below — but that rule is
specifically about the **third-party bearums MESAProvider validation tracks**
(all-rights-reserved, someone else's data). The helium/alpha `history.data` files
are **self-run MESA r24.03.1 output** — this project's OWN computed tracks, the
same class of artifact as MIST (which is itself published MESA output). No
third-party redistribution question applies, and the user explicitly authorized
the public publish. So `mesa-helium-baked-v1` + `mesa-alpha-baked-v1` host the six
`history.data` files each (3 masses × baseline/enhanced, ~4.2 MB/dataset), fetched
by `fetch_helium_baked.py` / `fetch_alpha_baked.py` (both onto `_baked_release.py`,
like the rest). **The only structural difference from the other fetch modules:**
every file is literally named `history.data`, and GitHub requires **unique asset
names per release**, so `_ASSETS` maps a unique asset name (`helium_baseline_1Msun.data`)
→ `(relpath_under_data_dir, sha256)` — a richer 2-tuple value than the flat
`{filename: sha256}` the spectra modules use (`fetch_one` already takes `dest`
separately from the URL, so this needed no `_baked_release.py` change). No npz bake
(the siblings read `history.data` raw). **A Windows-console bug was caught in
verification:** the fetch scripts printed `α`/`—` glyphs, which crash on cp1252
(`UnicodeEncodeError`) — a casual Windows user's exact path; fixed to ASCII-only
console output. Verified end-to-end: a real publish, then a real fetch into a clean
`STAR_SIM_HELIUM_DIR`/`STAR_SIM_ALPHA_DIR` scratch dir (all 12 hashes verify from
fresh bytes), then a real load through `helium_overlay`/`alpha_overlay` (enhanced
hotter+shorter for He, cooler+longer + `alpha_fe`≈0.4 recovered for α). **MESA the
provider-validation dataset stays the one hard exclusion** (bearums, third-party) —
regenerate it from `mesa_solar_recipe.md`, it has no baked shortcut.

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

**POSYDON grew a second metallicity bucket (2026-07-07), and it needed real test
fixes, not just a bake.** The user asked directly whether POSYDON could be
size-optimized like MIST was; the answer was no (it's already ~33x reduced —
column-trim + row-decimation + float32 + gzip, done at bake time from the start,
not retrofitted) — so the actual next lever was breadth: only the solar bucket was
baked+hosted despite 8 metallicity tarballs (~83 GB) sitting on disk. The user chose
to validate with ONE more bucket before committing to all 7. Picked `0.1Zsun`
([Fe/H]=−1.0, the smallest raw tarball) — extracted just the `HMS-HMS` grid h5 (the
tarball holds 6 grid types × 2 file formats each; only `POSYDON_data/HMS-HMS/<Z>.h5`
is used, `tar -x` with an explicit path + `--strip-components` pulls just that one
file without touching the rest), baked it (33,865 tracks / 1.46M rows / 140.3 MB —
near-identical yield to solar's 33,121/1.48M/142 MB), uploaded it as a second asset
on the SAME `posydon-baked-v1` tag (no new tag needed — `posydon.py`'s `BAKED_DIR`
just globs `*.npz`, so a second file is a pure drop-in, zero runtime code change).

**Adding the second bucket exposed 6 latent test bugs in `test_posydon.py`**, all
of the same shape: every "check bake integrity across the WHOLE grid" test (no
duplicate nodes, no non-finite values, exact-node round-trip, RLOF-episode
survival under decimation, merger-track smoke) read `pd._available_grids()[0]` —
correct when exactly one bucket existed, but `BAKED_DIR.glob("*.npz")` sorts
alphabetically, so `[0]` silently became the NEW `0.1Zsun.npz` (it sorts before
`1Zsun.npz`) instead of solar the moment a second file landed — tests kept passing
but stopped covering the bucket they were written for. Fixed by looping over
`pd._available_grids()` in every one of those tests instead of indexing `[0]`
(checking every bucket, not swapping which one silently). One test
(`test_merger_outcome_tracks_do_not_crash`) had a second latent bug: it fed a
grid's own node coordinates into `binary_track(..., feh=0.0)` hardcoded — fine
when grid IS the solar one, silently wrong (snaps to the nearest node in whatever
bucket you asked for, not the one you sampled from) once grid could be a
different bucket; fixed to pass `grid.feh`, not a hardcoded value. The RLOF-episode
test's population-size floor (`>50`) was solar-specific (measured 202 there vs
only 26 in the sub-solar bucket — a real, smaller-but-real population, not a bug);
fixed to assert the floor on the TOTAL across buckets, not per-bucket, while
keeping the per-bucket `lost<=2` regression tight. `test_feh_snaps_to_nearest_
available_bucket` was rewritten outright — its old premise ("only solar is baked,
everything snaps there") is now false; it asserts −0.8 correctly snaps to the new
−1.0 bucket (nearer, 0.2 dex vs 0.8 dex — inside `_FEH_FAR_DEX=0.25`, not flagged
far) while +0.5 still correctly flags far (0.5 dex from the nearest bucket).
**Lesson for the next bucket:** any test iterating `_available_grids()` by index
rather than by content is an artifact of a one-bucket world — this bit us once,
watch for the same pattern before adding a third.

**The remaining 6 metallicities landed in one pass (2026-07-08), and the lesson
above bit a SECOND time.** With validation proven on `0.1Zsun`, the user approved
doing the rest in one go ("run the rest now"): `0.01Zsun`, `0.2Zsun`, `0.45Zsun`,
`1e-3Zsun`, `1e-4Zsun`, `2Zsun` — all 6 raw tarballs were already on disk (~83 GB
total downloaded earlier). Each followed the exact same recipe as `0.1Zsun`
(discover the internal `POSYDON_data/HMS-HMS/<Z-label>.h5` path via `tar -tzf`,
`tar -x --strip-components=2` to pull just that one file, `bake_posydon.py
--z-label <label> --feh <log10(Z/0.0142)>`), pipelined two-at-a-time (bake one
bucket while extracting the next) since extraction is disk/decompress-bound and
baking is CPU-bound. Yield was consistent with the first two buckets — roughly
138-164 MB and 32k-36k tracks per bucket (0.01Zsun 150.6 MB/34675, 0.2Zsun 137.8
MB/33871, 0.45Zsun 138.7 MB/33532, 1e-3Zsun 163.8 MB/35265, 1e-4Zsun 158.9
MB/36121, 2Zsun 151.4 MB/31972) — no metallicity-dependent surprise in bake
behavior. One gotcha: the `1e-3Zsun`/`1e-4Zsun` tarballs were noticeably larger
(~12.3-12.4 GB vs ~10 GB for the others) and their listings/extractions took
longer — not a bug, just a bigger archive (more grid types packed in).

A SECOND latent test bug of the exact same shape as the first batch's five was
found by re-running pytest after all 8 buckets existed:
`test_feh_snaps_to_nearest_available_bucket` had been rewritten for the 2-bucket
world (asserting `-0.8` snaps to the `-1.0` bucket) — but with `0.2Zsun` now at
`feh=-0.69897`, `-0.8` is genuinely nearer to *that* bucket (0.101 dex) than to
`-1.0` (0.301 dex), so the hardcoded assertion failed correctly (the snap logic
was right; the test's premise was stale again). Fixed by rewriting the test to
derive its expectations from the live `_available_grids()` feh set — every real
bucket value round-trips onto itself, a point nudged just past the theoretical
midpoint snaps to whichever bucket `min(available, key=...)` actually names, and
a point far past the metal-rich edge is flagged far — so the test now describes
the *invariant* the snap function must satisfy at any bucket count, not a
snapshot of one particular set of buckets. This is the second confirmation of
the same anti-pattern; a third bucket-count change should assume any test
mentioning a specific feh value or bucket count needs re-deriving, not just
re-running.

**The POSYDON metallicity axis is now COMPLETE**: all 8 buckets from POSYDON DR2
are baked and hosted on `posydon-baked-v1` — `1e-4Zsun`, `1e-3Zsun`, `0.01Zsun`,
`0.1Zsun`, `0.2Zsun`, `0.45Zsun`, `1Zsun` (solar), `2Zsun`, spanning [Fe/H]
roughly −4.0 to +0.30. Zero runtime code changes were needed anywhere in this
batch — every bucket is a pure data drop-in via `BAKED_DIR.glob("*.npz")`, exactly
as designed. `fetch_posydon_baked.py`'s `_ASSETS` now lists all 8 filename→sha256
pairs; a full `fetch_posydon_baked` run against the live release confirmed every
hash verifies (all reported "skip" against the already-baked local files, i.e.
the uploaded bytes match byte-for-byte). 311/311 pytest passing.

See [[star-sim-binary-stripped]] for the POSYDON co-evolving-binary feature that
data backs, [[star-sim-mist-provider]] for the provider MIST hosting touches,
[[star-sim-rotation-subpop-atlas]] for the rotation axis MIST's bucket set spans.
