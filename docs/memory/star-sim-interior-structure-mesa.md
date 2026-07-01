---
name: star-sim-interior-structure-mesa
description: "Real interior-structure sibling — MESA radial profile.data behind /structure, the honest Lane–Emden successor (0.25/1/2/6/15/25 M☉ mass slices — the three regimes: 0.25 fully convective, 1 radiative-core+conv-envelope, 6/15/25 convective-core+radiative-envelope; 15 = the SN progenitor, 25 brackets the upper SN range — PLUS the metallicity axis: 1 M☉ at [Fe/H]=−1/+0.5, the convective envelope shallows as Z drops)"
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

## The 0.25 M☉ slice (BUILT — a fully-convective M dwarf, the third regime)
- Goes the **other way** from the massive slices: below the ~0.35 M☉ boundary an M dwarf is
  **fully convective** — a *single* convection zone spanning centre→surface, no radiative
  region. Completes the **trilogy of regimes**: 0.25 fully convective / 1 M☉ radiative-core
  +conv-envelope / 6·15·25 M☉ convective-core+radiative-envelope. (advisor decisively chose
  this over the literal "Next: other-Z" — a third *regime* is visible-by-construction so the
  honesty gate is met automatically; other-Z is subtler, envelope-CZ-depth, do it after.)
- **Two run changes (both advisor-flagged pre-run):** (1) the **TAMS stop never fires**
  (0.25 M☉ MS lifetime ~10¹²⁻¹³ yr, Xc barely leaves ~0.714) → stop by `max_age = 2d9`
  (safely settled onto the ZAMS; pre-MS contraction is a few hundred Myr); (2) **ship a
  *settled-MS* profile, not a pre-MS-contracting one** — with the age stop the profiles
  cluster in early pre-MS (small timesteps) and only the last few are MS (timesteps balloon
  once settled). Both are fully convective but the honest claim is the MS structure (a
  pre-MS star convects for a *different* reason — Hayashi contraction). L settles at
  ~0.0105 L☉, Teff≈3707 K, R≈0.25 R☉ only in the last 3 of 22 profiles. Shipped
  **profiles 20/21/22** (177 Myr / 919 Myr / 2 Gyr; 3 = the slider minimum, and an M dwarf
  is genuinely static over Gyr so near-identical snapshots are honest).
- Measured mid-MS: **ρ_c≈135–138 g/cc, T_c≈7.4×10⁶ K** (*below* the Sun's ~1.5e7 — weak pp
  burning), **R≈0.247 R☉**, M=0.25, convective zone **0→1** (whole star), `expected_n`→3/2,
  X(r) a flat ~0.71 (fully mixed, unburned).
- **The polytrope-honesty INVERSION** (advisor's bonus — measured *before* writing it into
  the caption): a fully-convective star *is* the textbook n=3/2 polytrope, so unlike every
  other slice the real ρ(r)/ρ_c **hugs the n=1.5 overlay** (within ~1–5% at r/R 0.25/0.5/
  0.75) and sits far above the more-concentrated n=3. **The one bucket where the idealization
  *works*** — inverting the panel's usual "the departure is the lesson."
