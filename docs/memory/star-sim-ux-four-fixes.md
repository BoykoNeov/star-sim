---
name: star-sim-ux-four-fixes
description: "Frontend slider/UX fixes — mass-slider 0.999 (source-of-truth), age-display honors exact entry, SED X-ray-gap marker + morph, HR-toggle no-resize (visibility:hidden), classification line, and moving mass/feh preserves the absolute age value (ageValue source of truth, Option-2 clamp-only-for-display)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 0a86551e-2508-48d1-ab1b-f771ee3c8ca7
---

Frontend-only fix bundle (no backend/API/spine touch; pytest unchanged 137). Four
user-reported issues, all advisor-reviewed before building, verified via Playwright
bundled Chromium on the real served UI. Documented in the CLAUDE.md "Done (UX, four
reported fixes)" bullet — this captures the **reusable gotchas**.

1. **Mass showed 0.999 instead of 1 (and reverted after editing).** Root cause =
   `<input type=range>` **step quantization**: the slider step (0.0005) can't represent
   the exact 1.0 M☉ thumb position, so re-deriving mass from `els.mass.value` yields
   0.99917; typing 1 only re-set the thumb → next refresh re-derived 0.999. **Fix = a
   source-of-truth `massValue`** in `main.js`: drags snap to the *exact* round mass at a
   tick (new `massTickVals` parallel to `massTickPos`; `massFromSliderInput`), the number
   box stores the exact typed value, `refresh()`/`refreshTrack()` read `massValue` then
   sync the thumb. **Two traps:** (a) the feh dead-corner clamp must clamp `massValue`
   **and persist it back** (not just the slider visual), else a metal-rich star sits below
   its floor; (b) you CANNOT just snap `massFromSlider`'s *output* to round masses —
   that breaks the number-box escape hatch (typing 0.99 would jump to 1.0). The
   escape-hatch (arbitrary precision, bypasses snapping) is a deliberate design feature.
   **Follow-up (later session) — the age number box had the SAME class of bug, now
   fixed.** `gyrNum` rounded the DISPLAY onto the coarse spinner step (0.05 Gyr for a
   1.44 M☉ star), so typing 2.14 vs 2.16 Gyr both showed "2.15" while the change
   handler set `ageFraction` from the EXACT value and the SED/readout used it (display
   *lied* about reality — 2.14 → SED X-ray gap, 2.16 → coronal band, both "2.15").
   **Fix = decouple display precision from the spinner step**: show the true value at
   **≥3 significant figures**, with `niceAgeStep`'s decimals only as a FLOOR (so a
   short-lived massive star doesn't collapse to "0.00"). Plain `toFixed(decimals)`
   RE-collides on coarse-step long-lived stars (a 12 Gyr 0.9 M☉ window → decimals=1 →
   2.14/2.16 both "2.1"); value-tied sig-figs is the actual fix (advisor caught this).
   Spinner `step`/`min`/`max` untouched (arrows still snap; an off-grid typed value is
   just honored — no form, no `:invalid` styling). **Surfaces ONLY on the BLUR path**:
   `setNum`'s `activeElement` guard suppresses the overwrite while focused, so
   typing+Enter looked fine — clicking away (blur fires `change` with focus gone) is
   what triggered the rounding. Generalizes the rule: the displayed value must equal
   the value actually in use.

