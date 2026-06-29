---
name: star-sim-ux-nine-fixes
description: Third user-reported UX-fix batch (nine items), ALL FIVE chunks A–E BUILT. A (HR auto-fit framing), B (endgame quick-wins), C (readout panel split + gateway greyed-button), D (gateway auto-appear = latency, not logic → "computing the star's fate…" placeholder + resnap note moved below sliders + the type-only `/endgame?meta=1` fast-path that structurally decouples the button from the 1 MB), E (age-slider remap = linear-in-EEP, marker PICKED from the track by row, no /state fetch — kills the dead MS plateau, mass-invariant 58.5% post-MS travel). Plan docs/plans/polished-cinder-frame.md.
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
- **Resnap note (`#endgame-resnap-note`) — deferred in C, then MOVED in the D session.** It has
  **no persistent content to fill a reserve**, so reserving = the empty space the user rejected;
  it appears only on a *failed* re-snap inside an endgame (deliberate exploratory drag). The clean
  close-out shipped: moved the `<p>` out of `#endgame-bar` (top of Controls) to **after
  `#endgame-age-caption`, before the gateway** — below the sliders, so it grows the panel
  **downward** instead of shoving the sliders under the cursor. CSS class is unscoped (pure markup
  move); `setWDResnapNote` drives `hidden`; `exitEndgame` clears it on return to live. Verified:
  note fires with right text, top sits below the age slider's bottom.

**Gotcha for future gateway work:** the gateway block no longer toggles `hidden` in live mode
(only enter/exitEndgame do); `updateGateway` returns early unless `mode==="live"` and always sets
`els.gateway.hidden=false` there. The WD/WR buttons carry `disabled` (toggled by `atEnd`), not
visibility — visibility is `hidden` per fate type. Verified Playwright: Sun greyed→lit, m=25 SN
note at genuine mid-MS (ageFrac 0.30), m=120 WR disabled at genuine mid-MS, both layout profiles,
zero page errors.

**Chunk D — gateway auto-appear (item 3) — ✅ BUILT 2026-06-29**, three files
(`frontend/index.html`, `frontend/src/main.js`, `frontend/styles.css`). The re-repro
(warned about in C) **disproved the "never appears" logic bug**: post-C the always-present
button + `updateGateway`-on-every-`refreshTrack` mean a mass change at end-of-life **does**
auto-show the new fate with **no age nudge** (measured: WR button enabled at **+628 ms**,
m=40 SN → m=50 WR, age untouched). So it was **latency/perception, not logic** (advisor
predicted this exactly). Causes: `/endgame` fetch **serialized after** `/track`, **+** a
**double-fetch** (`fetchEndgamePreview` tok A, then `maybeFetchEndgame` tok B invalidates A —
two ~1 MB fetches). Symptom: `refreshTrack` clears the gateway children then waits ½–2 s on
that fetch → **blank reserved slot** reads as "nothing happened"; nudging age just re-ran
`updateGateway` against the warm fetch (why it *looked* required).

