---
name: star-sim-ux-age-tick-fixes
description: "Age-slider landmark-tick fixes — off-by-one phase (step-quantization), endpoint-reach, RGB-tip-steals-snap, chronological chain-stagger + edge-anchor; reusable snap-slider gotchas."
metadata: 
  node_type: memory
  type: project
  originSessionId: b2c881bf-9511-479b-b6c3-74013acf6155
---

Frontend-only bundle (`main.js` + `styles.css`, **pytest unchanged 137**) fixing five
reported age-slider landmark-tick bugs in the Star Simulator. Diagnosed **empirically**
(a curl harness over `/track`+`/state` for the named stars), then verified via Playwright
bundled Chromium on the real served UI (16/16 snap→phase logic + a bounding-box overlap
check on phone). Reusable, non-obvious findings:

- **Off-by-one phase = `<input type=range step=…>` quantization.** The slider handler did
  `el.value = snap(...); frac = Number(el.value)` — re-reading the DOM AFTER assigning
  re-quantizes to the step (0.0005), landing the query just below a **razor-sharp phase
  boundary** → previous phase in the readout ("snap to CHeB, shows RGB"). Fix = keep the
  snapped value as an EXACT float source-of-truth (`ageFraction`), set `el.value` only as a
  display. **This generalizes the `massValue` pattern** — any snap-to-landmark slider that
  re-reads `el.value` has this latent bug. (Verified the exact-float round-trip
  `age = ageMin + pos*span` gives the right phase at every tick.) See [[star-sim-ux-four-fixes]]
  (the massValue 0.999 fix is the same class).

- **Landmark structure is always MS→RGB→CHeB→EAGB (no SGB), and RGB-tip ≈ CHeB onset
  ALWAYS** (measured |Δpos| < 1.3e-4 across all masses — the He flash is AT the tip). So
  the dedup rule: **phase transitions are never dropped** (the old global 0.01 dedup dropped
  CHeB = "CHeB nowhere as a tick"); the RGB-tip is the only droppable point. **Drop it
  against the FULL phase set, NOT in sort order** — the tip's pos is marginally *below*
  CHeB's, so an order-dependent dedup keeps the tip (processed first, opts empty) and then
  the snap **steals onto the tip's still-RGB row** → that WAS the M=0.66 "snap to end, shows
  RGB" bug. The verification caught it (don't trust order-dependent dedup).

- **Endpoints as snap targets fixes "can't reach the end."** A late landmark within the
  0.015 snap radius of pos 1.0 captured the whole right edge → slider stuck short of the
  final state. `snapAge()` adds **{0,1}** to the targets so dragging fully right lands on
  the true end (the late landmark stays hittable just before it).

- **Chain-stagger for crowded labels (no-drop), NOT greedy lowest-row.** Greedy "lowest
  free row" **inverts chronological order** (a later label grabs a freed top row — EAGB
  rendered ABOVE CHeB for the Sun; wrong for a teaching tool). Chain: a label close to its
  predecessor drops ONE row below it, a real gap resets to row 0 → guarantees earlier-phase-
  on-top. **Edge-anchor** decouples label from mark (mark at true pos; label left/right-aligns
  near the ends so it extends inward, not clipping — also fixes mass 0.1/300 + feh edges).
  Stagger is **opt-in** (age only; mass/feh keep single-row collision-skip — don't regress them).
  CSS grows the strip + slider-wrap margin via a `--tick-rows` var.

- **Layout-independent MIN_GAP trade-off (advisor-caught).** Kept normalized-pos (no pixel
  measure / resize hook). **MIN_GAP must be sized for phone** (a label is ~0.10 of the strip
  width at 390px) → **0.11**, so low-mass + ~20 M☉ render a clean 3-row staircase (the cost of
  never overlapping; the *chain*, not MIN_GAP, is what fixes order). My first pass used 0.085
  and only phone-tested M=0.66 (a 3-row cluster that never hits the same-row case) — the
  advisor flagged that the **default Sun / 0.9 M☉** (RGB→CHeB gap ~0.10) put CHeB on row 0
  beside RGB → **overlap at 390px**. Lesson: verify same-row overlap with a **bounding-box
  check across the default + low-mass stars at phone width**, not one staircase screenshot.

- **Deviation from the user's literal "above the slider":** stacked DOWNWARD (rows below)
  because above collides with the Age title/number-input row — same goal (every landmark
  visible) + chronological. Surfaced the deviation to the user.

Cross-refs: [[star-sim-ux-four-fixes]], [[star-sim-frontend-ux]], [[star-sim-mist-provider]]
(the phase/EEP window the landmarks come from).
