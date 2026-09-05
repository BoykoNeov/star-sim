# Visuals & performance plan — measured, ordered, executable

**Why this exists.** The app was feature-complete but nobody had *measured* it: no frame
timing, no first-paint timing, no profile of the age scrub. This document records what was
measured on 2026-09-05 (§1), what was fixed the same day (§2), and — the part that matters
for the next session — the remaining items with a measured or estimated payoff, a concrete
recipe, and an acceptance check each (§3, §4). Everything in §3/§4 is written so that a
smaller model can execute one row at a time without re-deriving the reasoning.

Ground rules that do not move: the §3 `StellarState` spine, siblings that bypass
`PROVIDER`, **measure first, then draw** (CLAUDE.md), no bundler, no deploy concerns.
Every visual change is verified by the Playwright pass (1440 + 390 px, zero console
errors) and every performance change by the harness in §0 — a number, not a feeling.

---

## 0. The measurement harness (reuse it; do not rebuild it)

Lives outside the repo, in `M:\claud_projects\temp\star-sim-perf\` (the repo's temp rule):

| File | What it measures | Run |
|---|---|---|
| `measure.mjs` | first paint (ms), every request's server time, rAF frame times idle / scrolled-off / after a scrub / at 8 M☉, backing-store `width` sets per canvas (a per-frame `setSize` shows up here), long tasks, every canvas's CSS vs backing size | `node measure.mjs <dpr> <swiftshader\|d3d11\|headed>` |
| `profile_scrub.mjs` | CDP CPU profile of 120 synchronous age-slider `input` events → self and inclusive time per function | `node profile_scrub.mjs <mass>` |
| `shots.mjs` | full-page + star-canvas screenshots, desktop 1440 and phone 390, Sun / 15 M☉ / 15 M☉ late / 0.3 M☉ | `node shots.mjs <suffix>` → `shots-<suffix>/` |
| `time_startup.py` | provider startup stages: dir discovery, fingerprint, `.npz` read per grid | `python time_startup.py` (backend venv) |

`node_modules` there is a junction to `M:\claud_projects\temp\star-sim-pw\node_modules`
(Playwright 1.61, Chromium already cached). The server must be up on :8000 first
(`python -m uvicorn star_sim.api:app --app-dir backend`). **Two GL backends, two
meanings:** `swiftshader` is software GL — a strict, cross-GPU *stress* signal, use it for
relative before/after numbers; `d3d11` uses the real GPU (an RTX 5090 on the dev box, where
everything is 60 fps — it cannot show a GPU problem, only a main-thread one).

Cold-disk numbers cannot be reproduced on demand (the OS file cache stays warm after one
run); the ones below were taken on the first request after a reboot-cold state. To re-create
a cold read, copy the `.npz` under a new name and time a read of the copy.

---

## 1. What was measured (2026-09-05, before any fix)

| Metric | Value | Where it came from |
|---|---|---|
| First `/track` on a cold OS cache | **155 s** (ten MIST `.npz` caches = 450 MB; warm: 0.2 s) | curl; `time_startup.py` |
| First `/photometry` on a cold cache | **10.9 s** (the 98 MB spectrum cube; warm: 10 ms) | `measure.mjs` request log |
| First paint of the page, warm server | **12.6 s** — the seven optional-data probes were awaited *serially* before the track fetch, so the cold `/photometry` probe held the whole page | `measure.mjs` |
| 3D canvas backing-store re-created **every frame** at DPR ≥ 1.5 | `resize()` compared `canvas.width` (backing px) to `clientWidth` (CSS px): equal only at DPR 1 | `measure.mjs` `canvasWidthSets` = frames |
| Idle frame, DPR 2, SwiftShader, Sun / giant | 48 ms / **1,600 ms** | `measure.mjs` |
| Age scrub, main-thread cost per slider event (1 M☉ / 8 M☉) | **9.9 / 8.9 ms** on the dev box; 12 ms p50, 37 ms max under SwiftShader | `profile_scrub.mjs` |
| …of which `planckToXYZ` (the Planck×CMF integral, once per HR track segment) | 36–56 % | profile self time |
| …of which `hr.js drawTrack` stroke calls (one `beginPath/stroke` per segment, ~800) | 18 % | profile self time |
| …of which `comp.js` stacked-band path building (6 bands × 2 × ~800 points, per event) | 20–23 % | profile inclusive |
| Render loop while the star is scrolled off screen | still rendering (no visibility gate) | code |
| HR axis title "Teff → (hot left)" vs the 10kK tick label | 3 px overlap at every width | screenshot |
| Everything else (SED, seismo, readout, scale, classify) | < 1 ms per event combined | profile |
| Real-GPU (d3d11) frame time, any state | 16.6 ms = vsync | `measure.mjs` |

---

## 2. Shipped the same day (the row in `SHIPPED.md` §7 carries the after numbers)

| Fix | File | Measured effect |
|---|---|---|
| Exact-key memo on `teffToLinearRGB` + `teffToCSS` (bounded Map, byte-identical output) | `frontend/src/color.js` | scrub 9.9 → 1.7 ms/event (1 M☉), 7.5 → 1.4 on the GPU box |
| `strokeRuns()` — consecutive same-colour, same-side segments join one stroke (also removes the double-blended bead at every vertex of the α 0.3 future track) | `frontend/src/hr.js` | part of the above; also the endgame track |
| Stacked X/Y/Z bands as `Path2D`s cached per (track, W, H) | `frontend/src/comp.js` | ~2.5 ms → < 0.3 ms per event for the bulk view |
| `resize()` compares against `clientWidth × pixelRatio` | `frontend/src/star.js` | backing-store sets per second: 60 → 0 at DPR 2; giant idle 1,600 → 90 ms (SwiftShader) |
| `IntersectionObserver` parks the render loop while the star canvas is off screen; restarts on re-entry with the fireball clock re-based | `frontend/src/star.js` | scrolled-off page: no GPU work |
| The six optional-data probes run concurrently and no longer gate the first star; `settleProbes()` re-runs `refresh()` once they land | `frontend/src/main.js` | first paint on a cold `/photometry`: 12.6 s → the track's own time |
| Startup pre-warm: a daemon thread loads every MIST grid and the spectrum cube the moment uvicorn is up (`STAR_SIM_NO_PREWARM=1` opts out; `TestClient(app)` never triggers it) + a load lock in `MISTProvider._ensure_loaded` | `backend/star_sim/api/__init__.py`, `providers/mist/provider.py` | the cold read overlaps the browser opening instead of the first click |
| HR tick labels lifted 3 px, axis title on its own 11 px line | `frontend/src/hr.js` | no overlap at 1440 or 390 |

---

## 3. Performance — remaining items, in payoff order

Each row: **what / why / recipe / acceptance**. Do one row per commit; run §0 before and
after and paste the numbers into the commit message.

### P1. Adaptive pixel ratio for the 3D star (integrated GPUs) · *sketched*

- **Why.** The surface shader is two Worley octaves × two granule generations = 108 hash
  evaluations per fragment; at DPR 2 the 420-px canvas is 705 k fragments (~76 M hashes per
  frame). On SwiftShader that is 45 ms (Sun) to 90 ms (a full-frame giant); a real
  integrated GPU (Intel Iris / Apple M-series at DPR 2) is untested and is the realistic
  worst case for a "runs locally" teaching app.
- **Recipe.** In `star.js` `animate()`: keep a rolling mean of the last 60 frame `dt`s
  (from `clock`). If the mean exceeds 25 ms for two consecutive windows **and** the current
  pixel ratio is > 1, call `renderer.setPixelRatio(max(1, pr − 0.5))` and force one
  `resize()` (the new backing size). Never raise it back automatically (hysteresis is not
  worth the flicker). Log one `console.info` line saying what happened (the screenshot pass
  greps for `error` only). Do NOT touch the shader.
- **Acceptance.** `measure.mjs 2 swiftshader`: the idle giant frame drops from ~90 ms to
  ~25–30 ms after the adaptation kicks in; `measure.mjs 1 d3d11` and the 1440/390 screenshot
  pass unchanged (a capable GPU never adapts, so the look is untouched there).
- **Alternative if the above is judged too clever:** cap `setPixelRatio(Math.min(1.5, dpr))`
  for the star canvas only. One line; the Playwright DPR-2 screenshot changes slightly
  (softer granulation); the 2D canvases keep DPR 2.

### P2. Vendor `three.module.js` (drop the unpkg dependency) · *sketched*

- **Why.** The importmap points at `https://unpkg.com/three@0.160.0/…` (1.2 MB). A
  first visit with no network — or unpkg slow — leaves the 3D panel black with no error
  the user can act on. Every other asset is local.
