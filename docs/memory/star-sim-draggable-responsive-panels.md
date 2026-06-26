---
name: star-sim-draggable-responsive-panels
description: Frontend dashboard UX — draggable panels (reorder-in-flow sortable) + responsive canvases + edge auto-scroll; the fitCanvas-inline-width and innerHeight-vs-clientHeight gotchas; the density-pass follow-up (2-col readout, wider columns, per-element legend toggle) + why masonry was NOT built.
metadata:
  type: project
---

The frontend panels are a **draggable, responsive dashboard** (frontend-only; no
backend/API/spine touch — pytest unchanged at 137). User ask: make panels
**movable, auto-stack to screen width (phone → vertical, desktop → several
columns), never overlap when moved.**

**The model (advisor-confirmed):** the only thing that satisfies all three at
once is a **reorder-in-RESPONSIVE-FLOW sortable, NOT free-floating windows.** Flow
layout can never overlap; column count is a pure function of viewport width (CSS
flex-wrap) so "vertical on a phone" is free. Persisting absolute x/y would have to
be discarded + re-packed on every resize — which *is* a flow layout the long way.
So `main` went grid→**flex-wrap** (compact panels `flex:1 1 320px;max-width:384px`;
the 3 full-width bands keep a `.wide` 100%-basis row). New **`layout.js`** =
the sortable.

**`layout.js` shape:** a drag **grip (⠿)** injected into each panel's `<h2>` is the
ONLY handle (sliders/buttons/`?` glyphs stay interactive — a whole-panel handle
swallows them); **Pointer Events** (not flaky HTML5 DnD); placeholder holds the
slot while the panel floats `position:fixed`; **2-D nearest-center** drop; order
**persisted to localStorage** keyed by a new `data-panel-id` (restore applies saved
order then **appends any panel NOT in it** so a later phase's new panel never
vanishes; a header **Reset layout** button clears it).

