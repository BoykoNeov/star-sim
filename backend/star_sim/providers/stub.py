"""StubProvider — the v1 stand-in behind the §3 boundary.

It returns plausible, physically-*flavored* numbers with **no external data**,
so the whole stack runs end to end from the first commit. It is deliberately not
a model of stellar evolution: it exists to prove the architecture and to keep the
§10 Sun sanity check wired in from day one.

Honesty about the seams (these are approximations, clearly labeled):
  * structure (L, Teff, R, logg) is a function of mass & [Fe/H] only — a crude
    main-sequence mass scaling. It does NOT evolve with age.
  * age drives only the EEP counter and core H-depletion (a hand-wave at core
    burning). Real age-driven drama — the subgiant/RGB visuals — is the job of
    `MISTProvider`, the next provider to land behind this same interface.

Anchors that MUST hold (so the swap to a real provider is a regression test):
  state_at(1.0, 0.0, 4.6e9) ~= Sun: L=1 L_sun, Teff=5772 K, R=1 R_sun, logg=4.44.
"""

from __future__ import annotations

import math

from ..provider import EndgameResult, ParameterOutOfRange
from ..state import StellarState

# --- Solar / reference anchors ------------------------------------------------
TEFF_SUN_K = 5772.0
LOGG_SUN = 4.438
Z_SUN = 0.0152          # protosolar-ish metal mass fraction
Y_PRIMORDIAL = 0.2485   # big-bang helium
DYDZ = 1.78             # galactic helium enrichment slope (Y = Yp + dY/dZ * Z)

# Fraction OF the metals Z carried by each exposed element at solar abundance
# (Asplund+ 2009 photospheric mass fractions / Z_sun). The stub has no nuclear
# processing, so it just splits its Z by these fixed ratios — flat in age and
# identical surface vs core. That is the honest stub stance (§ conventions): a
# static, *flavored* breakdown, not the CNO-cycle / dredge-up / diffusion /
# Li-depletion evolution that only MISTProvider can show. The sixteen match
# MISTProvider's element set; they sum to ~0.90 of Z (the rest is Cl/Ar/K/Cr/Mn/
# Ni/... that MIST's network doesn't track either), so the per-element sum stays
# safely under Z. The fragile light elements (Li, Be, and the §5.4 "light" view's F)
# are special: their present-day photospheric fractions are tiny (Li ~4e-9, Be ~1e-8,
# F ~2e-5 of Z), and the stub renders them as flat floors — only MISTProvider shows Li
# and Be actually *depleting* as the convective envelope deepens, and F holding steady.
# (Boron is absent on purpose, like in MIST: its only network isotope, the radioactive
# `b8`, is a numerical-zero transient, not stable boron — see mist.py CACHE_VERSION v8.)
METALS_OF_Z = {
    "Li": 3.8e-9, "Be": 1.0e-8,            # lithium / beryllium (fragile-light floors)
    "C": 0.155, "N": 0.046, "O": 0.377,    # the CNO trio
    "F": 2.4e-5,                           # fluorine (the light-view's stable backdrop)
    "Ne": 0.112, "Na": 0.0020,             # neon, sodium
    "Mg": 0.047, "Al": 0.0038,             # magnesium, aluminium
    "Si": 0.044, "P": 0.0004,              # silicon, phosphorus
    "S": 0.020, "Ca": 0.0042, "Ti": 0.0002,  # sulfur, calcium, titanium
    "Fe": 0.085,                           # the iron tracer
}

# MIST EEP convention (real numbers, for honesty): ZAMS=202, TAMS=454.
EEP_ZAMS = 202.0
EEP_TAMS = 454.0

# --- Stub grid bounds (chosen to give the §10 dramatic ZAMS spread) -----------
MASS_MIN, MASS_MAX = 0.1, 40.0
FEH_MIN, FEH_MAX = -2.0, 0.5
TEFF_FLOOR_K, TEFF_CEIL_K = 2600.0, 45000.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _composition(feh: float) -> tuple[float, float, float]:
    """Surface (X, Y, Z) mass fractions from [Fe/H].

    Z = Z_sun * 10**[Fe/H]; Y from a linear enrichment law; X is the remainder.
    """
    z = Z_SUN * (10.0**feh)
    y = Y_PRIMORDIAL + DYDZ * z
    x = 1.0 - y - z
    return x, y, z


def _metals(z: float) -> dict[str, float]:
    """Split a metal fraction Z into a fixed solar-ratio per-element breakdown (flavor)."""
    return {el: frac * z for el, frac in METALS_OF_Z.items()}


