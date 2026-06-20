# Star Simulator — Development Specification

**Purpose of this document:** a handoff/spec to drive development in Claude Code. Read this first in any new session. The architectural principle in §3 is non-negotiable; everything else is sequenced in §9.

---

## 1. What this is

An interactive stellar simulator whose two goals, in equal measure, are **teaching** and **beauty**. The user picks a star's **mass** and **metallicity**, then watches it evolve through its life cycle: the HR diagram tracks where the star is, a composition panel shows its changing interior, and a real-time 3D rendering shows a plausible turbulent stellar surface and corona.

Guiding value: **real data and real science, with approximation only where necessary.** Where we approximate (notably the surface/corona visuals), we approximate *toward* known physics and stay honest about what is computed vs. evoked.

---

## 2. Goals and non-goals

**Goals**
- Pick mass and metallicity; see the star evolve through time, including post-main-sequence drama (subgiant, red giant, etc. — this is where the visible time-evolution lives).
- An HR diagram that acts as the linking spine: a marker walks the evolutionary track; everything else updates from the same state.
- A composition readout (surface and core abundances) that evolves with the star.
- A real-time, physically-motivated 3D star: correct color, granulation, limb darkening, rotation, and an evocative corona/wind.
- An architecture that allows an **optional later path toward more science** (offline MESA runs, eventually a live structure solver, eventually a nuclear network) without rewriting downstream code.

**Non-goals (do not build these now; do not let them creep in)**
- Not a MESA reimplementation. We never solve the four stellar-structure equations on a mesh at runtime in v1.
- No live nuclear reaction network. Composition is **read off** the tracks, not integrated. (A network is a possible far-future provider, see §9.)
- Not shareable/deployable. This runs locally. No static-site constraint, no bundle-size budget, no public hosting concerns. Optimize for a good local dev experience, not distribution.
- Main-sequence-only is explicitly rejected as a scope — a single MS star changes too little over time to be interesting. The mass axis and the post-MS phases carry the drama.

---

## 3. Core architectural principle — the StellarState spine (NON-NEGOTIABLE)

Everything the user sees is a function of a single state object, and **no consumer is ever allowed to know where that state came from.**

```python
@dataclass
class StellarState:
    # identity / where we are
    age_yr: float            # current age in years
    eep: float               # equivalent evolutionary point (see §6)
    phase: str               # human-readable: "MS", "subgiant", "RGB", ...

    # input parameters (constant for a given star)
    mass_init_msun: float    # initial mass
    feh_init: float          # initial [Fe/H]

    # observable structure
    L_lsun: float            # luminosity / L_sun
    Teff_K: float            # effective temperature
    R_rsun: float            # radius / R_sun
    logg: float              # surface gravity, cgs dex

    # composition (mass fractions)
    X_surf: float; Y_surf: float; Z_surf: float
    X_core: float; Y_core: float; Z_core: float
    # optionally per-element surface/core abundances if available

    # optional / for visuals (may be derived, may be NaN early on)
    v_rot_kms: float | None = None     # surface rotation, if modeled
    activity: float | None = None      # 0..1 proxy driving corona brightness (see §7)
```

Behind it, a **provider interface**:

```python
class StellarStateProvider(Protocol):
    def parameter_ranges(self) -> dict:        # valid mass / [Fe/H] ranges for UI
        ...
    def age_range(self, mass, feh) -> tuple:   # min/max age for the scrubber
        ...
    def state_at(self, mass, feh, age_yr) -> StellarState:
        ...
```

- **v1 ships exactly one implementation: `MISTProvider`.**
- The HR diagram, the 3D star renderer, and the composition panel consume `StellarState` **only**. They must never reach into MIST columns, file formats, or interpolation internals directly.
- Later, `MESAProvider` (reads offline-generated MESA `.data`/history files) or `LiveSolverProvider` slot in behind the same interface and nothing downstream changes. This boundary *is* the "optional path to more science." If it is respected from day one, going deeper is a provider swap. If it is violated, that path quietly dies. Treat any consumer that imports MIST internals as a bug.

---

## 4. Tech stack

Because shareability is not a goal, prefer the scientifically natural tools, not the deployable ones.

- **Backend:** Python + FastAPI. Holds MIST grids in memory; exposes the provider over localhost (e.g. `GET /state?mass=&feh=&age=`, plus `/ranges`). numpy/scipy for interpolation; later scipy for Lane-Emden; later `mesa_reader` for the MESA provider.
- **Frontend:** single-page browser app. **Three.js / WebGL** for the star (this is the only sane tool for the surface shader). **d3 or plotly** for the HR diagram and composition panel. Plain fetch to the localhost backend.
- **Communication:** localhost HTTP. Keep the payload exactly the `StellarState` shape from §3.