Fix is **two parts** (a second advisor consult sharpened both):
- **A muted italic "Computing the star's fate…" placeholder** (`#gateway-loading`) fills the
  slot during the fetch. Gated on a real in-flight flag: `updateGateway` does
  `els.gatewayLoading.hidden = !(endgameLoading && !eg)` (shown only while a fetch is in flight
  AND no fate resolved). `endgameLoading` set true at the `refreshTrack` clear + in
  `fetchEndgamePreview`/`maybeFetchEndgame`; cleared on settle **by the latest token only**, on
  success OR failure. **First cut gated on `!!eg` — advisor caught it as DEAD CODE**: `eg` stays
  null on a fetch failure so `!!eg` re-shows the placeholder forever (stuck spinner). Flag fixes
  it; verified by aborting `/endgame` in Playwright (placeholder clears, doesn't stick).
- **De-duped the double-fetch — shortens the REAL gap** (not just masks it). `refreshTrack` tail
  `updateLiveGateway()` → `updateGateway()`. The old tail fired a 2nd `/endgame`
  (`maybeFetchEndgame` tok B) that, sharing `endgameToken`, **invalidated the already-landed
  (+406 ms) `fetchEndgamePreview` (tok A) response** → button waited for the later of two
  competing ~1 MB fetches. Safe: touches **no token internals** (age-scrub path still calls
  `maybeFetchEndgame`; `fetchEndgamePreview` is the sole repopulator on a track change). Button
  now **+474 ms** (was +628), single fetch.
- **The backend/scope root — initially deferred, then DONE 2026-06-29 (user opted in):** a type-only
  **`/endgame?meta=1`** that serves the same `EndgameResult` minus its `states` (~120–140 B vs ~1 MB),
  plus an explicit `has_states` boolean (mirrors the frontend's `states.length` guard). Still §3-clean
  (meta fields are the routing metadata the dataclass already exposes; route still goes through
  `PROVIDER.endgame()`). Frontend = a **purely additive fast-path**: a new `fetchEndgameMeta()` with its
  OWN `endgameMetaToken`/`endgameMetaKey`/`endgameMeta` cache fires alongside the untouched
  `fetchEndgamePreview()` (full); `updateGateway` derives the button's fate from full `endgame` **else
  falls back to `endgameMeta`**. The full fetch **stays eager** (NOT lazy) because it's load-bearing —
  it pre-warms the HR preview + the "slam-to-the-end" enter cache (`main.js:258`); meta just makes the
  button *appear* without waiting on the 1 MB (the user's "don't ship 1 MB" premise is only half-met:
  the 1 MB still loads for preview/enter, it just no longer gates the *button*; bandwidth is unchanged).
- **Enable-gating fix (advisor-caught — would have shipped a DEAD BUTTON).** Pre-meta, `isWd`/`isWr`
  needed the full `eg`, so `disabled = !atEnd` was safe (at-end ⟹ full loaded). With meta the button
  can SHOW from `egMeta` while `endgame` is null, so enable now gates on the full too:
  **`disabled = !atEnd || !eg`**. Without it, a click in the meta→full gap is a silent no-op
  (`enterWD/WR` read `endgame.states`) — reachable on the NORMAL path (change mass while pinned at end;
  **exit→re-enter** the reversible gateway restarts the full fetch from null while `atEnd` holds), not
  just on full-fetch failure. Locked by Playwright (full aborted → shown-but-`disabled`, forced click
  no-ops; exit→re-enter re-enables then re-enters).
- **Honest magnitude — STRUCTURAL win, not a big number.** The button is now *decoupled* from the 1 MB,
  guaranteed, regardless of full-fetch warmth. Measured warm-localhost saving on the `/endgame` hop is
  **modest (~15–30 ms median**; WD full 103–136 vs meta 98–112 ms fetch+parse) — 1 MB transfers+parses
  fast on localhost and warm provider compute (~37 ms) is identical either way. Larger when the full is
  cold/uncached/contended/slow-link or as state-count grows; **cold first call unchanged** (compute-bound
  — Chunk D placeholder covers it; the two compose). The earlier "~160 vs ~474 ms / 66%" was a
  **cross-session artifact** (474 ms baseline was cold/double-fetched) — corrected. Exactly 1 meta + 1
  full per change (meta-first, no double-fetch); all 3 abort combos no-stuck-spinner;
  `test_api_endgame_meta_is_type_only` (138 pytest).

**Gotcha for future gateway work:** the placeholder is now gated on `endgameLoading && !known` where
`known = !!fType` (a fate resolved from EITHER the full `endgame` OR the `endgameMeta` cache). The
**meta fetch must NOT touch `endgameLoading`** — the full fetch (`fetchEndgamePreview`) is its sole
owner; meta clearing it on *failure* would blank the slot before the full fetch lands (the fate is
genuinely still unknown then). The two caches/tokens are SEPARATE on purpose — never thread meta
through `endgameToken`/`endgameKey`/`fetchEndgamePreview`/`maybeFetchEndgame` (the Chunk D machinery).
`refreshTrack`'s tail calls `updateGateway` (not `updateLiveGateway`) on purpose — don't "restore" it
or the double-fetch + discarded-response regression returns. The full fetch stays EAGER (don't make it
lazy "to save the 1 MB") — it pre-warms the slam-to-the-end enter cache. And the WD/WR button's ENABLE
gates on the full `eg` (`disabled = !atEnd || !eg`), NOT on `atEnd` alone — `enterWD/WR` read
`endgame.states`, so enabling on `egMeta` alone makes a click in the meta→full gap a silent dead no-op
(the exit→re-enter path restarts the full fetch from null while `atEnd` holds — the reachable normal case).

**Chunk E — age-slider remap (item 2) — ✅ BUILT 2026-06-29**, frontend-only
(`frontend/src/main.js`). The slider was **linear in age**, so ~85–90% of it was a dead MS
plateau ("age rises, nothing changes"). Now it is **linear in EEP**, and the living marker is
**picked straight from the already-fetched `/track` by row** — *no `/state` fetch at all* on an
age scrub (like the WD/WR scrubs pick `states[i]`). Advisor reframed the design as **two
decisions**, both settled by **measuring first** (per the plan):

- **The MIST track is one row per integer EEP** (step exactly 1.0, eep 202→807) with a
  **mass-invariant** phase split — *always* 606 rows, MS 41.6 / RGB 24.9 / CHeB 16.8 / EAGB 16.7%
  at every mass. So EEP-index travel gives post-MS a constant **58.5%** of the slider at every
  mass (no per-mass tuning). Linear-age gives post-MS only 9–18%, and *which* phase vanishes varies
  with mass (CHeB/EAGB <1% low-mass; RGB collapses to 0.25–0.8% — invisible — for 5–20 M☉).
- **Decision 1 — marker MUST come from the EEP coordinate, not an age round-trip.** Flat-age bands
  are real and large (the 1 M☉ CHeB **blue loop** = 48 EEP rows over **~4,800 yr**), so an EEP slider
  that still fetched `/state?age=` would be **degenerate** there → a new dead band. This kills
  age-fetch, log-age, and piecewise-*in-age*. Marker = `currentTrack[round(pos·(N−1))]` (nearest row).
- **Decision 2 — linear-in-EEP, not piecewise.** `comp.js` positions its marker `xOf(eep)`, so a
  linear-in-EEP age fraction **equals the comp-marker x-fraction exactly** → age thumb & comp marker
  move in lockstep. Plus mass-invariant + §6-canonical ("interpolate on EEP, not age").
- **Pick-from-track, not a backend eep-fetch:** no Protocol change, fetch-free instant scrubs, and it
  *simplifies* — landmarks position by row index (`pos = i/(N−1)` in `criticalAges`/`rebuildAgeTicks`),
  `ageValue` (yr) is a **derived honest readout** of the picked row, and the **razor-sharp phase
  off-by-one is obsoleted** (rows addressed directly, no age→EEP round-trip). New helpers
  `trackRowFromPos` (pos→nearest row) + `posFromAge` (absolute-age→nearest-row position, the inverse).
  Four mapping sites all flow through them: `els.age` input (commit `ageValue` from the picked row),
  `refreshTrack` recompute + `els.age-num` typed path (both `posFromAge`), `rebuildAgeTicks`. `refresh()`
  is now sync + bails in endgame mode + paints via the new `paintState(s)` helper; `refreshTrack`'s catch
  surfaces a first-load `/track` failure itself (refresh no longer fetches). `/state` route **kept**
  (tests/other callers), just unused by the living marker.

**Gotcha for future age-slider / `refresh()` work:** the age scrub is now **fetch-free** — `refresh()`
picks `currentTrack[round(ageFraction·(N−1))]` and `paintState`s it; it does NOT call `/state`. `ageValue`
(yr) is the preserved DESIRED age (source of truth for the spring-back across a mass change) — **only an
explicit scrub or typed value commits it**; `refresh()` must NOT write `ageValue` (it derives the *display*
age from the picked row but leaves the variable alone, or the spring-back breaks). On a mass change the
thumb JUMPS (same absolute age sits at a different EEP fraction per mass — correct). The GATE_SHOW/GATE_FETCH
thresholds are position-space and their old "post-RGB crammed into the last ~2%" rationale is **obsolete**
under the EEP map (EAGB is now 0.833–1.0, so `atEnd ≥ 0.999` enables the gateway only at the true last row —
verified the gateway stays greyed through MS/RGB/EAGB-onset). The quiescent red-clump stretch in CHeB is
*physically* stationary (the star parks there) — NOT a dead slider, since EEP still advances and the
comp/HR marker still moves; don't "fix" it.

Chunk E verification = both advisor gates in the RUNNING app (Playwright, bundled Chromium): dead bands
animate (1.0/1.5 M☉ CHeB sweep Teff ~1300–1450 K / L×44–52; 5/20 M☉ RGB sweep Teff 9.2–12.2 kK; EEP strictly
advances), Sun on the §10 anchor under nearest-row (L=1.07/Teff=5835/4.63 Gyr — within 0.3%/0.6 K of the
exact 4.6 Gyr interp, so **no scalar interpolation needed**); zero page errors. No backend change → 138
pytest unaffected (the §10 anchor uses the untouched `state_at`).

Related: [[star-sim-wr-wd-endgame-plan]], [[star-sim-frontend-ux]], [[star-sim-composition-panel]].
