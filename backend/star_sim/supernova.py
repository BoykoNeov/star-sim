"""Core-collapse supernova light curve + photosphere — the SN endgame sibling.

Like `lane_emden.py` and `spectra.py`, this is a **sibling to the StellarState
spine (§3), not a provider and not (only) a `StellarState`**. The MIST tracks end
*at* core collapse and carry no explosion or light-curve data, so — unlike the
WD/WR endgames, which were already on the tracks — a supernova cannot be snapped
to a track. It is a **computed semi-analytic model**, parametrized by
progenitor-derived inputs. So `/supernova` is, like `/polytrope` and `/spectrum`,
a route that does **not** go through `PROVIDER` (docs/plans/radioactive-afterglow-
requiem.md, Chunk 1).

The model is a **hybrid**: the *classification* (is this star an SN? what are its
core masses / pre-collapse radius?) stays on the spine — `MISTProvider.endgame()`
returns `type="SN"` plus the progenitor scalars. This sibling does only the
*computation*, consuming those scalars (a §3-clean read of `EndgameResult`, done
in the route — this module never imports the provider, only `state.StellarState`,
which it emits). It produces **both** (a) a light-curve object (L vs days) and (b)
homologous-expansion photosphere `StellarState`s, so the existing 3D / SED /
scale-bar consumers eat a supernova exactly as they eat a white dwarf (§3 holds;
the source is just "computed").

The three honesty tiers — the heart of the arc, labeled so the UI never implies
the peak brightness is *predicted*:

  * Tier 1 — bulletproof, zero free parameters: the ⁵⁶Co radioactive **tail slope**,
    0.00975 mag/day, set *only* by τ_Co = 111.3 d. The verification jewel (SN 1987A's
    tail is the textbook match) — and it is the *tail*, not the peak.
  * Tier 2 — shape from the progenitor (+ a canonical E, + an assumed κ): the IIP
    recombination **plateau** L & duration, from MIST's M_ej & R₀ via Popov(1993) /
    Kasen–Woosley(2009). Robust in *shape*, ±dex in *level* (the SED-Chunk-2 lesson),
    and only where the progenitor is a red supergiant (the compact very-massive low-Z
    tail has no envelope → an honest radioactive-only fallback, `has_plateau=False`).
  * Tier 3 — absolute scale needs a free input: peak/tail height ∝ M_Ni. *Not*
    derivable from MIST (observed 0.001–0.3 M☉), so a **free slider**, canonical
    default 0.06 M☉. The plateau peak is recombination-powered and carries *no* M_Ni
    term; only the radioactive tail scales with it (so "M_Ni scales the peak" is true
    only for the no-plateau case — the IIP peak is the plateau).

Constants are cited inline: Nadyozhin(1994) decay energetics; Kasen–Woosley(2009,
ApJ 703, 2205) plateau scalings; τ from the ⁵⁶Ni (6.075 d) / ⁵⁶Co (77.2 d)
half-lives. The gate (Chunk 0) validated the canonical 15 M☉ curve lands in regime
(plateau ~1.5×10⁴² erg/s / ~133 d; Co-tail slope 0.00976 = textbook 0.0098). We
deliberately do **not** model the explosion mechanism (the bounce) — only its
parametrized aftermath — and omit the early shock-breakout / shock-cooling phase
(a separate hard piece). Observed light curves are the verification anchor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .state import StellarState

# --- physical constants (cgs) -------------------------------------------------
MSUN = 1.989e33              # g
RSUN = 6.957e10              # cm
LSUN = 3.828e33             # erg/s (IAU nominal)
DAY_S = 86400.0             # s
DAYS_PER_YEAR = 365.25
SIGMA_SB = 5.670374419e-5   # erg/s/cm^2/K^4 (Stefan–Boltzmann)
G_CGS = 6.674e-8            # cm^3/g/s^2

# --- ⁵⁶Ni → ⁵⁶Co → ⁵⁶Fe radioactive deposition (Nadyozhin 1994; full γ-trapping) ---
TAU_NI_D = 8.764            # d  ⁵⁶Ni mean life (half-life 6.075 d)
TAU_CO_D = 111.3           # d  ⁵⁶Co mean life (half-life 77.2 d) — sets the Tier-1 slope
EPS_NI = 3.9e10            # erg/s per gram of ⁵⁶Ni
EPS_CO = 6.8e9             # erg/s per gram of ⁵⁶Co (γ-only)

# --- Tier-3: the free nickel mass (the unmodeled explosion's yield) ------------
M_NI_DEFAULT = 0.06         # M_sun — canonical IIP nickel yield
M_NI_MIN = 0.001            # M_sun — observed floor
M_NI_MAX = 0.3              # M_sun — observed ceiling
E_KIN_DEFAULT = 1.0e51      # erg — canonical core-collapse kinetic energy

# --- Tier-2: Kasen–Woosley (2009) IIP recombination-plateau scalings ----------
KAPPA = 0.34                # cm^2/g — electron-scattering opacity (H, solar-ish)
T_ION = 6000.0              # K — hydrogen recombination-front temperature
# Below this pre-collapse radius there is no red-supergiant envelope, so the
# recombination-plateau model does not apply → an honest radioactive-only fallback.
# The Chunk-0 gate measured the RSG bulk at R₀ ≈ 400–1100 R_sun and the compact
# very-massive low-Z tail at 75–260 R_sun, so 300 separates them cleanly.
RSG_R0_MIN = 300.0          # R_sun

# --- remnant mass cut (a deliberately-simplified label; Chunk 5 refines) -------
# Reality is "islands of explodability" (non-monotonic compactness), not a crisp
# threshold; this is a teaching cut on the CO-core mass, explicitly labeled.
CO_NS_MAX = 7.0             # M_sun — CO core below → neutron star, above → black hole
M_NS_MSUN = 1.4            # M_sun — canonical neutron-star mass (baryonic ~1.5; simplified)
M_EJ_FLOOR = 0.1          # M_sun — keep ejecta strictly positive if a BH swallows the core

# --- light-curve time sampling ------------------------------------------------
T_MIN_D = 0.5              # d — first sample (shock breakout/cooling deliberately omitted)
T_MAX_D = 500.0           # d — runs onto the radioactive tail (the nebular tail goes years)
N_SAMPLES = 160           # log-spaced samples (the photosphere states share this grid)
T_RISE_D = 7.0            # d — fast rise onto the plateau
PLATEAU_EDGE_FRAC = 0.08  # plateau-edge drop width as a fraction of t_p (~10 d at t_p≈130)


@dataclass(frozen=True)
class Progenitor:
    """The progenitor inputs the SN model consumes — exactly the scalars the SN branch
    of `EndgameResult` exposes. A plain bundle so this module never imports the provider
    (§3): the `/supernova` route reads these off `PROVIDER.endgame()` and builds it.
    All masses are M_sun; `pre_sn_radius_rsun` is the robust pre-collapse R₀; `h_retained`
    True ⇒ a Type II (an H envelope survives — the only kind the SN branch reaches)."""

    mass_init_msun: float
    final_mass_msun: float       # current (pre-collapse) mass
    he_core_msun: float
    co_core_msun: float          # CO-core proxy (MIST c_core_mass)
    pre_sn_radius_rsun: float    # R₀ — the RSG envelope's pre-collapse extent
    h_retained: bool
    feh_init: float = 0.0


@dataclass
class SupernovaModel:
    """The computed supernova: classification, explosion scalars, the light curve, and
    homologous-photosphere `StellarState`s. The route serializes this verbatim (the
    `states` recurse to the §3 StellarState shape; every other served field is a plain
    `float` / `list[float]` so it survives JSON encoding)."""

    # classification
    type: str                     # "II" (H-retained) or "Ib/c" (stripped — not reached in v1)
    has_plateau: bool             # False for the compact tail (radioactive-only fallback)
    # progenitor echo (the snapped scalars, for the panel + re-snap)
    mass_init_msun: float
    feh_init: float
    final_mass_msun: float
    he_core_msun: float
    co_core_msun: float
    pre_sn_radius_rsun: float
    # explosion parameters
    m_ej_msun: float
    m_ni_msun: float              # the value used (after clamp to the observed range)
    m_ni_default: float
    m_ni_min: float
    m_ni_max: float
    e_kin_erg: float
    v_phot_kms: float             # characteristic ejecta velocity √(2E/M_ej)
    # remnant (Chunk 5 refines)
    remnant_type: str             # "NS" / "BH"
    remnant_mass_msun: float
    # observables
    peak_L_erg_s: float
    plateau_L_erg_s: float | None
    plateau_duration_days: float | None
    co_tail_slope_mag_day: float  # Tier-1 anchor (parameter-free: 2.5/ln10/τ_Co)
    light_curve: dict             # time_days + L_total/L_radio/L_plateau (erg/s) — lists
    states: list[StellarState] = field(default_factory=list)
    tiers: dict = field(default_factory=dict)


def _radioactive_L(t_days: np.ndarray, m_ni_g: float) -> np.ndarray:
    """⁵⁶Ni → ⁵⁶Co → ⁵⁶Fe deposition luminosity (erg/s) at times `t_days`, full trapping.

    Bateman two-step decay: with a = e^{-t/τ_Ni}, b = e^{-t/τ_Co},
        L = M_Ni[ ε_Ni·a + ε_Co · τ_Co/(τ_Co−τ_Ni) · (b − a) ].
    Exactly linear in M_Ni (the Tier-3 scaling). At late times the ⁵⁶Ni term is dead and
    L ∝ e^{-t/τ_Co}, giving the Tier-1 decline slope 2.5/ln10/τ_Co = 0.00975 mag/day."""
    a = np.exp(-t_days / TAU_NI_D)
    b = np.exp(-t_days / TAU_CO_D)
    l_ni = m_ni_g * EPS_NI * a
    l_co = m_ni_g * EPS_CO * (TAU_CO_D / (TAU_CO_D - TAU_NI_D)) * (b - a)
    return l_ni + l_co


def _plateau_kasen_woosley(
    e51: float, m_ej_msun: float, r0_rsun: float, kappa: float = KAPPA, t_ion: float = T_ION
) -> tuple[float, float]:
    """Kasen–Woosley (2009) IIP recombination-plateau luminosity (erg/s) & duration (d).

    Powered by the receding hydrogen-recombination front through the shock-heated RSG
    envelope — so it depends on (E, M_ej, R₀, κ, T_ion) and carries **no** M_Ni term (the
    plateau peak is *not* the radioactive scale; Tier-3 only moves the tail). Robust in
    shape, ±dex in level (the KW normalization + T_ion/κ assumptions)."""
    m10 = m_ej_msun / 10.0
    r500 = r0_rsun / 500.0
    k034 = kappa / 0.34
    ti = t_ion / 6000.0
    l_p = 1.26e42 * e51 ** (5 / 6) * m10 ** (-0.5) * r500 ** (2 / 3) * k034 ** (-1 / 3) * ti ** (4 / 3)
    t_p = 122.0 * e51 ** (-0.25) * m10 ** 0.5 * r500 ** (1 / 6) * k034 ** (1 / 6) * ti ** (-2 / 3)
    return float(l_p), float(t_p)


def supernova_model(
    progenitor: Progenitor,
    m_ni: float | None = None,
    e_kin: float = E_KIN_DEFAULT,
    n_samples: int = N_SAMPLES,
) -> SupernovaModel:
    """Compute the core-collapse light curve + photosphere for one progenitor.

    `m_ni` (M_sun) is the Tier-3 free nickel mass (default 0.06, clamped to the observed
    0.001–0.3 range); `e_kin` (erg) the canonical kinetic energy. Returns a fully-formed
    `SupernovaModel` — the light curve (L_total = plateau ⊕ radioactive tail) and the
    homologous photosphere states (R = v·t, Teff from L & R)."""
    p = progenitor
    m_ni = M_NI_DEFAULT if m_ni is None else float(m_ni)
    m_ni = min(max(m_ni, M_NI_MIN), M_NI_MAX)         # clamp to the observed range (Tier-3)
    e_kin = float(e_kin)
    e51 = e_kin / 1.0e51

    # --- ejecta / remnant split (a labeled CO-core mass cut; Chunk 5 refines) ---
    if p.co_core_msun < CO_NS_MAX:
        remnant_type, remnant_mass = "NS", M_NS_MSUN
    else:
        remnant_type, remnant_mass = "BH", p.co_core_msun   # the CO core collapses to a BH
    # never let the remnant exceed the star (keeps ejecta strictly positive).
    remnant_mass = min(remnant_mass, p.final_mass_msun - M_EJ_FLOOR)
    m_ej = p.final_mass_msun - remnant_mass

    # --- homologous ejecta velocity √(2E/M_ej) (v ∝ r; sets the photosphere R(t)) ---
    v_phot = math.sqrt(2.0 * e_kin / (m_ej * MSUN))    # cm/s

    sn_type = "II" if p.h_retained else "Ib/c"         # the SN branch is purely II in v1
    has_plateau = p.pre_sn_radius_rsun >= RSG_R0_MIN

    # --- the two-component light curve on a log time grid -----------------------
    t = np.logspace(math.log10(T_MIN_D), math.log10(T_MAX_D), n_samples)   # days
    m_ni_g = m_ni * MSUN
    l_radio = _radioactive_L(t, m_ni_g)

    if has_plateau:
        l_p, t_p = _plateau_kasen_woosley(e51, m_ej, p.pre_sn_radius_rsun)
        rise = 1.0 - np.exp(-t / T_RISE_D)
        # w: 1 during the plateau, smoothly → 0 at t_p (the recombination support
        # switches off as the front reaches the centre). The blend suppresses the
        # raw t=0 deposition spike (M_Ni·ε_Ni > L_p) that a max() would surface.
        w = 1.0 / (1.0 + np.exp((t - t_p) / (PLATEAU_EDGE_FRAC * t_p)))
        l_plateau = l_p * rise
        l_total = w * l_plateau + (1.0 - w) * l_radio
        plateau_l: float | None = float(l_p)
        plateau_dur: float | None = float(t_p)
        l_plateau_out: list | None = [float(x) for x in l_plateau]
    else:
        # No RSG envelope (the compact very-massive low-Z tail): the recombination
        # plateau model doesn't apply, so an honest radioactive-only curve.
        l_total = l_radio
        plateau_l = plateau_dur = l_plateau_out = None

    peak_l = float(np.max(l_total))

    # --- homologous-photosphere StellarStates (R = v·t; Teff from L & R) ---------
    m_ej_g = m_ej * MSUN
    if sn_type == "II":
        x_s, y_s, z_s = 0.70, 0.28, 0.02     # representative H-rich envelope (labeled
    else:                                    # placeholder; Chunk 4 does the real ejecta
        x_s, y_s, z_s = 0.0, 0.55, 0.45      # composition / onion shell)
    states: list[StellarState] = []
    for i in range(n_samples):
        t_day = float(t[i])
        r_cm = v_phot * (t_day * DAY_S)
        l_erg = float(l_total[i])
        teff = (l_erg / (4.0 * math.pi * r_cm * r_cm * SIGMA_SB)) ** 0.25
        # logg of freely-expanding ejecta is honestly tiny→negative (it is NOT a star's
        # surface gravity). Chunk 2 passes an explicit {endgame:"sn"} so the 3D/SED
        # consumers branch on the mode, not on this logg.
        logg = math.log10(G_CGS * m_ej_g / (r_cm * r_cm))
        states.append(
            StellarState(
                age_yr=t_day / DAYS_PER_YEAR,   # the supernova's own age (since explosion)
                eep=float(i),                   # a sample index — SN states aren't on the EEP grid
                phase="SN",
                mass_init_msun=p.mass_init_msun,
                feh_init=p.feh_init,
                L_lsun=l_erg / LSUN,
                Teff_K=float(teff),
                R_rsun=r_cm / RSUN,
                logg=float(logg),
                X_surf=x_s, Y_surf=y_s, Z_surf=z_s,
                X_core=x_s, Y_core=y_s, Z_core=z_s,   # photosphere placeholder (Chunk 4)
            )
        )

    # Tier-1 anchor: the ⁵⁶Co tail decline rate, set ONLY by τ_Co — parameter-free.
    co_slope = 2.5 / (math.log(10.0) * TAU_CO_D)

    light_curve = {
        "time_days": [float(x) for x in t],
        "L_total_erg_s": [float(x) for x in l_total],
        "L_radio_erg_s": [float(x) for x in l_radio],
        "L_plateau_erg_s": l_plateau_out,
    }
    tiers = {
        "tier1": "⁵⁶Co tail slope (0.00975 mag/day) — bulletproof, zero free parameters; "
                 "set only by τ_Co. The verification anchor (not the peak).",
        "tier2": "plateau L & duration — shape from your star's M_ej & R₀ (MIST) + a "
                 "canonical E and assumed κ; robust in shape, ±dex in level."
                 if has_plateau else
                 "no recombination plateau — this compact progenitor has no red-supergiant "
                 "envelope, so the curve is radioactive-only (honest fallback).",
        "tier3": "peak/tail height ∝ M_Ni — set by the (unmodeled) explosion's nickel "
                 "yield, not derivable from the track. Drag it; see where real SNe land.",
    }

    return SupernovaModel(
        type=sn_type,
        has_plateau=has_plateau,
        mass_init_msun=float(p.mass_init_msun),
        feh_init=float(p.feh_init),
        final_mass_msun=float(p.final_mass_msun),
        he_core_msun=float(p.he_core_msun),
        co_core_msun=float(p.co_core_msun),
        pre_sn_radius_rsun=float(p.pre_sn_radius_rsun),
        m_ej_msun=float(m_ej),
        m_ni_msun=float(m_ni),
        m_ni_default=M_NI_DEFAULT,
        m_ni_min=M_NI_MIN,
        m_ni_max=M_NI_MAX,
        e_kin_erg=float(e_kin),
        v_phot_kms=float(v_phot / 1.0e5),
        remnant_type=remnant_type,
        remnant_mass_msun=float(remnant_mass),
        peak_L_erg_s=peak_l,
        plateau_L_erg_s=plateau_l,
        plateau_duration_days=plateau_dur,
        co_tail_slope_mag_day=float(co_slope),
        light_curve=light_curve,
        states=states,
        tiers=tiers,
    )
