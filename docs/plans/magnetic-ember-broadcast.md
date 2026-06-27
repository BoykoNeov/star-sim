# Plan: Non-thermal SED layer — coronal soft-X-ray + radio (Phase 5)

## Status: Chunks 1 & 3 BUILT (frontend-only, shipped + verified). Chunk 2 PLANNED.

**Chunk 3 as-built (collapse the band → line via rotation):** all in `frontend/src/sed.js`
+ the SED control markup/CSS/legend, **no backend/spine touch** (pytest unchanged 137).
The chain is Teff→(B−V) (Ballesteros 2012, inverted) → P_rot (Mamajek–Hillenbrand 2008
gyrochronology) → τ_conv (Wright 2011 **mass-based**) → Ro → L_X/L_bol (Wright 2011,
sat `Ro_sat=0.13`, `β=−2.7`, `−3.13`) — **ONE self-consistent (all-Wright) calibration**;
it lands the **Sun at L_X/L_bol ≈ 10⁻⁶·²** (live P_rot 25.4 d; observed ~10⁻⁶·³). Three
advisor-caught guards: (1) the gyro line is gated **redward of the (B−V)=0.495 singularity**
(`B−V≥0.55 ≈ Teff 6150 K`) — just blueward `[(B−V)−0.495]^0.325` is NaN, just redward → 0 →
P_rot → 0 → a spurious "saturated" verdict; (2) the line's alpha is **tied to `coolA`** and it
draws **only in the cool branch** (never gap/hot/giant — a rotation value can't make an O-star
dynamo); (3) it is **clamped into [10⁻³,10⁻⁷]** with the **saturated branch plateauing**.
Gating reads `phase`/`Teff`/`logg`/`age`/`mass` (added to the redraw key): age-line for cool
`phase=="MS"` only, suppressed for **young** (≲300 Myr) with **wider fuzz + flags** for **old**
(van Saders) and **M-dwarf** (MH08 extrapolation). Slider model: **default-from-age,
drag-to-override, override cleared on a star change (mass/[Fe/H]) but kept across age-scrub**,
one control + a `⟲ age` reset; the line is cool-blue (vs the coral band — the more-concrete
rung). Captions stay **length-matched** (measured panel-height spread **0.0 px**). Verified via
Playwright on the real served UI across the Sun (young/now/old, line sweeps) + M-dwarf + F-edge
+ hot O + EAGB giant (no line) + slider drag + phone 390 px; only the favicon 404, no JS errors.

**Chunk 1 as-built (the cool-star coronal X-ray + Güdel–Benz radio band):**
all in `frontend/src/sed.js` + the `index.html`/legend, **no backend/spine touch**
(pytest unaffected). The normalization the plan flagged as the trickiest point was
solved cleanly and the radio finding turned out decisive:

- **Normalization (advisor-verified):** the blackbody ties its integral to its peak by
  a fixed effective width, `L_bol/F_peak = (π⁴/15)·(e^xp−1)/xp⁴·λ_peak ≈ 1.521·λ_peak`
  (`xp=4.9651`). Spreading `L_X` over the soft-X-ray band Δλ_X makes **L_bol cancel**:
  `Fλ_X/F_peak = (L_X/L_bol)·1.521·λ_peak/Δλ_X` → **the X-ray band placement is
  Teff-only** (the plan's listed `L_lsun` input is *not* needed for placement, only
  gating). Sun lands at −5.1…−1.1 dex — cleanly above the floored thermal X-ray.
- **The radio buries — keep FLOOR_DECADES=14, do NOT rescale the shipped panel
  (advisor).** On the Fλ axis the Güdel–Benz radio (`L_R = L_X/10^15.5 Hz`) maps to
  ~−16.7 dex for the Sun (below the −14 window) because per-Hz radio → tiny per-nm flux
  (the λ² makes radio intrinsically faint on Fλ — the AXIS, not the physics). So it is a
  **compact marker** near the floor (only a *saturated* cool star's top edge ~−13.7
  peeks in), with the `L_X/L_R≈10^15.5 Hz` correlation in the legend/caption. The genuine
  radio-above-floor payoff is **Chunk 2's wind tail** (λ⁻²·⁶ vs λ⁻⁴), which earns the
  long-λ space; the coronal GB radio is correctly a footnote here.
