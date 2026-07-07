# Plan: hosted pre-baked data assets (starting with POSYDON)

## Context

A casual user who clones the repo and runs `start.bat`/`start.sh` gets the core
MIST experience automatically (the fetch is already wired in). But every other
feature — POSYDON co-evolving binaries, WD/WR/α spectra, MESA validation — needs
its own manual `fetch_*.py` + (for POSYDON) a multi-GB download and a host-side
bake before it works. A user who doesn't know to go chasing `fetch_posydon.py`
just sees a broken/empty panel and concludes "this doesn't work."

The fix explored here: host **pre-baked** derived artifacts (the small `.npz`
files the bake scripts already produce) as GitHub Release assets, so a fetch
script can pull a ~100–500 MB compact file directly instead of a user
extracting+baking an 84 GB raw tarball tree themselves.

**Scope check (done before writing this plan):** grepped every `fetch_*.py` for
explicit redistribution license text.

- **POSYDON** (Zenodo DR2): explicit **CC-BY** — redistribution of derived
  artifacts is fine with attribution. ✅ confirmed.
- **MIST, Koester, TMAP, PoWR, Coelho, Gotberg spectra**: all "cite on use"
  (standard academic-attribution norm), served via SVO / VizieR / the MIST
  site — but **no explicit redistribution grant found** in any of them.
- **MESA** (bearums repo): explicitly all-rights-reserved — never redistributed,
  already excluded project-wide.

User decision (confirmed): **POSYDON only, for now.** The rest stay on the
existing "user runs the fetch script themselves" path until each source's terms
are separately verified or explicit permission is sought — that's a distinct,
separate follow-up, not part of this plan.

## Why GitHub Releases (not the repo tree)

Repo-committed files are capped at 100 MB and bloat clone size forever (git
history keeps every version). **Release assets are a separate store**: up to 2 GB
per file, don't touch git history, and are a plain HTTPS download — no GitHub API
auth needed to fetch a public release asset. `data/posydon/baked/1Zsun.npz` is
~139 MB — over the repo cap, comfortably under the release cap.

## Architecture

```
ONE-TIME (this pass, host-side, already have the solar bake on disk):
  data/posydon/baked/1Zsun.npz (139 MB, BAKE_VERSION 2)
    -> gh release create posydon-baked-v1 --title "..." --notes "..."
    -> gh release upload posydon-baked-v1 data/posydon/baked/1Zsun.npz
    -> sha256 recorded in the release notes (download integrity check)

RUNTIME (new, what a user runs instead of the raw-tarball recipe):
  python -m star_sim.fetch_posydon_baked
    -> downloads the release asset(s) straight into data/posydon/baked/
    -> verifies sha256, skips if already present and matching
    -> posydon.py picks it up exactly as if it had been baked locally
       (BAKED_DIR.glob("*.npz") — no runtime change needed at all)
```

`fetch_posydon.py`'s existing raw-tarball recipe stays as-is (it's how *new*
metallicities get baked in the first place — someone has to run it once per
metallicity before that metallicity can be uploaded as a release asset). The new
script is the "just get me the data" shortcut for everyone else.

## Steps

1. **Confirm the existing solar bake is sound** — `data/posydon/baked/1Zsun.npz`
   already exists (139 MB, `BAKE_VERSION` 2); sanity-check it loads via
   `posydon.py` (the existing `requires_posydon_data`-gated test suite covers
   this) before publishing it.
2. **Compute + record a sha256** of the asset, for the fetch script to verify
   against after download (corrupted/truncated download → don't silently accept
   it).
3. **Publish a GitHub Release** (`gh release create`, tag e.g.
   `posydon-baked-v1`) with `1Zsun.npz` attached, and release notes citing
   Fragos et al. 2023 / Andrews et al. 2024 + the CC-BY source (Zenodo DOI
   10.5281/zenodo.15194708).
4. **Add `backend/star_sim/fetch_posydon_baked.py`** — plain HTTPS download of
   the release asset(s) into `data/posydon/baked/`, sha256-verified, idempotent
   (skip a file already present and matching), mirroring the style of
   `fetch_koester.py` (plain `urllib`, no extra deps).
5. **Point users at it** — update `fetch_posydon.py`'s docstring and the README
   to lead with `fetch_posydon_baked` as the easy path, keeping the raw-tarball
   recipe as the "I want to bake a different/new metallicity" path.
6. **Test end-to-end**: remove the local baked file, run the new fetch script
   against the real published release, confirm `posydon.py` loads it and the
   gated pytest suite (`requires_posydon_data`) passes.
7. Commit the new script + doc updates, push.

## Non-goals (this pass)

- Baking/publishing the other 7 POSYDON metallicities — solar is the only one
  baked right now; more is a separate follow-up once this path is proven.
- Any of the non-POSYDON datasets (MIST/Koester/TMAP/PoWR/Coelho/Gotberg) —
  blocked on license clarification, tracked separately.
- The tiered "quick vs full" unified fetch-everything script discussed earlier —
  can layer on top of this later; not required for POSYDON to become one-command.