- **NOT a pure drop-in this time:** runtime `structure.py` unchanged, but the accompanying
  changes are a new `requires_structure_lowmass` marker (≤0.5 M☉ gate, mirrors
  `requires_structure_massive`), **2 new tests** (fully-convective span; ρ-hugs-n=1.5), the
  off-grid snap probe re-pointed **0.3→0.15** (0.25 is now the grid floor, so 0.3 is no
  longer far off-grid), and a **small frontend caption refinement** in `structure.js`
  (detect the single centre→surface zone → "fully convective → …the rare case the real
  profile follows it"; blank the "conv. base" readout — no radiative base). **236 pytest**
  (was 234, +2). Playwright-verified 1440 px, zero console errors (screenshot: ρ overlapping
  the n=1.5 dash, whole-panel convective shading).

## The metallicity axis (BUILT — 1 M☉ at [Fe/H] = −1.0 and +0.5, the first non-mass axis)
- The "other-Z buckets" Next, now built — the **first slice that varies [Fe/H] instead of
  mass**. Hold the star at 1 M☉, change only Z → "same star, different metallicity → different
  convection zone", overlaid on the solar 1 M☉ slice. Payoff = the **solar-abundance-problem
  effect**: lower Z → more transparent envelope → **shallower convective envelope** (base at a
  *higher* r/R). Advisor-settled: hold mass at 1 M☉ (don't drift), it reads as a direct overlay.
- **The gating measurement came first (honesty rule) and MUST be at matched central-H, not
  matched age** — a metal-poor 1 M☉ is hotter/shorter-lived, so equal age ≠ equal phase (the
  confound is *worse* than for the mass slices). Measured mid-MS (Xc≈0.35) convective-envelope
  base r/R: **[Fe/H]+0.5 → 0.70** (deepest, outer ~31%) · **0.0 → 0.75** (Sun) · **−1.0 → 0.95**
  (thin surface sliver). All three visibly, monotonically distinct → clears the gate. Ran
  **[Fe/H]=−2.0** too (base 0.99) but it **fragments** into tiny adjacent zones and is visually
  indistinguishable from −1.0 → **measured but NOT shipped** (don't ship a bucket you can't
  distinguish just to have "more" — advisor).
- **This is NOT a core-type flip** (advisor predicted): the core stays radiative
  (`expected_n = 3`) at every Z; the entire visible effect is the envelope-depth band. (Contrast
  the mass axis, where the flip to a convective core drives `expected_n`→3/2.)
- **Two MESA-run gotchas** (every prior slice varied only `initial_mass`): (1) **change `Zbase`
  too, not just `initial_z`** — the recipe hardcodes both at 0.0152; a mismatched `Zbase` gives
  inconsistent Type-2 opacities. Round Z → clean label (`structure.py`: [Fe/H]=log₁₀(Z/0.0152),
  so Z=0.00152→−1.00, Z=0.048→+0.50 auto). (2) **Keep the TAMS stop** (unlike the 0.25 M☉ dwarf)
  — a metal-poor 1 M☉ still reaches central-H exhaustion in a few Gyr. Rates cache already built,
  so 2nd/3rd concurrent 1 M☉ runs finish in ~1–2 min.
- **Runtime NO code change** (the index already snapped mass→feh→age; the frontend already passed
  the marker's [Fe/H] and reported the snapped value). Accompanying: data (dirs `1Msun_fehm1p0` /
  `1Msun_fehp0p5`, 5 profiles each, mid-MS anchor by Xc) + a new `requires_structure_multifeh`
  marker (gated on |[Fe/H]|>0.3 → skips not fails on a solar-only checkout) + one test
  (`test_convective_envelope_shallows_as_metallicity_drops` — the **matched-Xc monotone trend**,
  base(+0.5)<base(0)<base(−1), all `expected_n`=3) + two small `structure.js` polishes: a
  **[Fe/H]-snapped-far note** (mirrors the mass one — the Z grid is 1 M☉-only, so a 6 M☉/[Fe/H]−1
  request snaps to solar-Z and now says so; verified live) and the "conv. base" tooltip extended
  to the Z→envelope-depth link. **237 pytest** (was 236, +1). Playwright-verified 1440 px (band
  spans r/R 0.69→1.0 at +0.5, a sliver at 0.97 at −1.0; zero console errors). Recipe §10.

## The [Fe/H] axis at a SECOND mass — the 0.8 M☉ K dwarf (recipe §11) — BUILT

The metallicity axis now lives at **two masses (0.8 and 1 M☉)**, so the interior grid is a genuine
**partial 2D (mass × [Fe/H]) grid** for the first time. The 0.8 M☉ K dwarf is the same *regime* as
the Sun (radiative core + convective envelope) but a **deeper** envelope, so the Z-shallowing is
stronger AND — the load-bearing difference — **stays a single unfragmented zone at every Z**.
Matched-Xc envelope base **0.66 / 0.69 / 0.81** at [Fe/H] **+0.5 / 0 / −1**, monotone at every
phase, core stays radiative (`expected_n`=3, not a flip).

**Chosen by MEASUREMENT over two rejects** (the §10 non-ship discipline again — advisor-led fork:
"measure, don't physics-guess"; user picked 0.8 after seeing the 1.3 result):
- **6 M☉ convective-*core* edge vs Z** (the *novel* lesson — Z acting on a core, not an envelope)
  **FAILED the gate**: core-edge r/R shift across [Fe/H] −1…+0.5 is only ~0.02–0.03 and **loses
  monotonicity below Xc≈0.5** (metal-rich↔solar cross over). Massive stars respond to Z in R/Teff,
  not convective-core mass fraction — nothing visibly-monotone to show. (Advisor predicted this.)
- **1.3 M☉ envelope** (the transitional double-convective mass — a convective core AND a convective
  envelope at once, unlike any shipped slice) gave a clean **2-point** trend (+0.5 base 0.82, solar
  0.89) but its thin surface zone **fragments into ~0.99 slivers by [Fe/H]=−0.5** (real
  `mixing_type==1`, NOT an OR-clause artifact — split-mask-checked), and −0.5 ≈ −1 (indistinguishable
  from each other, the §10 non-ship condition). Not shipped as a Z axis; the double-convective
  *structure* remains a possible future standalone slice.
- **0.8 M☉ envelope** = the clean winner (deep K-dwarf envelope has room to shallow without breaking).

**Two run changes vs §10:** cap with **`max_age = 2.0d10`** (a K-dwarf MS is ~25 Gyr — the central-H
TAMS stop fires only after an unreasonable integration; 20 Gyr reaches mid-MS Xc≈0.3), and drop the
pre-MS Hayashi profiles (all fully-convective `[0.16–1.0]`, misleading). Otherwise `initial_mass=0.8`
with the three Zbase/initial_z pairs (0.048/0.0152/0.00152 — **change Zbase too**, §10 gotcha).

**Runtime NO code change** again (mass→feh→age snap; a Z-less mass falls back to solar — BOTH the
within-0.8 Z snap and the 2/6 M☉→solar fallback verified through the real `interior_structure()`
path, closing the advisor's "partial-2D-grid topology" concern). +3 data dirs (`solar_0p8Msun` /
`0p8Msun_fehp0p5` / `0p8Msun_fehm1p0`) + 1 test (`test_kdwarf_envelope_shallows_as_metallicity_drops`,
reusing a **mass-parametrized** `_midms_envelope_base`, existing `requires_structure_multifeh` marker
— no conftest change) + a `structure.js` comment refresh (grid now "0.8 and 1 M☉"; the snapped-far
note reads the *snapped* result so it stays correct as the axis grows). **238 pytest** (was 237, +1).
Playwright-verified 1440 px (conv. band visibly, monotonically shallows +0.5→−1: conv. base
0.659→0.694→0.807; radiative core → n=3 at every Z; zero console errors).

## [Fe/H]-axis clean window MEASURED to its edges — 0.6 & 1.1 M☉ NON-SHIPS (recipe §12)

The "extend [Fe/H] to still more masses" thread is **closed by measurement** — both neighbours
of the shipped 0.8/1.0 window fail the ship gate in the two complementary ways the mass axis
predicts (no data/test/code ships — nothing cleared the gate; a documented negative result like
[Fe/H]=−2 §10 and 1.3 M☉ §11). Envelope-base spread across [Fe/H] +0.5→−1 (matched mid-MS Xc):
- **0.6 M☉ — compression:** 0.633/0.642/0.721, spread **~0.09 < the 0.1 gate**, and **+0.5≈0.0**
  (0.633 vs 0.642, <0.01 — not a *visibly monotone* trend). The 1.0→0.8→0.6 spread SHRINKS
  (0.25→0.15→0.09): a deeper envelope gives a *smaller* Z-response, not a bigger one (advisor
  predicted). Core radiative at every Z incl. +0.5 (fully-conv-at-+0.5 degeneracy worry cleared).
  Long MS → `max_age=6d10` to reach mid-MS.
- **1.1 M☉ — fragmentation + core-flip:** spread big (0.26) & monotone BUT the −1.0 envelope
  **fragments into 2 zones** (0.99 sliver — the 1.3 M☉ failure, pushed −0.5→−1.0), AND the core
  type is **inconsistent across Z** (conv at +0.5 / rad at solar / conv at −1.0) → `expected_n`
  flips *within* the axis, breaking the clean "pure envelope-depth, core stays n=3" story. The
  flip is striking but non-monotonic/phase-sensitive — an aside, not a feature.
- **0.9 M☉** is the only remaining clean option (spread ~0.20, unfragmented) but **redundant** — a
  point *between* two shipped masses, no new regime → not shipped either.

**The usable clean-envelope [Fe/H]-axis window is 0.8–1.0 M☉ and is fully covered.** Measured via
raw `mixing_type` (correct for a non-ship — the OR-clause only adds r/R≥0.97 cells, can't rescue a
<0.01 gap). Container/temp cleaned up. Advisor-confirmed: thread exhausted; extending Z further is
not productive.

**Next (a USER choice, not auto-pursued):** ship the **1.3 M☉ double-convective structure** on its
own merits — a mass with a convective core AND convective envelope at once, a genuinely new
*structure* regime (not a Z axis) the panel doesn't yet show. See ROADMAP + [[star-sim-roadmap]].