- **Gating (Teff + logg, the cache key now includes logg):** Teff ≤6500 → full coronal
  band `10⁻⁷…10⁻³`; ≥10000 → collapse to a narrow wind-shock band ~10⁻⁷; 6500–10000 →
  the A/early-F **X-ray gap, no band drawn** (caption only); cool giants (logg<3 &
  Teff<5000) → **dimmed + capped at 10⁻⁵…10⁻⁸** (suppressed coronae past the
  Linsky–Haisch dividing line) + caption caveat. The band is hatched/translucent (the
  "evocative range" tier) so Chunk 2's solid wind line will contrast; the dimensionless
  `f_X` edges (10⁻³/10⁻⁷) are annotated on the ribbon (the guard against fake precision);
  γ stays explicitly empty in every regime's caption.
- **Caption resize-on-scrub avoided (advisor-caught):** the per-regime caption is the
  longest-varying text in the panel, so a regime-dependent height would resize the SED
  panel as you scrub across cool→gap→hot (the jank the Lane–Emden caption fix addressed).
  A px `min-height` reserve can't fix it here — the panel's flex-wrap width varies
  (432–700 px even on "desktop", so the caption's line count does too; measured). The fix
  is to keep each regime's sentence SHORT and **~equal in length (~130–140 chars)** so all
  four branches wrap to the same line count at any width (the depth lives in the legend
  tooltip + `<h2>` tip). Measured caption/panel height **spread = 0 px** across all five
  regimes at desktop, phone, and intermediate flex widths.
- **Verified** via Playwright (bundled Chromium — `chrome --headless` hijacks the user's
  running Chrome) on the **real served UI** across all five gating branches (cool dwarf
  5832 K / M-dwarf 3257 K / A-gap 9034 K / hot O/B 27482 K / cool giant 3625 K→Linsky) +
  phone 390 px; only the pre-existing favicon 404, no JS errors. (No JS test harness — the
  screenshot pass is the regression check, as in Phases 2–5.)

## Context

The broadband SED panel (`frontend/src/sed.js`, the "gamma → radio" view) is
done and shipped: it draws the **Planck blackbody** Fλ across ~14 decades and is
honest that the photosphere floors at the EM extremes — the caption already says
*"real X-ray/γ-ray comes from the magnetic corona and flares, not modeled here,
and its radio tail is a floor too (real stellar radio sits far above it)."*

The user then asked: **"can we also model this, is there an accepted scientific
model for that?"** — i.e. model the non-thermal emission the blackbody floors out.

**Answer: yes, but it is a fundamentally different KIND of model**, and that
distinction is the whole story. The photosphere is a clean function of
`(Teff, logg, [Fe/H])`. The X-ray/radio emission is **magnetic-activity-driven**
— governed by *rotation and age* (the dynamo), not by the SED's inputs — and the
accepted models are empirical scaling relations with large scatter that split by
stellar type. Verified-correct science (advisor-checked the load-bearing claims):

- **Cool stars (F/G/K/M, convective dynamo, "solar-like"):**
  - **Rotation–activity** (Pizzolato 2003; Wright 2011): `L_X/L_bol` set by the
    Rossby number `Ro = P_rot/τ_conv`. Fast rotators **saturate** at
    `L_X/L_bol ≈ 10⁻³` (Wright 2011: log ≈ −3.1); slower rotators fall as `~Ro⁻²`.
    Coupled with **gyrochronology** (Skumanich, `~t^−1/2`) → an age→activity→L_X chain.
  - **Coronal spectrum:** optically-thin thermal plasma at 1–10 MK (APEC/MEKAL) —
    a soft-X-ray bump, line-dominated, *not* a blackbody.
  - **Güdel–Benz** (Güdel & Benz 1993; Benz & Güdel 1994): `L_X/L_R ≈ 10¹⁵·⁵ Hz`
    — a tight radio↔X-ray correlation that maps an X-ray level into the radio.
- **Hot stars (O/B, no dynamo — different physics entirely):**
  - X-rays from **embedded wind shocks:** `L_X ≈ 10⁻⁷ L_bol` (Berghöfer 1997;
    Nazé 2009). A near-constant, narrow value, NOT the activity envelope.
  - **Thermal wind radio** (free–free): `S_ν ∝ ν^+0.6` (Panagia–Felli 1975;
    Wright–Barlow 1975), set by the **mass-loss rate Ṁ**.
- **Flares & γ-rays:** stochastic — flare energies follow `dN/dE ∝ E⁻²`, so they
  do NOT belong on a *static* SED. True stellar γ is flare-only / exotic; for a
  normal star the γ band has no steady-state value.

## The deciding finding (the honesty gate)

Before drawing anything, we checked **what the sim's `activity` proxy is actually
computed from.** In all three providers (`mist.py:943`, `stub.py:137`,
`mesa.py:440`) it is, identically:

```python
# visual proxy (§7), explicitly evocative: cool stars more chromospherically
# active than hot ones. v/vcrit=0.0 grid -> no modeled rotation.
activity = max(0.0, min(1.0, (6500.0 - teff) / (6500.0 - 3000.0)))
```

A **pure linear ramp in Teff** — no rotation, no age, no Rossby number. So feeding
`activity` into Pizzolato/Wright would produce a **fake `L_X`** — `(6500−Teff)/3500`
wearing a lab coat. That is exactly the project's recurring "label a non-feature"
trap (boron-b8, VO 7400, invisible-Na). **Conclusion: we cannot honestly draw a
single X-ray VALUE for a given star.** What we *can* draw honestly:

- ✅ a **shaded BAND** — the saturated→quiet envelope (`L_X/L_bol` from ~10⁻³ to
  ~10⁻⁷) — which shows *the range the science permits* without claiming a value
  we don't have. (Güdel–Benz maps the same band into the radio.)
- ✅ the **hot-star wind radio**, the ONE genuinely *predictive* piece, from the
  real on-disk mass-loss rate `star_mdot` (free–free `S_ν ∝ ν^+0.6`).
- ❌ a single X-ray curve placed by `activity` → dishonest.
- ❌ γ-rays — stay floored & labeled in every version.

This yields **two epistemic tiers** in one panel, which is itself the teaching
point: an *evocative band* (cool-star corona, because we lack rotation/age) vs a
*data-grounded prediction* (hot-star wind radio, from real Ṁ). Render them
distinctly (e.g. hatched/translucent ribbon for the band; a solid line for the
wind tail).

## Approved scope (the user chose "Band + real wind radio")

Draw, on the existing SED panel:
1. a cool-star coronal **soft-X-ray activity band** + its Güdel–Benz **radio band**
   (the evocative envelope tier), and
2. the hot-star **wind free–free radio** rising above the blackbody floor (the
   real-Ṁ predictive tier),
with γ staying floored and explicitly labeled as out of scope. Everything carries
the "evocative / activity-driven, not predictive" framing already used for the
3D corona layer (spec §7, §11 open question).

**Subsequently approved (the synthesis, Chunk 3):** turn the X-ray *band* into a
concrete *line* by supplying the missing rotation dimension two ways — derive a
default from the age the sim already has (gyrochronology, MS cool stars only) AND
expose an activity/rotation slider the user drives — with honest gating that grays
out where neither applies. See Chunk 3. This is an *upgrade ladder* on top of the
band, not a replacement: band → age-derived line → slider, each rung more concrete.

## Architecture — still a sibling, mostly frontend

`sed.js` stays a **sibling to the §3 spine** (driven by the marker's state, owns
no fetch). The cool-star band needs only `L_lsun` + `Teff_K`, both already in
`StellarState` → **frontend-only**. The hot-star wind radio needs **Ṁ**, which is
NOT in `StellarState` today (it lives in `_Track` + the `.npz` cache as
`star_mdot`, added at `CACHE_VERSION 9` for the endgame work but deliberately not
threaded into the blend path or the spine). So the feature splits cleanly:

### Chunk 1 — cool-star coronal X-ray + radio BAND (frontend-only) — ✅ BUILT (see status block above)

- In `sed.js`, draw a shaded ribbon across the **soft-X-ray band** (~0.1–10 nm)
  whose vertical extent is the `L_X/L_bol` envelope **10⁻⁷ … 10⁻³** (~4 decades),
  expressed on the existing per-peak Fλ axis (see "Normalization" below).
- Map that ribbon into the **radio band** via Güdel–Benz (`L_R = L_X / 10¹⁵·⁵ Hz`)
  — a second shaded ribbon at the long-λ end.
- **Type-dependence (must be honest):** the dynamo corona is a *cool-star* (F/G/K/M)
  phenomenon. For hot stars (O/B) the X-ray collapses to the narrow wind-shock value
  `~10⁻⁷ L_bol`; there is also a known **A-star / early-F X-ray gap** (no dynamo, no
  strong wind) and a cool-giant **corona–wind dividing line** (Linsky–Haisch) where
  coronal X-rays fade. v1 can: (a) show the full 10⁻⁷…10⁻³ band for cool dwarfs,
  (b) collapse it toward 10⁻⁷ for hot stars, and (c) caption the A-gap / giant
  caveats rather than draw them. Decide the exact Teff/logg gating in the build;
  do NOT pretend a value where the physics is a gap.
- Label the ribbon with the dimensionless `L_X/L_bol` range directly (annotation),
  so it reads as "an order-of-magnitude range," not pixel-precise flux.
- Pedagogy: legend entry + `?` tooltip — rotation–activity, saturation, why a band
  not a line ("we don't model rotation/age"), Güdel–Benz, γ still empty.

### Chunk 2 — hot-star wind free–free radio from real Ṁ (backend + frontend)

The one data-grounded, predictive piece. **Requires exposing Ṁ on the spine.**

- **Backend (§3 spine touch — the heavier part):**
  - Add `mdot_msun_yr: float | None = None` to `StellarState` (an *optional* visual
    field like `activity`/`v_rot_kms`, so providers without it degrade gracefully;
    keeps `EXPECTED_KEYS` additive — update the API/test key sets).
  - Thread `star_mdot` from `_Track` through `_grid_window` / `_blend_windows`
    (linear mix — current mass-loss is smooth along a single track; the endgame
    deliberately did NOT mix it, but the SED needs the *blended* value at the
    marker, so this is a new, intentional mix) into `_state_from_row`. **No
    `CACHE_VERSION` bump** — `star_mdot` is already in the cache (v9); only the
    in-memory blend + emit changes.
  - Stub/MESA: `mdot_msun_yr=None` (stub has no mass loss; MESA tutorial runs may
    have `star_mdot` — optional follow-up, not required for v1).
  - Tests: `mdot` present & ≤0 (MIST logs mass *loss* as negative `star_mdot`),
    grows by orders of magnitude into the RGB/AGB/WR regimes; the feh-blend path
    carries it (the recurring feh=0 short-circuit gap — verify off-grid).
- **Frontend:** in `sed.js`, when |Ṁ| is significant, draw the free–free tail
  `L_ν ∝ (Ṁ/v∞)^(4/3) · ν^+0.6`. In Fλ terms `Fλ ∝ λ^−2.6` (since `Fν ∝ ν^0.6`
  and `Fλ = Fν·c/λ²`) — a **shallower** slope than the blackbody R–J floor
  (`λ^−4`), so the wind tail visibly **rises above the floor** at radio/mm
  wavelengths. That is the payoff made concrete: "real radio sits above the
  blackbody floor," now drawn from real data for a mass-losing star. Draw it as a
  **solid** line (the data-grounded tier) vs the hatched evocative band.
- **The v∞ assumption (flag, like the PoWR WR work in `smoldering-cinder-gateway`):**
  free–free flux needs the terminal wind velocity v∞, which MIST does not provide.
  Assume `v∞ ∝ v_esc` (Lamers & Cassinelli: ~2.6 v_esc for hot stars) computed from
  `M`/`R`, or a fixed typical 2000 km/s for OB. Document the assumption in code +
  caption; absolute distance cancels under per-peak normalization (we plot `L_ν`,
  not a flux at a distance).

### Chunk 3 — collapse the band to a line: age-derived default + an activity/rotation slider (the synthesis) — ✅ BUILT (see status block above)

The X-ray band is wide only because **one dimension is missing — rotation.** There
are two honest ways to supply it, and the synthesis uses **both, in a ladder**.

**(a) Derive a default from age — the sim already has it.** The earlier framing
("the sim has no rotation/age input") was true of the *current `activity` proxy*
(the Teff ramp throws age away) but MISLEADING: `age_yr` is a core `StellarState`
field and the central scrubber of the whole sim. The established chain is

```
age --gyrochronology(age, color)--> P_rot --> Ro = P_rot/τ_conv --> L_X/L_bol
```

(Barnes 2007; Mamajek & Hillenbrand 2008 — `P_rot = f(age, B−V)`). Both inputs the
gyro relation needs — **age AND color/Teff** — are already onboard, so for a
**main-sequence cool star** the band can collapse to a *line* with **no new
control**, using data the sim already has. This directly answers the
two-stars-same-Teff-different-age point: they ARE distinguishable by age; the
current proxy simply ignores it.

**(b) An activity/rotation slider — the user supplies the dimension.** A slider —
on `P_rot` (fundamental: → `Ro` directly via τ_conv) or on age (intuitive) — lets
the user PIN the missing dimension. This is exactly the pattern the project already
blessed with the **Lane–Emden `n` slider**: the codebase *rejected* auto-deriving
`n` as dishonest and made it the user's to set. A rotation slider is the same move
— pinning it collapses the band to a line legitimately, because the **user**
supplied the input; the sim didn't fabricate it.

**The synthesis = both, with honest gating:**
- Where gyrochronology is valid (MS cool stars), derive a **default** activity from
  the existing age → draw the line there; the band becomes the *scatter envelope*
  around it.
- Expose a **slider** to override / explore ("what if a young fast rotator?") and to
  cover regimes age-derivation can't reach.
- **Gray out** where neither applies — the line/slider must NOT appear for stars that
  physically can't host the relation.

**The validity domain (gate on these — outside it, deriving a value is the
fake-precision trap again):**
- ✅ Main-sequence, cool (F/G/K, ~0.5–1.3 M☉): gyrochronology calibrated, clean.
- ❌ Hot stars (no dynamo, no magnetic braking → no spin-down law): age says nothing
  about their rotation; keep the Chunk-2 wind-shock model, not the band.
- ❌ Very young (≲ few hundred Myr): rotation hasn't converged — a *spread* at fixed
  age (the fast/slow "C and I" sequences), so age doesn't pin `P_rot`.
- ⚠️ M dwarfs: stay saturated for Gyr (weak braking) — a long plateau, gyro clock mushy.
- ⚠️ Evolved (post-MS): envelope restructures → gyrochronology no longer applies; the
  sim runs to RGB/AGB, so the line must **stop at the MS turnoff**, not follow the giant.
- ⚠️ Old (≳ solar age): **weakened magnetic braking / stalled spin-down** (van Saders
  2016) — gyrochronology may BREAK past the Sun's age; flag the growing uncertainty
  exactly where the sim still lets you scrub to old ages.

Even pinned, the value keeps a **~0.5–1 dex scatter + the ~10× activity-cycle
wobble** — so the honest rendering is "a line with a fuzz," never a razor.

**Implementation sketch (still a sibling, mostly frontend):**
- The **age path is frontend-only** (`age_yr`, `Teff_K`, `L_lsun`, `logg`, `phase`
  all already in state): compute `τ_conv` from Teff (an empirical relation, e.g.
  Wright 2011 / Cranmer & Saar 2011), `P_rot` from gyrochronology(age, color) reusing
  `color.js`'s Teff→color, then `Ro` → `L_X/L_bol` — collapsing the Chunk-1 band to a
  line *within its validity gate*.
- The **slider** is a new `sed.js`-local control (like `lane.js`'s n-slider) — its own
  state, no spine touch; it just overrides the derived `P_rot`/age.
- Gating reads `phase` (MS vs evolved) + Teff/mass — all in state, no backend change.

This is the upgrade ladder the discussion converged on: **band** (no extra input,
Chunk 1) → **age-derived line** (uses what's already onboard, MS cool stars) →
**slider** (the user drives it, covers the gaps). Each rung is more concrete; none
fakes a number the physics can't support.

## Normalization (the trickiest design point — solve it before drawing)

The panel's y-axis is **decades below the blackbody Fλ peak**. To place an
*integrated* luminosity ratio (`L_X/L_bol`) or a *spectral* luminosity (`L_ν`) on
that axis honestly:

- Relate `F_peak` to `L_bol = ∫Fλ dλ`. For a blackbody there is a fixed ratio
  between `B_λ,peak` and `∫B_λ dλ` (`σT⁴/π` per sr), so `L_bol ≈ F_peak · Δλ_eff`
  with a known `Δλ_eff(T)`. This converts a dimensionless `L_X/L_bol` into an Fλ
  level (a flux spread over the emitting band's Δλ): `log10(Fλ_X/F_peak) =
  log10(f_X) + log10(L_bol/F_peak) − log10(Δλ_band)`.
- **Risk:** this depends on a band-width assumption and can read as arbitrary pixel
  precision. **Mitigation (decide in build):** prefer annotating the band with the
  dimensionless `L_X/L_bol` ratio + Güdel–Benz `L_R` directly, using the Fλ
  placement only for rough vertical positioning, and keep the ribbon visibly an
  *order-of-magnitude range* (hatched, wide) — never a crisp line.

## Open questions / risks (resolve during build)

1. **Visual clutter.** The panel already carries 7 bands + Wien peak + the detail
   bracket. Two ribbons + a wind tail risk overload. Consider: only draw the
   cool-band when cool/convective, only draw the wind tail when |Ṁ| is significant,
   and/or a small toggle. Keep the blackbody the visual protagonist.
2. **Type gating done honestly** (cool dynamo vs hot wind-shock vs A-gap vs giant
   dividing line) — see Chunk 1. Better to caption a gap than to draw a fake value.
3. **γ stays empty — keep it explicit.** The feature answers *radio + soft X-ray*;
   it must not quietly imply it filled the γ end.
4. **Two-tier rendering must read as two tiers** — distinct styling for the
   evocative band vs the data-grounded wind line, mirrored in the legend/caption.
5. **No JS test harness** — the cool-band Chunk 1 is frontend-only, so a Playwright
   screenshot pass across the spectral sequence is its regression check (as in
   Phases 2–5). Chunk 2's backend (Ṁ threading) gets real pytest §10 tests.
6. **Caption rewrite.** The current SED caption *promises* this is unmodeled; once
   drawn, the caption must flip to describe what the ribbon/wind tail mean and what
   they still cannot say (the activity value, γ, flares).

## Suggested order

Chunk 1 first (frontend-only, immediate visible payoff, zero spine risk), then
Chunk 2 (the spine touch + the genuinely predictive wind radio), then Chunk 3 (the
synthesis — age-derived line + slider, frontend-only on top of Chunk 1's band).
Each is independently shippable and independently honest. Chunk 3 depends on
Chunk 1 (it collapses Chunk 1's band) but not on Chunk 2.

## References (all advisor-verified)

Pizzolato et al. 2003; Wright et al. 2011 (rotation–activity, saturation ≈ 10⁻³·¹);
Güdel & Benz 1993, Benz & Güdel 1994 (L_X/L_R ≈ 10¹⁵·⁵ Hz); Berghöfer et al. 1997,
Nazé 2009 (O-star L_X ≈ 10⁻⁷ L_bol); Panagia & Felli 1975, Wright & Barlow 1975
(thermal wind free–free, S_ν ∝ ν^+0.6); Güdel 2004 (review). Flare distribution
`dN/dE ∝ E⁻²`. Lamers & Cassinelli 1999 (v∞ ≈ 2.6 v_esc, hot stars).
**Gyrochronology / age→rotation (Chunk 3):** Skumanich 1972 (`v ∝ t^−1/2`); Barnes
2007, Mamajek & Hillenbrand 2008 (`P_rot = f(age, color)`); Cranmer & Saar 2011 /
Wright et al. 2011 (convective turnover time τ_conv); van Saders et al. 2016
(weakened magnetic braking / stalled spin-down past ~solar age).
