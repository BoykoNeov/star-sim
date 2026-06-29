---
name: star-sim-nonthermal-sed-plan
description: "Non-thermal SED layer (CHUNKS 1 & 3 BUILT, Chunk 2 planned) — coronal soft-X-ray + Güdel–Benz radio band, then a rotation→X-ray LINE (gyrochronology + slider) collapsing it; hot-star wind radio is Chunk 2. The accepted-science answer to \"model the gamma/radio floor\", with the activity-proxy honesty gate. + the cool→gap band-descent line-clamp + saturation-cue fixes."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1c083c58-0b48-4fcb-9de8-9e22d1374511
---

After the broadband SED panel ([[star-sim-phase5-spectra]]'s blackbody, `sed.js`)
shipped, the user asked: "can we also model" the non-thermal X-ray/γ/radio the
blackbody floors out — "is there an accepted scientific model?" Plan:
`docs/plans/magnetic-ember-broadcast.md` (whimsical name like
[[star-sim-wr-wd-endgame-plan]]'s smoldering-cinder-gateway).

**CHUNK 1 BUILT (frontend-only, `sed.js` + index.html legend/caption, NO spine touch,
pytest unchanged 137).** The cool-star coronal X-ray + Güdel–Benz radio BAND. Two
findings made it cleaner than the plan feared: **(1) Normalization (the plan's
"trickiest point") = Teff-only.** A blackbody ties its integral to its peak by a fixed
effective width `L_bol/F_peak = (π⁴/15)·(e^xp−1)/xp⁴·λ_peak ≈ 1.521·λ_peak` (xp=4.9651);
spreading L_X over the soft-X-ray band Δλ_X makes **L_bol CANCEL** → `Fλ_X/F_peak =
(L_X/L_bol)·1.521·λ_peak/Δλ_X`, so band placement needs only Teff (the plan's listed
`L_lsun` input is NOT needed for placement, only gating). Sun = −5.1…−1.1 dex, above the
floored thermal X-ray = the headline. **(2) Radio buries on the Fλ axis (advisor-decisive):**
GB radio (L_R=L_X/10^15.5 Hz) → ~−16.7 dex for the Sun, BELOW the −14 floor, because per-Hz
radio becomes tiny per-nm flux (the λ² — the AXIS, not the physics). So **keep
FLOOR_DECADES=14, do NOT rescale the shipped panel**; GB radio = a COMPACT MARKER near the
floor (only a saturated cool star's edge ~−13.7 peeks in), correlation in legend/caption.
**The genuine radio-above-floor payoff is Chunk 2's wind tail** (λ⁻²·⁶ vs BB λ⁻⁴) — let
radio earn space there. **Gating = Teff + logg** (logg now in the redraw cache key — an
advisor-caught bug: dwarf vs giant at equal Teff draw different bands): ≤6500 full band /
≥10000 collapse to ~10⁻⁷ wind-shock / 6500–10000 A-gap NO band (caption a gap, never a fake
value) / cool giant (logg<3 & Teff<5000) dimmed+capped 10⁻⁵…10⁻⁸ (Linsky–Haisch suppression).
Band is hatched/translucent (the "evocative range" tier, so Chunk 2's solid line contrasts),
dimensionless f_X edges annotated (10⁻³/10⁻⁷ — guard vs fake precision), γ explicitly empty in
every caption; the two stale "not modeled here" claims in the h2 tip + "non-thermal edges"
legend flipped. **Caption resize-on-scrub avoided (advisor-caught):** the regime-varying caption
would resize the panel scrubbing cool→gap→hot (the [[star-sim-true-size-scale-bar]]/Lane–Emden
caption jank); a px min-height reserve CAN'T fix it (the SED panel's flex-wrap width — so the
caption line count — varies 432–700px even on desktop, MEASURED), so each regime's sentence is
kept short + **~equal length** to wrap identically at any width → measured spread **0px** at
desktop/phone/intermediate. (Reusable: when flex-wrap width varies, equalize text length, don't
min-height-reserve.) Verified Playwright (bundled Chromium — chrome --headless hijacks the user's
Chrome) on the real served UI across all 5 gating branches + phone 390; only the pre-existing
favicon 404, no JS errors. **Chunk 2 (wind free–free radio from real Ṁ, the spine touch) remains;
Chunk 3 is now BUILT (see next).**

**CHUNK 3 BUILT (frontend-only, `sed.js`+SED control markup/CSS/legend, NO spine touch, pytest
unchanged 137).** Collapses the Chunk-1 BAND to a LINE via rotation — the upgrade ladder's top rung.
Chain (advisor-greenlit, Sun-cross-checked): Teff→(B−V) Ballesteros 2012 (inverted closed form) →
P_rot Mamajek–Hillenbrand 2008 gyro → τ_conv Wright 2011 **mass-based** → Ro → L_X/L_bol Wright 2011
(sat Ro_sat=0.13, β=−2.7, −3.13). **ONE self-consistent (all-Wright) calibration** — Ro_sat/β are
defined with Wright's OWN τ; mixing Noyes τ shifts the zero-point off the Sun → **Sun lands at
L_X/L_bol ≈ 10⁻⁶·²** (live P_rot 25.4 d matching the real Sun; obs ~10⁻⁶·³ = the anchor). **Three
advisor-caught guards (reusable):** (1) **blue-edge NaN + spurious-saturation trap** — `[(B−V)−0.495]^0.325`
is NaN below 0.495 and →0 just above (→ P_rot→0 → fake "saturated"), so gate the gyro line **redward
of the singularity** (B−V≥0.55 ≈ Teff 6150 K, NOT the bare 0.495 — verify an F8/6354 K dwarf is
suppressed not pinned-to-ceiling); (2) the line's **alpha tied to coolA** (the Chunk-1 morph weight),
drawn **only in the cool branch** (a rotation value can't make an O-star/giant dynamo); (3) **clamp into
[10⁻³,10⁻⁷]** + the **saturated branch plateaus** (no rise below Ro_sat). Gating reads phase/Teff/logg/
age/mass (added to the redraw key): age-line only for cool phase=="MS", suppressed **young** (≲300 Myr,
spin unconverged → band+note), **wider fuzz+flags** for **old** (van Saders braking) + **M-dwarf** (MH08
extrapolated). **Slider model (advisor-locked, the reusable pattern):** default-from-age,
**drag-to-override**, override **cleared on a star change (mass/[Fe/H]) but KEPT across age-scrub**
(hold a rotation, watch the band context) — one control + a ⟲-age reset, no toggle; the line is
cool-**blue** vs the coral band (two epistemic tiers read as two). Captions stay **length-matched**
(measured panel-height spread **0.0 px** — the resize jank guard). Verified Playwright (bundled Chromium)
across Sun young/now/old (line sweeps) + M-dwarf + F-edge + hot O + EAGB giant (no line) + slider drag +
phone 390. Below = the original plan record:

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

**CHUNK 3 ADDED — the synthesis (user-approved, the upgrade ladder):** collapse the
X-ray BAND to a LINE by supplying the missing rotation dimension two ways.
**(a) Age-derived default — the sim ALREADY has age.** My earlier "the sim has no
rotation/age input" was true of the *current activity proxy* (Teff ramp ignores age)
but MISLEADING: `age_yr` is a core StellarState field + the central scrubber. Chain:
`age --gyrochronology(age,color)--> P_rot --> Ro=P_rot/τ_conv --> L_X/L_bol` (Barnes
2007, Mamajek-Hillenbrand 2008) — both inputs (age AND color/Teff) are onboard, so for
a **MS cool star** the band collapses to a line with NO new control (answers the
two-same-Teff-different-age stars: distinguishable by age). **(b) Activity/rotation
slider** — user pins the dimension; exact precedent = the **Lane-Emden `n` slider**
(project rejected auto-deriving n as dishonest → user's to set). Synthesis = BOTH +
honest gating. **Validity domain (gate on these):** ✅ MS cool F/G/K ~0.5-1.3 M☉; ❌
hot stars (no dynamo/braking → keep wind-shock); ❌ very young ≲few-hundred-Myr (rotation
not converged, C/I-sequence spread); ⚠️ M dwarfs (saturated plateau, gyro mushy); ⚠️
evolved post-MS (line must STOP at MS turnoff — sim runs to RGB/AGB); ⚠️ old ≳solar
(weakened braking / stalled spin-down, van Saders 2016 — gyro may BREAK past Sun's age).
Even pinned: ~0.5-1 dex scatter + ~10× cycle wobble → "line with a fuzz", never a razor.
**Frontend-only** (age path uses age/Teff/L/logg/phase already in state; τ_conv from
Wright2011/Cranmer-Saar2011; slider = sed.js-local like lane.js n-slider; gating reads
phase). Ladder: **band (Chunk 1) → age-derived line → slider**, each rung more concrete,
none faking a number. Chunk 3 depends on Chunk 1 (collapses its band), NOT on Chunk 2.

**CHUNK 3 FOLLOW-UP (user-reported, frontend-only, pytest unchanged 137).** Two rotation-line
fixes on a warm cool-dwarf (1.29 M☉, [Fe/H] 0 at ZAMS, Teff 6380): **(1)** the blue "rotation
set" line **escaped ABOVE the coral band** — `drawActivityLine` clamped to the FIXED saturation
range [10⁻³·¹³,10⁻⁷], but in the cool→gap morph the band's top DESCENDS to `lerp(-3,-6,gapW)`
(≈10⁻³·⁹ at 6380 K) while a saturated fast rotator pins L_X/L_bol at 10⁻³·¹³ ABOVE it → the line
floated outside its own band ("rotation set band goes beyond the limits of coronal x-ray"). FIX =
pass the band's CURRENT `[bandHi,bandLo]` into `drawActivityLine` and clamp the line + fuzz to it
(a tiny, accepted understatement of the true saturation level vs. a line outside its band); also
moved the line LABEL **below** the line so a top-pinned (saturated) line doesn't collide with the
band's own "coronal X-ray" tag. **(2)** saturation was **silent** — below Ro_sat the line stops
moving (correct physics: faster spin won't raise X-rays), reading as a bug ("slider goes below
~1 d, nothing happens"). FIX = `rotNote` appends "· saturated: faster spin won't raise X-rays"
when `P_rot/τ_conv ≤ ROT_SAT`. **GOTCHA worth keeping:** the rotation→X-ray line only draws in a
NARROW window — cool MS, Teff<6500 (`dynamoLineAllowed`); a 1.29 M☉ is in it ONLY right at ZAMS
(Teff 6380; by 0.03 Gyr it's 6528 → suppressed), so "age 0" was load-bearing in the report.
Verified Playwright bundled Chromium (saturated line pinned inside the band top, note reads
"saturated"; slow rotator line sits mid-band).
