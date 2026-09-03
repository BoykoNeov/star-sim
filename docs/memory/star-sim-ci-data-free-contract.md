---
name: star-sim-ci-data-free-contract
description: The data-free contract enforced by .github/workflows/ci.yml — ruff (narrow net) + pytest on a clone with no grids must pass with every data-gated test skipped; the two MIST gates (working provider vs raw tracks); the §3 architecture table test.
metadata:
  type: project
---

**What CI runs (added 2026-09-02, branch `claude/project-structure-planning-nons2j`):**
`ruff check star_sim tests scripts` with the deliberately narrow rule set in
`backend/pyproject.toml` (`E9 F63 F7 F82 F401 F811 F841` — syntax errors, undefined
names, unused imports/locals; a correctness net, not a style regime), then
`python -m pytest -q` on ubuntu, Python 3.11 + 3.12, with **no data on disk**.
Baseline: 140 passed / 305 skipped / 0 failed.

`ruff` is a **dev extra** (`ruff>=0.6` in `[project.optional-dependencies].dev`), not a
separate CI install — one source of truth, so `pip install -e ".[dev]"` hands a
contributor exactly the checker CI will judge them with. Corrected 2026-09-02: the
branch as merged documented `ruff check ...` as a local command while shipping it only
in the CI step, so the documented command did not exist in a freshly set-up venv.

**Why it exists:** two tests (`test_binary.py::test_pair_route_snaps_far_in_band_not_422`,
`test_photometry.py::test_photometry_track_422_on_bad_mass`) had been failing on every
fresh clone (503 from the missing provider, no `requires_mist_data`) and nobody saw it.
The narrow ruff net paid for itself on day one: it caught an undefined `glob` in the
branch's own conftest patch before the suite ran.

**The two MIST gates.** `requires_mist_data` = a working provider — the hosted
cache-only download (`fetch_mist_baked`, `.npz` per bucket, no raw text) qualifies.
`requires_mist_raw_tracks` = a test reading a raw `.track.eep` via the vendored parser
as ground truth (`_real_track`). Nine tests use the second. Prefer the cache-friendly
form for new accuracy tests: the full provider's own grid node *is* the real track.

**`tests/test_architecture.py`** — the §3 boundary as one parametrized table over all
12 siblings (no `api`, no `provider`, no `providers.mist/stub`; helium/alpha may import
only `providers.mesa` helpers; bpass/photometry not even `state`), plus "only
`api`/`fetch_mist*` import the live provider" and "`state.py` is stdlib-only". Runs
with no data; three previously data-gated per-file AST tests were ungated. **Add every
new sibling to the table.**

See `docs/plans/structure-refactor.md` §0 for the rest of what that branch changed.

**The gates are one table (2026-09-03, `structure-refactor.md` §1.6).** `conftest.py`
holds `_DATASETS`: 33 rows of `name -> (predicate, reason)`, and `requires(name)` turns
a row into a skip marker, so each `requires_*` the tests import is a one-line alias.
Adding a gate is a table row plus that alias — never a new predicate + `skipif` pair.
581 → 422 lines.

Four things about it that are easy to get wrong later:

- **It buys no laziness.** `pytest.mark.skipif` takes a bool, not a callable, so every
  predicate still runs at import exactly as before. The wins are line count, one place
  per dataset, and the header.
- **`pytest_report_header` prints `data present (N/33)` / `gated off (…)`** at the top
  of every run, `--collect-only` included. This is how you see at a glance that a run
  is testing less than it looks like it is.
- **The sibling imports inside the predicates stay deferred** (`helium`, `alpha`,
  `bpass`, `isochrone`, `structure`, `posydon*` — now in named lookup helpers the
  table's lambdas call). Hoisting them to module scope makes *collecting the suite at
  all* depend on every sibling importing cleanly.
- **Check gating changes in BOTH directions.** The dev machine runs at zero skips, so a
  local green run only proves no gate collapsed into always-skip. The opposite failure —
  a gate that can no longer close — is invisible there. Reproduce it by moving the whole
  `data/` directory aside and diffing per-test outcomes old vs new (the §1.6 rewrite:
  identical, 152 passed / 316 skipped / 0 failed).
