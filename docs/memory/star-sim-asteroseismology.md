---
name: star-sim-asteroseismology
description: Axis C of the outward quartet — the asteroseismology panel (seismo.js): power spectrum + échelle diagram from the seismic scaling relations, a pure frontend view of Teff/log g/R.
metadata:
  type: project
---

The **asteroseismology panel** — Axis C of the outward quartet ("the star rings like a
bell"). Built 2026-07-13 (C1+C2 together, frontend-only, Playwright 1440+390 zero console
errors). The last piece of the quartet → **the outward quartet (A/B/C/D) is now complete.**

**What it is.** A new `#seismo-panel` + `frontend/src/seismo.js`. A pure VIEW of the marker's
served `Teff_K` / `logg` / `R_rsun` (no backend touch — the `sed.js`/`hz.js`/`cmd.js` precedent),
a pushed-data consumer fed from `paintState` via `refreshSeismo(s)`. Two stacked plots on one
canvas: (top) the **schematic power spectrum** — a Δν comb of ℓ=0/1/2 modes under a ν_max Gaussian
envelope, with a ν_max dashed marker + a Δν bracket; (bottom) the **échelle diagram** — frequency
mod Δν (x) vs frequency (y) → vertical ridges, ℓ=0 (white) + ℓ=2 (pink) packed into one ridge,
ℓ=1 (cyan) offset ~½Δν across. A readout caption below.

**The physics (Tier-2, labeled approximate — NOT a pulsation solve).** The two scaling relations:
- ν_max/ν_max,⊙ = (g/g_⊙)·(Teff/Teff_⊙)^(−1/2)
- Δν/Δν_⊙ = √(ρ̄/ρ̄_⊙) = √((M/M_⊙)/(R/R_⊙)³)
- **Real IAU/Huber solar anchors: ν_max,⊙=3090 µHz, Δν_⊙=135 µHz, log g_⊙=4.4377, Teff_⊙=5772.**

**Load-bearing decisions (all advisor-settled):**
1. **Keep the REAL solar anchors, don't re-anchor to the sim-Sun.** The sim-Sun is documented as
   not solar-calibrated (Teff~5835, log g~4.425), so it rings at **2984/132 µHz — ~3% below the
   canonical 3090/135, and that is the honest PASS**: a puffier/hotter "Sun" genuinely has a lower
   ν_max. The offset is common-mode → cancels in every relative comparison and in the Δν-relative
   échelle; only the absolute number carries it. Same class as the B-band ZP offset
   ([[star-sim-observer-cmd]]). Forcing 3090 would be subtly wrong physics + overstate the method's
   ~few-% systematic. The caption owns it.
2. **Current mass recovered EXACTLY from log g + R** (`M/M_⊙ = (g/g_⊙)(R/R_⊙)²`) — sidesteps the
   `mass_init` vs mass-loss trap (log g already encodes the current mass). No new state field needed.
3. **The M/R "recovery" is THE PRINCIPLE, not a measurement.** We compute ν_max/Δν *from* g and R,
   so inverting them recovers exactly what we put in — the match is arithmetic (there's no light
   curve to FFT). The caption says "the principle Kepler & TESS use to weigh stars", **never** "the
   sim measured this star's mass". This is the one real honesty risk in the feature.
4. **Gate-to-caption at Teff≈6700 (TEFF_CONV_MAX), not hide.** Solar-like p-modes need a convective
   envelope; hot stars (radiative) pulsate via the κ-mechanism → the instability strip. Above the
   gate the panel stays VISIBLE and blanks the spectrum with a note pointing at the variable-star
   HR overlay (the HZ-band gate-to-caption precedent). **Floor no lower than 6700** — Procyon
   (~6530 K) is a textbook solar-like F oscillator; measured 1.3–1.6 M☉ ~6500 K stars ring ON with
   sane values before shipping.
5. **Living-only via the shared chokepoint is REQUIRED, not tidiness.** `dropSeismoForModeSwitch()`
   in `dropHeliumForModeSwitch` (+ CSS `body.stripped-mode`/`body.binary-view .seismo-panel`). A
   cooling WD (log g~8, Teff dipping below 6700) would slip a pure Teff gate and paint a garbage
   ~10⁷ µHz spectrum — and WD/WR/SN/stripped states aren't solar-like oscillators anyway. Verified:
   hidden in WD mode, restored on Back.

**Gate 0 measured through the REAL served state BEFORE drawing** (the cardinal rule): Sun 2984/132,
R≈10 giant 34.2/4.2, RGB-tip 0.54/0.18, 5 M☉ MS (15.7 kK) gates off. Échelle ridges verified
visually on both the Sun (Δν=132) AND the giant (Δν≪1) — the plan warned the échelle "renders
silently wrong". ε (asymptotic phase offset) is schematic/clamped — it only shifts ridges together
mod Δν (cosmetic); the recognizable structure is the ℓ=1 half-Δν offset + the close ℓ=0/ℓ=2 pair.
Envelope σ=0.25·ν_max (schematic, labeled; true FWHM~0.66·ν_max^0.88).

**Wiring** (the `cmd.js`/observer template): `index.html` `#seismo-panel` + canvas + caption + `?`
help; `main.js` `createSeismo`, `refreshSeismo(s)` in `paintState`, `dropSeismoForModeSwitch` in the
chokepoint, RESPONSIVE resize entry (`seismo-canvas`, maxW 560, h 380), `fillSeismoCaption`; two
CSS hides + `#seismo-canvas` style. NO backend change, so **pytest unchanged (425)**.

Related: [[star-sim-observer-cmd]] (Axis A), [[star-sim-isochrone-cluster]] (Axis B),
[[star-sim-habitable-zone]] (Axis D), [[star-sim-frontend-ux]]. Plan:
`docs/plans/outward-quartet-atlas.md` §Axis C. **C3 (rotational mode splitting keyed to vvcrit) is
noted scope-edge, deferred.**
