---
name: star-sim-visual-performance
description: "The 2026-09-05 visuals/performance pass: what was measured (cold-disk first load, per-frame WebGL realloc at DPR≥1.5, the Planck integral dominating the age scrub), the seven fixes, the harness in temp/, and the plan doc for what remains"
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

**Open (in the plan, payoff order):** adaptive pixel ratio for integrated GPUs (P1), vendor
`three.module.js` (P2), measure the 811 KB `/track` parse before touching it (P3), the
~200 px reserved blank in the Controls panel on the default Sun (V1), row-height pairing in
the two-column layout (V2).
