---
name: star-sim-visual-performance
description: "The 2026-09-05/06 visuals/performance passes: the seven measured fixes, three.js vendored, the star's adaptive pixel ratio, and the reserved-floor raise (V1b) with its two measurement traps — the missing bottom padding and the 481px binding width"
metadata:
  type: project
---

The first *measured* performance pass (plan + remaining work:
`docs/plans/visual-performance.md`; shipped row: `SHIPPED.md` §7). Everything below was
taken through the real served app with a Playwright harness kept in
`M:\claud_projects\temp\star-sim-perf\` (`measure.mjs` · `profile_scrub.mjs` · `shots.mjs`
· `time_startup.py`; `node_modules` is a junction to the older `star-sim-pw` install).
**Reuse the harness, don't rebuild it** — and read its two GL backends correctly:
`--use-angle=swiftshader` is software GL (a strict stress signal for before/after ratios),
`d3d11` is the real GPU (an RTX 5090 here — it shows main-thread problems only).

**What was wrong, and why nobody saw it:**
- **`star.js resize()` re-created the WebGL drawing buffer every frame at DPR ≥ 1.5** — it
  compared `canvas.width` (backing px) to `clientWidth` (CSS px), equal only at DPR 1. The
  dev box is DPR 1 and every screenshot pass ran at DPR 1, so the defect was invisible
  here and present on every HiDPI laptop. Symptom under SwiftShader at DPR 2: a
  full-frame giant at 0.6 fps. Fix: compare against `Math.floor(css × renderer.getPixelRatio())`.
- **The age scrub spent 60–80 % of its main-thread time in `planckToXYZ`** — the HR track
  asks `teffToCSS` for each of ~800 segments per slider event, and each call integrated
  Planck×CMF over 81 wavelength steps. A track's Teffs repeat *exactly* scrub to scrub, so an
  **exact-key** memo (bounded Map, cleared when full) hits ~100 % and is byte-identical; a
  quantized key would have shifted colours by a unit and broken the screenshot regression.
  Scrub cost: 9.9 → 1.7 ms/event. The 3D star, SED, seismo and readout were never the cost.
- **First paint waited on seven serial probes** (`/health`, five `*_status`, the `/photometry`
  Sun probe) before fetching the track; the photometry probe loads the 98 MB spectrum cube,
  11 s cold. Now the probes run concurrently and the track does not wait; `settleProbes()`
  re-runs `refresh()` once they land so the gated controls appear (all readers of the
  `*HasGrid` flags are the `update*Control()` gates, so nothing else needed to know).
- **Cold-disk first load was 155 s** (ten MIST `.npz` caches, 450 MB; warm 0.2 s) — a disk
  fact, not a code one. The API now pre-warms in a daemon thread from a FastAPI lifespan
  (`STAR_SIM_NO_PREWARM=1` opts out); `TestClient(app)` without a context manager never
  runs the lifespan, so tests and CI stay data-free and thread-free. `_ensure_loaded` got a
  lock so a request arriving mid-warm waits instead of parsing twice.
- Smaller: HR `drawTrack` strokes runs of same-colour/same-side segments (one path, not
  ~800 — and the α 0.3 future track lost the double-blended bead at every vertex);
  `comp.js` bulk bands are `Path2D`s cached per (track, W, H); the render loop parks via
  `IntersectionObserver` while the star canvas is off screen; the HR "Teff → (hot left)"
  title no longer overlaps the 10kK tick (3 px, every width).

**Verified fine, don't re-propose:** real-GPU frame time is vsync in every state; the phone
star canvas; the supergiant's look; class bands / iso-radius lines at 390 px.

**Second batch, shipped 2026-09-05 (P2 then P1 — that order on purpose: P2 cannot move a
pixel, so it validates the screenshot baseline before P1 might change one).**

- **P2, three.js vendored.** The importmap pointed at unpkg — the one asset in the app
  served off the network. The plan predicted “a black 3D panel with no actionable error”;
  **measured with all external requests blocked, the whole app dies**: `main.js` statically
  imports `star.js`, which imports `three`, so one dead module takes down the entire graph
  — the `loading` skeleton never clears and `/track` is never fetched. After: 0 external
  requests, 0 console errors. The generalisable bit is the *method*: the before/after ran
  against one server in one script, with Playwright rewriting the importmap back to the CDN
  URL for the before pass (`offline.mjs`) — no stashing, no second checkout. Download
  integrity was verified rather than assumed (bytes, `REVISION`, no sub-imports, node
  imports it) because a truncated file reproduces exactly the symptom being removed.
- **P1, the star drops resolution instead of frames.** SwiftShader, DPR 2, 15 M☉ giant:
  **100 ms/frame → 33.4 ms**, backing store 840² → 420² in two steps. On the real GPU at
  the same DPR and mass it **never fires** — 24 s of vsync, backing store unmoved.
  **The whole difficulty was the negative case**, and it is the transferable lesson: the
  positive case (a slow machine adapting) is exactly what a runtime pass shows, and the
  expensive mistake (adapting when nothing is wrong — a silent visual regression on
  hardware that was fine) is exactly what it *cannot* show. So the decision came out of
  the render loop as pure `framebudget.js` and got unit-tested against a cold start, a GC
  pause and a backgrounded tab. That is also where the plan's own recipe was wrong twice:
  a **mean** would adapt on one 3000 ms frame from a returning background tab, and it had
  **no warm-up**, so a fast GPU would adapt during shader compile — violating the
  acceptance line the same recipe wrote. Read a recipe's acceptance criterion as the
  spec and the recipe's mechanism as a draft.
- **Two harness facts worth keeping.** `shots.mjs` runs on **d3d11 (real GPU)**, so it
  never trips the adaptation — check that before re-pointing it at software GL and reading
  softer granulation as a regression. And `measure.mjs` samples 3 s per phase while the
  render loop runs continuously across the whole page life, which is why P1's window is
  two × 30 frames rather than the planned 60: 60-frame windows would outlast a phase and
  the fix would read as dead code. `adapt.mjs <dpr> <gl> [mass]` joined the harness — it
  prints the star canvas **backing store** per window, the direct observable for this.

- **V1, the reserved blank — and the rule that reserved space must be LABELLED, not just
  held.** The ~180 px void on the Sun was *inside* the rotation section (316 px reserved,
  134 used), not panel slack, so the slot was fixable even though the panel's height is
  frozen. It now carries an "Appears for…" line whose `min-height` is sized to the
  **tightest state that shows it**, so the note absorbs slack it can never overflow. The
  transferable part: a fixed reservation and a request for less whitespace **cannot both be
  satisfied** — the reservation must cover the tallest reachable state, so the only real
  levers are labelling the space or making the tall state shorter. A plan row that promises
  a shrink *and* keeps the floor is asking for something impossible; read the acceptance
  criterion against the constraint before implementing it.
- **The floors were undersized, and `jumpcheck.mjs` is why we know it matters.** Both
  `.rot-control` (316) and `.controls-panel` (992/1060) missed reachable states, and the
  overflow **really did move 5–6 neighbouring panels** — 60/137/145 px at the uncertain-fate
  hedge, 33/21 px on ticking the rotating track at 1.35 M☉. A floor being numerically short
  is not the finding; a *neighbour moving* is, and those are different questions. Always ask
  the second one before changing a floor: a panel that is not the tallest in its flex row can
  overflow and shift nothing.

## V1b — the floors raised (2026-09-06)

Shipped: `.rot-control` 316 → **376** base + a new **412** phone rule; `.controls-panel`
992/1060 → **1214/1308**; `#incl-gate-note` 100/64 → **160** with the phone override deleted.
Acceptance met at **1440 / 512 / 481 / 390** on *two* scripts. Four things worth carrying to
any future reservation work:

