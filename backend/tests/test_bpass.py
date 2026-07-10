"""Validation for the coeval-population overlay sibling (`bpass.py`, `/population`).

Chunk 1 of docs/plans/coeval-ensemble-overlay.md — the first ENSEMBLE sibling. The feature
exists to show the single-star-vs-binary difference in a whole coeval population's
integrated spectrum: binaries keep it UV/ionizing-bright far longer than single-star
evolution can (stripped hot stars, blue stragglers, hot subdwarfs). The Gate-0 test below
locks that MEASURED payoff so a re-bake or a units slip that flattens it fails loudly.

A population is not a star — the sibling imports only numpy/stdlib (not even StellarState)
and must not touch PROVIDER; that isolation is asserted here too.

Data-gated by `requires_bpass_data` — skips on a checkout without the host-baked BPASS cube
(gitignored; bake per scripts/bake_bpass_spectra.py). One ungated test exercises the
status-gate route on every checkout.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim.api import app
from star_sim.bpass import bpass_available, hrd_available, population_hrd, population_sed

from .conftest import requires_bpass_data, requires_bpass_hrd_data

client = TestClient(app)


# --- the data-availability honesty gate (UNGATED — must answer even with no data) ---
def test_population_status_route_always_answers() -> None:
    """/population_status is the frontend's toggle-visibility gate — a plain 200 with bools
    whether or not the BPASS cubes are on disk (a fresh clone has none). The one test here that
    does NOT require the data, so the gate is exercised on every checkout. `has_grid` is the
    SED-spectrum cube (Chunk 1); `has_hrd` the HR-diagram number cube (Chunk 2)."""
    resp = client.get("/population_status")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("has_grid"), bool)
    assert body["has_grid"] == bpass_available()
    assert isinstance(body.get("has_hrd"), bool)
    assert body["has_hrd"] == hrd_available()


def _band_flux(lam: np.ndarray, flux: np.ndarray, lo: float, hi: float) -> float:
    """Summed flux in a wavelength band [lo, hi) Angstrom — a robust band proxy."""
    m = (lam >= lo) & (lam < hi)
    return float(np.asarray(flux)[m].sum())


# --- Gate 0: the measured single-vs-binary UV/ionizing payoff -----------------
@requires_bpass_data
def test_binaries_keep_the_population_uv_bright() -> None:
    """THE payoff, through the runtime: at an intermediate age a binary population is far
    brighter in the ionizing (<912 A) and FUV (~1500 A) continuum than a single-star one,
    while the optical (~5500 A) is essentially unchanged. Measured off the raw HDF5 (Gate 0,
    2026-07-10): ionizing bin/sin ~256x at 40 Myr, FUV ~26x at 1 Gyr, optical ~1x. We assert
    a conservative multiple so a units/sign slip (which would zero the gap) fails loudly."""
    # 40 Myr, solar: the ionizing peak. (Age in Gyr.)
    ion = population_sed(0.0, 0.04)
    lam = np.asarray(ion["wavelength"])
    ion_sin = _band_flux(lam, ion["flambda_sin"], 1.0, 912.0)
    ion_bin = _band_flux(lam, ion["flambda_bin"], 1.0, 912.0)
    assert ion_bin > 3.0 * ion_sin, "binaries must dominate the ionizing continuum at 40 Myr"

    # 1 Gyr, solar: the FUV peak.
    fuv = population_sed(0.0, 1.0)
    lam2 = np.asarray(fuv["wavelength"])
    fuv_sin = _band_flux(lam2, fuv["flambda_sin"], 1400.0, 1600.0)
    fuv_bin = _band_flux(lam2, fuv["flambda_bin"], 1400.0, 1600.0)
    assert fuv_bin > 3.0 * fuv_sin, "binaries must dominate the FUV at 1 Gyr"

    # Optical bulk (cool giants) is the same to within a factor ~1.5 either way — the binary
    # story is a UV/ionizing story, not an optical one.
    opt_sin = _band_flux(lam2, fuv["flambda_sin"], 5400.0, 5600.0)
    opt_bin = _band_flux(lam2, fuv["flambda_bin"], 5400.0, 5600.0)
    assert 0.5 < opt_bin / opt_sin < 1.6, "the optical bulk should be roughly unchanged"


# --- snap-always honesty ------------------------------------------------------
@requires_bpass_data
def test_snap_is_honest_and_flagged() -> None:
    """([Fe/H], age) snap to a TRUE grid node (nearest [Fe/H] linearly, age in log10),
    flagged in-band, never 422'd — the /structure snap-always contract. A far request snaps
    and is flagged; an on-grid one is not."""
    r = population_sed(0.0, 1.0)
    # solar [Fe/H]=0.0 is exactly on the BPASS axis, so it snaps to itself, not flagged.
    assert r["feh_snapped"] == pytest.approx(0.0, abs=1e-6)
    assert r["feh_snapped_far"] is False
    assert r["age_gyr_requested"] == 1.0

    far = population_sed(1.5, 1.0)   # past the +0.30103 grid ceiling -> snaps + flags
    assert far["feh_snapped"] <= 0.31
    assert far["feh_snapped_far"] is True


@requires_bpass_data
def test_age_snaps_in_log_space() -> None:
    """A request between two geometric age nodes snaps to the nearer IN LOG10 (the grid is
    log-spaced over 5 decades — linear-nearest would mis-assign near the geometric midpoint)."""
    r = population_sed(0.0, 0.05)   # near a real node ~0.0501 Gyr
    snapped = r["age_gyr_snapped"]
    grid = np.asarray(r["age_gyr_grid"])
    # the snapped node is the log10-nearest of the whole grid
    log_nearest = grid[int(np.argmin(np.abs(np.log10(grid) - np.log10(0.05))))]
    assert snapped == pytest.approx(log_nearest)


# --- the route ----------------------------------------------------------------
@requires_bpass_data
def test_route_shape_and_selectors_and_422() -> None:
    resp = client.get("/population", params={"feh": 0.0, "age_gyr": 0.1})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"feh_snapped", "age_gyr_snapped", "feh_snapped_far",
                         "age_snapped_far", "wavelength", "flambda_sin", "flambda_bin",
                         "zsun_bpass"}
    assert len(body["wavelength"]) == len(body["flambda_sin"]) == len(body["flambda_bin"])
    assert body["zsun_bpass"] == pytest.approx(0.020)

    # the population selector serves just the requested curve(s)
    only_bin = client.get("/population", params={"feh": 0.0, "age_gyr": 0.1, "population": "bin"}).json()
    assert "flambda_bin" in only_bin and "flambda_sin" not in only_bin

    # 422 for structurally invalid input (age <= 0, an absurd [Fe/H], a bad selector).
    assert client.get("/population", params={"feh": 0.0, "age_gyr": 0}).status_code == 422
    assert client.get("/population", params={"feh": 99, "age_gyr": 1.0}).status_code == 422
    assert client.get("/population", params={"feh": 0.0, "age_gyr": 1.0,
                                             "population": "nope"}).status_code == 422


# --- Chunk 2: the HR-diagram number-density overlay ---------------------------
@requires_bpass_hrd_data
def test_hrd_binaries_fill_hot_cells_singles_leave_empty() -> None:
    """THE Chunk-2 payoff, through the runtime (the HR-panel twin of the UV wedge): at an
    intermediate age the BINARY population puts stars in the hot HR-diagram cells (logTeff>4.4
    — blue stragglers, stripped-He stars) that the SINGLE-star population leaves EMPTY. Measured
    off the raw hrs files (Gate 0, 2026-07-10, solar 40 Myr): single hot-region count = 0,
    binary ~283; stripped-He (low surface-H) total ~33x more with binaries. We assert the
    single-star hot region is empty while the binary one is populated, and that binaries make
    strictly more stripped stars — a re-bake/units slip that flattens it fails loudly."""
    d = population_hrd(0.0, 0.04)   # solar, 40 Myr
    logt = np.asarray(d["logt"])
    sin = np.asarray(d["dens_sin"])   # (nT, nL)
    binp = np.asarray(d["dens_bin"])
    hot = logt > 4.4
    sin_hot = float(sin[hot].sum())
    bin_hot = float(binp[hot].sum())
    assert sin_hot == pytest.approx(0.0, abs=1e-9), "single-star pop has no hot stars at 40 Myr"
    assert bin_hot > 100.0, "the binary pop must populate the hot region (blue stragglers)"
    # some cells are literally binary-only (single empty, binary present) — the magenta payoff
    binary_only = int(((sin[hot] == 0) & (binp[hot] > 0)).sum())
    assert binary_only > 10
    # stripped-He (low surface-H) stars are dominantly a binary product
    assert d["stripped_bin"] > 5.0 * max(d["stripped_sin"], 1e-9)


@requires_bpass_hrd_data
def test_hrd_snap_and_route_and_422() -> None:
    """/population_hrd snaps ([Fe/H], age) to a true node (flagged in-band, never 422 for an
    off-grid but structurally valid request — the snap-always contract), serves the axes + the
    density grid(s), and 422s on structurally invalid input."""
    # snap honesty: solar on-grid is unflagged; a far [Fe/H] snaps + flags.
    r = population_hrd(0.0, 1.0)
    assert r["feh_snapped"] == pytest.approx(0.0, abs=1e-6)
    assert r["feh_snapped_far"] is False
    far = population_hrd(1.5, 1.0)
    assert far["feh_snapped"] <= 0.31 and far["feh_snapped_far"] is True

    resp = client.get("/population_hrd", params={"feh": 0.0, "age_gyr": 0.04})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) >= {"feh_snapped", "age_gyr_snapped", "logt", "logl",
                         "dens_sin", "dens_bin", "stripped_sin", "stripped_bin", "zsun_bpass"}
    nT, nL = len(body["logt"]), len(body["logl"])
    assert len(body["dens_sin"]) == nT and len(body["dens_sin"][0]) == nL
    assert len(body["dens_bin"]) == nT and len(body["dens_bin"][0]) == nL

    # the selector serves just the requested grid(s)
    only_bin = client.get("/population_hrd",
                          params={"feh": 0.0, "age_gyr": 0.04, "population": "bin"}).json()
    assert "dens_bin" in only_bin and "dens_sin" not in only_bin

    # 422 for structurally invalid input.
    assert client.get("/population_hrd", params={"feh": 0.0, "age_gyr": 0}).status_code == 422
    assert client.get("/population_hrd", params={"feh": 99, "age_gyr": 1.0}).status_code == 422
    assert client.get("/population_hrd", params={"feh": 0.0, "age_gyr": 1.0,
                                                 "population": "nope"}).status_code == 422


# --- the §3 boundary: the sibling never routes through PROVIDER ---------------
@requires_bpass_data
def test_sibling_does_not_import_provider() -> None:
    """bpass.py is a pure numpy/stdlib sibling (a population is not a StellarState) — it must
    not reach the provider, and in fact should not even import StellarState. Asserted at the
    AST level like the other siblings."""
    import ast

    import star_sim.bpass as bpass

    with open(bpass.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    imported = {
        (node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "api" not in imported and "star_sim.api" not in imported
    assert not any("provider" == m.rsplit(".", 1)[-1] for m in imported)
    # it returns plain arrays/dicts — not even StellarState is imported
    assert not any("state" == m.rsplit(".", 1)[-1] for m in imported)
