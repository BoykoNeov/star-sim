---
name: star-sim-phase2-shaders
description: "Phase 2 (spec §7) shader beauty — frontend-only: Planck→CIE color, H_p granulation, limb darkening, stable rotation, activity corona; + the 2026-07 shading rework (ring→monotone limb profile, chromatic limb darkening, Teff exposure, Teff×L glare quad, incandescent fireball)"
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

**The shading rework (2026-07, star.js-only — a visual-review follow-up):** pixel
measurement of Playwright star-canvas shots found the disk's radial profile ran
BACKWARDS — the corona's `smoothstep(0.92, 1.06, rd)` rim straddled the limb, and
additive glow stacked on the limb-darkened (and antialiased) disk edge clipped to a
white annulus up to 25% brighter than disk centre (an "annular eclipse" look, worst
on giants/M dwarfs); and because `teffToLinearRGB` is max-channel normalized, every
star rendered equally bright — an 800 kL☉ O star read as matte styrofoam, a 54 kK
WD as a flat disc, the SN fireball as a matte moon. Four changes, `color.js`
deliberately untouched:
- **Corona profile:** glow starts strictly OUTSIDE the silhouette's AA edge
  (`smoothstep(1.005, 1.06, rd)` — starting at 0.995 still ringed: additive light on
  the AA-blended limb pixels clips) and decays monotonically; limb alpha capped
  below the darkened disk edge (`uIntensity = 0.12 + 0.3·act`, was 0.3 + 1.4·act).
  Activity now shows mostly as REACH (extent unchanged). Disk centre is always the
  brightest thing in frame.
- **Chromatic limb darkening:** per-channel quadratic coefficients (`u1 =
  (0.33, 0.40, 0.50)`, `u2 = (0.20, 0.26, 0.33)` — blue darkens most, G matches the
  old scalar law) so the limb warms as it darkens. Real physics, adds the color
  depth the flat scalar law lacked.
- **Teff-keyed exposure (`uExpo`):** restores the brightness cue max-normalization
  discards — `0.85 + 0.15·sstep(3000, 5800, T) + 0.5·sstep(8000, 25000, T)`; anchored
  so the Sun sits at exactly 1.0 (face unchanged). Cool stars render deep/saturated
  (the honest 3300 K hue was measured CORRECT before — pale peach IS the Planck
  color; under-exposure is what makes it read rich), hot stars clip toward blue-white
  at centre (granulation washes out free — apt for radiative envelopes), and a
  cooling WD dims+reddens through the same curve (the "cold cinder" beat).
- **Glare quad (`GLARE_FRAG`):** third corona-style additive quad — tight sheath
  (0.42·e^−5.5Δ) + wide bloom (0.22·e^−1.6Δ), star hue nudged 30% toward white,
  keyed `sstep(7000, 22000, Teff)·(0.5 + 0.5·sstep(0, 6, logL))` — O stars/hot WDs/WR
  blaze, the Sun and cool giants get none. SN branch re-keys it to the light-curve L,
  dying with `snFade`; failed collapse gets zero. Set unconditionally each update()
  (the `star.visible` mode-switch rule). Fireball also gained white-hot plume cores
  (`mix(uColor, white, 0.45·hot)`, alpha ceiling 0.85→0.95) — incandescent, not matte.
Tuning gotchas: (1) glare's first cut (tight e^−9Δ at full alpha) re-created the ring
on the O star — the fix that generalizes is *start past the AA edge + cap limb alpha
below the disk edge; let the WIDE bloom carry the blaze*. (2) The ring detector is
cheap and worth keeping: radial luminance scan flagging any outward jump >12 units
past the falloff start (granulation cells near centre false-positive; ignore r≲0.3R).
(3) Backticks in a GLSL comment inside the JS template literal AGAIN (` around a
var name) — node ESM's error ("Unexpected identifier") points nowhere; `node --check
<copy>.mjs` gives the line. Verified: 12-state Playwright sweep (Sun/giant/M dwarf/
O star/A star/WD entry+hot+cold/WR/SN early+plateau+late) + full-page 1440/390, zero
console errors; WD-entry TPAGB continuity and failed-SN dimming preserved.

**Next:** Phase 3 — the Lane-Emden interior-structure panel (spec §8), validated
against Chandrasekhar's polytrope tables (n=0,1,5 closed forms).
