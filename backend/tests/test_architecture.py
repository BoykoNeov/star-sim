"""The §3 boundary, checked for EVERY sibling at once — and with no data on disk.

CLAUDE.md's one overriding rule: consumers and siblings never import a provider's
internals. Several siblings already carry a per-file AST test; this is the single
table that keeps the rule enforced for all of them (and for any new sibling — add it
here), so a fresh clone or CI verifies the architecture even though every grid is
absent. Pure source inspection: nothing here touches data.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PKG = pathlib.Path(__file__).resolve().parents[1] / "star_sim"

# Siblings that legitimately build StellarStates (they import `state`), but must
# never see the spine's provider, the live MIST/stub providers, or the API.
SIBLINGS = [
    "lane_emden", "structure", "spectra", "supernova", "binary", "posydon",
    "posydon_co", "isochrone", "helium", "alpha", "bpass", "photometry",
]
# Views that are not a star at all (a population, a magnitude): not even `state`.
NOT_EVEN_STATE = {"bpass", "photometry"}
# The what-if overlays reuse the *MESA parser's* free helpers (documented in
# CLAUDE.md: "imports only state.StellarState + the MESA parser's free helpers —
# never the live MIST spine"). Only `providers.mesa` is allowed for them.
MESA_PARSER_EXEMPT = {"helium", "alpha"}


def _source(module: str) -> tuple[pathlib.Path, list[str]]:
    """(file, owning package parts) for a package-relative dotted module name.
    "spectra" -> spectra.py in `star_sim`; "api" -> api/__init__.py, whose own
    package IS `api`; "api.spine" -> api/spine.py, package `api`."""
    parts = module.split(".")
    path = PKG.joinpath(*parts).with_suffix(".py")
    if path.exists():
        return path, parts[:-1]
    return PKG.joinpath(*parts, "__init__.py"), parts


def _imports(module: str) -> set[str]:
    """Dotted import targets of a `star_sim` module, package-relative.

    `module` is dotted and rooted at the package: "spectra", "api.spine". Relative
    imports are normalised against the importing module's OWN package, so a
    `from ..spectra import …` inside `api/` resolves to "spectra" and not to
    "api.spectra" — the depth matters now that `api` is a subpackage.
    """
    path, pkg = _source(module)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:                              # level 1 = own package, 2 = its parent, …
                anchor = pkg[: len(pkg) - (node.level - 1)]
                base = ".".join([*anchor, node.module] if node.module else anchor)
            if base:
                out.add(base)
            for alias in node.names:
                out.add(f"{base}.{alias.name}" if base else alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.add(alias.name)
    return {m.removeprefix("star_sim.") for m in out}


@pytest.mark.parametrize("module", SIBLINGS)
def test_sibling_never_imports_the_provider_layer(module: str) -> None:
    imported = _imports(module)
    forbidden = {"api", "provider", "providers", "providers.mist", "providers.stub",
                 "providers.mist.MISTProvider", "providers.stub.StubProvider"}
    hit = {m for m in imported if m in forbidden or m.startswith("api.") or m.startswith("provider.")}
    assert not hit, f"{module}.py reaches the provider layer: {sorted(hit)}"
    mesa = {m for m in imported if m.startswith("providers.mesa")}
    if module in MESA_PARSER_EXEMPT:
        assert mesa, f"{module}.py is expected to reuse the MESA parser helpers"
    else:
        assert not mesa, f"{module}.py must not import the MESA provider: {sorted(mesa)}"
    if module in NOT_EVEN_STATE:
        assert not any(m == "state" or m.startswith("state.") for m in imported), (
            f"{module}.py is not a star — it must not import StellarState")


def _package_modules() -> list[str]:
    """Every module in `star_sim`, dotted and package-relative — including the `api/`
    subpackage, so splitting a file into a package can never quietly drop it from the
    checks below (`api.py` -> `api/` is exactly how that happens)."""
    mods = [p.stem for p in PKG.glob("*.py") if p.stem != "__init__"]
    for sub in sorted(d for d in PKG.iterdir() if d.is_dir() and (d / "__init__.py").exists()):
        if sub.name in {"_vendor", "providers", "data", "__pycache__"}:
            continue
        mods.append(sub.name)                                   # the subpackage itself
        mods += [f"{sub.name}.{p.stem}" for p in sorted(sub.glob("*.py"))
                 if p.stem != "__init__"]
    return mods


def test_only_the_swap_point_and_fetchers_import_the_live_provider() -> None:
    """`PROVIDER` in `api/__init__.py` is the one swap point (spec §3). Not even the
    routers may name the live MIST provider — they reach it through `_deps.provider()`,
    which is what keeps a provider swap a one-line change. The only other modules
    allowed to name it are its own fetch/bake entry points."""
    allowed = {"api", "fetch_mist", "fetch_mist_baked"}
    offenders = sorted(
        m for m in _package_modules()
        if m not in allowed and any(x.startswith("providers.mist") for x in _imports(m))
    )
    assert not offenders, offenders


API_ROUTERS = ["spine", "interiors", "spectra", "binaries", "ensembles", "observer"]


@pytest.mark.parametrize("router", API_ROUTERS)
def test_router_never_names_a_concrete_provider(router: str) -> None:
    """A router may import the provider *boundary* (`provider.ParameterOutOfRange`,
    the Protocol) and any sibling, but never a concrete provider class — that is the
    other half of the §3 rule, seen from the API's side."""
    imported = _imports(f"api.{router}")
    hit = {m for m in imported if m.startswith("providers")}
    assert not hit, f"api/{router}.py names a concrete provider: {sorted(hit)}"


def test_the_swap_point_is_the_package_init() -> None:
    """Belt and braces on the sentence CLAUDE.md promises: `PROVIDER` is assigned in
    exactly one place, and that place is `api/__init__.py`."""
    def assigns_provider(module: str) -> bool:
        path, _ = _source(module)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            targets = ([node.target] if isinstance(node, ast.AnnAssign)
                       else node.targets if isinstance(node, ast.Assign) else [])
            if any(getattr(t, "id", None) == "PROVIDER" for t in targets):
                return True
        return False

    assert sorted(m for m in _package_modules() if assigns_provider(m)) == ["api"]


def test_state_is_a_plain_dataclass_with_no_web_or_data_concepts() -> None:
    """state.py is the contract: stdlib only, no numpy/fastapi/provider imports."""
    imported = _imports("state")
    assert imported <= {"annotations", "__future__", "dataclasses", "dataclasses.dataclass",
                        "dataclasses.field", "__future__.annotations"}, sorted(imported)
