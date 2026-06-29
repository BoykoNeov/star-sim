---
name: star-sim-ux-nine-fixes
description: Third user-reported UX-fix batch (nine items). Chunks A (HR auto-fit framing) & B (endgame quick-wins) BUILT; C–E planned. Plan docs/plans/polished-cinder-frame.md.
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
no JS test harness ([[star-sim-frontend-ux]]).

**Chunk B — endgame quick-wins (items 7, 8, 9) — ✅ BUILT 2026-06-29**, two files
(`frontend/src/sed.js`, `frontend/styles.css`); item 8 = no-fix.

- **Item 7 (bug):** WR's SED caption inherited the WD text via the shared `endgameMode` gate in
  `sed.js renderCaption()`. Fix = an `if (endgameWR)` branch **before** the WD branch. WR caption:
  stripped hot core / wind-not-dynamo → no coronal band / free–free radio "isn't drawn" (un-built
  SED Chunk 2) / next step = **core-collapse, not a white dwarf**. The phrase "white dwarf" survives
  ONLY as a corrective negation (the WD gateway is one mass-drag away → explicit contrast is a
  teaching beat, not evasion; advisor-endorsed, matches plan line 152). WD caption untouched.
- **Item 9 (polish):** `.endgame-back` restyled to a **compact filled-accent (yellow)** button —
  mirrors `.gateway-btn` (`color:var(--bg)`; `background:var(--accent)`; weight 600; hover
  `brightness(1.08)`; `:focus-visible` outline) but stays compact (no `width:100%`) so the bar's
  title-+-back single row survives. Yellow in BOTH wd-mode and wr-mode.
- **Item 8 (question, NO change):** WR shows the **generic** Lane–Emden intro ("teaching
  idealization… not the real interior"); only the WD remnant earns the "genuinely a polytrope"
  hint (`.lane-wd-hint`, `wd-mode`-only). A WR is radiation-pressure-dominated + wind-shrouded, NOT
  a single polytrope → the generic disclaimer is honest and adequate. Optional `.lane-wr-hint` =
  **available but deferred** unless the user opts in (additive, not a fix).

Chunk B verification: Playwright drove the real UI (WR m=120, WD m=1) — asserted WR caption reads
as a WR (no "contracts into a white dwarf"), WD caption unchanged, `#endgame-back` computed bg =
accent `rgb(255,210,127)` in both modes; zero page errors. **One mass per path suffices** (vs Chunk
A's sweep): WR caption is fixed text (Teff aside) + button is mode-CSS — both mass-independent.

**C–E still planned**: C layout (split readout panel + reserve jitter slots), D gateway auto-appear
(repro-driven), E age-slider remap (design). Related: [[star-sim-wr-wd-endgame-plan]].
