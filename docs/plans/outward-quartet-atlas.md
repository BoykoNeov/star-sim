# Plan: The outward quartet — four new axes turning the sim outward from the star

## Status: PROPOSED (not built). Four brand-new directions, planned together.

The single-star-over-time story is exhaustive (tracks, composition, 3D, spectra, SED, interior
structure, endgames, binarity, populations, rotation, He/α overlays). Every axis so far looks
*inward* — the star's own physics. This atlas opens four axes that turn the sim **outward**: how the
star is **seen** (the observer's view), how it is **grouped** (the coeval cluster / isochrone), how it
**rings** (asteroseismology), and what it **warms** (the habitable zone). Each is a genuinely new
dimension, each is data-backed and clears the project's measure-first honesty gate, and each fits the
established **sibling** idiom (bypass `PROVIDER`, never leak a data-source concept into `StellarState`).

This is a *thin multi-axis plan* like `whirling-cohort-atlas.md`: the per-axis section here is the
source of truth for design; each becomes its own ROADMAP row and (when built) its own memory topic.

**The unifying honesty rule (spec §3 + the measure-first gate):** before any control ships, measure
that the effect is *visible and correct through the runtime path* (the boron-b8 / VO-7400 / invisible-Na
discipline). Each axis below states its **Gate 0** — the one measurement that must pass first.

---

## Axis A — The observer's view (distance + extinction + observational CMD)

**The lesson.** Everything the sim shows is *intrinsic* (logTeff, logL, F_λ — the star as it is). A
telescope records something else: an **apparent** magnitude, **reddened** colors, dimmed by distance and
reddened by interstellar dust. This axis is the **theory→telescope bridge** — the single biggest
conceptual gap the sim currently has — and it ties together the spectrum, SED, and color pipelines that
already exist. The payoff diagram is the **observational color–magnitude diagram (CMD)**: the observer's
HR diagram, in (color, apparent/absolute magnitude) instead of (logTeff, logL).

**Honesty tier & data.** Tier-1/2 — real physics applied to the real baked spectrum, never evocative.
- **Reddening:** the Cardelli–Clayton–Mathis (CCM89) or Fitzpatrick (F99) extinction law A(λ)/A(V),
  a closed-form curve parameterized by R_V (default 3.1). Applied to the served spectrum → a reddened
  spectrum. Public, standard formulae.
- **Synthetic photometry:** convolve the (reddened) spectrum with **real filter transmission curves** —
  Gaia G/BP/RP, Johnson–Cousins UBVRI, 2MASS JHK — from the **SVO Filter Profile Service** (the same
  source the spectra panel already uses for Coelho/TMAP/Koester). Zero-points (Vega/AB) from SVO.
  m_X = −2.5 log₁₀(∫f_λ T_X dλ / ∫f_λ^Vega T_X dλ) + ZP.
- **Distance modulus:** μ = 5 log₁₀(d/10 pc); m = M + μ + A_X.

**Architecture.** Filter curves are tiny (~a few hundred points each) — bake them + Vega zero-points
into one small static asset (`data/filters/…` or a committed JSON). Two clean options for the compute:
either a `photometry.py` sibling + `/photometry` route (spectrum in → magnitudes/colors out), or fully
client-side in JS (CCM is a polynomial; the filter convolution is a dot product). **Recommend the
sibling** for testability and to keep the filter/Vega data server-side, mirroring `spectra.py`. Bypasses
`PROVIDER`; the intrinsic `StellarState` is unchanged (apparent quantities are a *view*, never on the
spine — the same rule the SED/spectrum siblings already honor).

**Gate 0 (measure first) — the flux/normalization gate is the tightest constraint.** A **color** (BP−RP)
survives *any* true-shape flux — the (R/d)² and absolute-flux scaling cancel — so a color-only check would
pass even if the absolute pipeline is wrong. Gate 0 must therefore anchor on an **absolute magnitude with
the R/d scaling made explicit**: the Sun's **absolute G ≈ 4.67** (and B−V ≈ 0.65, BP−RP ≈ 0.82 as the
shape checks), from the Sun's served spectrum scaled by (R_⊙/10 pc)² through the photometry path — that is
where the zero-point and radius errors hide. Then: redden by A_V = 1 → BP−RP shifts red by the CCM-
predicted amount; place at 1 kpc → m dims by μ ≈ 10.