Language choice is unconstrained (Claude Code does the coding), so this split is chosen for fit, not familiarity.

---

## 5. System components

1. **Provider** (§3, §6) — turns (mass, [Fe/H], age) into `StellarState`.
2. **HR diagram + marker** — the linking spine of the UI. Plots log L vs log Teff (Teff axis reversed, hot on the left, per convention). Draws the full evolutionary track for the chosen (mass, [Fe/H]); a marker sits at the current age. Scrubbing time or editing parameters moves the marker and re-emits state to all consumers.
3. **3D star renderer** (§7) — a sphere with a fragment shader driven by `StellarState`: color from Teff, granulation scale from physics, limb darkening, rotation, corona/wind glow.
4. **Composition panel** — surface and core mass fractions (X/Y/Z, optionally per-element), updating with age. Simple, honest, read straight off the state.
5. **Controls** — mass slider, [Fe/H] slider, age/time scrubber. Ranges come from `provider.parameter_ranges()` and `provider.age_range()` so the UI can never request an out-of-grid point.
6. **Lane-Emden interior panel** (§8) — deferred, optional. A live-computed static polytrope as a teaching/structure piece. Not on the critical path.

---

## 6. The MIST data layer (the real work hides here)

**Data source:** MIST (MESA Isochrones & Stellar Tracks) — freely downloadable grids of MESA-computed tracks giving L, Teff, R, logg, age, and composition vs. evolutionary phase, across a grid of mass and [Fe/H]. Claude Code should fetch the current MIST download location and file formats at build time rather than trusting any URL hard-coded here, since paths change. Reuse MIST's own `read_mist_models.py` parser for the `.track.eep` files instead of reinventing the format.

**Decide early:** which grid to pull. Start with a single [Fe/H] (solar) and a sensible mass sampling for the MVP; expand to a 2D (mass × [Fe/H]) grid once interpolation works.

### The one critical gotcha: interpolate on EEPs, not on age

This bites everyone. Two stars of different mass at the *same age* are in completely different evolutionary phases, so interpolating raw tracks against age produces physical nonsense (e.g. blending a main-sequence star with a red giant). MIST solves this with **Equivalent Evolutionary Points**: tracks are resampled so that "point N" is the *same phase* (ZAMS, TAMS, etc.) across all masses.

Interpolation algorithm:

1. **Metallicity (outer loop):** bracket the two nearest grid `[Fe/H]` values.
2. **Mass (inner, at fixed EEP):** within each [Fe/H], for the requested mass, interpolate each quantity between the two bracketing mass tracks **at the same EEP index**, not the same age.
3. **Map age ↔ EEP:** the user controls age; convert the requested age to a fractional EEP using the (mass-interpolated) age-vs-EEP relation, do step 2 there, then read everything else off.
4. **Blend metallicity:** interpolate the two [Fe/H] results.

Edge handling: clamp/disable parameter values outside the grid in the UI; do not extrapolate silently. Phases like the helium flash and (if ever added) AGB thermal pulses are non-monotonic and messy even in MIST — defer them; if encountered, handle explicitly rather than interpolating across.

**Composition** is read directly from the EEP-interpolated track columns (surface and core abundances). No integration.

---

## 7. The visualization — physically motivated, honest about the seams

The instinct to **represent** convection rather than simulate it is correct. A Three.js sphere with a fragment shader is the vehicle. The principle that keeps it "close to known physics" is: **every visual parameter is driven by a real number from `StellarState`.** Layers, roughly in order of physical rigor:

**Color (most physically honest pixel in the app).** Compute the Planck blackbody spectrum at `Teff_K`, integrate against the CIE XYZ color-matching functions, convert XYZ→sRGB with the correct white point and gamma. A fast tabulated Teff→sRGB approximation is acceptable, but the Planck→CIE→sRGB pipeline is the reference. Sanity target: the Sun (~5772 K) must render as a slightly-warm near-white, *not* yellow.

**Granulation scale (real physics for free).** Granule size scales with the pressure scale height, H_p = kT / (μ m_H g) ∝ T / (μ g) — use `Teff_K` and `logg`. Drive the noise cell density from this: a compact dwarf shows fine granulation; an evolved low-gravity supergiant (e.g. a Betelgeuse-like state) should show only a *handful* of enormous convective cells. This single relation makes the aesthetics encode genuine physics. Use **Worley/Voronoi noise** for the cells, animated.

**Limb darkening.** Apply a standard analytic limb-darkening law (e.g. a linear or quadratic law) across the disk — cheap, and it reads immediately as "a real star."

**Rotation / differential rotation.** Shear the noise field; animate the surface at roughly the convective turnover timescale. If a rotation rate is available, use `v_rot_kms`; otherwise pick a plausible visual rate. Differential rotation (faster equator) is a nice touch via latitude-dependent shear.