- **Recipe.** Copy the pinned build to `frontend/vendor/three-0.160.0.module.js`
  (keep the version in the filename; add the MIT licence text beside it — `NOTICE`
  already exists at the repo root, append the three.js entry). Change the importmap to
  `"three": "./vendor/three-0.160.0.module.js"`. Nothing else imports three except
  `star.js`. 1.2 MB in git is the cost; it never changes.
- **Acceptance.** Network log in `measure.mjs` shows no external request; `node --check`
  irrelevant (no JS change); screenshot pass byte-identical.

### P3. `/track` payload size (811 KB per mass change) · *measure first*

- **Why.** Every settled mass/[Fe/H] change sends ~800 rows × ~55 fields as full-precision
  JSON: 70–240 ms server time plus the client `JSON.parse`. On localhost the transfer is
  free; the *serialisation + parse* is what costs.
- **Recipe, step 1 (measure).** `performance.now()` around the `fetchJSON("/track…")`
  await and around `JSON.parse` (temporarily) at 1, 8 and 60 M☉. If the parse is < 15 ms,
  stop here and record the number in this row.
- **Step 2 (only if measured).** Add `GZipMiddleware(minimum_size=4096)` in
  `api/__init__.py` (stdlib zlib; ~80 % smaller). Do **not** round floats — several tests
  compare route output to provider output exactly, and the honesty rule prefers the real
  number.
- **Acceptance.** `measure.mjs` request log: `/track` `ms` and `size`; pytest unchanged.

