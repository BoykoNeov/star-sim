# Polished cinder & frame — nine user-reported UX refinements

A triage + chunking plan for nine items the user reported after using the
feature-complete app (Phases 1–5 + the WR/WD endgame). This is the **third**
user-reported-fix batch in the project's lineage (cf.
[[star-sim-ux-four-fixes]], [[star-sim-ux-age-tick-fixes]], and the recent
"six user-reported fixes" commit `39c56cc`).

**This doc is the deliverable of a planning session — nothing here is built yet.**
The work is split into five chunks meant for **different sessions**. The two
behavioural items (#2 age-slider, #3 gateway auto-appear) are **investigate-then-fix**:
their root cause can't be pinned by code reading alone — the plan records a concrete
repro/verification strategy so the implementation session is efficient, not a fresh
investigation.

Naming follows the endgame lineage ("smoldering-cinder-gateway"): *cinder* = the
endgame work most of these touch, *frame* = the headline HR-clipping fix.

---

## The nine items, mapped to chunks

| # | User report | Chunk | Severity |
|---|---|---|---|
| 5 | Massive WR/living stars beyond the upper HR scale | **A — HR framing** | high |
| 6 | Jumping to WR screen: trail so high up nothing is displayed | **A — HR framing** | **highest** (nothing shown) |
| 7 | WR screen's broadband SED talks about white dwarfs | **B — endgame quick-wins** | low (wrong text) |
| 8 | *Question:* how adequate is the Lane–Emden description for WR? | **B — endgame quick-wins** | n/a (answered below) |
| 9 | "Back to the living star" should be a yellow button like the gateway | **B — endgame quick-wins** | low (polish) |
| 1 | State readout should be its own panel, not inside Controls | **C — layout** | medium |
| 4 | Appearing buttons resize panels; panels should be fixed-size | **C — layout** | medium |
| 3 | Gateway button should auto-appear on mass change at end-of-life | **D — gateway auto-appear** | medium (needs repro) |
| 2 | Age slider past a point: age rises but nothing else changes | **E — age-slider remap** | medium (design) |

Recommended build order: **A → B → C → D → E** (severity first; A unblocks
nothing but is the most visible breakage; E is the meatiest design call and best
done last with its own consult).

Each chunk's regression gate is the **Playwright screenshot pass** (no JS test
harness — [[star-sim-frontend-ux]]). Items #2/#3/#5/#6 specifically need the app
**running** to confirm the behaviour, not just a screenshot.

---

## Chunk A — HR framing for massive & WR tracks (items 5, 6) · do first

### Root cause
`hr.js` uses **fixed plot bounds** per mode and **does not clip or clamp** the
track/marker draw (only the variable-star overlay and the WD preview are clipped).
A point above the ceiling simply draws off-canvas.

- Living view: `LOGL_MAX = 6` (`hr.js:13`). Massive stars (≳40–60 M☉) reach
  log L > 6, so their upper track + marker leave the frame (item 5).
- WR view: `LOGL_MAX_WR = 7.0`, `LOGT_MAX_WR = 5.5` (`hr.js:30–32`). The comment
  claims the 300 M☉ onset peaks at log L 6.80 — but I **could not verify from code
  alone** that 7.0 covers every WR sub-track (the scrub opens on a huge, luminous,
  cool R≈33 R☉ giant; very massive entries may sit near or above the ceiling).
  Item 6 = "nothing displayed" is consistent with the whole track landing above 7.0.

**That uncertainty is itself the argument against fixed bounds.** The fix is not to
nudge the constants — it's to make the frame follow the data.

### Approach — auto-fit the axes to the track (mirror an existing precedent)
The WR **3D** view already solves the exact analogue: `star.js` `applyWindScale`
recomputes a fit-to-frame extent **each frame** precisely because the WR scrub opens
on a huge R≈33 R☉ star a constant extent would clip (see CLAUDE.md endgame note).
Mirror that in the HR panel:

