"""Validation for the binary-stripped-star spectrum sibling (Chunk 3).

`/stripped_spectrum` serves the hot He-star's CMFGEN continuum-normalized spectrum from
the Götberg 2018 cube, keyed on the SAME (Z, M_init) grid node `binary.py` snaps. Like
the WR cube it is a flat-node cube (no interpolation — §6), so the anchors are:

  * **snap honesty + state<->spectrum consistency** — a request lands on a TRUE grid node
    (the one `/binary` resolved), so the panel's spectrum is the same star as the marker;
  * **the measure-first gate, as a regression** — the entire justification for a fourth
    cube: the sequence must run from pure ABSORPTION at the low-mass subdwarf end to strong
    EMISSION at the high-mass He-star end (Götberg's subdwarf↔Wolf-Rayet thesis), and the
    hot He-star's He II 4686 EMISSION must be a feature the H-atmosphere main cube cannot
    produce (which is why the Chunk-2 placeholder existed);
  * the continuum-normalized shape (Fnorm ≈ 1 continuum, bidirectional lines) + the route.

All gated `requires_stripped_spectra_data` (the cube is baked on the host from the
gitignored Götberg spectra tree, never committed).
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import binary as b
from star_sim.api import app
from star_sim.spectra import stripped_spectrum_data

from .conftest import requires_stripped_spectra_data

pytestmark = requires_stripped_spectra_data

# Anchor nodes on the solar grid (M_init / M_sun) spanning the sequence: subdwarf →
# hybrid → He-star, measured through the runtime (see the gate in Chunk 3).
_SUBDWARF = 2.0     # pure absorption, He II 4686 flat
_HYBRID = 6.66      # mixed absorption + weak emission onset
_HE_STAR = 18.17    # strong emission, He II 4686 ~7x continuum


def _line(lam, flux, l0, w=6.0):
    lam = np.asarray(lam)
    flux = np.asarray(flux)
    sel = (lam >= l0 - w) & (lam <= l0 + w)
    return float(flux[sel].min()), float(flux[sel].max())


# --- shape + provenance ------------------------------------------------------

def test_shape_and_continuum_normalized():
    d = stripped_spectrum_data(_HYBRID, 0.0)
    lam, flux = d["wavelength"], d["flux"]
    assert len(lam) == len(flux) > 100
    assert lam[0] < lam[-1]                      # ascending λ
    assert 3000 <= lam[0] <= 3010 and 8990 <= lam[-1] <= 9000
    assert d["continuum"] == 1.0
    assert d["feh_varies"] is False              # solar-only cube (matches binary.py)
    # Continuum-normalized: the bulk of the spectrum sits near 1 (median ~ continuum).
    assert 0.7 < float(np.median(flux)) < 1.3
    assert min(flux) >= 0.0


def test_snaps_to_binary_resolved_node():
    """Passing binary.py's resolved M_init lands on the exact spectrum node — the
    state<->spectrum consistency guarantee (no independent drift)."""
    st = b.stripped_star(6.5, 0.0)               # the /binary snap
    d = stripped_spectrum_data(st.m_init_msun, st.feh_snapped)
    assert d["minit"] == pytest.approx(st.m_init_msun, abs=1e-6)
    # And a raw midpoint snaps to a real grid node, never an interpolated in-between.
    d2 = stripped_spectrum_data(7.0, 0.0)
    minits = {m.m_init for m in b.available_models() if abs(m.grid_z - 0.014) < 1e-9}
    assert any(abs(d2["minit"] - m) < 1e-6 for m in minits)


# --- the measure-first gate, as a regression --------------------------------

def test_absorption_to_emission_sequence():
    """Götberg's thesis, measured through the runtime: He II 4686 runs from flat/absorption
    at the subdwarf end to strong emission at the He-star end, monotonically."""
    he = {}
    for m in (_SUBDWARF, _HYBRID, _HE_STAR):
        d = stripped_spectrum_data(m, 0.0)
        _, he_max = _line(d["wavelength"], d["flux"], 4686)
        he[m] = he_max
    # subdwarf: no emission (peak ~ continuum); He-star: strong emission (well above it).
    assert he[_SUBDWARF] <= 1.05
    assert he[_HE_STAR] >= 2.0
    # monotone rise along the sequence
    assert he[_SUBDWARF] < he[_HYBRID] < he[_HE_STAR]


def test_regime_labels_match_the_sequence():
    assert stripped_spectrum_data(_SUBDWARF, 0.0)["regime"] == "absorption"
    assert stripped_spectrum_data(_HE_STAR, 0.0)["regime"] == "emission"
    # display_max frames each: tight for absorption, tall for emission.
    assert stripped_spectrum_data(_SUBDWARF, 0.0)["display_max"] == pytest.approx(1.2, abs=0.05)
    assert stripped_spectrum_data(_HE_STAR, 0.0)["display_max"] > 3.0


def test_subdwarf_has_deep_balmer_absorption():
    """The low-mass end is an sdB-like subdwarf: Hα is a deep absorption line (well below
    the continuum), NOT the emission a WR shows — the honest subdwarf character."""
    d = stripped_spectrum_data(_SUBDWARF, 0.0)
    ha_min, _ = _line(d["wavelength"], d["flux"], 6563)
    assert ha_min < 0.7            # a real, deep Balmer absorption trough


# --- route -------------------------------------------------------------------

def test_route_payload():
    client = TestClient(app)
    r = client.get("/stripped_spectrum", params={"minit": _HE_STAR, "feh": 0.0})
    assert r.status_code == 200
    d = r.json()
    assert d["grid_name"] == "gotberg2018-stripped"
    assert d["regime"] == "emission"
    assert len(d["wavelength"]) == len(d["flux"])


def test_route_snap_always_and_invalid():
    client = TestClient(app)
    # off-grid mass snaps (no 422) — mirrors /binary's snap-always contract.
    assert client.get("/stripped_spectrum", params={"minit": 40.0}).status_code == 200
    # structurally invalid (mass <= 0) is a 422 (Query bound).
    assert client.get("/stripped_spectrum", params={"minit": 0.0}).status_code == 422
