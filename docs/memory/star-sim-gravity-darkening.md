---
name: star-sim-gravity-darkening
description: "Gravity darkening / oblateness of fast rotators (von Zeipel/ELR) — the honest capstone to the rotation axis; Gate 0 PASSED, chunk plan."
metadata: 
  node_type: memory
  type: project
  originSessionId: d9e67f80-f1dc-48b7-ad3f-fe43562cf5ab
---

Gravity darkening / rotational oblateness for the 3D star — the honest capstone to
the `vvcrit` rotation axis ([[star-sim-rotation-subpop-atlas]]). Fast rotators are
centrifugally oblate with **hot bright poles, cool dim equator** (Regulus/Achernar/
Vega). Chosen over the other two Tier-C items (magnetic peculiarity = no data driver,
skip; microturbulence = thin + needs a re-bake, defer). User directive 2026-07-02:
"choose the more honest approach to all (closer to reality)."

**Advisor design rulings (honesty-grounded):**
1. **Real ω, no faked driver.** Compute ω from served scalars `v_rot_kms`/`R_rsun`/
   `mass` (v_crit ≈ √(2/3)·437·√(M/R) km/s, Roche). Domain gate is FREE: `v_rot_kms>0`,
   which the grid gives only above the ~1.2 M☉ Kraft break — radiative envelopes, where
   **β=0.25 (von Zeipel) is the valid law**. Feature lives exactly where rotation is real.
2. **Inclination slider + feed sin i into v sin i broadening — the real payoff.** Even if
   the bulge is mild the *coherence* wins (pole-on→round/hot/sharp lines; edge-on→oblate/
   cool-limb/broad lines). **Legitimately REVERSES the earlier edge-on-only punt** in the
   v sin i work ([[star-sim-phase5-spectra]]) — which was punted *because* no oblateness
   model existed. Update that caption/code + memory when Chunk 2 lands.
3. **KEEP IT OFF THE SPINE — this is the MORE honest choice.** Intrinsic Teff/L is
   inclination-independent (what StellarState encodes, §3). Projected apparent Teff/L is a
   *viewing artifact* → belongs in the view (3D) + observable (spectrum), NEVER injected
   into the theoretical HR marker. "More honest" ≠ "touch more subsystems." An HR "as-seen
   at i=X" ghost marker, if ever wanted, is a separate clearly-labeled thing.

