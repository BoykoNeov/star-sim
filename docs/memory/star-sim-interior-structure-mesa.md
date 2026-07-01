---
name: star-sim-interior-structure-mesa
description: "Real interior-structure sibling — MESA radial profile.data behind /structure, the honest Lane–Emden successor (1/2/6/15/25 M☉ slices; the convective-core↔radiative-envelope flip built, 15 M☉ = the SN progenitor, 25 M☉ brackets the upper SN range)"
metadata: 
  node_type: memory
  type: project
  originSessionId: a58b4f87-b1ac-48c9-a0ec-9b714f38bb95
---

The **real interior-structure** feature — the honest successor to the Lane–Emden panel
([[star-sim-phase3-lane-emden]]). Where Lane–Emden gives an *idealized* static polytrope
from an index `n`, this serves a **real** radial structure of the selected star from an
offline MESA `profile.data` snapshot, and overlays the canonical polytropes so you can see
how good the idealization is. **Built end-to-end: 1 M☉ solar first (prove the chain per
advisor), then the 2 & 6 M☉ slice — the convective-core↔radiative-envelope FLIP.** ROADMAP
row flipped idea→done. 232 pytest.

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
  `data/mesa_profiles/solar_{1,2,6}Msun/` (5 snapshots each, ZAMS→TAMS). **2/6 M☉ gotcha:
  `./mk` builds `star` INTO each work dir (stock `rn` runs `./star`) — compile every dir, use
  SEPARATE work/LOGS dirs so runs don't clobber. Ran both concurrently detached (~4–5 min each).**

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

## The 2 & 6 M☉ flip (BUILT — the mirror of the Sun)
- Intermediate-mass MS star = **convective core** (CNO ε∝T¹⁶⁻¹⁸, centrally peaked) under a
  **radiative envelope** — the exact opposite of the 1 M☉ case. Runtime needed **NO code
  change** (index globs the tree, snaps on the true header mass/Z/age — the "drops in as a
  bucket" property). The accompanying changes: a **new data marker** `requires_structure_massive`
  (conftest, gated on a ≥4 M☉ slice so the flip test SKIPS not FAILS on a 1 M☉-only checkout —
  `requires_structure_data` alone is satisfied by the Sun), **3 flip tests** (6 M☉ convective-
  core+n=3/2+radiative-envelope-at-r/R=0.9; the direct Sun-vs-6M☉ mirror on the same two probe
  radii; 2 M☉ also core-convective), and **one stale test fixed** (`test_out_of_grid_mass_snaps`
  — off-grid 7.3 M☉ used to snap to 1.0, now snaps to 6.0; rewrote to assert snap-to-min-saved).
- **Snapshot-selection is the real risk** (advisor): a massive-star convective core is largest
  mid-MS and **shrinks toward TAMS** (the 2 M☉ core is already gone at central-H-exhausted). So
  deliberately kept a healthy **mid-MS** anchor (Xc≈0.4, central `mixing_type==1`): 6 M☉ profile17
  (Xc 0.41), 2 M☉ profile16 (Xc 0.39) — checked central mixing_type before copying, don't just
  span by age. Measured mid-MS: 6 M☉ ρ_c≈16/T_c≈2.95e7/R≈3.89, core r/R 0→0.131; 2 M☉ ρ_c≈71/
  T_c≈2.26e7/R≈2.07, core 0→0.088. `expected_n` flips to **3/2**; envelope radiative at r/R=0.9.
- **The semiconvection caveat did NOT bite** — checked across the FULL slice incl. the near-TAMS
  snapshots where it's worst (advisor caught that mid-MS is the *weakest* test: the Ledoux-stable
  μ-gradient is left behind by a *receding* core, so it grows toward TAMS). Compared
  `mixing_type==1` vs `gradr>grada` vs the served OR on 6 M☉ profile17/19/22 and 2 M☉ profile16/18/21:
  the OR adds **at most 1–2 cells**, and **every one is at r/R > 0.98** — a boundary cell of the thin
  near-surface convection sliver, **never a mid-radius shell** in the μ-gradient between the receding
  core (r/R≈0.05–0.13) and the envelope. So no over-shading of a Ledoux-stable region anywhere on the
  slice → **no change to the OR**. (Confirms the likely cause: the inlist used **default MESA
  (Schwarzschild, Ledoux off)**, so `mixing_type` *is* the Schwarzschild test and the OR is a near
  no-op by construction.) If a future run enables Ledoux and DOES show a spurious mid-radius shell,
  drop the OR to mixing_type-only.
- Playwright-verified 1440 px: 6 M☉ B5 V, caption "6 M☉ … convective core → canonical n = 3/2",
  core shading at r/R 0→0.13, X(r) flat-then-rising (mixed-core signature), zero console errors.

