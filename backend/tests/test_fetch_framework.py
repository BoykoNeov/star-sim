"""The fetch framework, checked with no data and no network (`structure-refactor` §1.5).

The `fetch_*.py` modules had no tests at all, and their entire payload is a table of
`(url, dest, sha256)` triples: a wrong URL is a 404 and a wrong destination is a file
the app never finds — both only visible after someone has waited out a ~450 MB
download. So the baked fetchers are run here end to end with the downloader stubbed
out, and what they *would* have fetched is asserted instead.

Nothing here touches the network or `data/`: `_fetch.fetch_one` is replaced, so every
test runs on a fresh clone. See `star_sim/_fetch.py` for the framework itself.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import re

import pytest

from star_sim import _fetch, fetch

PKG = pathlib.Path(_fetch.__file__).parent
REPO_DATA = PKG.parents[1] / "data"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _fetch_modules() -> list[str]:
    """Every fetcher module on disk (not the `fetch.py` dispatcher itself)."""
    return sorted(p.stem for p in PKG.glob("fetch_*.py"))


def _baked_modules() -> list[str]:
    return [m for m in _fetch_modules() if m.endswith("_baked")]


def _modules_with_a_user_agent() -> list[str]:
    """The raw fetchers, found by reading the source rather than importing it — a
    parametrize list is built at *collection* time, so importing all 21 up here would
    let one bad module take down the whole suite instead of one test. Same reason
    `conftest.py` keeps its sibling imports deferred."""
    return [m for m in _fetch_modules()
            if "_USER_AGENT = user_agent(" in (PKG / f"{m}.py").read_text(encoding="utf-8")]


def test_the_dispatcher_table_and_the_package_agree() -> None:
    """`star-sim-fetch`'s catalogue is the only list of fetchers, so it must stay
    exactly the set of modules on disk — a new fetcher that forgets its row would
    otherwise be invisible from the CLI, and a deleted one would crash on import."""
    listed = {fetch.module_name(name) for name in fetch.FETCHERS}
    assert listed == set(_fetch_modules())
    # The count is pinned too, because prose states it: `fetch.py`'s docstring, the
    # README and CLAUDE.md all say "21 fetchers". A 22nd should fail here and make
    # whoever adds it update those three sentences, rather than let them drift.
    assert len(listed) == 21


@pytest.mark.parametrize("module", _fetch_modules())
def test_every_fetcher_has_the_same_entry_point(module: str) -> None:
    """`main(argv=None) -> int` for all 21. The dispatcher forwards the tail of the
    command line to it and returns its exit code, so a fetcher that took no `argv` (or
    called `sys.exit` instead of returning) could not be driven through
    `star-sim-fetch` at all — three of them used to be shaped that way."""
    main = getattr(importlib.import_module(f"star_sim.{module}"), "main", None)
    assert main is not None, f"{module} has no main()"
    params = list(inspect.signature(main).parameters.values())
    assert [p.name for p in params] == ["argv"], f"{module}.main takes {params}"
    assert params[0].default is None


def test_the_framework_stays_a_leaf() -> None:
    """`_fetch.py` is imported by every fetcher, including ones that reach the live
    provider, so it must not reach back: stdlib only, nothing from `star_sim`. The
    dependency runs one way — a fetcher hands its own `*_DATA_DIR` down."""
    tree = ast.parse(pathlib.Path(_fetch.__file__).read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level:
            roots.add("<relative>")
        elif isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
    intra = {r for r in roots if r == "<relative>" or (PKG / f"{r}.py").exists()}
    assert not intra, f"_fetch.py must stay a leaf — it imports {sorted(intra)}"


@pytest.mark.parametrize("module", _baked_modules())
def test_a_baked_fetcher_resolves_to_this_repos_release_and_lands_under_data(
    module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run the module's whole `main()` with the downloader replaced, and check the
    three strings `run()` derives per asset: the URL is on this repo's release for the
    module's OWN tag, the sha256 is a real digest, and the destination is inside the
    repo's `data/` tree. That last one is the check with teeth — every one of these
    modules exists to put a file exactly where a sibling globs for it."""
    mod = importlib.import_module(f"star_sim.{module}")
    calls: list[tuple[str, pathlib.Path, str]] = []
    monkeypatch.setattr(_fetch, "fetch_one",
                        lambda url, dest, sha, timeout=300: calls.append((url, dest, sha)) or "ok")

    assert mod.main([]) == 0
    assert calls, f"{module} fetched nothing"
    base = _fetch.asset_base(mod.RELEASE_TAG)
    for url, dest, sha in calls:
        assert url.startswith(base + "/"), url
        assert SHA256.match(sha), (url, sha)
        assert REPO_DATA in dest.parents, dest
    assert len({sha for _, _, sha in calls}) == len(calls), f"{module} repeats a digest"


