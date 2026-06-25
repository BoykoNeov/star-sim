---
name: star-sim-nonthermal-sed-plan
description: "PLANNED (not built) non-thermal SED layer — coronal soft-X-ray + radio band + hot-star wind radio; the accepted-science answer to \"model the gamma/radio floor\", with the activity-proxy honesty gate."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1c083c58-0b48-4fcb-9de8-9e22d1374511
---

After the broadband SED panel ([[star-sim-phase5-spectra]]'s blackbody, `sed.js`)
shipped, the user asked: "can we also model" the non-thermal X-ray/γ/radio the
blackbody floors out — "is there an accepted scientific model?" **Answer planned,
NOT built.** Plan: `docs/plans/magnetic-ember-broadcast.md` (whimsical name like
[[star-sim-wr-wd-endgame-plan]]'s smoldering-cinder-gateway).

**The science is real & advisor-verified** but a DIFFERENT KIND of model than the
photosphere: magnetic-**activity**-driven (rotation/age, not Teff/logg/[Fe/H]),
empirical scalings with big scatter, split by type:
- Cool stars (dynamo): **rotation–activity** `L_X/L_bol` saturates ~10⁻³ (Wright
  2011 log −3.1), falls ~Ro⁻²; coronal spectrum = optically-thin thermal plasma
  1–10 MK (APEC, not blackbody); **Güdel–Benz** `L_X/L_R ≈ 10¹⁵·⁵ Hz` maps X-ray→radio.
- Hot stars (O/B, wind shocks): `L_X ≈ 10⁻⁷ L_bol`; **thermal wind free–free
  radio** `S_ν ∝ ν^+0.6` (Panagia–Felli/Wright–Barlow), set by mass-loss Ṁ.
- Flares `dN/dE ∝ E⁻²` (stochastic, not on a static SED); **γ is flare-only/exotic
  → stays floored & empty in every version.**

**THE HONESTY GATE (the deciding finding):** the sim's `activity` proxy is, in all
three providers (`mist.py:943`/`stub.py:137`/`mesa.py:440`), a **pure Teff ramp**
`(6500−Teff)/3500`, **no rotation/age**. So feeding it into Pizzolato/Wright = a
FAKE L_X (the boron-b8 / VO-7400 / invisible-Na "label a non-feature" trap again).
→ **Cannot draw a single X-ray value.** Honest renderings only: a shaded **BAND**
(the saturated→quiet 10⁻⁷…10⁻³ envelope — a range, not a value; Güdel–Benz maps it
to a radio band) + the one genuinely PREDICTIVE piece, hot-star wind radio from the
real on-disk `star_mdot`. **Two epistemic tiers in one panel** (evocative band vs
data-grounded wind) = the teaching point; render distinctly (hatched ribbon vs solid line).

**User chose "Band + real wind radio"** (over hot-radio-only / prose-only).

**Chunking:** Chunk 1 = cool-star coronal X-ray + Güdel–Benz radio band,
**frontend-only** (`sed.js` has L_lsun + Teff already). Chunk 2 = hot-star wind
free–free radio, needs **Ṁ on the spine**: `star_mdot` is in `_Track`+cache (v9,
from endgame) but NOT in StellarState — add optional `mdot_msun_yr` (like
`activity`), thread through `_grid_window`/`_blend_windows`→`_state_from_row`,
**NO CACHE_VERSION bump** (already cached). Frontend draws `Fλ ∝ λ^−2.6` (from
`Fν ∝ ν^0.6`) rising ABOVE the blackbody λ⁻⁴ R–J floor = "real radio sits above
the floor" made concrete. **v∞ assumption** (MIST gives no terminal wind velocity):
assume v∞ ≈ 2.6 v_esc (Lamers & Cassinelli) — flag like the PoWR WR assumption-mapping.

**Hard design point: normalization** — placing integrated L_X/L_bol or L_ν on the
per-peak-Fλ axis needs an L_bol↔F_peak conversion + band-width assumption → risk of
fake precision; mitigate by annotating the dimensionless ratio + keeping the ribbon
visibly an order-of-magnitude range. Other risks: visual clutter (panel already
dense), type-gating honestly (A-star X-ray gap, cool-giant corona–wind dividing
line → caption gaps, don't draw fake values), caption must flip from "not modeled
here" to describing the ribbon.
