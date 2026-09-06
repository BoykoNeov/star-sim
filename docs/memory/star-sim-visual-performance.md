---
name: star-sim-visual-performance
description: "The 2026-09-05/06 visuals/performance passes: the seven measured fixes, three.js vendored, the star's adaptive pixel ratio, the reserved-floor raise (V1b) with its two measurement traps, and V2's height-paired panel order"
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

## V6 (2026-09-06) — the last two floors, and the rule for which mechanism to use

`.observer-panel` had **no floor at all**; `.structure-panel`'s 855 was short. Both were short
for the **same** reason, and it is the one to carry forward: *a floor is only as good as the
state space it was swept over, and each panel's state space is its own controls, not the star's.*
Sizing both with the Controls panel's trigger (6.5 M☉ at `[Fe/H]` −1.5) recorded the structure
panel as short by 9 px when it is short by **27** — its tallest text is the snapped-far note,
which needs the request off the partial MESA grid in **mass and metallicity at once** (0.1 M☉ at
`[Fe/H]` −1.5 → 882 px), a state a gateway-shaped mass list never visits. The observer panel's
two variable notes are driven by **its own three sliders** (distance, A_V, R_V), which a
mass × `[Fe/H]` sweep never touches at all.

Shipped: `.observer-panel` **675 / 715** (new), `.structure-panel` 855 → **890** (the 910 phone
floor already covered 882).

