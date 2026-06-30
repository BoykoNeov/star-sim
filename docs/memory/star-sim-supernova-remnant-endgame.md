---
name: star-sim-supernova-remnant-endgame
description: "Core-collapse SN + NS/BH endgame arc — Chunk 0 gate DONE + Chunk 1 BUILT (backend vertical: supernova.py sibling + EndgameResult progenitor scalars + CACHE_VERSION 11→12 + /supernova route) + Chunk 2 BUILT (frontend: reversible sn-mode gateway + L-vs-LINEAR-days light-curve panel + ⁵⁶Ni slider + cited sn.js observed overlays = the deferred Tier-1 anchor) + Chunk 3 BUILT (3D expanding-fireball→remnant shader: star.js FIREBALL_FRAG + REMNANT_FRAG, cooling-Teff color the only honest cue, snGrow/snFade beats, NS hot-dot reveal vs BH winks-out — measured BH-on-SN at 30 M☉ solar) + Chunk 4 BUILT (frontend: comp.js drawSNOnion pre-collapse onion shell — real boundaries remnant/CO/He/total sized area∝mass, inner Si/Fe faint schematic since MIST ends before the iron core forms, honest NS-vs-BH contrast (BH swallows the CO core → no copper band), exaggerated slider-tied ⁵⁶Ni ring; no backend change) + Chunk 5 BUILT (remnant branch NS/BH/failed-SN: a labeled fallback continuum φ=smoothstep(CO 7→12) softens the old CO=7 cliff in the light curve AND the onion — remnant grows, ejecta+ejected-Ni shrink; the NS↔BH label flips at the remnant crossing NS_MAX~2.5 not at CO=7 — advisor blocker, so 30 M☉ solar is now a heavy NS not a BH; failed/direct-collapse SN does NOT expand — stays at R₀ and dims, the 'disappearing supergiant' — advisor blocker; 3D reconciled: NS dot / BH-fallback fades-no-dot / failed winks-out; new fields fallback_fraction/failed_sn/m_ni_ejected_msun), 220 pytest — the SN arc is COMPLETE. Plan docs/plans/radioactive-afterglow-requiem.md. Fills the dead type=\"SN\" branch. Constraints the user fixed: ⁵⁶Ni light curve, homologous ejecta expansion, *maybe* light nucleosynthesis, EXPLICITLY no explosion mechanism, observed light curves as verification. Hybrid sibling (classify on the spine, compute in supernova.py + /supernova)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1110aafc-b403-49c6-b0c6-a56da0da566b
---

The user wants an endgame for **core-collapse supernovae + their compact remnants
(neutron stars & black holes)** — the successor to the branch the current endgame
classifier reaches but leaves un-rendered (`type="SN", states=[]`).
**Status: Chunk 0 (gate) DONE; Chunk 1 (backend vertical) BUILT; Chunk 2 (frontend
gateway + light-curve panel) BUILT; Chunk 3 (3D fireball→remnant) BUILT; Chunk 4
(pre-collapse onion shell) BUILT; Chunk 5 (remnant branch NS/BH/failed-SN + cliff
softening) BUILT — the SN arc is COMPLETE.**
Plan: `docs/plans/radioactive-afterglow-requiem.md` (sibling to
`smoldering-cinder-gateway.md`). This file holds the locked constraints + the gate's
measured verdict + Chunk 1/2's built state; the plan is the design source of truth.

**Chunk 1 BUILT (backend, 215 pytest green, no frontend):**
- `EndgameResult` gained `pre_sn_radius_rsun`/`he_core_msun`/`co_core_msun`/`h_retained`,
  populated by `MISTProvider.endgame()` **only on the SN branch** (None for WD/WR/none and
  for Stub/MESA). `CACHE_VERSION` **11→12** parses `he_core_mass`/`c_core_mass`/`o_core_mass`
  (the **Mcur pattern** — cached in `_TRACK_COLS`, read straight off the snapped track, NOT
  blended in `_grid_window`/`_blend_windows`). `StellarState` untouched.
- **R₀ estimator SETTLED (the open knob):** max radius over the final-phase (CHeB-onward)
  rows **excluding the terminal EEP row** — a low-g artifact that can spuriously *inflate*
  (g=GM/R²) **or** shrink R, so `max` could grab an inflated terminal; excluding it + max
  (not the median, which the gate found underestimates by averaging in compact pre-RSG rows)
  captures the RSG extent. t_p∝R₀^(1/6) is weak, so the estimate is robust.
