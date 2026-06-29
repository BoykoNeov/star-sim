---
name: star-sim-ux-nine-fixes
description: Third user-reported UX-fix batch (nine items). Chunks A (HR auto-fit framing), B (endgame quick-wins) & C (readout panel split + gateway greyed-button) BUILT; D–E planned. Plan docs/plans/polished-cinder-frame.md.
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

**Chunk C — layout: readout panel split + gateway jitter (items 1, 4) — ✅ BUILT 2026-06-29**,
three files (`frontend/index.html`, `frontend/src/main.js`, `frontend/styles.css`).

- **Item 1 (readout panel):** moved `State readout` `<h2>` + `#readout` + `#status` into a new
  `<section class="panel readout-panel" data-panel-id="readout">` after `controls`. JS is
  id-referenced (untouched); the new `<h2>` auto-gets a `layout.js` drag grip. Saved-layout users
  get `readout` **appended last** (accepted trade); Reset restores authored order. Both verified.
- **Item 4 (jitter) — user redirected from "reserve empty space" to "place the button, greyed out
  until available," which is strictly better.** Gateway block is **always in the layout** (live
  mode); its control shows as soon as the endgame TYPE is known (`fetchEndgamePreview` fetches
  `/endgame` on **every** track regardless of age). The **WD/WR Continue button is shown but
  `disabled`/greyed (muted outline) until `ageFraction >= GATE_SHOW`**, where it enables and
  **"lights up" to filled-accent yellow** — *same box in both states → panel never resizes* (the
  literal cure for "appearing buttons resize panels"). `min-height` on `.gateway` (~1 button row)
  stops collapse during the type-load window / for no-endgame stars; the taller SN note still
  expands (rare, accepted). `refreshTrack` clears the gateway **children**, not the block, on a
  track change so the reserve holds. **This sidesteps the plan's reserve-vs-waste dichotomy** —
  the slot is filled by a meaningful disabled control, not empty space.
- **SN note now foreshadows from ZAMS — user-confirmed.** SN branch changed `atEnd&&type==="SN"` →
  `isSn`, so every 8–40 M☉ star shows the honest core-collapse dead-end note (no Continue; remnant
  not modeled) throughout life, consistent with the WD/WR buttons. Pedagogy change beyond the
  literal ask → explicitly confirmed (user chose "From the start (foreshadow)").
- **Resnap note (`#endgame-resnap-note`) — DEFERRED (conscious).** Unlike the gateway it has **no
  persistent content to fill a reserve**, so reserving = the empty space the user rejected; it
  appears only on a *failed* re-snap inside an endgame (deliberate exploratory drag). Advisor
  retracted its earlier "reserve it." Clean close-out if revisited: move the note **below** the
  sliders (it's mass-control feedback) so it grows the panel downward, no empty space.

**Gotcha for future gateway work:** the gateway block no longer toggles `hidden` in live mode
(only enter/exitEndgame do); `updateGateway` returns early unless `mode==="live"` and always sets
`els.gateway.hidden=false` there. The WD/WR buttons carry `disabled` (toggled by `atEnd`), not
visibility — visibility is `hidden` per fate type. Verified Playwright: Sun greyed→lit, m=25 SN
note at genuine mid-MS (ageFrac 0.30), m=120 WR disabled at genuine mid-MS, both layout profiles,
zero page errors.

**D–E still planned**: D gateway auto-appear (repro-driven; note the always-present greyed button
may have shifted its dynamics — re-repro before fixing), E age-slider remap (design). Related:
[[star-sim-wr-wd-endgame-plan]].