**`.observer-panel` re-measured 2026-09-06 → 707 / 728** (`temp/star-sim-perf/nir-observer-floor.mjs`)
after the near-IR work ([[star-sim-near-ir-cube]]) added a band-picker row (23 px) *and* lengthened
the readout's labels — the CMD plane is selectable now, so the widest strings are the 2MASS/Gaia
ones (M_Ks / (BP−RP)₀ / E(BP−RP)), not M_V / (B−V)₀ / E(B−V). **Both had to be re-swept: a new
control raises a floor twice over — the row it adds, and whatever it makes the existing text say.**
The tallest state still pairs the longest READOUT with the Johnson NOTE (the B-band zero-point
caveat is Johnson's alone and the note is empty in the other two planes) — a combination no single
screen shows, which is exactly why it is injected rather than swept for. The panel-order pairing is
unaffected: 707 sits in the same band 675 did, between the SED (830) and seismology (530).

- **Which mechanism a note gets — the rule was already written down** for `#isochrone-note` /
  `#population-note` and generalises: **a note that is LAST in its panel is absorbed by the
  panel floor and needs no reserve; one with siblings below it needs its own**, because its
  extra line shoves them. So `#observer-readout` 2.8em → **3.5em** (3 lines / 43 px, three dust
  sliders below it) and `#structure-caption` **4.35em** at every width (3 lines / 54 px at a
  433 px panel) — but `#observer-note` and `#structure-note` get nothing.
- **Fixing it at the element removes the variation instead of hiding it.** After the readout
  reserve the observer panel's *natural* height is constant at 670 px across all 105 swept
  states at 1024 — the floor is then a guarantee, not a patch.
- **Scope a shared class by id.** `#structure-caption` rather than `.lane-caption`, which the
  Lane–Emden and Roche captions also use and whose longest strings were not re-measured.
- **Trap 3: wider is not always shorter.** The dashboard packs **two** columns at both 1024 and
  1440, so 1440 gives the **widest** panel (688 px) and 1024 the narrower one (480). 481 (a
  433 px panel) is still the binding width and covers everything above it — 1024 was only where
  the symptom was visible, not a regime needing a third media rule.
- **Acceptance above the recipe.** The row proposed one `jumpcheck 1024` state pair, which a
  still-short floor can pass. Use V5's standard instead: **every swept state renders at exactly
  the floor** (`min === max` on the rendered height). Met at five widths on both panels, plus
  `jumpcheck` clean at all six.
- **`panelfloor.mjs`** (`ctlfloor.mjs` generalised to any panel) reports natural max **and min**
  — the min is what the floor costs in permanent blank — the **rendered** height, and **each
  child's own max over the whole sweep**, which is the number that decides "raise one element's
  reserve" vs "raise the panel".
- **Price, stated:** the structure raise costs **+35 px** of permanent blank at 1440 — on top of
  the 149 px the old floor already held there, so the big wide-width void is pre-existing. A
  third tier would recover ~140 px but is **not** a safe one-liner: **panel width is not
  monotonic in viewport width** (`flex: 1 1 460px; max-width: 700px` → two columns first fit at
  a 984 px viewport, so the panel is 700 px wide at 983 and **460 at 984**), and there is a
  second wrap cliff just above the binding width (a 480 px panel measures 742, a 464 px one
  841). Sizing at 481 covers both cliffs — which is why the two-tier rule holds. Left as-is.
- **Two limits recorded rather than papered over.** (1) The structure sweep sampled the age axis
  at **three points**, not against the bounded set of `phase` strings the caption embeds — a
  longer phase name is one wrapped line (18 px) against 8 px of margin, so **re-measure if a
  phase name changes**; the `capmax.mjs` move (inject the string set) is the fix if it matters.
  (2) A per-element reserve scoped to an **id** must sit ABOVE the phone rule and be named in its
  selector list: an id outside a media query outranks a class inside one in *both* directions, so
  a later raise of the phone value would silently stop applying while still reading as if it did.
- **Found, not fixed:** `/photometry_track?mass=0.1&feh=0.25` 422s on a real corner of MIST's
  non-rectangular domain — caught, locus cleared, retryable, panel height unaffected. An
  honesty-gate question, not a layout one.

## V2 — the panel order pairs by height (2026-09-06)

The last visual row. `main` is a flex-wrap grid, so a wrap row is as tall as its tallest
panel and every shorter panel in it leaves a hole until the next row starts.

- **The plan's first option was already in the file.** It proposed `align-items: flex-start`
  so panels stop stretching; that has been on `main` since the dashboard was built. Panels
  were already ragged-bottom, so the dead space was never *inside* a panel — it was
  **between rows**. Read the CSS before quoting a plan row's remedy.
- **Measured** (`rowgaps.mjs`, per row and per panel, through the served page): the authored
  order left **1453 px** dead at 1440 on a 5070 px page. The worst single pair was the 303 px
  state readout beside the 1024 px Controls panel: 721 px.
- **Every packing regime, both orders loaded natively** (2 columns to ~1590 px, 3 to ~2050,
  5 at 2560, 1 on a phone) — dead space and page height, old → shipped: 1280 1435→416 /
  5070→4267 · 1440 1453→434 / 5070→4267 · 1600 2015→**1438** / 3660→3300 · 1920 2243→1541 /
  3660→3300 · 2560 2275→2174 / 2824→**2297** · 390 0→0 / 8697 unchanged. **At the wide end
  read page height, not dead space:** at five panels per row the holes move between rows
  instead of closing, so 2560 shows a ~100 px dead-space win and a 527 px shorter page.
- **Shipped** a reordered `index.html` — a pure block move, since `layout.js` captures the
  DOM order as the default *before* applying a saved one, so anyone who has dragged panels
  keeps theirs. Pairs, by measured height: star 815 + HR 820 · composition 464 + spectrum
  487 · Controls 1024 + interior/MESA 890 · SED 830 + Lane–Emden 703 · observer 675 +
  seismology 530 · **readout last and alone** (the shortest panel wastes nothing by itself).
  **1453 → 434 px**, page 5070 → **4267 px**; the white-dwarf endgame 905 → **287 px**.
- **The better-packing order was measured and rejected in writing.** Sorting purely by height
  is *identical* at 1280/1440 and wins only at ≥ 1600 px (1136 vs 1541 at 1920, 1729 vs 2174
  at 2560) — and it puts the composition panel tenth, one of the spec's three core views. The
  price of refusing it is **width-dependent** (nothing at 1440, ~400 px at 1920, ~450 at 2560)
  and is stated as that range rather than as one number. The arithmetic sits in an
  `index.html` comment so it is not re-derived; **if you add a panel, pair it by height.**
- **The hidden panel a click away was measured; the other is labelled unmeasured.** With the
  habitable-zone history shown the shipped order still wins at every width (749 vs 1317 at
  1440), costing 315 px because it lands on the readout's otherwise-free last row. The Roche
  panel needs binary mode to appear, so its position says so in the markup — a comment full
  of measured numbers must not let an unmeasured line ride along as if it were one.
- **The measurement trap this row is really worth remembering for.** Reordering the live DOM
  and measuring 500 ms later is wrong at 3+ columns: the reorder changes each panel's WIDTH
  and canvas heights follow width through a `ResizeObserver`, so the boxes are still settling
  — it read 1282 px at 1600 where a native load reads 1438. **A round-trip catches it**:
  re-apply the order the page already has and it must reproduce its own native numbers.
  The trustworthy method is `rowgaps5.mjs` — intercept the *document* request and fulfil it
  with the old commit's `index.html` while the modules and API come from the live server
  (that commit touched nothing else under `frontend/`). A second uvicorn on the old commit is
  a dead end: the venv's editable install resolves `star_sim` to the working tree, so it
  would serve the *new* frontend.
- **V1b/V6 are what make one static order correct.** With every panel pinned to its reserved
  floor, Sun / 15 M☉ / 0.3 M☉ measure *identically* — the anti-jump work bought this for free.
- **The phone changes in sequence, not in packing.** 390 px is one column, 0 px dead before
  and after; the readout moves 7th → last, accepted because the pinned strip already carries
  mass, `[Fe/H]` and age.
- **V3 closed on the same run.** The parked-render-loop worry (a screenshot catching the frame
  before the `IntersectionObserver` restarts the loop) does not reproduce: 15 M☉ late returns
  a red-supergiant disk, not the previous star's frame. No `waitForTimeout` added.

New in the harness: `rowgaps{,2,3,4,5}.mjs` — `2` compares candidate orders, `3` sweeps four
star states (endgame included), `4` adds the round-trip check, **`5` is the one to trust.**

**Still open (in the plan, payoff order):** static layers for `sed.js` / the comp cno view
(P4) and cold-disk first load (P5) — both conditional, neither queued.

## Turning a physics error into pixels — the HR panel's measured scale (2026-09-06)

Reusable beyond the row that needed it (`science-hurdles.md` §1.1a, "is the 0.3-0.45 M☉
grid coarseness visible?"). The generic question is *"we know the model is X dex off — can
anyone see it?"*, and the conversion is panel geometry, so measure the panel, don't read
constants out of the source.

**The HR panel at a 1440 viewport is 654 × 320 CSS px** (`fitCanvas` returns CSS px, not
device px — `PAD` 30 / `PAD_L` 50), and its living frame is FIXED for anything that doesn't
overflow it (log Teff 3.4-4.7, log L -4..6). That gives a **17× asymmetry**:

| axis | span | px/dex |
|---|---|---|
| log Teff (x) | 1.3 dex over 574 px | **441.5** |
| log L (y) | 10 dex over 260 px | **26.0** |

So a tenth of a dex in Teff is 44 px and screams; the same error in L is 2.6 px and hides.
Any "is it visible" answer that quotes only Δlog L is answering the easy half.

**Confirm the frame is unexpanded through the runtime, not by reading `applyLivingBounds`:**
screenshot the canvas at several inputs and diff. If the frame auto-fit per input, the axis
furniture would move and the diff would cover the canvas; a diff confined to a ~40 × 40 px
box around the marker proves the mapping you just used. That check is 20 lines of Playwright
and it is the difference between a measured verdict and a plausible one.

**The other half of a "visible?" question is the control's own resolution.** The mass slider
is `step = 0.0005` of a 0..1 position spanning 0.1-300 M☉ logarithmically = **0.00174 dex per
step**, and the thumb is ~449 px wide, so one step is 0.22 px of thumb travel and a whole
0.05-M☉ grid bracket down at 0.3 M☉ is only ~9 px of drag. Compare the artefact against the
per-step motion, not against zero: an artefact smaller than one step's own movement cannot be
perceived as a discontinuity.

Harness: `M:\claud_projects\temp\star-sim-lowmass` (`sweep.py` = the per-step walk,
`measure2.py` = readout kinks + held-out offsets, `visual.py` = the screenshot diff).