2. **SED coronal/wind X-ray band appeared/disappeared dragging mass/age = NOT a bug,
   real physics.** `regimeOf()` in `sed.js` gates at Teff 6500 K (cool→A/early-F **X-ray
   gap**) and 10000 K (gap→hot wind-shock band) — established physics (the A/F X-ray
   gap). The bug was the UX: the gap drew **nothing** → looked broken. **Fix = draw a
   faint dashed "X-ray gap" marker on the canvas** in the gap regime so the feature
   *transforms*, not vanishes. **Canvas-ONLY** — do NOT lengthen the caption: the "gap"
   caption branch is deliberately length-matched across regimes to stop the panel
   resizing as you scrub (lengthening it re-creates the HR-resize bug). Cool/hot regimes
   unchanged.
   **Follow-up (later session) — the user asked whether the *sudden* gap switch is
   physically real; it is NOT a cliff, so the hard switch became a gradual MORPH.** The
   convective-dynamo X-ray decline across the **Kraft break (~6200 K)** is a ramp, not a
   step at 6500 K — so the hard `regimeOf` boundary overstated the sharpness and a fade
   is *more* honest (the boundaries were always nominal; fits "evocative range, not
   predictive"). `drawActivity` rewritten to morph via `smoothstep` weights: across
   cool↔gap the band's saturated ceiling descends 10⁻³→10⁻⁶ as it fades, **shrinking
   INTO** the dashed gap sliver right where it lands = **one object morphing, NOT two
   ghosts crossfading** (advisor's steer — the dashed line fades IN only in the 2nd half
   of the transition, by which point the band has collapsed onto its level → no double
   image; verified by screenshotting 6300/6500/6700/6900 K). Secondary gap↔hot (10000 K)
   edge = plain alpha crossfade (the user's case is the 6500 K edge). Band-draw
   extracted to a reusable `drawXrayBand(decFromLog,{logHi,logLo,dim,tag,labels,alpha})`;
   `drawXrayGap`/`drawGudelBenzRadio` gained an `alpha` param; edge labels ride the band
   alpha (text can't interpolate → it dissolves). **Caption stays DISCRETE +
   length-matched** (don't fade text = the resize jank).

3. **HR variable-star-zones toggle resized the panel.** `.legend-vars` was `display:none`
   → revealed on toggle, adding height. **Fix = `visibility:hidden`→`visible`** (NOT
   `display`, not always-show = orphan legend, not measured `min-height`+media-query =
   fragile at flex-wrap widths). `visibility` keeps the layout box so panel height is
   identical on/off (measured 444=444 px), auto-reserves the correctly-wrapped height at
   any width with no measurement, drops it from tab order. Accepted cost: a small
   permanent gap below the canvas when off (don't fill with a hint line — won't match the
   2-row legend height → partial resize). This is the **general pattern for a
   toggle-without-resize** in this dashboard.

4. **Star classification + description** — new `classify.js`, a sibling TEXT view like
   `scale.js` (reads the marker, no fetch), shown under the 3D star (`index.html`
   `.star-class`, fixed `min-height` so a changing label can't resize the panel).
   Schematic Morgan–Keenan: Teff → temp class O–M + 0–9 sub; **luminosity class is
   PHASE-FIRST, log g fallback** — anchor on `phase` (MS/PMS→V) so a 40 M☉ O-star is a
   main-sequence **dwarf** (V), not mislabeled "III" by its giant-like logg≈3.9. **"white
   dwarf" terminology trap:** an A V star is "white main-sequence star", NOT "white dwarf"
   (a degenerate remnant) — restrict the "<color> dwarf" idiom to G/K/M. `?` help labels
   it schematic (from Teff/log g/phase, not real spectral lines). Verified: Sun=G2 V
   yellow dwarf, hot ZAMS=O4 V blue main-sequence, evolved 1 M☉=K3 III orange giant.

5. **Moving the mass (or [Fe/H]) slider no longer changes the age value** (user ask:
   "don't change one slider's value when moving another — specifically mass vs age").
   Root cause = the age source of truth was the slider **fraction** (0..1), not the
   absolute age: each track has its own `[ageMin, ageMax]` window read off the track, so
   keeping the fraction across a mass change made the absolute age (`ageMin + frac·span`)
   jump — a short-lived star at "fraction 0.46" is a wildly different Gyr value than a
   long-lived one. **Fix = make absolute years `ageValue` the source of truth** (the same
   pattern as `massValue` / the age-display fix): on a mass/feh change, `refreshTrack`
   recomputes the slider *fraction* from the preserved `ageValue`, clamped to the new
   window. **Option 2 (advisor-confirmed): keep `ageValue` UNCLAMPED** (the desired age) —
   only the fetch/display clamp it. The mass slider fires `refreshTrack` on **every input
   event**, so clamping `ageValue` itself (Option 1) would *ratchet* the age to ~0 as you
   drag up through Myr-lifetime massive stars; Option 2 makes the age ride along and
   **spring back** when you drag back into a long-lived regime. **NOT the lying-display
   antipattern** (the discriminator that separates it from the 2.14/2.16 bug above):
   everything shown — number box, readout `s.age_yr`, thumb — uses the **clamped** age;
   only the hidden `ageValue` is unclamped and never shown, so display == fetch == readout
   always. **Three rules to preserve:** (a) `refresh()` computes
   `age = clamp(ageValue, ageMin, ageMax)` for BOTH the fetch and `setNum`, and must
   **not** re-read/recompute the thumb from `els.age.value` (that re-quantizes to the
   0.0005 step and reintroduces the razor-sharp-phase off-by-one — see
   [[star-sim-ux-age-tick-fixes]]); thumb-setting stays in the handlers + `refreshTrack`.
   (b) the age-scrub handler sets `ageValue = ageMin + snappedFraction·span` (the EXACT
   float, so a landmark snap still fetches the landmark age → phase readout correct).
   (c) the age-num handler sets `ageValue = typedGyr·1e9`. **feh comes along for free**
   (both go through `refreshTrack`). `firstTrackLoaded` removed — initializing
   `ageValue = DEFAULT_AGE_YR` makes the general path place the default Sun at 4.6 Gyr, no
   special case. **Consequence (intended):** dragging mass *up* from the 4.6 Gyr Sun now
   clamps massive stars to their **end-state** (4.6 Gyr exceeds their Myr life) instead of
   the old fraction-0.46 mid-MS — the literal correct reading of the request. Verified via
   Playwright (5 Gyr preserved on a 1→0.9 nudge; clamps to the EAGB end at 8 M☉, thumb
   pinned 1.0; springs back to 5 Gyr; feh −0.25 preserves age; CHeB snap reads CHeB; §10
   Sun anchor intact). Frontend-only, pytest unchanged (137).

See [[star-sim-frontend-ux]], [[star-sim-draggable-responsive-panels]],
[[star-sim-instability-strip-overlay]], [[star-sim-phase5-spectra]],
[[star-sim-ux-age-tick-fixes]].
