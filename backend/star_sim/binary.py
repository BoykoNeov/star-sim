"""Binary-stripped stars — the ~70% WR/subdwarf channel, as a sibling.

A star of initial mass ~2–18 M☉ in a close binary fills its Roche lobe near the end
of its main sequence (Case-B mass transfer); the companion strips the hydrogen
envelope, exposing a hot, compact, He-rich core that then burns helium. This object
is the missing link that unifies subdwarfs (low mass) and Wolf–Rayet stars (high
mass) as one sequence of stripped-envelope stars (Götberg+2018). The *dominant*
observed channel for stripped/WR stars is binary stripping (~70%, Sana+2012,
Shenar+2020), so this retires the caveat the single-star WR demo keeps writing —
"a single-star WR shows the minority channel."

Like `supernova.py`, `structure.py`, `spectra.py` and `lane_emden.py`, this is a
**sibling to the StellarState spine (§3), not a provider**. It imports only
`state.StellarState` (which it emits) and never touches `StellarStateProvider`: a
binary product cannot go through that single-star interface without discarding the
companion or mutating the dataclass (both §3 violations). `/binary` bypasses
`PROVIDER` exactly like `/structure` and `/supernova`.

What it does: reads the committed Götberg 2018 stripped-star parameter table (its own
CSV parser), **snaps** a request to the nearest grid model in (Z, initial mass) —
never interpolates (§6: raw grid rows have no cross-model alignment) — and returns a
`StellarState` for the stripped star plus a few §3-clean routing scalars (the current
stripped mass `M_strip`, the snapped `M_init`/Z, and the eligible progenitor-mass
range the frontend gates its toggle on). The stripped star is a hot He object — a
perfectly ordinary single-star `StellarState` the existing 3D/HR/comp/spectrum
consumers render with zero consumer changes.

Two honest caveats (owned by the frontend caption, Chunk 2):
  * The grid is ONE representative state per stripped star — the long-lived
    core-He-burning stage ("halfway through", X_He,c=0.5) — not a full time-track.
    Perfect for a snap-to-model endpoint; it is a "here is the product" view, not an
    animated in-spiral. Hence `age_yr`/`eep` are a documented sentinel, not age zero.
  * The companion is not modeled — we show the stripped star alone; the caption names
    the companion as the *cause* without drawing it (that is path (b), out of scope).

Provenance (two-source — see docs/plans/stripped-consort-unveiling.md and the header of
star_sim/data/gotberg_z014.csv): the spectra/SEDs are on VizieR (gitignored under
data/gotberg_stripped/); these *structural parameters* are the paper's Table 1,
transcribed and then VERIFIED against the on-disk SEDs (≤0.07 dex, all 23 solar rows).
That check is a durable regression in test_binary.py::test_table_matches_seds.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

from .state import StellarState

# Götberg 2018's reference solar metallicity. The grid's four Z buckets map to [Fe/H]
# by [Fe/H] = log10(Z / GOTBERG_SOLAR_Z): Z=0.014→0, 0.006→−0.37, 0.002→−0.85,
# 0.0002→−1.85 — the same scale the rest of the sim reports [Fe/H] on.
GOTBERG_SOLAR_Z = 0.014

# The grid is ONE representative state per stripped star (the long-lived core-He-burning
# stage), not a time-track — so age/EEP are a documented sentinel, NOT age zero. Nothing
# consumes them meaningfully (the age slider is repurposed / disabled in stripped-mode,
# Chunk 2); they exist only to satisfy the StellarState contract.
REPRESENTATIVE_AGE_YR = 0.0
REPRESENTATIVE_EEP = 0.0

# A request whose [Fe/H] is farther than this (dex) from the nearest grid Z is flagged
# `feh_snapped_far` (an honest in-band note; the frontend decides note-vs-hide). With
# only the solar bucket on disk, everything off ~solar is far; the threshold tightens
# automatically as the 3 non-solar Z tables land (half the gap to the next node).
_FEH_FAR_DEX = 0.25

# star_sim/binary.py -> star_sim/data/  (the committed tables live *inside* the package,
# unlike the gitignored grids under the repo-root data/ — these are tiny, verified, and
# versioned with the code).
_DATA_DIR = Path(__file__).resolve().parent / "data"

# The committed per-Z parameter tables: (filename, grid Z). SOLAR-ONLY for now; the three
# non-solar Z tables (Z=0.006 / 0.002 / 0.0002) each append here + a dropped-in CSV when
# acquired (ar5iv truncates before Appendix B — a scoped follow-up). No other change is
# needed: the snap already keys on Z, and [Fe/H] is derived from Z.
_GRID_TABLES: list[tuple[str, float]] = [
    ("gotberg_z014.csv", 0.014),
]


class BinaryDataMissing(RuntimeError):
    """The committed Götberg parameter table(s) could not be read.

    Committed data, so this should never fire in a normal checkout — it guards the
    degenerate case (the CSV deleted / unreadable), and the API maps it to a 503 with
    an actionable hint, exactly like a missing baked spectrum or MESA profile."""


_MISSING_HINT = (
    "No Götberg stripped-star parameter tables found under {data_dir}. These are "
    "committed to the repo (star_sim/data/gotberg_z*.csv); if missing, restore them "
    "from version control (see docs/plans/stripped-consort-unveiling.md)."
)


@dataclass(frozen=True)
class _StrippedModel:
    """One parsed grid row — a snap node. Column semantics are the CSV header's."""

    grid_z: float
    m_init: float      # progenitor initial mass / M_sun (the snap key, the slider's meaning)
    m_strip: float     # the stripped star's CURRENT mass / M_sun
    teff_kK: float     # spectroscopic Teff (NOT T_star — see the CSV header gotcha)
    logL: float        # log10(L / L_sun)
    logg: float        # log10 surface gravity, cgs
    r_eff: float       # radius / R_sun
    x_h: float         # surface H mass fraction (rounded)
    x_he: float        # surface He mass fraction (rounded)

    @property
    def feh(self) -> float:
        return math.log10(self.grid_z / GOTBERG_SOLAR_Z)


