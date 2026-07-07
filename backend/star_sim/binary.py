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
    p_init: float      # INITIAL orbital period / days (RLOF-onset approx; the Roche-geometry
                       # separation via Kepler, path (b) Chunk 3 — see the CSV header)

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
            if len(row) != 9:
                raise BinaryDataMissing(f"{path}: expected 9 columns, got {len(row)}: {row!r}")
            m_init, m_strip, teff_kK, logL, logg, r_eff, x_h, x_he, p_init = (float(v) for v in row)
            models.append(_StrippedModel(
                grid_z=grid_z, m_init=m_init, m_strip=m_strip, teff_kK=teff_kK,
                logL=logL, logg=logg, r_eff=r_eff, x_h=x_h, x_he=x_he, p_init=p_init,
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


# --- path (b): the companion (accretor) — the two-star co-evolution view ------

# The Götberg grid's fixed companion mass ratio. Every model is labelled
# `M1_<Minit>q0.8P<P>Z<Z>_vinf1.5` (see data/gotberg_stripped/ReadMe), i.e. the companion
# (secondary) starts at M2_init = 0.8 * M_init. This is the ONE number path (b) needs
# from the grid to place the companion: the accretor is then an ordinary single star at
# that known mass, produced by the single-star PROVIDER with ZERO accretion-efficiency
# guess. See docs/plans/stripped-consort-unveiling.md (path (b)).
COMPANION_MASS_RATIO = 0.8


def companion_init_mass(m_init: float) -> float:
    """The companion's initial mass M2_init = 0.8 * M_init (the grid's fixed q=0.8)."""
    return COMPANION_MASS_RATIO * m_init


# --- path (b) Chunk 3: the Roche-lobe / mass-transfer geometry ----------------
#
# A genuinely new two-star render: the ORBITAL-PLANE cross-section at the moment of
# Case-B mass transfer — the two Roche lobes meeting at L1, the donor filling its lobe
# and streaming through L1 onto the lighter companion. This is the CAUSAL story behind
# the stripped star, and it is a DIFFERENT evolutionary snapshot than the marker: here
# the donor is still the MORE massive star (M1 > M2, it overflows), whereas the other
# panels show the POST-strip state where the donor is the lighter object and the mass
# ratio has reversed (mass_ratio_final > 1). The render's caption owns that reversal (it
# is the same convention-mismatch class as the q-bug that bit path (b) Chunk 1).
#
# The geometry is HONEST, not schematic: the Roche-lobe SHAPE depends only on the mass
# ratio q (a known constant, 0.8), and the physical SCALE (the separation a) comes from
# Kepler's third law applied to the real (M1, M2, P_init) of the snapped grid node. The
# ONE soft spot (caption-owned) is that P_init is the *initial* period used as the
# RLOF-onset approximation. The mass-transfer STREAM is the only illustrative element (a
# schematic Coriolis-deflected arc from L1 toward the accretor), labelled as such.
#
# roche_geometry is a PURE sibling function (no PROVIDER): it needs only q and the node's
# (M_init, P_init) — pure orbital mechanics, no stellar model. It is folded into the
# /binary_pair payload (the companion sphere size the frontend draws comes from that
# route's real modelled companion state), so the Roche panel appears exactly when the
# "Show companion" reveal is on.

# Roche-lobe outline resolution (points per lobe) and the marching bounds. 160 angular
# samples give a smooth teardrop; the cusp at L1 lands on a sample by construction (the
# axis angle θ=0/π is included).
_ROCHE_LOBE_SAMPLES = 160

# Solar-unit Kepler: a³[AU] = M_tot[M_sun] · P²[yr], and 1 AU = 215.032 R_sun. So the
# separation follows from the node's masses + initial period with no unit soup.
_AU_PER_RSUN = 215.032
_DAYS_PER_YEAR = 365.25


def _roche_potential(x: float, y: float, q: float, x_cm: float) -> float:
    """Dimensionless Roche (Kopal) potential in the co-rotating frame, separation a=1,
    G·M1=1. The donor (M1) sits at the origin, the companion (M2) at (1, 0); q = M2/M1
    and x_cm = q/(1+q) is the centre of mass. More negative = deeper in a well; the value
    at L1 is the critical potential whose contour is the touching figure-of-eight."""
    r1 = math.hypot(x, y)
    r2 = math.hypot(x - 1.0, y)
    r1 = max(r1, 1e-9)
    r2 = max(r2, 1e-9)
    return -1.0 / r1 - q / r2 - 0.5 * (1.0 + q) * ((x - x_cm) ** 2 + y ** 2)


def _dphi_dx_axis(x: float, q: float, x_cm: float) -> float:
    """dΦ/dx along y=0 — its roots on the three axis intervals are the collinear Lagrange
    points L3 (x<0), L1 (0<x<1), L2 (x>1)."""
    return (x / abs(x) ** 3
            + q * (x - 1.0) / abs(x - 1.0) ** 3
            - (1.0 + q) * (x - x_cm))


def _bisect_axis(lo: float, hi: float, q: float, x_cm: float) -> float:
    """Bisect for a zero of dΦ/dx on (lo, hi) — the interval brackets exactly one L-point."""
    flo = _dphi_dx_axis(lo, q, x_cm)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        fmid = _dphi_dx_axis(mid, q, x_cm)
        if flo * fmid <= 0.0:
            hi = mid
        else:
            lo, flo = mid, fmid
    return 0.5 * (lo + hi)


def _trace_lobe(cx: float, q: float, x_cm: float, crit: float,
                 n: int = _ROCHE_LOBE_SAMPLES) -> list[list[float]]:
    """The critical-equipotential outline around a star centred at (cx, 0): for each angle,
    march radially out from the centre and stop at the lobe boundary, which is the FIRST of
    either (a) Φ crossing up to the critical value `crit` — the ordinary case, most rays —
    or (b) Φ turning over (ceasing to rise) below crit. Case (b) is essential on the ray
    pointing at the companion: there Φ is TANGENT to crit at L1 (the saddle is a maximum
    along the axis, not a transversal crossing), so a strict `≥ crit` test would miss it and
    the march would leak across L1 into the companion's well. Detecting the turnover pins
    the cusp at L1, so the two lobes kiss there by construction.

    `n` trades outline resolution for speed: the CSV single-node path (`roche_geometry`)
    uses the full `_ROCHE_LOBE_SAMPLES` (one call per request); the POSYDON per-step path
    (`track_roche_geometry`) decimates it (up to ~300 calls per track fetch — see there)."""
    pts: list[list[float]] = []
    for i in range(n):
        th = 2.0 * math.pi * i / n
        ct, st = math.cos(th), math.sin(th)
        prev_r = 1e-4
        prev_phi = _roche_potential(cx + prev_r * ct, prev_r * st, q, x_cm)
        boundary = 1.5
        r = 0.02
        while r < 1.5:
            phi = _roche_potential(cx + r * ct, r * st, q, x_cm)
            if phi >= crit:                        # ordinary crossing — bisect (prev_r, r)
                lo, hi = prev_r, r
                for _ in range(48):
                    rm = 0.5 * (lo + hi)
                    if _roche_potential(cx + rm * ct, rm * st, q, x_cm) >= crit:
                        hi = rm
                    else:
                        lo = rm
                boundary = 0.5 * (lo + hi)
                break
            if phi < prev_phi - 1e-12:             # turned over below crit — the L1 tangent ray
                boundary = prev_r
                break
            prev_r, prev_phi = r, phi
            r *= 1.05
        pts.append([cx + boundary * ct, boundary * st])
    pts.append(pts[0][:])                          # close the outline
    return pts


def _eggleton_rl_over_a(q_donor: float) -> float:
    """Eggleton (1983) volume-equivalent Roche-lobe radius R_L/a for a star with mass
    ratio q_donor = M_this / M_other. Used for the donor's filled-lobe size scalar."""
    c = q_donor ** (1.0 / 3.0)
    return 0.49 * c * c / (0.6 * c * c + math.log(1.0 + c))


def _stream_path(l1x: float, q: float, x_cm: float) -> list[list[float]]:
    """A schematic mass-transfer stream from L1 toward the accretor — a Coriolis-deflected
    arc (it leads the companion, +y in the co-rotating frame), NOT a ballistic integration.
    The lobes and L-points are honest physics; the stream is illustrative (caption-owned)."""
    pts: list[list[float]] = []
    steps = 24
    for i in range(steps + 1):
        t = i / steps
        x = l1x + (1.0 - l1x) * t
        # A parabolic bulge to the leading side, fading to zero as it reaches the companion.
        y = 0.16 * (1.0 - l1x) * math.sin(math.pi * t) * (1.0 - 0.35 * t)
        pts.append([x, y])
    return pts


def _roche_geometry_from_params(q: float, m1: float, m2: float, separation_rsun: float,
                                 n_samples: int = _ROCHE_LOBE_SAMPLES) -> dict:
    """The pure orbital-mechanics engine behind `roche_geometry`: given ONLY the mass
    ratio q = M2/M1, the two masses (for the caption/scalars — they don't affect the
    dimensionless shape) and the physical separation, return the orbital-plane Roche-lobe
    cross-section (donor at the origin, companion at (1, 0), units of separation a).

    Factored out so a SECOND caller can drive it from a real co-evolving binary's
    per-step q(t)/a(t) (`track_roche_geometry`, path (b) Chunk 4b) instead of this
    module's single CSV-node snapshot (`roche_geometry`, Chunk 3) — the shape math is
    identical, only where q/a come from differs. `n_samples` trades lobe-outline
    resolution for speed (see `_trace_lobe`)."""
    x_cm = q / (1.0 + q)

    # Collinear Lagrange points (roots of dΦ/dx on the three axis intervals).
    l1x = _bisect_axis(1e-4, 1.0 - 1e-4, q, x_cm)
    l2x = _bisect_axis(1.0 + 1e-4, 3.0, q, x_cm)
    l3x = _bisect_axis(-3.0, -1e-4, q, x_cm)
    crit = _roche_potential(l1x, 0.0, q, x_cm)     # the touching figure-of-eight potential

    donor_lobe = _trace_lobe(0.0, q, x_cm, crit, n_samples)
    companion_lobe = _trace_lobe(1.0, q, x_cm, crit, n_samples)

    # The donor fills its Roche lobe at RLOF — its bloated size is the volume-equivalent
    # Eggleton radius (q_donor = M1/M2), a scalar for the caption ("swells to ~R R☉").
    donor_rl_a = _eggleton_rl_over_a(m1 / m2) if m2 > 0 else 0.0

    return {
        "q": q,
        "m_donor_msun": m1,
        "m_companion_msun": m2,
        "separation_rsun": separation_rsun,
        "x_cm": x_cm,
        "l1_x": l1x,
        "l2_x": l2x,
        "l3_x": l3x,
        "donor_lobe": donor_lobe,
        "companion_lobe": companion_lobe,
        "donor_roche_radius_rsun": donor_rl_a * separation_rsun,
        "stream": _stream_path(l1x, q, x_cm),
    }


def roche_geometry(mass: float, feh: float = 0.0) -> dict:
    """The mass-transfer geometry for the snapped grid node — pure orbital mechanics, no
    provider. Snaps (Z, M_init) exactly like `stripped_star` (state↔geometry consistency),
    reads the node's initial period, and returns the orbital-plane Roche-lobe cross-section
    at Case-B RLOF: the two lobes, the collinear Lagrange points, the separation from
    Kepler, and a schematic stream. All coordinates are in units of the separation a (donor
    at the origin, companion at (1, 0)); `separation_rsun` carries the physical scale.

    Mass ordering AT RLOF (the caption must own the reversal vs the other panels): the
    DONOR is M1 = the snapped M_init, the HEAVIER star, overflowing its (bigger) lobe onto
    the LIGHTER companion M2 = 0.8·M1. In the post-strip state shown elsewhere the donor is
    the lighter object and the ratio has reversed."""
    grid = _load_grid()
    z = _snap_grid_z(grid, feh)
    at_z = [m for m in grid if m.grid_z == z]
    node = min(at_z, key=lambda m: abs(m.m_init - mass))

    m1 = node.m_init                       # donor at RLOF (the heavier star)
    m2 = COMPANION_MASS_RATIO * m1         # companion / accretor (lighter)
    q = COMPANION_MASS_RATIO               # M2 / M1 = 0.8

    # Separation from Kepler (solar units): a³[AU] = M_tot · P²[yr].
    p_yr = node.p_init / _DAYS_PER_YEAR
    a_au = (m1 + m2) * p_yr * p_yr
    a_au = a_au ** (1.0 / 3.0)
    a_rsun = a_au * _AU_PER_RSUN

    geo = _roche_geometry_from_params(q, m1, m2, a_rsun)
    geo["period_init_d"] = node.p_init
    geo["separation_au"] = a_au
    return geo


# Angular resolution for the POSYDON per-step geometry (path (b) Chunk 4b): this runs
# once PER STEP in a track fetch (up to ~300 calls), not once per request like the CSV
# snapshot above, so it trades outline smoothness for a sub-second track fetch. Measured
# (2026-07-07): ~2ms/step at 40 samples vs ~14ms/step at the full 160 — the movie doesn't
# need hero-shot lobe smoothness, the single Chunk-3 snapshot does.
_TRACK_ROCHE_SAMPLES = 40


def track_roche_geometry(steps: list, n_samples: int = _TRACK_ROCHE_SAMPLES) -> list[dict | None]:
    """Per-step Roche-lobe geometry for a POSYDON co-evolving binary track (path (b)
    Chunk 4b) — the Chunk-3 panel's payoff paid off twice: instead of one CSV-node
    snapshot at a fixed q=0.8, each step gets its OWN geometry from the track's REAL
    q(t) = m2_current/m1_current and separation(t), so the lobes visibly reshape as the
    orbit widens and (during RLOF) the donor's lobe tightens around it. Donor (star_1)
    always sits at the origin and companion (star_2) at (1, 0) — fixed by IDENTITY, not
    by which one currently masses more, so the reversal reads as the lobes swapping
    size, never as a relabeling (the Chunk-1/Chunk-3 convention-mismatch class of bug).

    Takes `posydon.BinaryStep` instances (duck-typed here, so this module stays free to
    import from — `posydon.py` is the one that imports `track_roche_geometry` FROM here,
    mirroring the `structure.py` → `lane_emden.solve_lane_emden` precedent of one pure
    sibling calling another) via their `m1_current_msun`/`m2_current_msun`/
    `separation_rsun` fields. Returns `None` for any step whose masses/separation can't
    form a geometry (defensive; `binary_track` already truncates before a merger row
    could go non-finite, so this should not fire in practice on the current bake)."""
    out: list[dict | None] = []
    for s in steps:
        m1, m2, a = s.m1_current_msun, s.m2_current_msun, s.separation_rsun
        if not (m1 and m2 and m1 > 0 and m2 > 0 and a and a > 0):
            out.append(None)
            continue
        out.append(_roche_geometry_from_params(m2 / m1, m1, m2, a, n_samples))
    return out


def binary_pair_payload(mass: float, feh: float, companion_state: StellarState,
                        elapsed_age_yr: float) -> dict:
    """The `/binary_pair` payload: the stripped DONOR (verbatim `/binary` shape) plus a
    `companion` block — the two-star Algol co-evolution view, path (b).

    `binary.py` stays a pure §3 sibling: it never fetches the companion itself (that needs
    the single-star `StellarStateProvider`, which a sibling must not import). The route
    computes the companion `StellarState` via `PROVIDER.state_at(0.8*M_init, feh, elapsed)`
    and hands it in here; this function only assembles the payload and the transfer scalars.

    The companion is the ACCRETOR of the Algol system: it starts LESS massive than the
    donor (q=0.8) but ends up MORE massive than the stripped donor product — the
    mass-ratio *reversal* (`mass_ratio_final < 1`) that is the intellectual payoff. The
    baseline is deliberately NON-conservative — the companion stays at its known M2_init:
    the envelope the donor loses is dominated by wind + non-conservative RLOF loss, and
    critically-rotating accretors reject most of it, so attributing that mass to the
    companion would stack two guesses (an accretion efficiency AND the ΔM attribution)
    onto a headline that is already visible without either. Any accretion boost is a
    labeled refinement, not the baseline."""
    from dataclasses import asdict

    payload = stripped_star_payload(mass, feh)     # the donor, exactly as /binary serves it
    m_init = payload["m_init_msun"]                # the snapped node (state↔companion consistency)
    m_strip = payload["m_strip_msun"]
    m2 = companion_init_mass(m_init)
    # Both ratios are COMPANION ÷ DONOR (one convention, so the reversal reads as crossing 1.0):
    # before RLOF the companion is 0.8× the donor (< 1, lighter); after stripping it is
    # M2 / M_strip > 1 (heavier). That single number crossing 1 IS the Algol reversal.
    payload["companion"] = {
        "state": asdict(companion_state),
        "mass_msun": m2,                            # M2_init = current mass (non-conservative baseline)
        "mass_ratio_init": COMPANION_MASS_RATIO,    # M2_init / M1_init = 0.8 (companion lighter)
        "mass_ratio_final": m2 / m_strip,           # M2 / M_strip after stripping (companion now heavier, > 1)
        "elapsed_age_yr": elapsed_age_yr,           # system age at stripping ~ donor's MS lifetime
    }
    # path (b) Chunk 3: the mass-transfer geometry (the causal story behind the stripping),
    # folded in so the Roche panel appears with the "Show companion" reveal. Pure orbital
    # mechanics on the same snapped node — the companion sphere the frontend draws inside its
    # lobe is sized from the modelled companion_state above (its real R_rsun).
    payload["roche"] = roche_geometry(mass, feh)
    return payload