**The prerequisite (first step of A1, before any magnitude):** confirm the source cube is **absolute
physical surface F_λ**. The WR and stripped-star cubes are *continuum-normalized* (per CLAUDE.md) —
meaningless for photometry; the WD Koester/TMAP cube and the SED are separate concerns. The main
MSG/pymsg absorption cube *should* be physical (PHOENIX/CAP18/OSTAR model-atmosphere fluxes) — **verify
that, then scope Axis A to the cubes that are absolute.** Photometry on a normalized cube is a silent
wrong answer.

**Chunks.**
- **A1 (backend + data): ✅ BUILT 2026-07-10** (+10 tests). Gate 0 measured FIRST: the main absorption
  cube is **absolute physical surface F_λ** (the Sun integrates to 98.2% of the Planck in-band σT⁴), so
  ×(R/d)² gives real absolute mags. **The anchor swapped M_G → M_V** because the cube stops at **8999 Å**
  (advisor catch — Gaia G/RP + 2MASS JHK are uncomputable/truncated); flagship CMD = **(B−V, M_V)**, clean
  bands **Bessell B, V + Gaia BP** (verification). `fetch_filters.py` → committed `data/filters.json` (SVO
  transmission + Vega ZeroPoint(Jy) + DetectorType per band). `photometry.py` (pure sibling, AST-tested
  no-provider/no-StellarState): CCM89 reddening + a **vectorized** synth core (flux stack, for A3's
  track+isochrone) + DetectorType-aware Vega-ZP mags. `/photometry` composes `spectrum_data` + synth like
  `binary_pair`. **Gate 0 PASSED through the runtime:** Sun M_V=4.832, distance modulus exactly 10.000,
  E(B−V)=0.296 at A_V=1. **Advisor-settled: SVO ZeroPoints, not a Vega spectrum** (empirically ruled out —
  M_V nails it); synthetic B−V=0.612 is a known **common-mode** B-band ZP offset that cancels in relative
  CMD placement (so the star still sits on the cluster locus, the turnoff still dates it).
- **A2 (frontend):** an **"Observer" control group** — distance, A_V, R_V — that draws a reddened
  overlay on the SED + spectrum panels and an apparent-magnitude / color readout. Off by default →
  intrinsic view byte-unchanged.
- **A3 (frontend):** the **observational CMD panel** — the star (and its living track, transformed into
  observational coordinates) plotted in (BP−RP, M_G). Composes with Axis B (see interconnections).

---

## Axis B — The isochrone / cluster view

