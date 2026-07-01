---
name: star-sim-interior-structure-mesa
description: "Real interior-structure sibling — MESA radial profile.data behind /structure, the honest Lane–Emden successor (1 M☉ solar slice built end-to-end)"
metadata: 
  node_type: memory
  type: project
  originSessionId: a58b4f87-b1ac-48c9-a0ec-9b714f38bb95
---

The **real interior-structure** feature — the honest successor to the Lane–Emden panel
([[star-sim-phase3-lane-emden]]). Where Lane–Emden gives an *idealized* static polytrope
from an index `n`, this serves a **real** radial structure of the selected star from an
offline MESA `profile.data` snapshot, and overlays the canonical polytropes so you can see
how good the idealization is. **Built as one vertical slice: 1 M☉ solar, end-to-end**
(picked over a broad grid per advisor — prove the chain first). ROADMAP row flipped
idea→done. 229 pytest.

## Architecture (a §3 sibling, like lane_emden/spectra)
- `backend/star_sim/structure.py` + `/structure?mass=&feh=&age=` route (in `api.py`, right
  after `/polytrope`). **Bypasses `PROVIDER`** — interior structure is a sibling, NOT a
  `StellarState`. The sibling has its **own** ~15-line MESA-profile parser and **never imports
  a provider** (importing `providers.mesa` would be a §3 boundary bug — a consumer reaching
  into a provider). `StructureDataMissing` → 503 (like `SpectraDataMissing`).
- **Snaps** (mass, [Fe/H], age) to the nearest saved snapshot and reports the *true* values —
  no interpolation across snapshots (raw MESA profiles have no EEP alignment). The panel
  **jumps** between the handful of snapshots as age scrubs, labeled "nearest saved snapshot".
- Returns center-normalized `rho_over_rhoc`/`T_over_Tc`/`P_over_Pc` + `X`/`Y`/`Z` vs `r_over_R`,
  `convective`/`convective_zones` (from MESA `mixing_type==1` ∪ Schwarzschild `gradr>grada`),
  `central` scalars (ρ_c/T_c/P_c/R/M), `polytropes` (the two canonical overlays), `expected_n`,
  `available_ages_yr`.
- Frontend `frontend/src/structure.js` — a **live consumer** wired into `paintState` (own
  debounced latest-wins fetch, like spectrum.js). Draws ρ bold-filled + T/X thinner lines +
  **dashed n=1.5/3 polytrope references** + shaded convective bands; snapshot caption; scalar
  readout; **snapped-far note** when the star is off-grid (today everything snaps to 1 M☉
  solar — honestly stated). New `structure-panel` in index.html (after the lane panel), auto-
  picked up by `layout.js` (DOM order) + registered in the RESPONSIVE resize list.

## The two advisor-settled calls
1. **Canonical n, NOT a best fit.** Overlay draws n=3/2 (convective/adiabatic) and n=3
   (radiative, Eddington standard model) as FIXED references — a fitted n would hide the very
   mismatch the panel exists to show. `expected_n` is a labeled hint from the *core* type
   (radiative→3 / convective→3/2), never a fit. The real ρ sits near/between the two and the
   departure IS the lesson.
2. **Tolerant tests.** The generating run is deliberately NOT solar-calibrated (no α_MLT/Y
   tuning), so exact SSM numbers won't land. `test_structure.py` (9 tests) gates on invariants
   that hold regardless: convective envelope exists in the outer radius fraction, radiative
   core, monotone ρ spanning ≳6 decades, ρ_c/T_c of the right *order* (~150 g/cc, ~1.5e7 K).

## Data generation (MESA-only, offline — MIST has no profiles, live solve out of scope §2/§9)
- Self-run once via **Docker MESA** (`evbauer/mesa_lean:r24.03.1.01`, ~19.6 GB image), the
  solar recipe ([[star-sim-phase4-mesa]]) + profile snapshots. **On Windows: start Docker
  Desktop's Linux engine first** (`docker info` must respond — the CLI works even when the
  daemon is down, which silently empties `docker images`). Used `docker cp` for files (robust
  vs Windows bind-mount drive-sharing).
- **Two inlist additions:** `write_profiles_flag=.true.` + `profile_interval=25`; and in
  `profile_columns.list` **uncomment `grada`, `gradr`, `mixing_type`** (the convection
  indicator — the one thing the polytrope can't fake, the panel's reason to exist). Profile
  header (line 3) carries `star_age`/`model_number`, so age-snapping needs NO `profiles.index`.
  profile.data shares history.data's 6-line-header format.
- Recipe: `backend/docs/mesa_structure_recipe.md`. Profiles gitignored under
  `data/mesa_profiles/solar_1Msun/` (5 snapshots ZAMS→TAMS: profile 8/9/10/11/13).

## Measured / gotchas
- Mid-MS (≈ solar age, profile 10): **ρ_c≈190 g/cc, T_c≈1.66e7 K, R≈1.06 R☉**, radiative core
  (n=3) + **convective envelope base r/R≈0.75** (SSM ≈0.71 — close, not calibrated). ρ/ρc sits
  *below* even n=3 (evolved dense He-core). X(r) visibly **hollowed in the core** (H burning).
- **Near-ZAMS (profile 8) shows a REAL transient convective core** → `expected_n=3/2`, an honest
  label flip. Verified against the raw column (`mixing_type==1` at center; mid-MS center is 0),
  NOT an artifact of the `gradr>grada` OR clause — it's the early-MS ¹²C→¹⁴N-burning core before
  CN equilibrium. X(r) there is nearly flat (unburned).
- No JS test harness → **Playwright screenshot IS the regression check** (bundled Chromium via
  the npx-cache `playwright` — import it by absolute `file://` path + default-export destructure,
  since ESM ignores NODE_PATH and playwright is CJS). Verified 1440 + 390 px, zero console errors,
  snapped-far note renders.
- **Port gotcha:** a stale uvicorn from a prior session held :8000 (no `/structure` route → 404
  looked like a bug); used :8010. Don't assume :8000 is your fresh server.

**Next:** a 2/6 M☉ slice (the convective-core↔radiative-envelope flip — 6 M☉ is the opposite of
the Sun) drops in as another `data/mesa_profiles/<run>/` dir with **no code change** (the index
globs the tree and snaps on the true header mass/Z/age). See ROADMAP + [[star-sim-roadmap]].
**Advisor caveat to re-check then:** `_convective_mask` ORs `mixing_type==1` with Schwarzschild
`gradr>grada` — clean for the 1 M☉ slice, but in a μ-gradient region a zone can be Schwarzschild-
unstable yet **Ledoux-stable** (MESA calls it radiative/semiconvective, mixing_type 0/3), where
the OR would over-shade. The convective-core slice is exactly where semiconvection appears, so
re-verify the shading against `mixing_type` there (or drop the OR to mixing_type-only).