- For the **endgame views** (WD + WR): compute axis bounds from the actual
  `endgame.states` min/max of `log10(Teff_K)` and `log10(L_lsun)`, plus a small
  padding margin, and use those instead of the hard-coded `*_EG` / `*_WR` constants.
  `endgame.states` is a known finite list → min/max is trivial and **guarantees** the
  track is framed regardless of progenitor mass.
- For the **living view** (item 5): two options —
  - (a) **auto-fit to the current track** (robust, same mechanism), or
  - (b) widen `LOGL_MAX` to ~7 to cover the grid (simplest, keeps a stable frame).
  - **Decision to make:** auto-fit trades the *stable reference frame* (fixed axes you
    can read absolute L/Teff off at a glance, and compare stars against) for guaranteed
    framing. Recommendation: **auto-fit the endgame views** (they're single-track and
    already "a journey," so a moving frame is fine) and **widen the living ceiling to ~7
    with fixed bounds** (preserve the comparison frame for the main teaching view). Round
    the auto-fit bounds to "nice" gridline values so the axis labels stay legible.
- Keep the gridline arrays (`GRID_T*`, `GRID_L*`) consistent with whatever bounds win
  — if bounds become dynamic, derive the gridlines from the bounds rather than hard-coding.

### Files
- `frontend/src/hr.js` (bounds + the `xOf`/`yOf` closures already read `let` bindings
  `bT0/bT1/bL0/bL1`, so dynamic bounds slot in at `setEndgame`/`setTrack` cleanly).

### Verification
Run the app. Living: drag mass to 100–300 M☉, confirm the upper MS/track stays in
frame. WR: enter the WR endgame at several masses (e.g. ~35, ~60, ~120, ~300 M☉) and
[Fe/H] extremes, scrub the full sub-track, confirm the track + marker are always
visible. Playwright screenshots at the extremes.

### Consult
**Own advisor consult when built** — the auto-fit-vs-fixed decision and the
"nice rounding" of dynamic gridlines are worth a second opinion.

### Status — ✅ BUILT (2026-06-29)
Implemented in `frontend/src/hr.js` (only changed file). Diverges from the plan's
recommendation in one deliberate way, endorsed by the advisor consult:

- **Endgame views (WD + WR):** auto-fit as planned — `setEndgame` computes
  `fitBounds(endgameTrack, track)` (the endgame journey **plus** the faint living-context
  track drawn under it) with a small padding margin, regenerating gridlines from the live
  bounds (`niceStepL` integer-dex / `niceStepT` half-dex → `genTicks`). `kind` is now
  framing-agnostic. Verified: WR m=120 (316→56 kK, framed with headroom), WD m=1 cooling
  track (100 kK→3.2 kK, framed; living context greyed).
- **Living view:** *not* the plan's "widen `LOGL_MAX` to ~7 with fixed bounds." Instead a
  **hybrid** (`applyLivingBounds`): keep the exact fixed teaching frame (3.4–4.7 logT,
  −4…6 logL) + hand-tuned gridlines for ordinary stars, and expand **only the edges the raw
  track actually crosses** (margin added solely on overflowing edges; only an expanded axis
  regenerates its gridlines). The advisor flagged that pure auto-fit would destroy the
  inter-star scale cue (a 0.5 M☉ and a 5 M☉ would fill the frame identically) — the hybrid
  preserves the comparison frame **and** guarantees framing. Verified: Sun/0.1/1/5 keep the
  exact default frame; m=300 expands the overflow edges and frames the marker.