### P4. Static layers for the two panels that still repaint per scrub · *optional*

- **Why.** After §2 the whole scrub is ~1.5 ms. The rest is `sed.js` re-sampling the Planck
  curve and re-painting the rainbow band per column (0.5 ms), and `renderReadout`
  rebuilding innerHTML (0.15 ms). Only worth doing if a slower target is measured.
- **Recipe.** In `sed.js`, paint the bands + rainbow + axes once per (W, H, hidden-series
  set) into an `OffscreenCanvas`/detached canvas and `drawImage` it; keep the Planck curve
  live. In `comp.js`, extend the `Path2D` cache to the cno/light views the same way the
  bulk view does (`bulkPaths()` is the template).
- **Acceptance.** `profile_scrub.mjs 1`: `update sed.js` inclusive < 0.2 ms/event.

### P5. Cold-disk startup (the 155 s) · *only if it is still a complaint after the pre-warm*

- **Why.** Ten `.npz` caches of 45 MB each are read whole on the first load. On a cold
  OS cache and a slow disk that was 155 s. The pre-warm (§2) hides it behind the browser
  opening but does not shorten it.
- **Options, cheapest first.** (a) Check `_write_cache` uses `np.savez` (uncompressed) —
  if it is `savez_compressed`, the CPU decompress is part of the cost; switch and bump
  `CACHE_VERSION`. (b) Per-column `.npy` files with `mmap_mode="r"` so only touched pages
  are read — a cache-format change: `CACHE_VERSION` bump, one ~200 s reparse per machine,
  **and** a re-bake of the hosted `mist-baked` release assets (`fetch_mist_baked`), which is
  the real cost. (c) Load only the two [Fe/H] grids that bracket the request and the rest
  lazily — changes `_ensure_loaded`'s contract (`parameter_ranges()` needs every grid's
  bounds), so it needs a cheap per-grid header first. Recommend (a) now, (b) never unless
  measured on a laptop, (c) not at all.
- **Acceptance.** `time_startup.py` on a cold copy of one `.npz`.

### P6. `<link rel="modulepreload">` for the 24 local modules · *skip unless measured*

The module graph loads in dependency order (25 requests, ~5–15 ms each on localhost);
first paint on a warm server is ~0.5 s. Preload hints would parallelise the discovery.
Measured gain would be < 200 ms on localhost; record and skip unless a remote-serve use
case appears.

---

## 4. Visuals — remaining items

### V1. The reserved blank in the Controls panel · *sketched, needs a 1440 + 390 check*

- **What.** On the default Sun the Controls panel shows ~200 px of empty space between the
  rotation caption and "Chemically peculiar" (`shots-base/desk-sun.png`, y ≈ 1900–2100).
  It is the reserved height of the inclination / gravity-darkening facet, which only
  appears for a rotating massive star — the anti-jump discipline in
  [[star-sim-frontend-ux]].
- **Recipe.** Replace the fixed reservation with the same treatment the other gated
  controls already use (the "three hide reasons" rule): a one-line greyed "Appears for
  rotating stars ≳ 1.3 M☉ (gravity darkening)" note in the facet's slot, sized like the
  Ap/Bp note. Then check the jump: scrub mass 1 → 5 at 1440 and 390 and confirm the panels
  below do not shift by more than the one line the note already occupies.
- **Acceptance.** Screenshots before/after at both widths; the panel's height on the Sun
  shrinks by ~150 px; no console errors.

### V2. Row-height imbalance in the two-column layout · *idea, judgement call*

- **What.** Flex rows stretch to their tallest panel: State readout (short) beside
  Controls (tall), Spectrum beside the much taller SED, Interior (MESA) alone on the last
  row at half width.
- **Options.** (a) Change the default panel order so tall pairs with tall (Controls ↔
  Composition, Readout ↔ Spectrum) — one array in `layout.js`; users who reordered keep
  their saved order. (b) `align-items: flex-start` on `main` so panels stop stretching —
  ragged bottoms instead of dead space inside panels; try it and screenshot. (c) A
  `layout.js` rule that gives the last panel `flex-basis: 100%` when it is alone on its
  row (needs a measurement of the row, CSS alone cannot express it).
- **Acceptance.** Full-page 1440 screenshot with visibly less dead space; 390 unchanged
  (single column, nothing to pair).

### V3. Verify the parked render loop against the screenshot pass · *do with any V-item*

The loop now parks when `#star-canvas` leaves the viewport. Playwright's element
screenshot scrolls the element into view and the observer restarts the loop on the next
tick, so a `canvas.screenshot()` taken *immediately* after a scroll could capture the last
frame before restart (still a valid frame, just not the newest uniforms). If a future
screenshot pass ever sees a stale star, add a `page.waitForTimeout(100)` after the scroll
— do not remove the gate.

### V4. Things checked and found fine (do not re-propose)

- The 3D star at 358 px on a 390 px phone: granulation resolves, the AA fade works.
- The M1 I red supergiant: the disk reads as a giant (dim granulation, warm limb).
- HR class bands, iso-radius diagonals, the "→ white dwarf" leader: legible at both widths.
- Real-GPU frame time is vsync-bound in every state measured.