- `supernova.py` = a **pure sibling** (imports only `state.StellarState`, never the provider):
  a frozen `Progenitor` input bundle (route builds it from the EndgameResult), gate-cited
  constants, `supernova_model(progenitor, m_ni, e_kin)` → `SupernovaModel` (light curve +
  photosphere `StellarState`s). Light curve = **`w·L_p·rise + (1−w)·L_radio`** (the blend
  suppresses the t=0 ⁵⁶Ni deposition spike that a `max()` would surface as a false peak).
  Photosphere `R=v·t` (homologous), Teff from Stefan-Boltzmann, `logg` honestly negative
  (−5 late; the boiling-fireball gate is Chunk 2's `{endgame:"sn"}` signal). Remnant NS/BH
  from a labeled CO-core cut (BH for CO>7 M☉), `M_ej = final − remnant`. No-plateau fallback
  (radioactive-only) for compact R₀<300 progenitors (the gate's 140–160 M☉ low-Z tail).
- `/supernova` route bypasses `PROVIDER` for the compute but calls `PROVIDER.endgame()` for
  the progenitor; a non-SN progenitor → `is_supernova:false` + the real fate echoed, no curve.
- **Two advisor-led test corrections, both validated by the measurement** (canonical 15 M☉
  solar, real snapped: final 11.976, R₀ 911.5, CO 2.796 → NS 1.4, M_ej 10.58, plateau
  **1.83e42/138.7 d**, Co-slope **0.00976**): (1) the Tier-3 test scales the radioactive
  **TAIL**, not the peak — the IIP peak IS the plateau (`L_p`), which carries **no M_Ni term**,
  so the plan's literal "peak ∝ M_Ni" would go RED on the canonical case; (2) the Tier-1
  Co-slope is measured on the served **`L_radio` component** (0.00976 = analytic) — on
  `L_total` the plateau cutoff bleeds in and steepens it to 0.01023, so the clean anchor needs
  the component, not the total. Light-curve physics unit-tested deterministically (no grids);
  the runtime path (endgame→scalars→sibling→route) tested through the real provider.
- **The Tier-1 observed-photometry anchor (deferred from Chunk 1) is now LANDED in Chunk 2**
  (`frontend/src/sn.js`) — see the Chunk 2 section below.

**Chunk 2 BUILT (frontend gateway + light-curve panel, 215 pytest, backend untouched):**
- A reversible **`sn-mode`** mirroring WD/WR. The static SN dead-end note becomes a
  `→ Continue: Supernova` **gateway button** (`#gateway-sn`, enabled only at end-of-life,
  `disabled=!atEnd` in `updateGateway`; the SN note still foreshadows from ZAMS). `enterSN`
  (latest-wins `snToken`) fetches `/supernova`, `exitEndgame` reverts (WD/WR/none re-snap
  with a note).
- **The HR panel becomes the light-curve panel.** A CSS title-swap (`.hr-title-live` →
  `.hr-title-sn` "Supernova light curve") + `hr.setSupernova(model, observed)` redraws it as
  **L (erg/s, log) vs days (LINEAR)** — the LINEAR x-axis is load-bearing: ⁵⁶Co decay is
  exponential, so log L is linear in linear time → the iconic **straight tail** on which the
  Tier-1 slope is visually checkable against SN 1987A (a log-time axis would bend it). Draws:
  the observed overlays, the `L_radio` component (dashed), `L_total` (solid), and the scrubber
  marker (from `marker.age_yr·365.25` / `marker.L_lsun·LSUN_ERG_S`). y auto-fits to enclose
  model+observed.
- **The age slider becomes a linear-days time scrubber.** `snStateIndex` maps
  `snFraction·maxDay` → the nearest homologous-photosphere state by time, so the marker tracks
  the slider linearly and the tail gets bulk travel. `ageValue` is the derived day readout.
- **The ⁵⁶Ni-mass slider** (`#sn-control`, Tier-3, 0.001–0.3 log-spaced, default 0.06,
  debounced `/supernova` refetch via `refetchSNMni`) lifts the **radioactive TAIL, not the
  plateau** (the IIP peak is the M_Ni-free plateau `L_p` — measured: tail +~0.6 dex at
  M_Ni=0.25, plateau unmoved). Labeled "free parameter, not predicted."
- **The cited observed-photometry overlays** (`frontend/src/sn.js`) — **SN 1987A ⁵⁶Co tail**
  (`L₁₅₉·exp(−(t−159.1)/100)`, the one real tabulated point 159.1 d / 10^41.381) +
  **SN 1999em IIP plateau** (1.2e42→1.0e42 to day 95, drop, then 0.30× the 87A tail). These
  are **published bolometric *fits*, not raw photometry** — CDS/VizieR machine-readable
  endpoints all failed (bot-block/DB-error/catalog-not-found; per-epoch bolometric LCs are
  figure/electronic-only), so the honest resolution (advisor-endorsed) is to build the curves
  from the papers' **published fit parameters** + the one tabulated point, **cited in code AND
  in a visible `.hr-sn-caption`** (Suntzeff & Bouchet 1990; Elmhamdi 2003; Bersten & Hamuy
  2009), labeled as fits not raw data. **Bolometric** (V-band's BC-varying slope would break
  the Tier-1 anchor); SN 1987A is a **tail-only** anchor (compact blue-supergiant progenitor →
  no normal IIP plateau).
- **Anchor-slope calibration (advisor-caught post-commit, the load-bearing detail):** the
  SN 1987A overlay e-fold **MUST equal `TAU_CO_D` (111.3 d)** — the same ⁵⁶Co decay constant
  the model's `L_radio` uses — so the two tail slopes genuinely **coincide** (0.009755 ≈
  0.00976 mag/day; measured in-browser). The first cut used a 100 d e-fold (slope 0.01086, 11%
  steeper) that only *looked* parallel — but the Tier-1 anchor IS slope equality, so an eyeball
  "looks parallel" silently undercut the one parameter-free honesty claim. 111.3 d is also the
  honest description of 1987A (its bolometric tail **tracked the ⁵⁶Co decay** over day ~120–500;
  leakage steepening bites only after ~day 530, past the window). SN 1999em's tail e-fold was
  likewise corrected 119→111.3 d (a radioactive tail cannot decline *slower* than full Co
  trapping). If you re-touch `sn.js`, keep `SN1987A_EFOLD_D == TAU_CO_D`.
- **Consumers fed via an explicit `{endgame:"sn"}` signal, NOT naive reuse** (the WD/WR
  discipline): `refreshSN` passes the photosphere `StellarState` to 3D/SED/comp/scale/readout/
  classify with the mode flag, because the freely-expanding ejecta `logg≈−5` would trip the
  consumers' `clamp((4−logg)/3)` boiling-fireball gate. `star.js` → smooth glowing sphere
  (granulation/corona off, `(wr||sn)?0`; the real fireball is Chunk 3); `comp.js`/`spectrum.js`
  → honest "ejecta composition / no model" placeholders; `classify.js` `snLabel` → Teff-based
  "SN II — expanding fireball / cooling photosphere / nebular"; `sed.js` SN caption (expanding
  photosphere, coronal band suppressed). Entry **narrates the un-modeled bounce**.
- **Verified** with Playwright (bundled Chromium) at **1440 + 390 px**: zero console errors;
  the straight ⁵⁶Co tail lying parallel to SN 1987A's overlay, the M_Ni slider lifting the tail
  not the plateau, the time scrubber, re-snap, back-to-living restoration, the title swap, and
  the citation caption all confirmed.

**Chunk 3 BUILT (3D expanding fireball → remnant, frontend-only; 215 pytest still green,
backend untouched; Playwright-verified 1440 + 390 px, zero JS/page errors):**
- `star.js` gained two shaders: **`FIREBALL_FRAG`** on a dedicated `fireball` sphere mesh
  (reuses `star.geometry`, additive, depthWrite off) + **`REMNANT_FRAG`** on a small
  camera-facing additive dot mesh (the corona-quad pattern). In SN mode `star.visible=!sn` /
  `fireball.visible=sn` are set **unconditionally** (advisor: a mode switch must not strand a
  stale mesh). The fireball = 3D value-noise fbm mottling on a **bounded** sin/cos time orbit
  (boils, no unbounded drift or angular seam), center-bright with a soft round silhouette.
- **The ONE honest cue is the color** = the real blackbody at the photosphere Teff (uColor);
  the blue-white→orange→red shift over the scrub IS the genuine cooling. Everything else
  (size, turbulence, the dot) is **evocative, labeled** (the corona/WR-wind precedent, spec §7).
- **White-out trap avoided** (advisor point 3): a single back-face-culled additive sphere is
  ONE layer, so a clamped per-fragment alpha (≤0.8) keeps the Teff hue + cell structure rather
  than saturating to white — verified on the explosion frame (a colored blue-white ball, not a
  white disk). (If it had whited out, the fallback was an opaque-emissive body.)
- `main.js` `refreshSN` drives two scrub-derived beats threaded as `{endgame:"sn", remnant,
  snGrow, snFade}`: **`snGrow`** = `0.4+0.6·smoothstep01(0,0.14,dayFrac)` swells the ball over
  the early scrub (the "expanding" beat — on-screen size is decoupled from the true AU-scale R,
  which the scale bar carries, the WR fit-to-frame precedent); **`snFade`** =
  `smoothstep01(0.55,1,dayFrac)` dissipates it over the late tail (breaks into sparse wisps,
  dims via `1-0.97·uFade`).
- **The remnant reveal** (the heart of the chunk): as `snFade`→1 an **NS** emerges as a tiny
  hot blue-white dot (`remnantMat` ramp `(fade-0.7)/0.3`); a **BH / failed SN** shows **no dot
  at all** — the frame just goes dark = the star **"winks out."** The NS-dot color is a fixed
  pale blue-white **labeled EVOCATIVE, NOT a blackbody Teff** (advisor point 4 — a real NS's
  optical thermal emission is negligible; the Crab pulsar is V≈16 synchrotron). A late-time
  caption swap (`snFade>0.6`) narrates the nebular phase + which remnant.
- **Measured grounding (advisor point 2 — confirm BH-on-SN exists BEFORE treating winks-out as
  tested):** probed the real provider → a BH-on-SN progenitor IS in-grid: **30 M☉ solar** (CO
  core 7.68 > the 7.0 cut → BH) vs the canonical **15 M☉ solar** (NS). So winks-out is NOT dead
  code; both verified on-screen across explosion / plateau / late-reveal scrub positions.
- **The verification IS the screenshots, not the console** (advisor point 1): a default
  zero-console-errors pass would have gone green on dead reveal logic, so I captured NS + BH ×
  multiple scrub fracs and looked at each — the small-blue-white→huge-orange→red expansion, the
  thinning wisps, the NS dot appearing, the BH dark frame. The lone console line is an
  environmental favicon.ico 404 (not in the diff, not a JS error).

**Chunk 4 BUILT (pre-collapse onion shell, frontend-only; 215 pytest still green, backend
untouched; Playwright-verified 1440 + 390 px, zero console errors):**
- `comp.js` `drawSNOnion` replaces the SN placeholder (`drawSNPlaceholder` removed) with the
  progenitor's **pre-collapse onion-shell cross-section** (mirrors `drawWD`), driven ENTIRELY
  by the scalars `/supernova` already serves — `final_mass_msun` / `he_core_msun` /
  `co_core_msun` / `remnant_mass_msun` / `remnant_type` / `m_ni_msun`. **No backend change** at
  all (the data was already on the `SupernovaModel`). `setSupernova(model)` now takes the model;
  `main.js` `applySNModel` passes it; `comp.update` is a **no-op in SN mode** (the pre-collapse
  structure is static across the time scrub — it redraws only when the model re-fetches).
- **One consistent honest sizing rule:** the four REAL boundaries (remnant, CO core, He core,
  total) are sized by **area ∝ enclosed mass** (radius ∝ √(M/M_tot) — the ring between r(m₁) and
  r(m₂) genuinely has area πRd²(m₂−m₁)/M_tot). The disk is the **mass budget, not physical
  radius**; the caption owns the inverted-radial-structure caveat (the real Fe core is ~thousands
  of km inside a hundreds-of-R☉ envelope).
- **The inner Si/O–Ne shells are faint SCHEMATIC dividers** in the remnant→CO band, NOT confident
  fills. The load-bearing honesty point (advisor): the scalars are read at the **end of the MIST
  window**, and **MIST v2.5 never builds the Si/Fe core** (it runs massive stars only to ~carbon
  burning, so `c_core_mass` — the CO boundary — is the *last computed* boundary; the gate saw
  `o_core=0` for some φ3-enders). The caption says exactly that ("MIST's tracks end before the
  iron core forms, so those are not computed here") — the boron-b8 / VO-7400 discipline.
- **NS/BH contrast shows honestly:** for a BH the remnant = the whole CO core, so the C/O core
  all collapses and **only He + H eject** → the onion VISIBLY LACKS the copper C/O+heavy band
  (the void fills ~68% of the disk radius at **30 M☉ solar**: final 16.4 / He 10.9 / CO 7.68,
  remnant = CO). NS (**15 M☉ solar**: final 12.0 / He 4.7 / CO 2.8 / remnant 1.4) = a degenerate
  steel core with the full ejected C/O→Si band. Both measured + screenshotted.
- **⁵⁶Ni is exaggerated, not to scale** (0.001–0.3 M☉ vs several-M☉ ejecta): a bright ring at
  the inner ejecta boundary tied to the slider, labeled. **Kept on the BH onion too** (advisor-
  confirmed: consistent with the light curve, which still uses the slider M_Ni for BH — zeroing
  it would contradict the curve; the failed-SN/dim-Ni asymmetry is Chunk 5's job).
- **Phone-width bug caught + fixed by the screenshot pass:** the label column overran INTO the
  caption at 390 px (5 entries × 2-line sublines didn't fit the short band). Fix = the label
  column fits its band with **even spacing**, folding the caveat sublines into the always-shown
  caption when the band is short (the caveats live in the caption regardless, so nothing honest
  is lost). The disk + the (dynamic-reserve) caption were never the problem — the LABELS were.
- **Two live-update paths verified on-screen** (the advisor's flagged gap): dragging the ⁵⁶Ni
  slider redrew the green-ring label 0.06→0.25 M☉; a **15→30 M☉ mass re-snap INSIDE SN mode**
  redrew the onion NS→BH (the debug confirmed the re-snap sends `mass=30` — an earlier "still
  NS" reading was a waitForResponse race in the test harness, NOT a bug). One-line hardening
  added while in the file: `setSupernova`/`setEndgame` now mutually clear `sn`/`wd`.
- **The CO=7.0 NS/BH cut is now a visual cliff in TWO places** (the light curve's M_ej jump AND
  the onion's copper-band→void collapse) — both faithful to the model's hard mass cut, both the
  "islands of explodability" artifact Chunk 5 should soften together (noted in the plan).

**Chunk 5 BUILT (remnant branch NS/BH/failed-SN + cliff softening; backend + frontend, 220 pytest
green — +5 SN tests; Playwright-verified 1440 + 390 px, zero console errors):**
- The hard CO=7 NS/BH cut became a **labeled fallback continuum** (`supernova.py`): one smoothstep
  **φ = smoothstep(CO_NS_MAX=7, CO_DIRECT=12, co_core)** drives THREE softenings at once — remnant
  `M_NS + (M_final−M_NS)·φ` (proto-NS grows via fallback), ejecta `M_ej = M_final − M_remnant` shrink
  smoothly to ~0, **ejected** ⁵⁶Ni `= M_Ni·(1−φ)` dims (the deepest ash falls back first). New served
  fields `fallback_fraction`, `failed_sn`, `m_ni_ejected_msun`; `m_ni_msun` stays the synthesized slider
  value (the Tier-3 linearity still holds — doubling the slider doubles the ejected tail at fixed φ).
  New constants `CO_DIRECT`, `NS_MAX_MSUN=2.5`, `M_EJ_FAIL=2.0`, `NI_EJECT_FLOOR=1e-4`, `V_PHOT_MAX_KMS`.
- **Advisor blocker 1 (fixed): the NS↔BH LABEL flips where the remnant mass crosses NS_MAX (~2.5 M☉), NOT
  at CO=7** — else a near-threshold "black hole" sits in the observed NS↔BH mass gap and reads as a bug.
  CO=7 is "fallback onset." This **reclassified the Chunk-3 demo: 30 M☉ solar (CO 7.68) is now a heavy NS
  ~2.16 M☉, NOT a BH.** New on-screen demos: **NS = 15 M☉/[Fe/H]0**, **BH-fallback = 40 M☉/[Fe/H]−0.5**
  (rem 20.6, M_ej 8.8, a real fainter SN), **failed = 50 M☉/[Fe/H]−1.0** (CO 14.2, M_ej 0.1).
- **Advisor blocker 2 (fixed): a failed SN must NOT reuse the homologous photosphere** — `v=√(2E/M_ej)`
  blows up as M_ej→floor (an AU-swelling photosphere is the opposite of "winks out") and ejected Ni→0 →
  `log(0)` breaks the panel y-fit. Branch it: the states stay at the progenitor radius **R₀ (constant) and
  just DIM** — the "disappearing supergiant" (N6946-BH1); the served curve uses a tiny floored Ni so it's
  strictly positive but ~3 dex below a real IIP (the reported `m_ni_ejected_msun` stays the honest ~0).
- **Measured reachability (the Chunk-3 discipline — failed branch is NOT dead code):** the SN-bucket CO core
  caps at **~14.2 M☉** (50 M☉, [Fe/H]=−1.0) because heavier stars strip to WR; CO_DIRECT=12 puts the failed
  cases at the genuinely extreme 50 M☉ low-Z tail.
- **The 3D reconciliation (a Chunk-3 inconsistency fixed):** Chunk 3 made *all* BH "wink out", but a fallback
  BH ejected a real (if fainter) envelope → it should NOT. Now (verified on-screen): **NS → bright fireball +
  blue-white dot**; **BH-fallback → bright fireball → fades to a dark, invisible remnant (no dot, NOT a
  wink-out)**; **failed → a dim grey ball → black (winks out)**. `star.js` gained a `failed` opt (dims the
  fireball ×0.3); `main.js refreshSN` skips the "expanding" grow beat + fades from the start for failed.
- **Frontend (all branch on `failed`/the continuum):** `comp.js drawSNOnion` drops the `rem≤co_core` clamp
  so the grown remnant eats inward through C/O→He→H (the copper band shrinks GRADUALLY, no cliff); the ⁵⁶Ni
  ring uses the *ejected* Ni (gone for a failed SN); a failed onion is ≈ all void (only a thin H sliver) with
  a "winks out" caption. `hr.js` draws a violet **"Direct collapse — failed supernova: almost no light
  emitted"** banner over the faint curve. `main.js` readout adds **⁵⁶Ni ejected (+ "% fell back")** and a
  **"black hole · direct collapse"** remnant label; captions reconcile winks-out (failed) vs dark-remnant
  (BH-fallback). `classify.js` → "failed SN — direct collapse" (not "expanding fireball"); `sed.js` → a
  non-expanding failed caption. The NS baseline onion is unchanged (no regression). Type Ia still NOT this arc.

**Architecture (advisor-affirmed): a HYBRID sibling.** Classification stays in
`PROVIDER.endgame()` (it already returns `type="SN"` + progenitor scalars — §3-clean
routing metadata; do NOT relocate it). A new sibling **`supernova.py` + `/supernova`**
(bypasses `PROVIDER`, like `lane_emden`/`spectra`) does the light-curve **computation**,
emitting BOTH photosphere `StellarState`s (feed the existing 3D/SED/scale consumers —
the expanding photosphere has L/Teff/R) AND a light-curve object (a new panel). So the
SN state is a `StellarState` *and* a sibling object — the open §3 question, resolved.
Progenitor inputs ride **scalar fields on `EndgameResult`** (`pre_sn_radius_rsun`,
`he_core_msun`, `co_core_msun`, `h_retained`) — a `CACHE_VERSION` bump to parse the
`he_core_mass`/`c_core_mass`/`o_core_mass` columns; `StellarState` untouched.

**The 3-tier honesty framing IS the arc:** Tier-1 = the ⁵⁶Co tail slope (0.0098 mag/d,
set only by τ_Co=111.3 d) — bulletproof, zero free params, THE verification anchor (not
the peak). Tier-2 = plateau L & duration from MIST M_ej/R₀ + canonical E,κ (Popov/Kasen-
Woosley) — robust shape, ±dex level. Tier-3 = peak/tail height ∝ M_Ni — NOT MIST-derivable
(0.001–0.3 M☉), so a **free slider** (default 0.06), explicitly not predicted.

**Chunk 0 gate — measured over the full MIST grid (the scope-setting findings):**
- **The SN bucket is PURELY Type II** (all 279 SN-classified tracks retain H, surf-H
  0.30–0.75; **zero Ib/c** — the stripped stars classify as **WR**, 329 of them). ⇒ v1
  SN arc = **Type II / IIP**. Stripped-envelope **Ib/c is the WR endpoint** (a follow-on
  chunk: "→ Continue: Supernova" off the WR scrub, pure Arnett no-plateau), NOT v1.
- **Core masses present & sane** (0 unphysical) → clean ejecta/remnant split. Progenitors
  are **red supergiants** (final-phase R₀ ≈ 400–1100 R☉) → IIP plateau valid; use the
  **final-phase-median R₀** (terminal EEP row is a low-gravity artifact for some tracks).
- **Canonical 15 M☉ solar curve lands in regime:** plateau 1.5e42 erg/s / 133 d, Co-tail
  slope 0.00976 mag/d (= analytic = textbook 0.0098). **Verdict: shape-GO, scale-via-
  slider** (the SED-Chunk-2 pattern). Cite Nadyozhin(1994) ε_Ni/ε_Co, Kasen-Woosley(2009).

**Where it slots in (the existing dead-end this fills):** today `MISTProvider.endgame`
classifies an ends-at-φ5-onset track as **`type="SN"` with `states=[]`** — an honest
dead-end ("core collapse — not simulated", the gateway shows the SN mass but no
remnant line, no scrubbable sequence). See [[star-sim-wr-wd-endgame-plan]]. This arc
turns that dead end into a real renderer the way WD/WR became real renderers.

**The constraint set the user fixed (treat these as locked requirements, not
suggestions):**
- **⁵⁶Ni light curve** — the observable centerpiece. The honest, feasible path is a
  **semi-analytic radioactive-decay light curve** (Arnett-style: ⁵⁶Ni→⁵⁶Co→⁵⁶Fe
  decay deposition powering an expanding ejecta photosphere), NOT a hydro simulation.
- **Ejecta expansion** — homologous (v ∝ r) expansion, photospheric radius/velocity
  evolution; the visual + the timescale that sets the light-curve width.
- **"some nucleosynthesis maybe"** — explicitly tentative. At most the ⁵⁶Ni mass and
  the decay chain, perhaps a few yield species; **NOT a full nuclear network.**
- **NO computational explosion mechanism** — the user named this as **infeasible** and
  ruled it out. We do not simulate the neutrino-driven / hydro explosion. We model the
  *aftermath* (parametrized: Ni mass, ejecta mass, kinetic energy → light curve), not
  the bounce.
- **Observed light curves as verification** — the regression anchor must be **real
  observed SNe** (e.g. SN 1987A IIP-ish, SN 1993J IIb, Ia templates, a IIP plateau
  source), exactly the project's "verify against measured data, never against what we
  wish it showed" honesty rule (the boron-b8 / VO-7400 lesson, spec §7).

**Scope this arc as CORE-COLLAPSE + NS/BH remnants** — i.e. the massive-star φ5
branch (Type II / Ib/c; IIP has a H-recombination plateau *then* the Ni tail). That
is exactly the dead branch this fills.

**Type Ia is a SEPARATE path — do NOT build it off this branch (advisor-flagged):**
a Type Ia is a *thermonuclear* WD event, and a single MIST star produces an isolated
cooling WD that **never reaches the Chandrasekhar mass on its own** — it needs
accretion or a WD–WD merger, **both binary channels**. So Ia is gated on the
**binarity engine** (already a ROADMAP §3 item), branches off the **WD** endgame (not
this core-collapse branch), and only *then* connects to the Lane–Emden-in-WD n→3 /
Chandrasekhar hint in [[star-sim-wr-wd-endgame-plan]]. Mentioned here only so future-
you doesn't start Ia off the wrong branch or imply a lone star can do it.

**Open framing notes for the future designer (NOT decided):**
- **Remnant = another mass threshold**, like the existing WD→SN snap. The endgame
  already snaps & reports `final_mass`; NS vs BH is a further boundary above the WD/SN
  one (solar WD↔SN measured between 6.5 and 7.0 M☉; NS↔BH is higher, progenitor/
  remnant-mass dependent). MIST tracks end at core collapse — they carry **no** remnant
  or light-curve data, so this needs a **new data source / parametrized model**, not the
  existing grid (unlike WD/WR, which were already on the MIST tracks).
- **Architecture:** still no live solver (spec §2/§9). Likely the same gateway pattern
  (reversible "→ Continue: Supernova", a scrubbable time axis = days/months post-
  explosion instead of cooling Gyr), but the light curve is a **computed model + an
  observed-template overlay**, not a snap to a MIST track. Whether the SN/remnant state
  can still be a `StellarState` (a photosphere has Teff/L/R) or needs a sibling object
  (like the spectra/Lane–Emden siblings) is an open §3 question.

When this is picked up: write a real plan doc (sibling to
`docs/plans/smoldering-cinder-gateway.md`), and update `docs/plans/ROADMAP.md`
from "idea" as it gets designed.