**The lesson.** The transpose of a track. A track is one mass over all ages; an **isochrone** is all
masses at **one age** — a coeval cluster frozen in time, a locus on the HR diagram. The **main-sequence
turnoff** (the luminosity where stars are just leaving the MS) *is* the cluster's age — this is how star
clusters are dated, the most famous single result in stellar populations. Distinct from the BPASS
coeval-ensemble overlay (that is *integrated light* + number density; this is the **individual-star
locus**, the thing you actually fit to a cluster's photometry).

**Honesty tier & data.** Tier-1 — and the cleaner the source, the cleaner the Tier-1 claim. **Prefer
MIST's *published* isochrone grids (`.iso`) as the primary source.** MIST ships isochrones as a
first-class data product; snapping/reading them is the *same* real-grid idiom as the tracks, and it
avoids **interpolation-of-interpolation**. The tempting alternative — construct the isochrone from the
already-fetched EEP-aligned tracks by inverting age-at-fixed-EEP for the mass — is legitimate but is
exactly the EEP-interpolation hazard this project has been bitten by (the reason the `lies-between-
neighbors` test exists). So invert the roles: **`.iso` primary; the from-tracks construction is the
cross-check** (a cheap parity assertion, not the served path). This keeps the Tier-1 claim clean rather
than "Tier-1 with an interpolation caveat." (`.iso` is a modest new download, gitignored like the tracks;
the hosted-data-assets pattern applies if it wants a Release.)

**Architecture.** A sibling reading the MIST `.iso` grid (its own parser, never imports a provider — the
`structure.py`/`bpass.py` §3-boundary rule for a data product that isn't the live spine), exposed as
`/isochrone`, returning a locus of §3-clean `StellarState`s at fixed (age, feh, vvcrit). The HR panel
already knows how to draw a population cloud (`setPopulationHRD` precedent); a locus is simpler — a
Teff-colored polyline with the turnoff highlighted. (If a future need makes an on-spine `isochrone()`
provider method cleaner, it can adopt the from-tracks construction — but the honest first build reads the
published grid.)

**Gate 0 (measure first).** A young cluster (100 Myr) turns off high on the MS with luminous blue stars
still present; an old cluster (12 Gyr) turns off low and faint. The two loci must be visibly, dramatically
different, and the turnoff luminosity must drop monotonically with age. Trivially passes — but *measure*
it through the real `isochrone()` path before shipping the turnoff caption (don't label a non-feature).

**Chunks.**
- **B1 (backend + data):** fetch the MIST `.iso` grid; an isochrone sibling + `/isochrone` route reading
  it, snapping (age, feh, vvcrit). Gate 0 (young vs old turnoff) as a regression test; add the from-tracks
  construction as a *cross-check* parity test (not the served path).
- **B2 (frontend):** a **"Cluster (isochrone)" HR overlay** at the marker's age & [Fe/H], turnoff
  highlighted, the user's star sitting on it, a turnoff-dating caption. Rides the HR panel; opt-in toggle.
- **B3 (optional):** an independent cluster-age slider that sweeps the turnoff down the MS — the "cluster
  aging" movie — decoupled from the single star's age.

---

## Axis C — Asteroseismology (the star rings)

**The lesson.** The star oscillates like a bell — solar-like p-modes driven by the convective envelope.
Two observables carry almost all the information: **ν_max** (the frequency of maximum oscillation power)
and **Δν** (the large frequency separation between consecutive overtones). With Teff they give the star's
**mass and radius** — the seismic scaling relations, how *Kepler* and *TESS* weigh and age hundreds of
thousands of stars. The beauty payoff is the **échelle diagram** (frequency mod Δν → vertical ridges).

**Honesty tier & data.** Tier-2 — real, well-calibrated **scaling relations**, labeled as approximate
(not a full pulsation solve). Everything needed is already on `StellarState` (M, R, Teff, g):
- ν_max/ν_max,⊙ = (g/g_⊙)(Teff/Teff_⊙)^(−1/2) = (M/M_⊙)(R/R_⊙)^(−2)(Teff/Teff_⊙)^(−1/2)
- Δν/Δν_⊙ = √(ρ̄/ρ̄_⊙) = (M/M_⊙)^(1/2)(R/R_⊙)^(−3/2)
- solar anchors ν_max,⊙ ≈ 3090 µHz, Δν_⊙ ≈ 135 µHz.
The schematic power spectrum is a **Δν comb under a Gaussian envelope of width ∝ ν_max centered at
ν_max**; the individual mode frequencies follow the asymptotic relation (ε, δν02 approximate — labeled).

**The honesty gate is intrinsic to the physics.** Solar-like oscillations require a **convective
envelope** — cool dwarfs (F/G/K/M) and red giants. Hot stars (radiative envelopes) don't ring this way;
their opacity-driven δ Sct / β Cep modes are the *instability strip* already overlaid on the HR panel. So
the seismic panel is **gated to the convective-envelope regime** (the SED coronal-band gate precedent),
and points the user at the instability strip for the hot side. Red giants ring slowly (ν_max ~ µHz) — a
huge, real, beautiful dynamic range.

**Architecture.** A pure function of the served M/R/Teff → **frontend-only**, a new `seismo.js` panel
(the `sed.js` precedent — derives everything from the marker's state, no backend touch). The échelle
diagram is the payoff. The pedagogical loop: show that the scaling relations *recover* the known M and R
(the inverse), closing the "this is how we measure stars" story.

**Gate 0 (measure first).** The Sun must reproduce ν_max ≈ 3090 µHz, Δν ≈ 135 µHz through the panel's own
computation; a red-giant marker (R ≈ 10 R☉) must ring at ν_max ~ 30 µHz with a visibly wider comb. Verify
on-screen (the échelle ridges are the thing that can silently render wrong).

**Chunks.**
- **C1 (frontend):** `seismo.js` — ν_max/Δν from M/R/Teff; a schematic power spectrum (Gaussian envelope
  × Δν comb); the seismic-mass/radius readout; gated to convective-envelope stars. Gate 0 (solar values).
- **C2 (frontend):** the **échelle diagram** (frequency mod Δν → ridges; l = 0/1/2 schematically) — the
  beauty chunk.
- **C3 (optional, note as scope-edge):** rotational mode splitting keyed to the vvcrit axis (ties to
  rotation) — likely deferred; recorded so it isn't re-proposed as novel.

---

## Axis D — The habitable zone (what the star warms)

**The lesson.** The circumstellar zone where liquid water is possible, from the star's L and Teff — and,
the real payoff, watching it **march outward** as the star brightens up the giant branch (Earth's fate:
the HZ sweeps past 1 AU, then swallows it). Ties directly into the existing true-size **scale bar**, which
already carries orbit landmarks and swallowed-orbit rings.

**Honesty tier & data.** Tier-2 — the **Kopparapu (2013/2014) HZ boundaries**, a standard climate-model
parameterization: the effective stellar flux thresholds S_eff(Teff) for the inner (runaway greenhouse)
and outer (maximum greenhouse) edges, then d = √(L/S_eff). Public, standard, labeled as a simplified
parameterization (not a climate model). L and Teff are already on `StellarState`.

**Architecture.** A pure function of L/Teff → **frontend-only**, a light band on the scale bar's log-
distance axis (`scale.js`) rather than a whole new subsystem — this is the scope-edge axis (it edges
toward planets, not pure stellar physics), so keep it a restrained overlay, not a planetary sandbox.

**Gate 0 (measure first).** The Sun's HZ ≈ 0.95–1.7 AU; a red giant (L ≈ 1000 L☉) HZ ≈ 30–50 AU. The band
must move visibly outward over the track, and a 1 AU (Earth) landmark must be seen entering, then exiting
(then being swallowed by) the HZ as the star evolves.

**Chunks.**
- **D1 (frontend): ✅ BUILT 2026-07-10** (Playwright 1440+390, zero console errors). Kopparapu **2014**
  (ApJ 787 L29, the corrected coefficients, 1 M⊕) inner/outer edges from L + Teff → the HZ band on the
  scale bar. A pure helper `hz.js` (`habitableZone(Teff,L)` → the four edges in AU; `inRange()` gate) +
  `scale.js` `setHZ()` drawing a solid **conservative band** (runaway greenhouse → maximum greenhouse)
  with dashed **optimistic** edges (recent Venus → early Mars); `#hz-toggle` in the scale panel. **Moist
  greenhouse dropped** (the 2014 runaway revision moved inside the 2013 moist edge — mixing them is
  inconsistent; the 2014 paper itself omits it), leaving four internally-consistent nested edges.
  **Measure-first (advisor reorder): coefficients validated against the solar anchor BEFORE drawing** —
  Sun (T*=0) → runaway 0.95 / maxGH 1.68 AU exactly (a wrong coefficient is a plausible-but-wrong band a
  screenshot can't catch). **The quartic DIVERGES outside 2600–7200 K**, so `inRange()` skips the compute
  AND the band entirely (not merely the caption — else NaN/absurd distance breaks the draw); the band
  honestly blinks off for hot stars with an out-of-range caption. **Axis auto-widens** past R_MAX for a
  luminous giant (the SN-idiom `logHi` extension) + swaps in the outer-planet landmarks (Neptune anchors
  the tens-of-AU reach). **Living-only:** `dropHZForModeSwitch()` in the shared mode-switch chokepoint +
  CSS hides the toggle in every endgame/stripped mode (verified: no leak onto the WD/SN/stripped scale
  bar). Gate 0 PASSED through the runtime: Sun 0.98–1.7 AU straddling Earth's ring; the same 1 M☉ marched
  to **34–65 AU past Neptune** at old age (Earth "left inside the conservative inner edge"); K/M-dwarf
  zones correctly **closer in** (advisor caught + fixed a reversed directional clause). Spectrum enters
  through Teff (the near-IR albedo/absorption effect IS the Teff-dependence); UV/X-ray/flares deliberately
  OUT of the band, owned by the caption caveat. Planet mass fixed at 1 M⊕ (no planetary sandbox).
- **D2 (frontend): NOT built** — the HZ **history** (ghost of the band at ZAMS vs now vs RGB; highlight
  the moment a landmark orbit enters/exits/is-swallowed). Deferred: the live march-outward on the age
  scrub already carries the payoff (drag the age and the band sweeps outward past Earth in real time).
  A future add if a static past-position trail proves worth it.

---

## Sequencing (cheapest-honest-win-first, and how they compose)

1. **Axis B — isochrone/cluster.** Cheapest real build: a modest MIST `.iso` download (the same real-grid
   idiom as the tracks — no interpolation-of-interpolation), reuses the HR panel, bulletproof famous
   pedagogy. Ship first.
2. **Axis C — asteroseismology.** Frontend-only, **no new data** (derives from `StellarState`), a new
   panel + the beautiful échelle diagram. Ship second.
3. **Axis D — habitable zone.** Frontend-only, one HZ formula, rides the scale bar. Cheap but scope-edge.
   Ship third.
4. **Axis A — the observer's view.** The meatiest (filter curves + reddening + a new CMD panel) and the
   highest conceptual payoff. Ship last as the **capstone**.

**Interconnections (the reason to plan them together):**
- **A × B = the real observed cluster diagram.** An observational CMD (Axis A) of a cluster isochrone
  (Axis B) is *exactly* the Gaia color–magnitude diagram of a star cluster — the single most important
  diagram in modern stellar astronomy. Build A last and it lands on top of B for free.
- **C × rotation (vvcrit).** Rotational splitting of oscillation modes ties the seismic panel to the
  existing rotation axis (C3, deferred).
- **D × the scale bar.** The habitable zone shares the log-distance axis with the swallowed-orbit rings —
  Earth's engulfment becomes one continuous story.

**Cross-cutting caution (inherited from the atlas rule).** Every new axis multiplies the UI; prefer
**overlays/views and opt-in toggles** over yet another always-on slider, and keep *view* axes (observer
distance/A_V, the seismic panel, the HZ band) visibly distinct from *evolution* axes so a viewing knob
never implies the star's track changed. Axes A/C/D are pure views (never touch the HR marker); Axis B is a
population view (the user's star is one point on the locus, not moved).

## Honesty tiering (applied)

- **A (observer):** Tier-1/2 — real reddening law + real filter curves on the real spectrum. Exact,
  testable (solar colors). The apparent quantities are a *view*, never on the spine.
- **B (isochrone):** Tier-1 — MIST's *published* `.iso` grid (primary), the from-tracks EEP construction
  only as a cross-check, so the claim is clean of the interpolation-of-interpolation caveat. The
  turnoff-age relation is bulletproof; still measure young-vs-old through the real path before the caption.
- **C (seismology):** Tier-2 — real scaling relations, labeled approximate; gated to the convective-
  envelope regime by the physics itself (hot-star pulsation → the instability-strip overlay).
- **D (habitable zone):** Tier-2 — a standard but simplified climate parameterization, labeled; the
  moving-HZ evolution is the real, visible payoff.

Each axis's Gate 0 is the measurement that must pass **before** its control/caption ships — the project's
standing rule that we never label a non-feature.
