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


def _imports(module: str) -> set[str]:
    """Dotted import targets of a star_sim module (relative imports normalised)."""
    tree = ast.parse((PKG / f"{module}.py").read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            out.add(mod if node.level == 0 else f"star_sim.{mod}" if mod else "star_sim")
            for alias in node.names:
                out.add(f"{mod}.{alias.name}" if mod else alias.name)
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


def test_only_the_api_and_fetchers_import_the_live_provider() -> None:
    """`PROVIDER` in api.py is the one swap point (spec §3). The only other modules
    allowed to name the live MIST provider are its own fetch/bake entry points."""
    allowed = {"api", "fetch_mist", "fetch_mist_baked"}
    offenders = sorted(
        p.stem for p in PKG.glob("*.py")
        if p.stem not in allowed and any(m.startswith("providers.mist") for m in _imports(p.stem))
    )
    assert not offenders, offenders


def test_state_is_a_plain_dataclass_with_no_web_or_data_concepts() -> None:
    """state.py is the contract: stdlib only, no numpy/fastapi/provider imports."""
    imported = _imports("state")
    assert imported <= {"annotations", "__future__", "dataclasses", "dataclasses.dataclass",
                        "dataclasses.field", "__future__.annotations"}, sorted(imported)
