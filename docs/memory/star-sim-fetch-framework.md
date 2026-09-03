---
name: star-sim-fetch-framework
description: The fetch framework (`_fetch.py` + `run()`, one user-agent formatter, the `star-sim-fetch` catalogue) — the shipped structure-refactor §1.5, its four measured corrections to the plan, and the cp1252 gate.
metadata:
  type: project
---

`structure-refactor.md` §1.5, shipped 2026-09-03 — the last step of that plan.
**534 pytest / 0 skipped (+66 new), ruff clean, a 317-line behaviour snapshot
byte-identical before and after.**

## What it is

`star_sim/_baked_release.py` → **`star_sim/_fetch.py`**, renamed because it is now the
leaf *both* families of fetcher sit on, not just the baked half:

- `run(tag, assets, *, what, dest_root, citation, url_of=, dest_of=, label_of=)` — a
  baked fetcher's entire body. `assets` is uniformly `{key: sha256}`.
- `user_agent(purpose)` · `asset_base(tag)` · `parse_no_args(description, argv)` ·
  `fetch_one` · `sha256`.

Each `fetch_*_baked.py` is now its docstring, its table and a ≤ 12-line `main()`
(826 → 695 lines across the ten). `star_sim/fetch.py` is the **`star-sim-fetch`**
console script (`[project.scripts]`): no arguments prints all 21 fetchers grouped
pre-baked vs from-source; `star-sim-fetch mist-baked --feh p000` forwards the tail to
that module's `main()`. `python -m star_sim.fetch_<name>` is unchanged.

**The line count went up** (2,726 → 2,808 across the fetch surface). The duplication
fell by 131 lines; the growth is the dispatcher, three missing entry points and
docstrings. Say that plainly rather than quoting only the shrinking half.

## The rules worth keeping

- **Three strings, not one.** The release asset name, the destination path and the
  printed progress label are different for two of the ten tables — MIST's asset is
  `<bucket>.npz` but its destination is the parse cache *inside* that bucket's
  `eeps/`; helium/alpha's assets are uniquely named because GitHub demands it while
  every file is literally `history.data`. Collapsing them to one key would change what
  the user sees. Hence the three optional callables. See [[star-sim-hosted-data-assets]].
- **`run()` does not own argparse.** Each module keeps its own parser and filters its
  own table before calling `run()`, so `--feh`/`--vvcrit`/`--asset` live with the
  fetcher that has them instead of becoming escape hatches in the shared runner.
- **The user-agent format is shared; the purpose tag is not.** Eight raw fetchers pass
  their own tag to `user_agent()`. These strings reach MIST, SVO, Zenodo and CDS.
- **`_fetch.py` stays a leaf** — stdlib only, nothing from `star_sim`, dependency
  running one way (a fetcher hands its own `*_DATA_DIR` down). Pinned by a test, the
  same rule `_grid.py` carries ([[star-sim-shared-grid-leaf]]).
- **One entry-point shape for all 21:** `main(argv=None) -> int`. The dispatcher
  forwards a command line to it and returns its code; a parametrized test pins it.

## Four measured corrections to the plan's text

The plan (written from a skim) was wrong in four places; all are recorded in
`structure-refactor.md` §1.5 and worth not re-deriving:

1. **"Ten byte-identical `_fetch_one` wrappers" → six.** MIST's differs; helium and
   alpha have none at all.
2. **"Seven user-agent strings" → eight** (nine counting `_baked_release`'s own).
3. **"Five have no `main()`" → two** (`fetch_bpass`, `fetch_posydon`), plus
   `fetch_gotberg`'s `main() -> None`. All three now have the uniform shape.
4. **`star-sim-bake` is blocked, not skipped.** `[tool.setuptools.packages.find]`
   packages `star_sim*` only, so `backend/scripts/bake_*.py` are not importable and no
   console script can resolve to them. Giving them one means moving nine host-side
   one-offs — and their bake-only deps (h5py, pymsg) — into the runtime package. The
   reason is written into `pyproject.toml` and `fetch.py`, not just this file.

## The two things that would have gone wrong

- **There was no safety net, so one came first.** These modules had zero tests and
  their whole payload is `(url, dest, sha256)` triples — a wrong URL is a 404 and a
  wrong destination is a file the app never finds, both only visible after someone has
  waited out a ~450 MB download. The acceptance was a harness that stubs the
  downloader, runs every `main()` (plus every filter, both error paths and all ten
  `--help` texts) and prints each triple beside every printed line: **317 lines, zero
  diff**. `tests/test_fetch_framework.py` is that harness made permanent — 66 cases,
  data-free and network-free, so CI runs them on a clone with no grids.
- **A Windows console is cp1252 and has no Greek block.** The new catalogue printed
  `α`; `print` raised `UnicodeEncodeError` and the listing died half-drawn. This is
  the *same* defect [[star-sim-hosted-data-assets]] records being hand-fixed once
  before in the helium/alpha fetchers — so it is now gated: two tests encode the
  catalogue and every baked fetcher's output as cp1252. Em dashes and `×` are fine
  (they *are* in cp1252); the Greek and mathematical blocks are not.