class StubProvider:
    """A `StellarStateProvider` (structurally — see ../provider.py)."""

    name = "StubProvider"

    # -- UI metadata -----------------------------------------------------------
    def parameter_ranges(self) -> dict:
        return {
            "mass_msun": {"min": MASS_MIN, "max": MASS_MAX},
            "feh": {"min": FEH_MIN, "max": FEH_MAX},
        }

    def mass_range(self, feh: float) -> tuple[float, float]:
        """Full mass span — the stub's analytic grid is rectangular in (mass, feh)."""
        return (MASS_MIN, MASS_MAX)

    def age_range(self, mass: float, feh: float) -> tuple[float, float]:
        self._check_mass_feh(mass, feh)
        # Crude main-sequence lifetime: t ~ 10 Gyr * M^-2.5 (Sun -> 10 Gyr).
        t_ms = 1.0e10 * mass**-2.5
        return (0.0, t_ms)

    # -- the one method that matters ------------------------------------------
    def state_at(self, mass: float, feh: float, age_yr: float) -> StellarState:
        self._check_mass_feh(mass, feh)

        _, t_ms = self.age_range(mass, feh)
        age = _clamp(age_yr, 0.0, t_ms)         # age never extrapolates past TAMS
        f = age / t_ms if t_ms > 0 else 0.0     # main-sequence fraction in [0, 1]

        # --- structure: mass scaling only (NOT age-evolved in the stub) -------
        L = mass**3.5                                   # mass-luminosity relation
        teff = _clamp(TEFF_SUN_K * mass**0.5, TEFF_FLOOR_K, TEFF_CEIL_K)
        # Stefan-Boltzmann in solar units: L = R^2 (Teff/Teff_sun)^4.
        r = math.sqrt(L) / (teff / TEFF_SUN_K) ** 2
        logg = LOGG_SUN + math.log10(mass) - 2.0 * math.log10(r)

        # --- composition: surface fixed; core H burns down with age ----------
        x_s, y_s, z_s = _composition(feh)
        x_c = x_s * (1.0 - f)            # core hydrogen depletes over the MS
        y_c = y_s + x_s * f             # ...converting to helium
        z_c = z_s

        # --- evolutionary bookkeeping ----------------------------------------
        eep = EEP_ZAMS + (EEP_TAMS - EEP_ZAMS) * f
        phase = "MS"                    # the stub only knows the main sequence

        # --- visual proxies (§7), explicitly approximate ---------------------
        # activity: cool stars more chromospherically active than hot ones.
        activity = _clamp((6500.0 - teff) / (6500.0 - 3000.0), 0.0, 1.0)

        return StellarState(
            age_yr=age,
            eep=eep,
            phase=phase,
            mass_init_msun=mass,
            feh_init=feh,
            L_lsun=L,
            Teff_K=teff,
            R_rsun=r,
            logg=logg,
            X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
            X_core=x_c, Y_core=y_c, Z_core=z_c,
            metals_surf=_metals(z_s),
            metals_core=_metals(z_c),   # = surface: the stub has no CNO processing
            v_rot_kms=None,             # the stub does not model rotation
            activity=activity,
        )

    def track(self, mass: float, feh: float) -> list[StellarState]:
        """The stub's whole life is the main sequence (ZAMS -> TAMS), so sample it
        uniformly in age. EEP is linear in age here, so even-age == even-EEP; the
        composition panel's EEP axis lands on a regular grid. `state_at` does all
        the real work — this just walks it."""
        self._check_mass_feh(mass, feh)
        _, t_ms = self.age_range(mass, feh)
        n = 60
        return [self.state_at(mass, feh, t_ms * i / (n - 1)) for i in range(n)]

    def endgame(self, mass: float, feh: float) -> EndgameResult:
        """The stub knows only the main sequence, so it exposes no endgame
        (type="none"); the gateway shows nothing. Keeps the stub a complete
        StellarStateProvider behind the §3 boundary."""
        return EndgameResult(type="none", mass_init_msun=mass, feh_init=feh)

    # -- validation ------------------------------------------------------------
    def _check_mass_feh(self, mass: float, feh: float) -> None:
        if not (MASS_MIN <= mass <= MASS_MAX):
            raise ParameterOutOfRange(
                f"mass {mass} M_sun outside stub grid [{MASS_MIN}, {MASS_MAX}]"
            )
        if not (FEH_MIN <= feh <= FEH_MAX):
            raise ParameterOutOfRange(
                f"[Fe/H] {feh} outside stub grid [{FEH_MIN}, {FEH_MAX}]"
            )
