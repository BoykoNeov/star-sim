---
name: star-sim-true-size-scale-bar
description: Frontend-only UX — 3D star +20% (clip-clamped) and a true-size scale bar (Earth/Sun/planet-orbit landmarks on a log length axis).
metadata: 
  node_type: memory
  type: project
  originSessionId: a2c7b92f-4911-48b7-8f39-901285aaf0ba
---

User asked to make the 3D star ~20% bigger and add a **scale bar at the bottom**
showing the "vastly different sizes of stars" via **Earth, Sun, and planet orbits**.
Shipped **frontend-only** (no backend/API/spine touch; pytest unchanged 137).

**Bigger star (`star.js`):** `displayRadius` → `min(2.65, 1.2 * base)`. 1.2 = the 20%;
the clamp keeps the largest giants in-frame. **Advisor caught a real math bug:** a
sphere's visible silhouette is the **tangent cone `asin(R/d)`, NOT the pole angle
`atan(R/d)`** — so the disk clips at `R = 8·sin(20°) ≈ 2.74` (camera z=8, 40° vertical
FOV), and my first-pass 2.78 clamp would *still* clip. 2.65 leaves margin. Corona
needed no change (`corona.scale = rad·extent` keys off the same `rad`). **VERIFY THE
WORST CASE, not the Sun** (clip is silent on small stars): a 5 M☉ EAGB giant at R=327
clamps to the max display size 2.65 → confirmed a clean full circle, no flat pole.

**Scale bar (`scale.js`, new):** a **sibling like sed.js** — reads ONE number (`R_rsun`)
off the marker, tinted by `teffToCSS(Teff)`, **no fetch**. Reason-for-being (advisor's
framing, now the lead comment): the 3D render is **log-compressed / deliberately not to
scale** (dwarf & giant render nearly the same size on purpose), so a ruler calibrated to
the *rendered* star would be a lie — the honest device is an **independent log length
axis** (R☉, ~0.004–1500). Landmarks: **bodies** (Earth 0.0092 / Jupiter 0.10 / Sun 1.0
R☉) = warm dots BELOW; **orbits** (Mercury 83 / Venus 155 / Earth 215 / Mars 328 /
Jupiter 1119 R☉, via `AU·215.032`) = cool-blue rings ABOVE under a faint **"planet
orbits" bracket** (the SED "detailed spectrum" idiom — groups the cluster AND
disambiguates *Earth-orbit 215* above from *Earth-body 0.009* below). Current star =
tinted "reach" fill (left of marker = smaller) + `teffToCSS` marker line + on-canvas
readout pill ("this star · 154 R☉", **clamped on-canvas**) + a **dynamic caption** naming
what it engulfs. **The orbit cluster is the layout risk** (Mercury→Mars span only 0.6
decades → labels collide): handled the advisor's way — **staggered 2-row text labels +
collision-skip, NO cryptic planet glyphs** (wrong for a teaching tool); the caption
carries the precise figures the skipped labels can't.

Wiring: `index.html` (title + `?` + canvas + caption, reusing `spectrum-caption` class),
`styles.css` (`#scale-canvas`/`.scale-title`), `main.js` (`scale.update(s)` in
`refresh()`; RESPONSIVE entry `maxW:480,h:150` so the ResizeObserver re-fits it — the
`fitCanvas` inline-width gotcha from [[star-sim-draggable-responsive-panels]]).

Verified via **Playwright bundled Chromium** (the `chrome --headless` hijack — use
playwright-core + the ms-playwright chromium exe; install playwright-core in scratchpad)
on the real served UI across dwarf 0.22 / Sun 1 / giant 327 R☉, desktop + phone 390 (pill
clamps on-canvas, labels legible), captions correct, no console errors. Screenshot pass
IS the regression check (no JS harness). See also [[star-sim-frontend-ux]],
[[star-sim-phase2-shaders]] (the §7 star renderer this enlarges).