- **A panel-level jump check is not enough — `innerjump.mjs` exists because of this.**
  `jumpcheck.mjs` snapshots `main > section`, so it cannot see a panel's own children move.
  At 1440 the Controls floor absorbed the rotation section's growth: no neighbour moved, the
  check said clean, and the age slider plus the entire endgame gateway still slid **36 px**
  down under the cursor (53 at 512, 89 at 390). The plan had recorded that width as
  "0 (absorbed)". **Two mechanisms, two checks:** the panel floor stops neighbours moving, the
  per-element floor stops siblings moving, and each needs its own probe.
- **The two reservations ADD.** Once a rotation floor covers its own tallest state the section
  renders at exactly that floor in every state, so the panel requirement is
  `max(content outside it) + that floor + 19` — exact, not an upper bound. Reading a raw
  observed panel height instead (which is what produced the row's "~140 px" estimate) under-
  counts it; the real cost was **+222 px desktop / +248 px phone** of permanent slack.
- **Trap 1: the missing bottom padding (+19).** A "content height" measured from the panel's
  box top to its lowest child's bottom carries the *top* padding but not the bottom one, while
  `min-height` is a border-box height covering both. Omitting it left the phone jumping 13 px
  after the raise. Any floor derived from a `panelUsed`-style number owes this.
- **Trap 2: 481 px, not 512, is the binding width** for a rule whose phone breakpoint is 480.
  Those 31 px cost the hedge caption another 19 px (813 vs 794). Every earlier floor in this
  file was sized at 512, so each was short over its own narrowest 32 px — and the acceptance
  run passed regardless, because it never visited them. **Size a responsive floor at the
  narrowest member of its regime, and put that width in the checker.** 481 is now in
  `jumpcheck.mjs`.

The uncertain-fate hedge caption — the single dominant term, 215/253 px — was **not**
shortened; that was the row's recorded third option and it was declined, because it is the
3rd honesty gate ([[star-sim-uncertain-fate-band]]). The floors move to fit the caption, never
the reverse. New harness scripts: `innerjump.mjs` · `notefit.mjs` · `edge481.mjs` ·
`phonegap.mjs` · `panelshot2.mjs` (the last shoots the three states that *vary*, since
`panelshot.mjs` only ever shot the Sun and so could not show a change in the states that
drove it).

**Still open (in the plan, payoff order):** static layers for `sed.js` / the comp cno view
(P4), cold-disk first load (P5), row-height pairing in the two-column layout (V2 — worth
more now that Controls is 222 px taller).