@dataclass
class StrippedStar:
    """A stripped-star result: the §3-clean `StellarState` plus routing scalars.

    The `state` is what every existing consumer eats (3D/HR/comp/spectrum) — a perfectly
    ordinary hot single-star state. The scalars are things that have NO home on
    StellarState (which is single-star and carries only `mass_init`), mirroring how
    `EndgameResult` carries `final_mass_msun` off the state: the CURRENT stripped mass,
    the true snapped grid node, and the eligible-range / snapped-far honesty flags the
    frontend gates its toggle and caption on."""

    state: StellarState
    m_strip_msun: float        # CURRENT mass (StellarState has only mass_init — audit
                               # scale.js/classify.js in Chunk 2 to read THIS, not mass_init)
    m_init_msun: float         # snapped progenitor initial mass (a true grid node)
    grid_z: float              # snapped grid metallicity
    feh_snapped: float         # log10(grid_z / GOTBERG_SOLAR_Z)
    mass_snapped_far: bool     # requested mass outside the eligible progenitor range
    feh_snapped_far: bool      # requested [Fe/H] far (> _FEH_FAR_DEX) from nearest grid Z
    mass_grid_min: float       # eligible progenitor-mass range at the snapped Z (UI gate)
    mass_grid_max: float


# --- parse (own CSV reader — sibling discipline) -----------------------------

_GRID_CACHE: list[_StrippedModel] | None = None


def _parse_table(path: Path, grid_z: float) -> list[_StrippedModel]:
    """Parse one committed Götberg CSV. Skips `#` provenance lines and blanks (the
    header comment carries the ≤0.07-dex verification note). Own parser, no dependency
    on any provider — a clean §3 sibling."""
    models: list[_StrippedModel] = []
    with open(path, newline="") as fh:
        reader = csv.reader(row for row in fh if row.strip() and not row.lstrip().startswith("#"))
        for row in reader:
            if len(row) != 8:
                raise BinaryDataMissing(f"{path}: expected 8 columns, got {len(row)}: {row!r}")
            m_init, m_strip, teff_kK, logL, logg, r_eff, x_h, x_he = (float(v) for v in row)
            models.append(_StrippedModel(
                grid_z=grid_z, m_init=m_init, m_strip=m_strip, teff_kK=teff_kK,
                logL=logL, logg=logg, r_eff=r_eff, x_h=x_h, x_he=x_he,
            ))
    return models


def _load_grid() -> list[_StrippedModel]:
    """All grid models across every committed Z table (lazy, cached process-wide)."""
    global _GRID_CACHE
    if _GRID_CACHE is not None:
        return _GRID_CACHE
    models: list[_StrippedModel] = []
    for filename, grid_z in _GRID_TABLES:
        path = _DATA_DIR / filename
        if path.is_file():
            models.extend(_parse_table(path, grid_z))
    if not models:
        raise BinaryDataMissing(_MISSING_HINT.format(data_dir=_DATA_DIR))
    _GRID_CACHE = models
    return models


def available_models() -> list[_StrippedModel]:
    """All parsed grid nodes (for tests / introspection)."""
    return list(_load_grid())


