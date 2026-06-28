---
name: star-sim-tooltip-singleton
description: Frontend-only fix — viewport-clamped singleton tooltip replaces per-element CSS ::after tooltips that clipped at panel edges once panels became draggable.
metadata: 
  node_type: memory
  type: project
  originSessionId: b1cc12d2-2685-4a27-b03f-0fd786da12de
---

The pedagogy hovers (the `?` help glyphs + dotted-underline `.tip` tokens) were
CSS `::after` pseudo-tooltips **statically anchored** to open right / left
(`.help-left`) / up (`.tip-up`). Once the panels became draggable + responsive
([[star-sim-draggable-responsive-panels]]), a panel — and its glyphs — can land
anywhere, so a leftward tooltip on a **left-edge** panel clipped off-screen (the
reported bug), with the symmetric latent right-edge clip on the default rightward
ones.

**The reusable nugget:** once panels are draggable, the static-anchor CSS tooltip
is fundamentally broken — CSS can't detect a viewport collision, and you can't
`getBoundingClientRect()` a `::after` pseudo-element to clamp its far edge. The
answer is a **single body-mounted, `position:fixed` tooltip layer** (`tooltip.js`,
`initTooltips()` in `main.js`), shown on hover/focus of any `[data-tip]` via
**event delegation** (so it also covers the JS-rendered readout `?` rows), with
**JS clamping on BOTH axes**: below the trigger → flip above on bottom overflow
(absorbs the old `.tip-up` case for free) → horizontally `clamp(MARGIN, left,
vw-tw-MARGIN)`.

**Why a clamp, not a side-flip** (the advisor's discriminator, verified): a
mid-panel glyph on a 390px phone with a wide tooltip clips BOTH ways, so picking a
side can't help — only clamping keeps it on-screen. Verified center trigger
cx≈195 → clamped to [42, 382] at 340px width.

**Gotchas worth keeping:**
- A few tips are ~2000 chars (longest 2128) → at the old 250px they wrapped
  TALLER than the viewport. Fix = widen `max-width` to 340 (`width:max-content`
  leaves short tips compact) **+** a JS `max-height = vh - 2*MARGIN` cap with
  `overflow:hidden`, and pin top to MARGIN when too tall (show the START).
  Exercised + verified at a short 1280×600 landscape (scrollH 679 > clientH 582,
  pinned top=8, no scrollbar).
- `pointer-events:none` on the layer is load-bearing: the legend `.tip` lives
  inside the click-to-toggle `span[data-el]`, so the layer must never intercept
  clicks. Verified the toggle still works.
- Use `documentElement.clientWidth/Height` (same coord space as
  getBoundingClientRect; scrollbar-excluded), not `window.inner*` — same lesson as
  the auto-scroll bug in [[star-sim-draggable-responsive-panels]].
- Hide on `scroll` (capture) + `resize` so a fixed tooltip doesn't float
  detached. (Test artifact: programmatic scroll-into-view fires this hide → drive
  the mouse AFTER the scroll settles when verifying.)
- Deleted the dead `::after` rules + `.help-left`/`.tip-up` classes
  (`index.html`, `lane.js`, `main.js` helpers). Keep `.help`/`.tip` (glyph
  affordance + delegation hook).

Verified via Playwright bundled Chromium (the `chrome --headless` hijack caveat):
all 49 visible tooltips fully on-screen at 1440×900 AND 390×844 (worst overflow
0px), legend toggle + keyboard focus + status upward-flip intact, §10 Sun anchor
unregressed, no JS errors. **pytest unchanged (137) — frontend-only.** Cross-refs
[[star-sim-frontend-ux]], [[star-sim-ux-four-fixes]].
