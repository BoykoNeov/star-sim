---
name: star-sim-shared-grid-leaf
description: `_grid.py` — the shared snap/bake-version leaf, the spectra cube-loader collapse, and the four abstractions that were measured and REJECTED (missing_hint, snap_far, and two wrong counts).
metadata:
  type: project
---

# `_grid.py` — the shared leaf (shipped 2026-09-03)

`backend/star_sim/_grid.py` is the one place the "snap, don't interpolate" (§6)
plumbing lives. Four functions, numpy + stdlib only:

- `snap_index(values, x)` / `snap_value(values, x)` — nearest-node index / value.
  **13 call sites**: `alpha` `helium` `bpass`×4 `isochrone` `structure`×3 `spectra`
  `providers/mesa`×2. Units are the caller's business — pass both sides already in
  log space for a log axis; the helper does not guess.
- `load_npz(path, …)` / `require_bake_version(npz, path, …)` — the "this `.npz` was
  written by an older bake" gate, raising the sibling's own `*DataMissing`.
  **7 sites**: `bpass`×2 `posydon` `posydon_co` `spectra`×3.

**It is a *shared leaf*, and a test says so.** `test_architecture.py`'s
`test_shared_leaves_stay_leaves` pins `_grid` and `errors` to numpy+stdlib with
nothing from `star_sim` — every sibling imports them, so anything they can reach a
sibling can reach, and a provider import here would be a §3 back door.
The sibling table also now walks a sibling that has become a *package* (see
[[star-sim-api-routers]]), instead of silently checking only its `__init__.py`.

Same commit: `spectra.py`'s five cache globals + five near-identical `_load_*()`
became one `_CUBE_FILES` table (name → filename + recipe) and one `_cube(name, cls)`
— 762 → 718 lines. Adding a sixth cube is a table row plus one call.

## The four things measured and REJECTED — do not re-propose

The plan ([[structure-refactor]] §1.2) asked for four helpers. Two of them are bad
ideas and two of its counts were wrong:

1. **`missing_hint(dataset, path, fetch_cmd)`** — the eight `_MISSING_HINT`
   templates are hand-written **recipes**, not a shape. Different format keys
   (`data_dir` / `baked_dir` / `kind` / none) and genuinely different instructions
   (a Docker MESA batch · a 1 GB Zenodo download with a pre-baked shortcut ·
   "restore these from version control"). A builder could only take a free-text
   blob (no reduction) or flatten a user-facing 503 hint (a regression).
2. **`snap_far(values, x, tol)`** — `*_snapped_far` has **three incompatible
   meanings**: absolute (`isochrone._FEH_SNAP_FAR`), relative-to-the-node
   (`alpha`/`helium`, `> 0.25 × snapped`), log-dex (`posydon._M1_FAR_DEX`, `bpass`
   on `log_age`). One `tol` parameter would silently change one of them.
3. **"22× `argmin`" is 13.** The rest are `argmin` over a *precomputed distance*
   array (`posydon`, `posydon_co`, the WR (log T*, log Rt) snap) or over a cost
   curve (`providers/mist`) — different return semantics, not snaps.
4. **`allow_pickle=False` was never an inconsistency** — it is numpy's own default,
   so the five bare `np.load` calls always behaved identically. It is now passed
   explicitly in one place, for documentation only.

`providers/mist.py`'s six `argmin` sites were left alone on purpose: that is §1.4,
and its log-mass interpolation core had just changed.

## What made this believable

**Verify the safety net before touching a call site.** The plan's acceptance was
"behaviour is bit-identical, so the data-gated tests are the check" — true only for
siblings whose grids are on the machine. `pytest -q -rs` first: **464 passed, 0
skipped** (468 after, the 4 extra being this step's own new assertions). Without
that number the refactor would have been unguarded edits reported as green.

Two more checks worth repeating on any similar move:

- **Prove a collapsed cache is still load-bearing.** Removing the `_LOADED` swap
  from the two "not baked" tests makes them fail (200 instead of 503, and DID NOT
  RAISE) — so they exercise a fresh load rather than passing off a warm cube.
- **Diff the public surface mechanically, not by eye.** HEAD's `spectra.py` copied
  into the package under a second name, imported alongside the working tree, and
  the five `*_spectrum_data` functions compared on `inspect.signature` *and*
  returned dict keys — the [[star-sim-api-routers]] OpenAPI-diff precedent, scaled
  down.