def eligible_mass_range(feh: float = 0.0) -> tuple[float, float]:
    """The (min, max) progenitor initial mass on the grid at the Z nearest `feh`. The
    frontend gates its stripped-mode toggle on this (hide/grey outside it)."""
    grid = _load_grid()
    z = _snap_grid_z(grid, feh)
    masses = [m.m_init for m in grid if m.grid_z == z]
    return (min(masses), max(masses))


# --- snap (nearest node in Z, then initial mass — never interpolate, §6) -----

def _snap_grid_z(grid: list[_StrippedModel], feh: float) -> float:
    """Nearest grid Z to the requested [Fe/H] (compared in [Fe/H] space)."""
    zs = sorted({m.grid_z for m in grid})
    return min(zs, key=lambda z: abs(math.log10(z / GOTBERG_SOLAR_Z) - feh))


def stripped_star(mass: float, feh: float = 0.0) -> StrippedStar:
    """(progenitor initial mass, [Fe/H]) -> the stripped He-star it becomes in a close
    binary. Snaps Z→nearest grid metallicity, then mass→nearest grid initial mass at
    that Z, and reports the TRUE snapped node (§6 honesty — no interpolation).

    The composition mapping bakes in the two CSV-header gotchas: Z_surf is the grid Z
    (not 1−X−Y, which the 2-dp rounding would zero out), and the rounded (X_H, X_He)
    pair is renormalized to close at 1−Z — the He-rich surface is the headline. The
    core is taken as a He-burning core by construction (X_core≈0), honest for the
    "halfway through core-He burning" state the grid represents."""
    grid = _load_grid()

    z = _snap_grid_z(grid, feh)
    at_z = [m for m in grid if m.grid_z == z]
    node = min(at_z, key=lambda m: abs(m.m_init - mass))

    masses = [m.m_init for m in at_z]
    mass_min, mass_max = min(masses), max(masses)

    # Surface composition: Z_surf = grid Z (the rounding gotcha), renormalize (X_H, X_He)
    # to close at 1 − Z.
    s = node.x_h + node.x_he
    x_surf = node.x_h / s * (1.0 - z)
    y_surf = node.x_he / s * (1.0 - z)

    state = StellarState(
        age_yr=REPRESENTATIVE_AGE_YR,
        eep=REPRESENTATIVE_EEP,
        phase="stripped-envelope star",
        mass_init_msun=node.m_init,
        feh_init=node.feh,
        L_lsun=10.0 ** node.logL,
        Teff_K=node.teff_kK * 1000.0,   # spectroscopic Teff, NOT T_star (evolutionary gap)
        R_rsun=node.r_eff,
        logg=node.logg,
        X_surf=x_surf,
        Y_surf=y_surf,
        Z_surf=z,
        # A He-burning core by construction ("halfway through core-He burning"): H spent,
        # the rest is He + the grid metals. Honest given the table carries no core data.
        X_core=0.0,
        Y_core=1.0 - z,
        Z_core=z,
        # No wind Ṁ in the verified 8-column table -> None (the SED free-free tail is a
        # Chunk-2 decision that must be measured for this fast-wind regime, not assumed).
        mdot_msun_yr=None,
    )

    feh_snapped = node.feh
    return StrippedStar(
        state=state,
        m_strip_msun=node.m_strip,
        m_init_msun=node.m_init,
        grid_z=z,
        feh_snapped=feh_snapped,
        mass_snapped_far=(mass < mass_min - 1e-9 or mass > mass_max + 1e-9),
        feh_snapped_far=(abs(feh - feh_snapped) > _FEH_FAR_DEX),
        mass_grid_min=mass_min,
        mass_grid_max=mass_max,
    )


def stripped_star_payload(mass: float, feh: float = 0.0) -> dict:
    """JSON-friendly `/binary` payload: the StellarState (exact §3 shape) + the routing
    scalars flattened alongside it (mirroring how `/supernova` serves its scalars next
    to the states). The frontend reads `state` for the consumers and the scalars for the
    gate/caption/current-mass."""
    from dataclasses import asdict

    result = stripped_star(mass, feh)
    return {
        "state": asdict(result.state),
        "m_strip_msun": result.m_strip_msun,
        "m_init_msun": result.m_init_msun,
        "grid_z": result.grid_z,
        "feh_snapped": result.feh_snapped,
        "mass_snapped_far": result.mass_snapped_far,
        "feh_snapped_far": result.feh_snapped_far,
        "mass_grid_min": result.mass_grid_min,
        "mass_grid_max": result.mass_grid_max,
    }