@pytest.mark.parametrize("module", _baked_modules())
def test_a_baked_fetcher_names_every_asset_in_its_table_exactly_once(
    module: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The table is the module's whole content; `run()` must consume all of it. Guards
    the filtered fetchers in particular (`--feh`, `--asset`), where an unfiltered run
    is meant to be everything."""
    mod = importlib.import_module(f"star_sim.{module}")
    calls: list[str] = []
    monkeypatch.setattr(_fetch, "fetch_one",
                        lambda url, dest, sha, timeout=300: calls.append(sha) or "ok")
    mod.main([])
    digests = [v[1] if isinstance(v, tuple) else v for v in mod._ASSETS.values()]
    assert calls == digests


def test_mist_baked_filters_narrow_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one fetcher with a two-axis filter. Pinned because the [Fe/H]xrotation
    bucket names are parsed out of strings, not read off a grid."""
    mod = importlib.import_module("star_sim.fetch_mist_baked")
    seen: list[pathlib.Path] = []
    monkeypatch.setattr(_fetch, "fetch_one",
                        lambda url, dest, sha, timeout=300: seen.append(dest) or "ok")

    assert mod.main(["--feh", "p000"]) == 0
    assert len(seen) == 2                                   # both rotation buckets
    seen.clear()
    assert mod.main(["--feh", "p000", "--vvcrit", "0.0"]) == 0
    assert [p.parent.parent.name for p in seen] == ["feh_p000_afe_p0_vvcrit0.0"]
    seen.clear()
    assert mod.main(["--feh", "zzz"]) == 1                  # no match is an error, not a no-op
    assert mod.main(["--asset", "nope"]) == 1               # and so is an unknown bucket
    assert not seen


def test_posydon_baked_rejects_an_unknown_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("star_sim.fetch_posydon_baked")
    monkeypatch.setattr(_fetch, "fetch_one",
                        lambda *a, **k: pytest.fail("must not fetch on a bad --asset"))
    assert mod.main(["--asset", "nope"]) == 1


def test_run_reports_skips_without_counting_them_as_downloads(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: pathlib.Path
) -> None:
    """The summary line every fetcher ends on. A file already present with the right
    hash is a "skip", and re-running a fetcher must be a cheap no-op rather than a
    re-download — that is what makes these safe to put in a README as `run once`."""
    monkeypatch.setattr(_fetch, "fetch_one", lambda url, dest, sha, timeout=300: "skip")
    rc = _fetch.run("some-tag", {"a.npz": "0" * 64, "b.npz": "1" * 64},
                    what="2 test cubes", dest_root=tmp_path, citation="Cite nobody.")
    out = capsys.readouterr().out
    assert rc == 0
    assert "Fetching 2 test cubes from release 'some-tag'" in out
    assert out.count(": skip") == 2
    assert "Done: 0 downloaded, 2 already present." in out
    assert out.strip().endswith("Cite nobody.")


@pytest.mark.parametrize("module", _modules_with_a_user_agent())
def test_a_raw_fetcher_identifies_itself_through_the_shared_formatter(module: str) -> None:
    """One User-Agent format, eight purpose tags. These strings go to third-party
    servers (MIST, SVO, Zenodo), so the prefix is shared but each fetch stays
    identifiable — collapsing them to a single constant would lose that."""
    agent = importlib.import_module(f"star_sim.{module}")._USER_AGENT
    assert agent.startswith("star-sim/0.1 (+local teaching tool; ")
    assert agent.endswith(")")
    assert agent != _fetch.USER_AGENT, f"{module} did not say what it is fetching"


def test_the_catalogue_prints_on_a_windows_console(capsys: pytest.CaptureFixture[str]) -> None:
    """`star-sim-fetch` with no arguments is the first thing a fresh checkout runs, and
    this project is developed on Windows, where the console is cp1252. A Greek α in a
    blurb is not a cosmetic problem there — `print` raises UnicodeEncodeError and the
    catalogue dies half-printed (measured, 2026-09-03). Em dashes and × are fine; the
    Greek and mathematical blocks are not."""
    assert fetch.main([]) == 0
    capsys.readouterr().out.encode("cp1252")


@pytest.mark.parametrize("module", _baked_modules())
def test_a_baked_fetchers_output_prints_on_a_windows_console(
    module: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same gate for the progress lines and citations — `Götberg` and `Gräfener` are
    cp1252, but a future citation with a Greek or curly-quote character would take the
    fetcher down *after* the download, at the last print."""
    mod = importlib.import_module(f"star_sim.{module}")
    monkeypatch.setattr(_fetch, "fetch_one", lambda url, dest, sha, timeout=300: "skip")
    mod.main([])
    capsys.readouterr().out.encode("cp1252")


def test_the_purpose_tags_are_distinct() -> None:
    agents = {m: getattr(importlib.import_module(f"star_sim.{m}"), "_USER_AGENT", None)
              for m in _fetch_modules()}
    named = [a for a in agents.values() if a]
    assert len(set(named)) == len(named), agents
