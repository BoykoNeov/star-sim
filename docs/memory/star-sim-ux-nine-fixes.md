---
name: star-sim-ux-nine-fixes
description: Third user-reported UX-fix batch (nine items). Chunk A (HR auto-fit framing) BUILT; B–E planned. Plan docs/plans/polished-cinder-frame.md.
metadata: 
  node_type: memory
  type: project
  originSessionId: 672e8ccd-ca1d-47ef-93d3-cfdcedf01f86
---

The **third** user-reported-fix batch (cf. [[star-sim-ux-four-fixes]],
[[star-sim-ux-age-tick-fixes]]): nine items triaged + chunked **A→E** in
`docs/plans/polished-cinder-frame.md` (status mirrored in [[../plans/ROADMAP.md]]).

**Chunk A — HR framing (items 5 & 6) — ✅ BUILT 2026-06-29**, `frontend/src/hr.js` only.
The HR diagram used fixed plot bounds and never clipped/clamped the track, so massive
living stars (≳60 M☉, logL>6) and WR endgame tracks drew off the top ("nothing displayed").

- **Endgame views (WD+WR): auto-fit** — `setEndgame` → `fitBounds(endgameTrack, track)`
  (endgame journey + the faint living-context track under it) + padding; gridlines
  regenerated via `niceStepL` (integer-dex) / `niceStepT` (half-dex) → `genTicks`. `kind`
  is now framing-agnostic. Mirrors `star.js applyWindScale` (the WR-3D fit-to-frame precedent).
- **Living view: a HYBRID, not pure auto-fit** (`applyLivingBounds`) — keep the exact fixed
  teaching frame (3.4–4.7 logT, −4…6 logL) + hand-tuned gridlines for ordinary stars; expand
  **only the edges the RAW track crosses** (margin added solely on overflow edges; only an
  expanded axis regenerates gridlines). **Why not pure auto-fit:** advisor flagged it would
  destroy the inter-star scale cue (0.5 M☉ and 5 M☉ would fill the frame identically). **Why
  not the plan's "widen LOGL_MAX to 7":** the hybrid both preserves the comparison frame *and*
  guarantees framing for any mass/[Fe/H]. Sun/0.1/1/5 keep the exact default; m=300 expands.
- **WD living preview** (the user's 2 extra asks): dashed → **solid faint grey** (to match how
  the endgame view greys the living track). The "clipped/unclear" artifact was the **full**
  post-AGB→WD cooling sequence drawn as a confusing diagonal across the frame — raw states
  meander on the cool TPAGB, **jump blueward to a ~100–200 kK exposed core**, then sweep down to
  logL≈−5. Fix: draw only a **directional leader** from the AGB tip (living-track end) to the
  **hottest** state (post-AGB knee), exiting the frame toward hot, labeled `→ white dwarf`. Full
  cooling physics stays in the dedicated WD endgame view (the gateway). **Suppressed for SN**
  (m≳7 here → `type="SN"`, no preview) and WR.

**Gotcha for future hr.js work:** `LOGT_MIN/MAX`, `LOGL_MIN/MAX` are now **only default seeds**
for the `bT0..bL1` `let` bindings + the overflow thresholds in `applyLivingBounds` — never used
in a draw path. `xOf`/`yOf` and the variable-star overlay read the live bindings, so decorations
follow expanded/auto-fit bounds automatically (overlay is also clipped + living-mode-only).

Verification = Playwright sweep (m=1/3/7/120/300, living + WR + WD views) + numeric containment;
no JS test harness ([[star-sim-frontend-ux]]). **B–E still planned**: B endgame quick-wins
(7 WR-SED-says-WD · 8 Lane–Emden-for-WR=no-fix · 9 yellow Back button), C layout (split readout
panel + reserve jitter slots), D gateway auto-appear (repro-driven), E age-slider remap (design).
Related: [[star-sim-wr-wd-endgame-plan]].
