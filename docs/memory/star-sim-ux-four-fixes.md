---
name: star-sim-ux-four-fixes
description: "Four user-reported frontend fixes — mass-slider 0.999 (source-of-truth), SED X-ray-gap visible marker, HR-toggle no-resize (visibility:hidden), and the spectral-classification line."
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
   The age slider has the same latent quantization but `gyrNum` already rounds it to a
   clean grid — left alone (don't expand scope).

2. **SED coronal/wind X-ray band appeared/disappeared dragging mass/age = NOT a bug,
   real physics.** `regimeOf()` in `sed.js` gates at Teff 6500 K (cool→A/early-F **X-ray
   gap**) and 10000 K (gap→hot wind-shock band) — established physics (the A/F X-ray
   gap). The bug was the UX: the gap drew **nothing** → looked broken. **Fix = draw a
   faint dashed "X-ray gap" marker on the canvas** in the gap regime so the feature
   *transforms*, not vanishes. **Canvas-ONLY** — do NOT lengthen the caption: the "gap"
   caption branch is deliberately length-matched across regimes to stop the panel
   resizing as you scrub (lengthening it re-creates the HR-resize bug). Cool/hot regimes
   unchanged.

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

See [[star-sim-frontend-ux]], [[star-sim-draggable-responsive-panels]],
[[star-sim-instability-strip-overlay]], [[star-sim-phase5-spectra]].
