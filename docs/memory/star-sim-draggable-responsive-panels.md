---
name: star-sim-draggable-responsive-panels
description: Frontend dashboard UX — draggable panels (reorder-in-flow sortable) + responsive canvases + edge auto-scroll; the fitCanvas-inline-width and innerHeight-vs-clientHeight gotchas.
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
