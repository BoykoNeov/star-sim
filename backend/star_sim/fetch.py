"""`star-sim-fetch` — one entry point in front of the twenty-one fetch modules.

Every grid this app can show has a `fetch_*.py` that puts it under `data/`, and
until now the only way to find them was to read the README or list the package.
This is the catalogue as code: `star-sim-fetch` with no arguments prints every
fetcher, grouped by which of the two families it belongs to, and `star-sim-fetch
<name> [args…]` hands the rest of the command line to that module's `main()`.

    star-sim-fetch                              # the catalogue
    star-sim-fetch mist-baked --feh p000        # a module's own flags, untouched
    python -m star_sim.fetch_mist_baked --feh p000   # still works, unchanged

The table below is the only place a fetcher is named: the module is always
`fetch_` + the name with dashes turned back into underscores, and
`tests/test_fetch_framework.py` fails if the table and the package disagree in
either direction. A new fetcher is one row here plus its module.

There is deliberately no `star-sim-bake` twin. `backend/scripts/bake_*.py` are
host-side one-offs that live outside the installed package (`pyproject.toml`
packages `star_sim*` only), so no console script can resolve to them; giving them
one means moving them into the package, which is a bigger move than this step.
"""

from __future__ import annotations

import importlib
import sys

# name -> what it puts under data/.  Suffix "-baked" = this project's own pre-baked
# GitHub Release asset (small, one command); no suffix = the original path, which
# talks to somebody else's server and is usually much bigger.
_BAKED: dict[str, str] = {
    "mist-baked": "MIST parsed-track caches — the live provider's [Fe/H]×rotation grid",
    "mist-iso-baked": "MIST isochrone cubes — the cluster-isochrone HR overlay (/isochrone)",
    "posydon-baked": "POSYDON co-evolving binary tracks (/binary_track), all 8 metallicities",
    "koester-baked": "white-dwarf spectra (/wd_spectrum) — Koester DA spliced with TMAP",
    "powr-baked": "PoWR Wolf-Rayet wind-emission spectra (/wr_spectrum)",
    "gotberg-baked": "binary-stripped-star spectra (/stripped_spectrum)",
    "coelho-baked": "the [alpha/Fe] spectrum what-if cube (#alpha-toggle)",
    "bpass-baked": "the coeval-population cubes (/population, /population_hrd)",
    "helium-baked": "self-run MESA initial-helium (Y) runs — the /helium HR overlay",
    # ASCII "alpha", not the letter: this table is *printed*, and a Windows console
    # is cp1252, which has no Greek block. `test_the_catalogue_prints_on_a_windows
    # _console` is the gate — the em dashes and × below are fine, they are cp1252.
    "alpha-baked": "self-run MESA alpha-enhanced (equivalent-Z) runs — the /alpha HR overlay",
}
_RAW: dict[str, str] = {
    "mist": "MIST's own EEP tarballs, per [Fe/H] (~180 MB each) — the from-source path",
    "mist-iso": "MIST's ~6.7 GB isochrone tarball, baked down per metallicity",
    "mesa": "MESA `history.data` sample tracks — the second provider, MIST cross-validation",
    "koester": "Koester DA model spectra from SVO (the cool/mid WD cooling track)",
    "tmap": "TMAP hot post-AGB/CSPN spectra from SVO (the hot end of the WD splice)",
    "powr": "PoWR model tarballs (Galactic WNE/WNL/WC, more with --grids all)",
    "coelho": "Coelho (2014) [alpha/Fe] model spectra from SVO (~8-17 GB)",
    "filters": "SVO filter profiles for the observer's-view photometry",
    "gotberg": "validate a hand-downloaded Götberg (2018) grid tree (a manual handoff)",
    "posydon": "inspect a hand-downloaded POSYDON grid tarball (recon only)",
    "bpass": "the BPASS SSP-spectra HDF5 pair from Zenodo (--download) + schema recon",
}
FETCHERS: dict[str, str] = {**_BAKED, **_RAW}


def module_name(name: str) -> str:
    """"mist-iso-baked" -> "fetch_mist_iso_baked". The one naming rule."""
    return "fetch_" + name.replace("-", "_")


def _catalogue() -> None:
    print("usage: star-sim-fetch <name> [options]        (a name's own --help still works)\n")
    for title, table in (("pre-baked (fast: one HTTPS download from this repo's releases)", _BAKED),
                         ("from source (the original recipe: bigger, and someone else's server)", _RAW)):
        print(f"{title}:")
        for name, blurb in table.items():
            print(f"  {name:<16} {blurb}")
        print()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "--list"}:
        _catalogue()
        return 0
    name, rest = argv[0], argv[1:]
    if name not in FETCHERS:
        print(f"Unknown fetcher: {name!r}\n")
        _catalogue()
        return 1
    module = importlib.import_module(f"star_sim.{module_name(name)}")
    return module.main(rest)


if __name__ == "__main__":
    sys.exit(main())
