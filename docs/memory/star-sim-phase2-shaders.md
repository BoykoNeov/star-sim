---
name: star-sim-phase2-shaders
description: "Phase 2 (spec §7) shader beauty — frontend-only: Planck→CIE color, H_p granulation, limb darkening, stable rotation, activity corona"
metadata: 
  node_type: memory
  type: project
  originSessionId: 78c4b4b3-595e-4fb2-bb55-266df2edc060
---

Phase 2 ("beauty", spec §7/§9) is **done** and **frontend-only** — touched
exactly `color.js`, `star.js`, `index.html`. No backend, no API, and the
`activity` proxy was deliberately NOT touched (a §11 open question, not Phase 2;
changing it would mean editing `_state_from_row` and breaking frontend-only
cleanliness). Every visual reads a real `StellarState` field, so §3 holds.
Builds on [[star-sim-mist-provider]] / [[star-sim-composition-panel]] /
[[star-sim-frontend-ux]].

**What shipped:**
- **Color (color.js):** the reference Planck→CIE 1931 (Wyman analytic CMF fit)→
  linear sRGB pipeline, replacing the Tanner-Helland approximation. Order is
  load-bearing: clamp out-of-gamut negatives to 0 → normalize by **max channel**
  (full-brightness chromaticity for a self-luminous disk) → gamma **last**.
  Exposes `teffToLinearRGB` (linear, for the shader) + `teffToRGB`/`teffToCSS`
  (display sRGB, contracts preserved for the 2D UI). §10 check passes: 3000 K
  orange-red, Sun 5772 K warm near-white (NOT yellow), 10000–40000 K blue-white.
- **star.js → `ShaderMaterial`** (GLSL1; replaced `MeshBasicMaterial`). Surface
  shader: base color × **granulation** × **quadratic limb darkening**, gamma at
  the very end. Granulation = animated 3D Worley; cell frequency from the
  pressure scale height: `Q = R·10^logg/Teff`, tuned so the Sun ≈22 cells,
  clamped [2.5, 90] (the low floor IS the spec's "handful of enormous cells" for
  a giant; the cap stops dwarf aliasing). `uTime` from a `THREE.Clock` (frame-rate
  independent), not a per-frame `+=`.
- **Corona:** camera-facing additive quad (not a back-shell — a shell gave a
  detached glow ring with a dark gap). Glow worked in units of the limb radius
  (`rd = d/uInnerFrac`), soft rim hugging the limb + exponential outward falloff;
  intensity AND extent scale with `activity`. Hot O/B star (activity≈0) is
  near-glowless on purpose (§7-honest). Labelled "evocative, not predictive" in
  BOTH a code comment and the UI tooltip (§7 asks for both). Old placeholder halo
  removed so glows don't stack.

**The one real bug (caught by advisor + a t=0/30/60s screenshot check):** the
naive differential rotation `omega(lat)*uTime` accumulates unbounded latitude-
dependent shear, winding granulation into longitudinal **streaks** by ~60 s — a
2 s screenshot can't see it. Fix: split rotation into a continuous **rigid spin**
(latitude-independent → zero shear, ever) plus a **bounded** differential shear
that runs ±half a cycle and **resets every granule lifetime** (`uLife`=8 s),
cross-faded between two staggered generations (triangle weights summing to 1) so
cells dissolve and reform (solar) and shear can never exceed one lifetime.
Re-verified coherent over a full minute. See `granulation()`/`genGranule()` in
star.js — do NOT revert to the simple accumulating shear.

**The granulation moiré/grid fix (later session, advisor-guided, frontend-only):**
the user saw two unnatural artifacts on the 3D star — a **rectangular grid** and
**moiré/static** — which are two different failures at opposite ends of the
granule-frequency range, confirmed by a 4-star harness (giant/sun/M-dwarf/compact)
shot at native res:
- **Grid** (worst on a low-`uCells` supergiant): the old `fract(sin(dot(...)))`
  hash left each Worley cell's feature offset *correlated along the object axes*,
  so a "handful of enormous cells" lined up in rows/columns and the cubic lattice
  read as a grid. NOT sphere tessellation (the discriminator: a tessellation grid
  would be a curved lat/long graticule converging at the poles — this was straight
  axis-aligned cells). Fix: swap to a sin-free **Dave Hoskins `hash33`** → offsets
  decorrelate → even a few big cells scatter organically.
- **Moiré** (worst on a high-`uCells` compact dwarf, ~90 cells × the 2.7× second
  octave on a tiny disk): sub-pixel granules beat against the pixel grid. Fix:
  **per-octave analytic antialiasing** in `genGranule` — fade each octave toward
  the Worley-F1 mean (`WMEAN=0.54`) once its frequency `F·fw ≳ 0.5`, where
  `fw = length(fwidth(vObjPos))` is the object-space pixel footprint. Needs
  `extensions: { derivatives: true }` on the surfaceMat (core in WebGL2; emits the
  `GL_OES_standard_derivatives` pragma on WebGL1). Gotchas: (1) **per-octave, not
  one fade on the sum** — keying the fade off the finer 2.7× octave over-fades the
  resolvable coarse octave and smooths an M dwarf completely (the coarse ~5px cells
  are above Nyquist — keep them); (2) fade toward the *mean*, not 0, so the
  smoothed disk keeps the same brightness (both-faded → `f=WMEAN` exactly,
  neither-faded → byte-identical to the old field); (3) analytic frequency, NOT
  `fwidth(f)` — the latter spikes on the Worley cell-edge ridges and would erode
  the dark intergranular lanes. Bonus: `fw` blows up at the foreshortened limb, so
  the same term cleans the disk edge, and being resolution-adaptive it does more
  fading on a small panel, less on a large one. Verified safe alongside the WD
  `uGran` gate (`uGran=0` forces `granule=1.0`, AA inert; the TPAGB-giant frame at
  `uGran>0` keeps organic granulation). Stills suffice — the mesh never rotates
  (`uOmega·time` is in-shader), so `fwidth(vObjPos)` is time-constant and faded
  regions can't shimmer.

**Verification method (no JS test harness):** headless Chromium via
`playwright-core` (browsers were already cached at
`%LOCALAPPDATA%/ms-playwright/chromium-1223/chrome-win64/chrome.exe`; launch with
`--use-angle=swiftshader`), driving the live app on :8000, screenshotting
`#star-canvas` at Sun / hot 15 M☉ / RGB-clump giant / 0.2 M☉ dwarf, plus a
2-frame byte-diff for animation and the t=0/30/60 wind-up check. SwiftShader
(software GL) is a strict cross-GPU signal. Also caught a self-inflicted bug:
backticks around `` `ang` ``/`` `gen` `` in a GLSL comment *inside* a JS template
literal terminate the string — keep backticks out of shader-string comments.

**Next:** Phase 3 — the Lane-Emden interior-structure panel (spec §8), validated
against Chandrasekhar's polytrope tables (n=0,1,5 closed forms).