## The 15 M☉ slice (BUILT — the SN arc's canonical progenitor)
- Extends the massive end to the **canonical core-collapse SN progenitor** (the supernova
  light curve is measured at 15 M☉ — [[star-sim-supernova-remnant-endgame]]). The payoff is
  **honesty where a built feature lives**: before this, a 15 M☉ structure request snapped to
  the 6 M☉ run + showed the "snapped-far" note. Same recipe (`initial_mass=15.0`, Z=0.0152,
  TAMS stop), **NO runtime code change** (drops in as a bucket) — the accompanying change is
  one new gated test (`test_massive_15msun_has_the_deepest_convective_core`, same
  `requires_structure_massive` marker, **no conftest change** — the ≥4 M☉ gate already covers
  it) + the recipe §7 record. Snapping topology unaffected (off-grid 0.3 M☉ still snaps to the
  lightest; no test asserts high-mass→6). **233 pytest** (was 232, +1).
- Shipped **5 snapshots** (profiles 9/10/11/12/13, near-ZAMS→TAMS), mid-MS anchor **profile11**
  (model 250, age 6.81 Myr, Xc 0.409, central `mixing_type==1`) — selection caution is
  **sharpest here** (a 15 M☉ core recedes fastest toward TAMS), so anchored by central mixing
  type + Xc, not age. Measured mid-MS: **ρ_c≈5.9 g/cc, T_c≈3.5×10⁷ K, R≈6.67 R☉, convective core
  0→0.178** — hotter/less-dense than the 6 M☉ core and the **deepest** of the 2/6/15 set;
  `expected_n`→3/2, envelope radiative at r/R=0.9.
- **Advisor OR-clause re-check at this slice** (the μ-gradient region grows with mass): across
  all five 15 M☉ snapshots every cell the served OR adds beyond `mixing_type==1` is at r/R≥0.97
  (near-surface opacity bump), **never a mid-radius shell** — so no over-shading, same as 6 M☉
  (inlist still default-Schwarzschild). The little shells at r/R≈0.19–0.21 just above the core
  are MESA's own `mixing_type==1` (real receding-core convection), not OR-invented. Playwright
  1440 px: caption "15 M☉ … convective core → canonical n = 3/2", zero console errors.

## The 25 M☉ slice (BUILT — brackets the upper SN progenitor range)
- Extends the massive end **past** the canonical 15 M☉ SN progenitor to bracket the *upper*
  core-collapse range — the 1→2→6→15→**25** "deepest convective core yet" ladder into
  heavier-progenitor territory (advisor: "bracket the SN range" = go heavier, 25 over the
  weaker gap-filler 10; "cheapest" just meant *mechanical*, don't deliberate). Same recipe
  (`initial_mass=25.0`, Z=0.0152, TAMS stop), **NO runtime code change** (drops in as a
  bucket) — the accompanying change is one new gated test
  (`test_massive_25msun_brackets_the_upper_sn_range`, same `requires_structure_massive`
  marker, **no conftest change** — the ≥4 M☉ gate already covers it) + the recipe §8 record.
  Snapping topology unaffected (off-grid 0.3 M☉ still snaps to the lightest). **234 pytest**
  (was 233, +1).
- Shipped **5 snapshots** (profiles 9/10/11/12/13, near-ZAMS→TAMS), mid-MS anchor **profile11**
  (model 250, age 3.25 Myr, Xc 0.465, central `mixing_type==1`) — the selection caution is
  **sharpest of the whole set** (a 25 M☉ core recedes fastest), so anchored by central mixing
  type + Xc, not age. The run wrote 15 profiles. Measured mid-MS: **ρ_c≈3.79 g/cc, T_c≈3.78×10⁷ K,
  R≈8.47 R☉, convective core 0→0.228** — the **deepest** of the 2/6/15/25 set (0.131→0.178→0.228),
  hottest + lowest-density core; `expected_n`→3/2, envelope radiative at r/R=0.9. Test threshold
  set FROM the measurement (core > 0.20).
- **Advisor OR-clause re-check** (as at 15 M☉): the served OR adds 10 cells beyond
  `mixing_type==1` at the mid-MS anchor, all either just above the core (r/R≈0.23–0.27,
  receding-core convection) or at the near-surface opacity bump (r/R≈0.97) — **zero at
  mid-radius (0.3<r/R<0.95)** — so no over-shading, same as 6/15 M☉ (inlist still
  default-Schwarzschild).
- **Playwright skipped** (unlike prior slices): the change is pure data + one gated test + doc,
  **zero frontend/runtime code touched**, and the served `/structure` payload was verified
  directly through the real `interior_structure()` code path — a screenshot would only
  re-exercise the unchanged 15 M☉ render path with structurally identical data.

**Next:** other-Z buckets drop in the same way (but verify the structural effect is *visible in
the panel* before shipping a control, per the honesty rule). See ROADMAP + [[star-sim-roadmap]].