**Corona / wind (the honest artistic layer).** Be explicit, in code comments and ideally in the UI, that this is *evocative, not predictive*. The real physics splits by type: hot O/B stars have radiatively driven winds and no solar-type corona; cool stars have magnetic chromospheres/coronae structured by fields we are not modeling. Render it as an additive outer glow whose brightness/extent is tied to the `activity` proxy (0..1) — a function of, say, rotation and a cool-star/hot-star distinction. Treat `activity` as the single knob; do not pretend to resolve loops or ejecta.

All of the above read from the same state vector the HR marker is showing, so the picture, the diagram, and the numbers are always describing one consistent star.

---

## 8. Lane-Emden interior panel (deferred, optional)

Not on the critical path; build after the spine and visuals work. Value: a clean, live-computed *static structure* teaching piece, plus a sanity check on intuition.

Lane-Emden gives a single static polytrope under P = K ρ^(1+1/n). It is **not** evolution — no time, no temperature history, no burning. It belongs as an "interior structure" panel, never as the evolution engine.

Numerics: integrate the dimensionless equation outward from the center; step off the r=0 singularity with the series expansion θ ≈ 1 − ξ²/6 + n ξ⁴/120 − …; stop at the first zero ξ₁ (the surface). Exact closed-form solutions exist for n = 0, 1, 5 — use them to validate the integrator. Validate ξ₁ against Chandrasekhar's tabulated polytrope values. Physical anchors for intuition: n = 1.5 ≈ a fully convective star (and non-relativistic degenerate matter); n = 3 ≈ the Eddington standard model / radiative core.

---

## 9. Build plan (phased — ship the spine first)

**Phase 0 — MVP / the spine.** One [Fe/H] (solar), one or a few MIST tracks loaded via `read_mist_models.py`. Backend exposes `state_at` for a single mass. HR diagram drawn with a track and a time scrubber; marker walks the track. Star renders as a sphere with **Teff→color** and **radius→size** updating from `StellarState`. No granulation, no corona yet. This thin vertical slice proves the entire architecture end to end.

**Phase 1 — parameters.** Add the mass slider (the showpiece — dragging mass slides the marker along the track and transforms the star's color and size) and the [Fe/H] slider. Implement full EEP-based 2D interpolation (§6). Add the composition panel.

**Phase 2 — beauty.** Granulation driven by H_p (Teff, logg); limb darkening; rotation. Then the corona/wind glow tied to the `activity` proxy. This is the bulk of the frontend/shader work.

**Phase 3 — Lane-Emden panel.** The static interior structure piece (§8), validated against the polytrope tables.

**Phase 4+ — optional path to more science** (only if desired later, each behind the existing provider interface):
- `MESAProvider`: read offline-generated MESA history/profile files (`mesa_reader`) to extend or replace the grid, or to validate MIST.
- Per-element composition, more phases (RGB tip, He flash handling, beyond).
- Eventually `LiveSolverProvider` and/or a reduced nuclear network — large efforts, explicitly out of current scope.

---

## 10. Validation / sanity checks (wire these in as you go)

- **Sun:** at ~1 M⊙, [Fe/H]≈0, present age ~4.6 Gyr, the state should give L≈1 L⊙, Teff≈5772 K, R≈1 R⊙ — and render as warm near-white.
- **Color pipeline:** blackbody white point and gamma correct (Sun not cartoon-yellow; hot stars blue-white; cool stars orange-red).
- **ZAMS spread:** across the mass range, luminosity should span roughly nine orders of magnitude (~10⁻³ L⊙ for low-mass dwarfs up to ~10⁵–10⁶ L⊙ for massive O stars), with color sweeping from ~3000 K red to ~40,000 K blue. If the mass slider doesn't produce a dramatic transformation, interpolation is wrong.
- **EEP interpolation:** an interpolated intermediate-mass track must lie *between* its bracketing tracks on the HR diagram at every phase — never loop through an unrelated region. This is the direct test that you interpolated on EEP, not age.
- **Lane-Emden:** computed ξ₁ for n = 0, 1, 5 matches the exact analytic values; other n match Chandrasekhar's tables.

---

## 11. Open questions / decisions to revisit

- **Which MIST grid resolution** (mass spacing, [Fe/H] values) balances smooth interpolation against memory/load time? Start coarse, refine.
- **How far up the life cycle** to expose initially — subgiant/RGB is the sweet spot for visible drama; the helium flash and beyond are messy and can wait.
- **`activity` proxy definition** — what exactly drives corona brightness (rotation rate? a hot/cool split? a Rossby-number-like quantity?). Pick something defensible and label it as a proxy.
- **Rotation data** — does the chosen MIST grid include rotation, or is `v_rot_kms` purely a visual parameter for now?

---

*End of spec. The first thing to build is Phase 0. The thing never to compromise is §3.*
