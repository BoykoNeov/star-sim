---
name: star-sim-hosted-data-assets
description: Pre-baked data hosted via GitHub Releases (POSYDON only) to spare casual users the raw-tarball fetch; per-dataset license audit that scoped it to POSYDON.
metadata: 
  node_type: memory
  type: project
  originSessionId: 614a40b0-c4a6-4698-a4c9-e486917bf270
---

Star Simulator now hosts **pre-baked derived data artifacts as GitHub Release
assets** (repo `BoykoNeov/star-sim`, tag `posydon-baked-v1`), so a user can run
`python -m star_sim.fetch_posydon_baked` (plain HTTPS + sha256 verify) instead of
downloading POSYDON's ~10 GB-per-metallicity raw tarball and baking it
host-side. Plan: `docs/plans/lantern-grid-waystation.md`.

**Why GitHub Releases, not the repo tree:** committed repo files cap at 100 MB
and bloat clone size forever; release assets cap at 2 GB, live outside git
history, and need no API auth to download publicly. The solar baked grid
(`1Zsun.npz`) is 139 MB — over the repo cap, fine as a release asset.

**Scoped to POSYDON only, on purpose — a license audit, not an oversight.**
Grepped every `fetch_*.py` for redistribution terms:
- **POSYDON** (Zenodo DR2): explicit **CC-BY** → redistributing a baked
  derivative with attribution is compliant. The only one cleared.
- **MIST, Koester, TMAP, PoWR, Coelho, Gotberg spectra**: all "cite on use"
  (academic norm, served via SVO/VizieR/MIST's own site) but **no explicit
  redistribution grant found** in any fetch script. Left un-mirrored.
- **MESA** (bearums repo): explicitly all-rights-reserved — already excluded
  project-wide, never redistributed.

**Why:** the user's underlying concern was casual users hitting "this doesn't
work" because most features need a manual multi-GB fetch script run before they
light up — GitHub's 100 MB repo-file cap plus most datasets' license terms are
why the raw grids were never just committed.

**How to apply:** if asked to host more pre-baked data (a new POSYDON
metallicity, or any other dataset), check whether that specific source has an
explicit redistribution grant (like CC-BY) FIRST — "freely fetchable" and
"cite on use" are not the same as "licensed for third-party redistribution."
Only POSYDON has cleared that bar so far. If baking + publishing a new
metallicity: run `bake_posydon.py`, sha256 the output, `gh release upload
posydon-baked-v1 <file>`, then add the filename+hash to
`fetch_posydon_baked.py`'s `_ASSETS` dict.

See [[star-sim-binary-stripped]] for the POSYDON co-evolving-binary feature this
data backs.
