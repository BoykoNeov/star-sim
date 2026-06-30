"""§10 sanity checks for the Wolf-Rayet spectrum panel (endgame Chunk 7).

The mirror of test_wd_spectra.py, for the THIRD spectrum sibling `/wr_spectrum` (the
PoWR wind-emission cube). Two layers:

* Always-on (no baked cube needed): the route contract — the generous `Query` bounds
  reject absurd inputs with 422, a 250 kK stripped core does NOT 422 (it routes to the
  honest off-grid frame), and a missing cube surfaces a clean 503. These pin the API a
  fresh checkout still has.

* Data-gated (`requires_wr_spectra_data`): the mapping + emission physics, **measured
  through the runtime path** (`wr_spectrum_data()` → the PoWR (T*, Rt) snap), NOT copied
  from raw grid numbers. The robust outcomes are pinned (the recipe §7a gate findings):
    - the cool, hydrogen-rich WNh ENTRY maps in-grid → a real emission spectrum.
    - the hot, compact stripped core (Teff 200+ kK) is OFF every PoWR model → no model
      (the evolutionary-vs-spectroscopic Teff gap — MIST's T* is hotter/denser-wind than
      any observed WR PoWR was tuned to).
    - the subtype is read from the surface composition: WC (carbon surfaced) / WNL
      (hydrogen present) / WNE (hydrogen-free).
    - the served spectrum is EMISSION (continuum-normalized, lines stand ABOVE 1).
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from star_sim import spectra
from star_sim.api import app
from star_sim.spectra import SpectraDataMissing, wr_spectrum_data

from .conftest import requires_wr_spectra_data

client = TestClient(app)

# A representative WNh entry (the in-grid regime) and a stripped WC core (off-grid),
# taken from the measured MIST WR locus (recipe §7a): a 60 M☉ solar star's φ9 sub-track.
# Keys are the /wr_spectrum QUERY names (xsurf/…); `_direct` maps them to the runtime's
# underscored kwargs for a direct (non-HTTP) call.
ENTRY = dict(teff=32300, lum=10 ** 6.04, xsurf=0.28, ysurf=0.71, zsurf=0.016, feh=0.0)
STRIPPED = dict(teff=230000, lum=10 ** 6.04, xsurf=0.0, ysurf=0.13, zsurf=0.866, feh=0.0)


def _direct(d: dict) -> dict:
    """Call wr_spectrum_data with a query-name dict (xsurf→x_surf, …)."""
    return wr_spectrum_data(d["teff"], d["lum"], d["xsurf"], d["ysurf"], d["zsurf"],
                            d.get("feh", 0.0))


# --- always-on route contract (no baked cube needed) -------------------------

@pytest.mark.parametrize("params", [
    {**ENTRY, "teff": 500},                    # absurdly cool
    {**ENTRY, "lum": 0},                       # non-positive luminosity
    {**ENTRY, "xsurf": 1.5},                   # mass fraction > 1
    {**ENTRY, "feh": 5},                       # absurd metallicity
])
def test_wr_spectrum_out_of_range_is_422(params):
    assert client.get("/wr_spectrum", params=params).status_code == 422


def test_wr_spectrum_hot_stripped_core_does_not_422():
    """A 250 kK stripped WR core is far hotter than any PoWR model, but the wide `Query`
    bound keeps it from a 422 — it routes to the honest off-grid frame. 200 if baked
    (regime 'none'), 503 if not — never 422."""
    r = client.get("/wr_spectrum", params={**STRIPPED, "teff": 250000})
    assert r.status_code in (200, 503), r.status_code


def test_wr_spectrum_not_baked_is_503(tmp_path, monkeypatch):
    """If the WR cube hasn't been baked, /wr_spectrum returns a clean 503 (actionable),
    not a 500 — the app stays up; only this panel is unavailable until the bake."""
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)   # empty dir
    monkeypatch.setattr(spectra, "_WR_CACHE", None)             # force a reload
    r = client.get("/wr_spectrum", params=ENTRY)
    assert r.status_code == 503
    assert "wr" in r.json()["detail"].lower() or "powr" in r.json()["detail"].lower()


def test_wr_spectrum_data_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(spectra, "SPECTRA_DATA_DIR", tmp_path)
    monkeypatch.setattr(spectra, "_WR_CACHE", None)
    with pytest.raises(SpectraDataMissing):
        _direct(ENTRY)


# --- data-gated: the mapping + emission physics ------------------------------

@requires_wr_spectra_data
def test_wr_spectrum_endpoint_well_formed():
    r = client.get("/wr_spectrum", params=ENTRY)
    assert r.status_code == 200
    d = r.json()
    assert len(d["wavelength"]) == len(d["flux"]) > 100
    assert d["regime"] in ("WR", "none")
    assert d["subtype"] in ("WNE", "WNL", "WC")
    assert d["feh_varies"] is False
    # shares the other cubes' 3000–9000 Å window so the panel x-axis lines up
    assert d["wavelength"][0] > 2999 and d["wavelength"][-1] < 9001


@requires_wr_spectra_data
def test_wnh_entry_maps_in_grid():
    """The cool, hydrogen-rich WNh entry is the part the gate found in-grid → a real
    PoWR emission spectrum (regime 'WR', the H-rich WNL grid)."""
    d = _direct(ENTRY)
    assert d["regime"] == "WR"
    assert d["off_grid"] is False
    assert d["subtype"] == "WNL"            # hydrogen present → WNL


@requires_wr_spectra_data
def test_stripped_hot_core_is_off_grid_no_model():
    """The hot, compact stripped core (Teff 200+ kK) is hotter/denser-wind than any
    PoWR model — the evolutionary-vs-spectroscopic Teff gap → honest no-model frame."""
    d = _direct(STRIPPED)
    assert d["regime"] == "none"
    assert d["off_grid"] is True
    assert d["teff_requested"] > d["teff_max"] or "wind" in d["off_reason"]


@requires_wr_spectra_data
def test_subtype_read_from_surface_composition():
    """WC when carbon/oxygen has surfaced, WNE when hydrogen is gone, WNL when it isn't —
    the WN→WC stripping story told by line SPECIES (the gate's 'species not strength')."""
    wc = wr_spectrum_data(60000, 10 ** 5.6, 0.0, 0.2, 0.7)
    assert wc["subtype"] == "WC"
    wne = wr_spectrum_data(60000, 10 ** 5.6, 0.0, 0.95, 0.02)
    assert wne["subtype"] == "WNE"
    wnl = wr_spectrum_data(45000, 10 ** 5.6, 0.2, 0.75, 0.02)
    assert wnl["subtype"] == "WNL"


@requires_wr_spectra_data
def test_in_grid_spectrum_is_emission_lines_above_continuum():
    """A WR spectrum is wind EMISSION: continuum-normalized, the lines stand ABOVE the
    continuum (≈1), unlike the absorption notches of the other panels. So the peak is
    well above 1 and the median sits near the continuum."""
    d = _direct(ENTRY)
    assert d["regime"] == "WR"
    flux = np.array(d["flux"])
    assert flux.max() > 1.3                 # at least one real emission line
    assert 0.7 < np.median(flux) < 1.4      # the bulk is continuum near 1
    assert d["display_max"] >= flux.max() * 0.99 or d["display_max"] == 12.0


@requires_wr_spectra_data
def test_metallicity_selects_a_grid_and_reports_it():
    """[Fe/H] snaps to the nearest available metallicity grid; the served spectrum
    reports which grid (z_grid, metal) it came from so the panel can label it honestly.
    (Galactic-only cube → always 'gal'; LMC/SMC widen this in a later data re-bake.)"""
    d = _direct({**ENTRY, "feh": -0.7})
    assert d["metal"] in ("gal", "lmc", "smc")
    assert d["z_grid"] > 0