**Honesty trap:** "closer to reality" ⇒ the median effect is SUBTLE — show it subtle,
never exaggerate the bulge/gradient to make it pop (the opposite of the SN ⁵⁶Ni "not to
scale" ring). Regulus drama, if wanted beyond what real ω gives, is a labeled "what-if
rotation" slider — NOT cranking real ω.

**Gate 0 PASSED (2026-07-02, measured over the real provider, `temp/gravdark_gate0*.py`):**
ZAMS ω≈0.36–0.40 confirms the v_crit convention matches MIST vvcrit=0.4 (not inflated).
MS-only distribution (14704 states, dropped giant artifacts — a 12 M☉ CHeB R=165 giant
gives spurious ω=1.0 because v_crit→tiny; ω peaks at ZAMS, giants unreliable):
- **Median MS rotator: R_eq/R_pol = 1.081 (8% bulge), ΔTeff 7.9%** — exactly the advisor
  forecast; clears the ≳1.05 / ≳3–4% discriminator.
- 90th pct 1.187; **fastest reachable 5 M☉ [Fe/H]=+0.5 MS: R_eq/R_pol=1.367, ΔTeff 38.6%
  (≈4900 K)** — a REAL near-Regulus from honest data, no exaggeration. 2–4 M☉ get spun up
  most (ZAMS ω~0.7). So the Regulus look is reachable AND the typical star stays gentle.

**Architecture facts (frontend `star.js`):** surface = `SphereGeometry(1,96,64)` scaled
`star.scale.setScalar(rad)`; single `uColor` (Teff, max-normalized chromaticity) across the
disk; `uExpo` carries brightness; fixed camera (0,0,8), pole=+y, visual-only rotation.
`vObjPos = normalize(position)` is the UNDISTORTED unit-sphere latitude (scale is applied via
modelView, so vObjPos.y = sin(lat) survives an oblate `star.scale.set(eq,pol,eq)`); the limb-
darkening normal `vViewNormal` uses `normalMatrix` so it correctly follows the oblate shape.

**Chunk plan:** Gate 0 ✅ → **Chunk 1 BUILT** → **Chunk 2 BUILT (2026-07-02, frontend-only,
254 pytest unchanged, Playwright 1440+390 zero console errors) — the gravity-darkening arc is
COMPLETE.** No plan file was needed (the memory + advisor rulings were the spec).

**Chunk 2 (BUILT):** an **Inclination slider** (0°=pole-on … 90°=edge-on) — a persisted VIEWING
choice OWNED by `main.js` (`inclinationDeg`, default **60°** = isotropic median) and pushed to
BOTH consumers via `star.setInclination`/`spectrum.setInclination` (single source, no dual-default
drift). ONE angle drives two things coherently: (1) `star.js` tilt `star.rotation.x = (π/2)(1−i/90)`
= θ=90°−i (dropped Chunk 1's ω-ramp/fixed-0.6 tilt; `lastGd` cached so the slider re-tilts with no
repaint) — pole-on looks down the hot pole (round disk), edge-on shows the oblate egg side-on; (2)
`spectrum.js` `v sin i = v_rot·sin(i)` — **retires the fixed sin i=1 "edge-on" punt** (advisor ruling
#2; the earlier v sin i work in [[star-sim-phase5-spectra]]/[[star-sim-rotation-subpop-atlas]] punted
edge-on *because* no oblateness model existed — now reversed). sinI folded into all 4 spots: `mainFlux`
guard, `rotBroaden` amount, the broaden **memo key** (was keyed only on v_rot → would strand a stale
line on drag — advisor plumbing catch), and the caption+`ROT_VISIBLE_KMS` note. **OFF THE SPINE**
(ruling #3): inclination never touches the HR marker — only what is SEEN (3D) + OBSERVED (lines).
UI: a THIRD facet in the unified Rotation control (`#incl-control`, reuses `.sed-rot` styling),
**gated track-stably on `showToggle && rotationOn`** (NOT per-state `gd.active` — advisor's key
catch: gd.active varies along the track via the logg giant-gate, so gating on it would appear/
disappear the facet mid-age-scrub and jitter the Age thumb; the track-stable gate keeps the control
height fixed, and at giant ages star.js just sets tilt=0 while the slider stays put). Measured coherent
story on the near-Regulus (5 M☉ [Fe/H]+0.5 MS): pole-on → round/uniformly-hot/sharp lines (v sin i→0,
broadening clause suppressed below the 120 km/s floor); i=60 → tilted oblate, hot-pole + cool-equator
band both visible, v sin i≈195; edge-on → fully oblate side-on, v sin i≈225 (max). Sun hides the facet.

**Chunk 1 (BUILT):** new `frontend/src/gravdark.js` (`rotationDistortion(state)` → Roche ω from
v_rot/v_crit, volume-preserving spheroid k_eq=q^(1/3)/k_pol=q^(-2/3) with q=R_eq/R_pol, gEq =
g_eff(eq)/g_eff(pole), endpoint temps anchored so the AREA-WEIGHTED flux = the star's L
[T_pole=Teff·(3/(1+2gEq))^¼, T_eq=T_pole·gEq^¼]). `star.js`: surface shader gains uColorPole/
uColorEq/uGeq; the gradient blends color by the g_eff(lat) temperature profile and multiplies
brightness by **gRatio (exponent 1.0 — the honest von Zeipel radiance law F∝T⁴∝g_eff**; my
first `^0.5` cut under-represented it), pole-normalized so a near-critical equator drops to
~14% (the Regulus dark band). Oblate scale `star.scale.set(rad·kEq, rad·kPol, rad·kEq)`.
**Two fixes found by rendering, not math:** (1) edge-on MASKS the gradient — the hot poles land
at the top/bottom limb (limb-darkened) while the cool equator is at disk-centre (brightest), so
they cancel → a **fixed 3/4 tilt** (`star.rotation.x = 0.6·smoothstep(0.1,0.45,ω)`, ramped so a
marginal rotator stays pole-up) reveals both shape AND gradient; (2) **advisor BLOCKER — the
runtime lacked Gate 0b's giant guard**: `v_rot>0` alone fired on evolved giants whose ω is a
v_crit-collapse ARTIFACT (measured: a 145 R☉/logg 1.2 bright giant flattening to req≈1.5). Fixed
with a surface-gravity regime gate `ω *= smoothstep(2.0, 3.0, logg)` (MS logg~4 full, giants <3
off), smooth so scrubbing never pops. Round/non-rotating stars + all endgames byte-identical.
Star-panel tooltip updated (GRAVITY DARKENING clause; stale "v/vcrit=0 grid" line fixed).
Measured in-app: Sun clean · 2.5 M☉ gentle · 5 M☉ Regulus · 12 M☉ giant round.
See [[star-sim-frontend-ux]], [[star-sim-phase2-shaders]], [[star-sim-phase5-spectra]].