**GOTCHA 1 — the canvases were the real work (the phone-breaker).** `fitCanvas`
sets `canvas.style.width` **inline**, which **overrides** the stylesheet
`width:100%` (those rules were DEAD) → CSS alone can't make the 720 px spectrum/SED
canvases responsive; on a phone they overflowed a ~360 px panel. Fix: each 2-D plot
module (`hr/comp/spectrum/sed/lane`) made `W/H` (+ sed's `plotW`) **`let` not
`const`** and gained a **`resize(w,h)`** that re-runs `fitCanvas` + redraws **from
retained state** (track/data/teff — no refetch); `main.js` drives them with a
**`ResizeObserver`** per canvas → `resize(min(maxW, availWidth), h)`, **skipping a
`.dragging` panel** (box locked mid-drag). The **3D star needed no JS** — `star.js`
already re-fits its WebGL renderer from `clientWidth/Height` every frame, so just a
responsive CSS box (`width:min(320px,100%);aspect-ratio:1`).

**GOTCHA 2 — `window.innerHeight` ≠ pointer `clientY` space (a REAL bug touch
verification caught).** Edge **auto-scroll** during a drag (lets a phone user reach
an off-screen panel in the tall single column — without it `touch-action:none` +
pointer-capture freeze the page mid-drag) first used `window.innerHeight`, which
under mobile emulation / a pinch-zoomed visual viewport is a **different coordinate
space than `clientY`** (measured **1321 vs the 844 CSS-px layout viewport**) → the
bottom-edge test could NEVER fire. Fix: **`document.documentElement.clientHeight`**
(same CSS-px space as `clientY`). Lesson: for viewport-edge math against pointer
coords, use `documentElement.clientHeight`, not `innerHeight`.

**Verification (the project's "screenshot pass IS the regression check", no JS test
harness):** Playwright **bundled Chromium** (the `chrome --headless` hijacks the
user's running Chrome — see [[star-sim-phase5-spectra]]) on the REAL served UI:
desktop mouse (4-across, drag-reorder, persist, reset, zero overlaps, no canvas
overflow) **and a real CDP TOUCH drag** at 390 px (`Input.dispatchTouchEvent`,
`hasTouch:true` context) — touch reorder works, auto-scroll reaches `scrollY≈1035`
past 3 off-screen panels; phone = clean 7-row single column, no overflow, no
console errors. **My first pass tested drag with a MOUSE only** (1440 px viewport) —
the advisor insisted on touch, which is what surfaced GOTCHA 2. Always verify the
touch path on a touch-claimed device, not just a resized viewport with mouse events.

**Two accepted known limitations:** other panels' canvases can re-fit mid-drag when
a row's fill changes (cosmetic jank, no error); ultra-wide monitors leave dead
space right of the 4 capped compact panels (deliberate text-readability cap).

---

**DENSITY-PASS FOLLOW-UP (frontend-only; `layout.js` UNTOUCHED → verified
touch-drag still holds, mouse re-check sufficed).** User: dashboard had "a lot of
empty space" that "doesn't look good" (Lane–Emden graphic stranded from its
readout; big gaps below the controls/HR row; spectrum/SED each hogging a whole
row), wanted denser arrangement + a way to **turn off individual elements** in the
per-element comp view.

**The advisor's two decisive calls (both right):**
1. **Don't build masonry this turn.** The user was *brainstorming* mechanisms
   (columns/resizable), not specifying masonry; flex-wrap already IS 2–3 columns; a
   masonry rewrite forces re-doing the full CDP **touch** verification (this very
   memory records mouse-only missing a real touch bug once). Offer it as a one-line
   opt-in instead. **If ever built:** per-column drop zones, **NO auto-rebalance on
   drop** (that's what keeps the drop crisp — reflow-surprise only happens if you
   greedy-repack on every change), redistribute only on load + column-count change.
2. **The big gap was ONE outlier, not a flex-wrap flaw.** Measured: a 317px gap
   below `comp` came from the **781px `controls` panel** (almost all its 14-row
   readout) sitting next to a 464px panel. **The fix is the readout, not the layout
   engine.**

**What shipped (CSS + comp.js only):**
- **Per-element on/off:** click a `legend-cno` entry → `comp.toggleElem(el)`
  hides/shows that line (session-only `hidden` Set, scoped to the cno view).
  `main.js` delegates the click via `closest("span[data-el]")` so the inner `.tip`
  hover label still works; an `.off` class dims the entry + hollows its swatch.
  **The non-obvious half (advisor): hiding must drive the AUTOSCALE** — `drawCno`
  passes only `ELEMS.filter(!hidden)` to `region()`, which already ranges over
  exactly the elements it's handed, so hiding the abundant O/C **rescales the
  y-axis** and the trace lines fill the height. A toggle that only declutters but
  keeps O's scale is half the feature.
- **`.readout` → `grid-template-columns: repeat(auto-fit, minmax(240px,1fr))`** =
  **two columns on a wide panel, one on a phone**. Width-driven (NOT a media/
  container query) so it stays correct as panels are dragged/reflowed to any width.
  Cut controls **781→595px**, worst gap **317→131px**, main height 2594→2346.
- **Lane–Emden un-`wide` + `lane-body` collapsed to a single vertical column**
  (canvas above controls). The old `1fr minmax(220,320)` grid stranded the
  ~380px-capped canvas in a much wider column with a dead gap; stacking is denser
  AND lower-risk than filling a variable column.
- **Spectrum + SED un-`wide`** → pair side-by-side on one row (user explicitly
  sanctioned "can fit on a single row"). **Wider columns** (`.panel` flex-basis
  320→**460**, max-width 384→**700**) → 2 cols laptop / 3 wide / 1 phone, so short
  panels pair with short. Canvas `maxW`→720 so `avail` binds and each canvas fills
  its panel (little internal dead space).

**Rejected: user-resizable panels** (advisor — free pixel-resize fights
responsive-flow exactly like stored *positions* did, which this memory already
rejected). **Rejected: hand-tuned default order** to close residual gaps (brittle —
panel heights shift with content: feh→mass_range, comp legend re-wrap, readout
value widths). Residual ~60–131px gaps are draggable-away; lane alone on the last
row is "the least-offensive waste." pytest unchanged (137) — frontend-only.