- **WD living-view preview** (the user's two extra asks, beyond items 5/6): dashed → **solid
  faint grey** (matches how the endgame view greys the living track). The "clipped, and it is
  unclear what it is" complaint was the **full** post-AGB→WD cooling sequence drawing a
  confusing diagonal clear across the living frame (the raw states meander on the cool TPAGB,
  jump blueward to a ~100–200 kK exposed core, then sweep down to logL ≈ −5). Fix: draw only a
  **directional leader** from the AGB tip (where the living track ends) to the **hottest** state
  (the post-AGB knee), which runs up-left and exits the frame toward the hot WD regime, with a
  `→ white dwarf` label on the line. The full cooling physics lives in the dedicated WD endgame
  view (the gateway). Correctly **suppressed for SN** progenitors (m ≳ 7 here → `type="SN"`, no
  preview) and WR.

**Advisor's two flagged checks, both cleared:** (1) the preview no longer reads as a stray
clipped line (leader + label, verified m=1/3/7); (2) fixed-coordinate decorations under
expanded/auto-fit bounds — the variable-star overlay follows `xOf`/`yOf` (the live `bT0..bL1`
bindings, not `LOGT_MIN`-class constants, which are only default seeds + overflow thresholds)
and is clipped + living-mode-only; verified rendering cleanly at m=300. No JS errors across the
Playwright sweep (m=1/3/7/120/300, living + WR + WD views).

---

## Chunk B — endgame quick-wins (items 7, 8, 9) · cheap & safe

### Item 7 — WR SED caption says "white dwarf" (bug)
`sed.js` `renderCaption()` has an `if (endgameMode)` branch (`sed.js:799`) that writes
the WD caption ("…contracts into a degenerate white dwarf…") for **both** endgames —
it never checks `endgameWR` (which *is* tracked, `sed.js:225,252`). The draw path
already correctly suppresses the coronal band for WR (`sed.js:304–308`); only the
caption text is wrong.

**Fix:** branch the caption on `endgameWR`. Write an honest WR caption: a stripped
hot core (peaks far-UV / soft-X-ray), **wind not dynamo** (no coronal band — wind
free–free radio is the un-built SED Chunk 2), and the un-modeled next step is
**core-collapse**, not a white dwarf. Keep it length-matched to the other branches
(the panel guards against caption-length-driven resize — `sed.js:787–793`).

### Item 8 — Lane–Emden description for WR (a question — here is the answer)
In `wr-mode` the body has class `wr-mode` (not `wd-mode`), so CSS shows the **generic**
`.lane-intro` and hides the WD-specific `.lane-wd-hint` (`styles.css:557–559` only
target `wd-mode`). The generic intro reads: *"A teaching idealization for building
intuition, **not** the real interior of the star above."*

**Assessment: the generic intro is honest and adequate for a WR.** A Wolf–Rayet is a
radiation-pressure-dominated, vigorously mass-losing star with an extended optically-
thick wind — emphatically **not** a single polytrope (unlike a WD's degenerate core,
which genuinely *is* one — the reason the WD path earned its `.lane-wd-hint`). The
generic disclaimer already says the panel is not the real interior, which is exactly
right. **No bug, no required change.**

*Optional polish (not required):* a `.lane-wr-hint` could note "a WR has a
convective He/C-burning core wrapped in a radiative, wind-shrouded envelope — no
single index `n` captures it, so read this panel as pure teaching here." Defer unless
the user wants it; it's additive, not a fix.

### Item 9 — make "Back to the living star" a yellow button (polish)
`.gateway-btn` is the big accent/yellow button (`styles.css:471–479`); `.endgame-back`
is a subtle transparent bordered button in the endgame-bar top row (`styles.css:503–508`).
User wants consistency.

**Fix:** restyle `.endgame-back` to the accent (yellow) treatment.
**Decision to make:** keep it compact-in-bar (yellow text/border or a small filled
accent button beside the title) vs make it a full-width `gateway-btn`-style bar. User
said "yellow button," so accent **background** is the safe read; size is a judgment
call — recommend a compact filled-accent button so the bar layout (title + back on one
row) survives. Confirm against a screenshot.

### Files
- `frontend/src/sed.js` (caption branch), `frontend/styles.css` (`.endgame-back`),
  optionally `frontend/index.html` + `styles.css` for a `.lane-wr-hint` if the user
  opts into the #8 polish.

### Verification
Playwright: WR endgame at a WR-forming mass — confirm the SED caption no longer says
"white dwarf" and reads as a WR; confirm the back button is yellow in both WD and WR
modes. No app-behaviour repro needed (pure text/CSS).

### Consult
None needed — small, safe, self-contained.

### Status — ✅ BUILT (2026-06-29)
Two files changed (`frontend/src/sed.js`, `frontend/styles.css`); item 8 confirmed
**no-fix**.

- **Item 7 (bug):** added an `if (endgameWR)` branch **before** the `endgameMode` (WD)
  branch in `sed.js renderCaption()` — the two are now distinct objects with distinct
  captions, so WR no longer inherits the WD text via the shared `endgameMode` gate. WR
  caption: *"…This bared hot core blows a dense wind, not a dynamo — so no coronal band
  (its free–free radio isn't drawn); the un-modeled next step is core-collapse, not a
  white dwarf…"* The phrase "white dwarf" survives **only as a negation** that corrects
  the exact misconception the user flagged (the WD gateway is one mass-drag away in the
  same UI, so the explicit contrast is an active teaching beat, not evasion — advisor-
  endorsed). Honest content: stripped hot core (peaks far-UV/EUV via the live `peakTxt`),
  wind-not-dynamo → no coronal band, free–free radio "isn't drawn" (the un-built SED Chunk
  2), next step = core-collapse. The WD caption is untouched.
- **Item 9 (polish):** restyled `.endgame-back` to a **compact filled-accent (yellow)**
  button — mirrors `.gateway-btn`'s treatment (`color: var(--bg)`; `background: var(--accent)`;
  `font-weight: 600`; hover `brightness(1.08)`; `:focus-visible` outline) but stays compact
  (no `width:100%`) so the bar's title-+-back single row survives.
- **Item 8 (question, no change):** confirmed in-app — WR mode shows the **generic** Lane–Emden
  intro ("a teaching idealization… not the real interior"), WD mode shows the WD-specific
  "genuinely a polytrope" hint. The generic intro is honest and adequate for a WR (it's not a
  single polytrope; the WD's degenerate core genuinely is). The optional `.lane-wr-hint` polish
  is **available but deferred** unless the user opts in — additive, not a fix.

**Verification (Playwright, the regression gate):** drove the real UI — WR endgame at m=120,
WD endgame at m=1. Asserted the WR caption reads as a WR (no "contracts into a white dwarf"),
the WD caption is unchanged, and `#endgame-back`'s computed background is the accent yellow
(`rgb(255,210,127)`) in **both** modes. Zero page errors; full-page screenshots both modes. One
mass per path suffices (unlike Chunk A): the WR caption is fixed text (only Teff varies) and the
button is mode-CSS — both mass-independent.

---

## Chunk C — layout: split the readout panel + stop the jitter (items 1, 4)

These two are **coupled**: splitting the readout out of Controls changes the Controls
panel, which is the main jitter offender, so do them together.

### Item 1 — State readout as its own panel
Today `controls-panel` (`index.html:103–190`) holds the endgame bar, the three
sliders, the gateway, **then** `<h2>State readout</h2>` + `#readout` + `#status`.

**Approach:** move the `State readout` heading, `#readout`, and `#status` into a new
`<section class="panel readout-panel" data-panel-id="readout">`. The JS references
those by **id** (`els.readout`, `els.status`), so moving the DOM does not break wiring.
`layout.js` injects a drag grip into each panel's `<h2>` and persists order — a new
`data-panel-id` is handled gracefully: `restore()` (`layout.js:204–210`) appends any
panel **not** in the saved order.

**Caveat to record (acceptable):** existing users with a saved layout get the new
`readout` panel **appended last** (after `lane`), not in its authored position, until
they click **Reset layout**. New users / anyone who resets see the authored order. This
is the same trade the project already accepts for added panels — mention it, don't
engineer around it.

### Item 4 — fixed panel size (scope it deliberately)
User: "panels should have fixed size, equal to the maximum size of content they could
represent." Taken literally this is in **tension** with the endgame bar: reserving the
full endgame-bar height in live mode wastes a large vertical band on the most-used view,
and the flex-wrap container means **any** panel's height change re-flows its row (you
can't fully eliminate relayout).

**Recommended scope (a decision to confirm with the user):**
- **Reserve slots for the incremental jitter** — the things that flip on/off *while you
  scrub within one mode*: the gateway button block (`#gateway`), the resnap note
  (`#endgame-resnap-note`), the endgame age caption, the SED rotation note, per-regime
  captions. Give these fixed reserved heights (the project already does this for several
  captions via `min-height`, e.g. `styles.css:148,200,517`) so showing/hiding them does
  **not** resize the panel.
- **Treat entering/leaving an endgame as a deliberate mode transition** where a one-time
  relayout is acceptable (the whole dashboard intentionally changes character — endgame
  bar appears, age label swaps, etc.). Don't reserve the endgame bar's full height in
  live mode.
- Splitting the readout (#1) already removes the biggest live-mode jitter source from
  Controls (the 14-row readout reflowing), so #1 does a lot of #4's work for free.

**Decision to make:** confirm "reserve incremental jitter, accept mode-transition
relayout" vs the literal "reserve max height everywhere." Recommend the former; surface
it because the user's wording leans toward the latter.

### Files
- `frontend/index.html` (new panel section; move readout markup),
- `frontend/styles.css` (reserved `min-height` slots; any `.readout-panel` styling),
- possibly `frontend/src/main.js` (only if the readout/status need any new wiring —
  expected **none**, since they're id-referenced; verify).

### Verification
Playwright: confirm the readout renders in its own draggable panel, drag/reset still
work, and that scrubbing age within live mode (and within an endgame) no longer jitters
panel heights. Check a fresh profile (no saved layout) **and** a profile with a saved
layout (new panel appended last).

### Consult
**Consult on the reserve-vs-waste decision** (the #4 scope) before building — it's a
genuine product trade-off the user gestured at.

---

## Chunk D — gateway auto-appears on mass/[Fe/H] change at end-of-life (item 3)

### Status: investigate-then-fix (root cause NOT pinned by reading)
Report: at end-of-life (gateway showing, e.g. m=40 SN note), changing mass to 50
**should** auto-show the new star's "Continue: Wolf–Rayet" (or WD) button without
nudging the age slider — currently it doesn't.

From the code the path **should** already work: `refreshTrack` ends with
`await refresh(); updateLiveGateway()` (`main.js:1382–1383`); `updateLiveGateway`
calls `maybeFetchEndgame()` + `updateGateway()` (`main.js:1123–1127`); and after a
mass raise at end-of-life, `ageFraction` re-clamps to 1.0 (`main.js:1371–1373`, since
the preserved absolute `ageValue` exceeds the new, shorter `ageMax`), so
`updateGateway`'s `ageFraction >= GATE_SHOW` gate (`main.js:1064`) should pass. Because
inspection can't find the break, **two live suspects** remain:

- **(a) Latency, not logic.** The ~1 MB `/endgame` fetch is fire-and-forget
  (`fetchEndgamePreview` / `maybeFetchEndgame`). The button may appear **seconds late**;
  nudging the age slider just retriggers `updateLiveGateway` after the fetch is warm, so
  it *looks* like the nudge is required. → a *perception* bug.
- **(b) A token/guard early-return.** `endgameToken` is shared by
  `fetchEndgamePreview` and `maybeFetchEndgame`; one drops the other's response. A
  stale-token drop, or `endgameKey === egKey()` mismatch (`main.js:1063`), could leave
  `updateGateway` with no data on the settled star. → a *logic* bug.

### Repro that discriminates in one shot
At end-of-life, change mass, and `console.log` inside `updateGateway`:
`ageFraction`, `endgame?.type`, and `endgameKey === egKey()`. Watch whether the button
appears **late** (→ latency, suspect a) or **never** (→ logic, suspect b).

- If **latency:** show an immediate "computing endgame…" affordance in the gateway slot
  (the slot is reserved by Chunk C anyway), or prefetch more eagerly so the warm data is
  present when the track settles. Do **not** make `/endgame` blocking.
- If **logic:** fix the token/key guard so the settled star's `updateGateway` always
  runs against matching data.

### Files
`frontend/src/main.js` (the `fetchEndgamePreview` / `maybeFetchEndgame` /
`updateLiveGateway` / `updateGateway` cluster, `main.js:1062–1127`,`1334–1384`).

### Verification
App running: at end-of-life, change mass across endgame-type boundaries
(WD↔SN↔WR) and confirm the correct gateway button/note swaps in **without** touching
the age slider, promptly.

### Consult
Optional — consult only if the repro reveals the fix touches the token/latest-wins
machinery (that code is subtle and load-bearing).

---

## Chunk E — age-slider remap so every phase has visible travel (item 2) · meatiest, do last

### Root cause (confirmed) + the open question (empirical)
The age slider is **linear in age** (`age = ageMin + frac*(ageMax-ageMin)`). A star
spends ~90% of its life on the main sequence barely changing, so most of the slider is
a near-flat plateau — "age rises, nothing else changes." This is the same fact the
`GATE_SHOW` comment already records: the post-RGB drama is crammed into the last ~2% of
the slider (`main.js:245–255`).

**Not pinned by reading:** *why it's worse for more massive stars.* Don't reason it out
— **measure it.** Fetch `/track?mass=1.5` and `/track?mass=5` (and ~1.06, the threshold
the user named) and look at how `age_yr` distributes across phases/EEPs. That settles
the mechanism and chooses the remap.

### Approach — make slider travel track *evolution*, not *years* (a design decision)
This is the §6 philosophy ("interpolate on EEP, not age") applied to the slider's
**feel** — the composition panel already uses an **EEP x-axis** for exactly this
reason, so there's in-repo precedent. Candidate remaps (pick after measuring):

- **EEP-proportional travel** — slider position maps to EEP, so equal drag = equal
  evolutionary progress. Most aligned with the project's spine.
- **Piecewise-uniform per phase** — give each phase (MS/SGB/RGB/CHeB/EAGB) a fair band
  of the slider (like the WD endgame's 3-zone band map, `main.js:266–295`).
- **Log-age** — cheap, helps, but still compresses the interesting end less precisely
  than EEP.

**Decision to surface:** *any* remap makes the slider **non-linear in age** — equal
travel no longer means equal Gyr. That changes the age *landmark tick* spacing
(`rebuildAgeTicks`, `main.js:701–732` — currently `pos = (age-ageMin)/span`, which would
have to become the new mapping) and the snap targets. The **age readout/number box must
stay honest** (show true Gyr) even as the slider becomes non-linear — keep `ageValue`
the source of truth and only change the *position↔age* mapping. Verify the existing
off-by-one-at-razor-sharp-phase fix (`main.js:1488–1503`) still holds under the new map.

### Files
`frontend/src/main.js` (the slider↔age mapping in the `els.age` `input` handler,
`refresh`, `refreshTrack`'s `ageFraction` recompute, and `rebuildAgeTicks` — all must
use the *same* mapping or the marker jumps off its landmark, the invariant flagged at
`main.js:696–700`).

### Verification
App running: for 1.06 / 1.5 / 5 / 20 M☉, drag the age slider end-to-end and confirm the
star visibly evolves across the *whole* travel (no long dead plateau), landmarks still
snap onto their phases, and the age readout shows honest Gyr. Playwright screenshots at
several positions per mass.

### Consult
**Own advisor consult when built** — the remap choice (EEP vs piecewise vs log) and the
tick/snap/readout consequences are a real design decision, not a mechanical fix.

---

## Cross-chunk notes

- **Don't implement in the planning session.** Each chunk is a separate session; A and B
  are independent and safe to do first/quickly; C precedes D (C reserves the gateway slot
  D may use); E is independent but best last.
- **No backend changes** are required for any chunk (all frontend: `hr.js`, `sed.js`,
  `main.js`, `index.html`, `styles.css`). #2 and #3 *read* existing endpoints
  (`/track`, `/endgame`) but add no routes.
- **Honesty rule still applies** (`STAR_SIM_SPEC.md` §7): the WR SED caption (#7) and any
  optional Lane–Emden WR hint (#8) must label what the data backs — wind not dynamo, not
  the real interior.
- Update this doc (not a second list) when scope changes; keep the ROADMAP row a one-line
  hook.
