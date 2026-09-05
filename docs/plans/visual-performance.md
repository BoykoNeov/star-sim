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
| `heights.mjs` | the Controls panel's vertical budget: reserved vs *used* height for the panel and for the rotation section, plus every facet's box, across seven mass/rotation regimes at 1440 / 512 / 390 | `node heights.mjs` |
| `rotmax.mjs` | the **tallest reachable** rotation section and Controls panel, swept over 22 masses × 5 [Fe/H] × rotation off/on at three widths — what a `min-height` floor has to cover | `node rotmax.mjs` |
| `gatenote.mjs` | the `#incl-gate-note` floor against the state space that actually selects its text — **[Fe/H] × mass**, not mass alone, because the rotating-track toggle's visibility moves with metallicity — at all three widths | `node gatenote.mjs` |
| `jumpcheck.mjs` | whether a state change actually **moves a neighbouring panel** — every panel's top/height before and after the two known overflow states. The difference between a real jump and a floor that is merely undersized on paper | `node jumpcheck.mjs` |
| `panelshot.mjs` | just the Controls panel, desktop + phone, so a reserved-space change can be compared without diffing a 4000 px full-page shot | `node panelshot.mjs <suffix>` → `panel-<suffix>/` |
| `p3_track.mjs` | `/track` payload bytes, row/field counts, fetch and `JSON.parse` time per mass (P3); plus a 41-step age sweep asking whether a facet is ever *enabled* on a given track | `node p3_track.mjs` |
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

### P1. Adaptive pixel ratio for the 3D star (integrated GPUs) · **shipped 2026-09-05**

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

**What shipped, and the three places it departs from the recipe above.** All three are
consequences of the acceptance bar being the NEGATIVE case — “a capable GPU never adapts,
so the look is untouched there.” A false trigger is a silent visual regression on hardware
that was fine, so the design is shaped around not producing one.

1. **Median, not mean.** `dt` is rAF pacing, so one stall decides a mean: a GC pause, a
   mass-change fetch, or a backgrounded tab returning (frames stop entirely there, so the
   first one back is a multi-second dt — one 3000 ms frame among 29 healthy ones averages
   116 ms and would adapt twice). The median ignores all of it and equals the mean for the
   case we want, every frame slow.
2. **Two 30-frame windows, not one 60-frame window.** Same 60 frames of evidence, half the
   wall-clock. At ~100 ms/frame a 60-frame window is 6 s and two of them 12 s — longer than
   a `measure.mjs` sampling phase, so the fix would have read as dead code.
3. **A warm-up (3 s), which the recipe did not have.** Shader compilation and first paint
   land in the first frames; without it a fast GPU can adapt on a cold start, which is
   precisely the outcome the acceptance line forbids.

The decision left the render loop as **`frontend/src/framebudget.js`** — pure, fed frame
times, no canvas or clock of its own — so those three cases are unit-tested
(`framebudget.test.mjs`, 7 tests, mostly negative). The runtime pass cannot show them; it
can only show the positive case. `star.js` keeps the WebGL half: `setPixelRatio`, the
immediate `resize()`, and `frameBudget.forget()` at the two seams where frame times stop
being comparable (a ratio change, and the IntersectionObserver un-parking the loop).

**Measured.** Baseline taken by restoring the committed `star.js` on the same running
server, so both runs differ only in this change (`adapt.mjs <dpr> <gl> [mass]`, added to
the §0 harness — it prints the star canvas backing store per window, which is the direct
observable: 420 CSS px × the pixel ratio).

| SwiftShader, DPR 2, 15 M☉ late (full-frame giant) | before | after |
|---|---|---|
| frame time, sustained | 100 ms | **33.4 ms** |
| star backing store | 840² | 420² |
| adaptations | — | 2 → 1.5 at t=11 s, 1.5 → 1 at t=16.5 s, then quiet |

| d3d11 (RTX 5090), DPR 2, same giant, 24 s | before | after |
|---|---|---|
| frame time | 16.7 ms (vsync) | 16.7 ms (vsync) |
| star backing store | 840² | **840² — never moves** |
| adaptations | — | **none** |

Also unchanged: `measure.mjs 2 d3d11` through the scroll-off/on park cycle, the scrub and a
mass change — backing store 840² at the end, `canvasWidthSets.star-canvas` still 0 (the
2026-09-05 realloc fix holds; the new `resize()` call adds no per-frame churn). Screenshot
pass 1440 + 390: `errors []`. Two independent things keep the screenshot pass out of the
adaptation's way, and it is worth knowing both before anyone re-points it at software GL and
reads softer granulation as a regression: `shots.mjs` runs on **d3d11**, where the frame
time never approaches the threshold; and it screenshots after 1.2–1.5 s waits, **inside the
3 s warm-up**, where no sample counts at all. The warm-up alone would protect it.

### P2. Vendor `three.module.js` (drop the unpkg dependency) · **shipped 2026-09-05**

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
- **What it actually was (measured 2026-09-05).** The “black 3D panel” in the *Why* above
  **understated it**. `offline.mjs` (in §0's harness dir) runs two passes against the same
  server with every non-localhost request aborted, rewriting the importmap back to the CDN
  URL for the *before* pass:

  | With all external network blocked | before (CDN) | after (vendored) |
  |---|---|---|
  | external requests attempted | 1 | **0** |
  | console errors | 1 (`net::ERR_FAILED`) | **0** |
  | `loading` skeleton cleared | **no** (30 s timeout) | yes |
  | `/track` ever fetched | **no** | yes |

  The whole app dies, not the 3D panel: `main.js` statically imports `star.js`, which
  imports `three`, so the failed import takes down the entire module graph before any
  panel runs. That is the honest version of the payoff.
- **Also changed (the caption rule, applied to a code comment).** The comment above the
  importmap said “internet assumed at dev time … a pinned CDN build is the simplest sane
  setup” — false the moment this shipped, so it was rewritten. Same for CLAUDE.md's
  “Three.js via CDN importmap”. `NOTICE` gained a three.js paragraph in the MIST entry's
  form, and `LICENSE.three.txt` sits beside the build (the `LICENSE.MIST_codes.txt` idiom).
- **Download integrity was verified, not assumed** (a truncated file or an error page would
  reproduce exactly the black-panel symptom this removes): 1,272,972 bytes,
  `REVISION = '160'`, zero relative sub-imports, and `node` imports it (416 exports).
  sha256 `76dea8151bc9352aef3528b4262e249b2604f62543828328db978d060d61a495`.
- **After numbers on the normal (online) path.** `measure.mjs 1 d3d11`: no external request
  in the log, `/vendor/three-0.160.0.module.js` served in 14 ms, first paint 573 ms, idle
  16.6 ms (vsync), star-canvas backing-store sets 0. Screenshot pass 1440 + 390: `errors []`.
  Pixel-identical was **not** claimed — the surface granulation boils on a real clock, so no
  two runs match byte-for-byte; the check is zero console errors plus a rendering star.

### P3. `/track` payload size · **measured 2026-09-06 → no change made**

- **Why it was on the list.** Every settled mass/[Fe/H] change sends the whole track as
  full-precision JSON. The row assumed "~800 rows × ~55 fields = 811 KB" and 70–240 ms of
  server time, and asked whether the client `JSON.parse` was hurting the scrub.
- **The gate the row set for itself.** "If the parse is < 15 ms, stop here and record the
  number." Measured with `p3_track.mjs` (§0 harness; three runs per mass, median of the
  medians, warm server, localhost, 1440 px, d3d11):

  | mass | payload | rows × fields | `fetch` (incl. server) | `JSON.parse` |
  |---|---|---|---|---|
  | 1 M☉ | 792 KB | 606 × 20 | 79 ms | **2.6 ms** |
  | 8 M☉ | 786 KB | 606 × 20 | 79 ms | **2.5 ms** |
  | 60 M☉ | 597 KB | 461 × 20 | 63 ms | **1.8 ms** |
  | 0.3 M☉ | 332 KB | 253 × 20 | 32 ms | **0.8 ms** |

- **Verdict: skip, and do not re-propose.** The parse is 6× under the gate at its worst.
  The row's own premise was also wrong in the direction that matters: the payload is
  **606 rows × 20 fields**, not ~800 × ~55, so the "811 KB" figure came from somewhere
  other than this route's current output. What remains is the 32–79 ms inside `fetch`,
  which is **server-side serialisation** — `GZipMiddleware` would shrink the bytes on a
  link that is already free (localhost) and would *add* CPU to the part that actually
  costs. Compression is the wrong tool here; it was not added.
- **If a remote-serve use case ever appears**, this changes: transfer stops being free and
  gzip becomes worth it. That is the only condition under which to reopen this row. Even
  then, do **not** round the floats — several tests compare route output to provider output
  exactly, and the honesty rule prefers the real number.

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

### V1. The reserved blank in the Controls panel · **shipped 2026-09-06 (label, not shrink)**

- **What.** On the default Sun the Controls panel showed ~180 px of empty space between the
  rotation caption and "Chemically peculiar" (`panel-before/desk-sun.png`). It is the reserved
  height of the inclination / gravity-darkening facet, which only appears for a rotating
  massive star — the anti-jump discipline in [[star-sim-frontend-ux]].
- **Measured** (`heights.mjs`, 1440 / 512 / 390): the blank is *inside* the rotation section,
  not panel-floor slack — on the Sun at 1440 the section reserved 316 px and used 134. So the
  slot itself was the fixable thing.
- **Shipped.** `#incl-gate-note` — an "Appears for…" line in the facet's own slot, in the
  three-hide-reasons idiom the other gated controls use, with two texts kept apart: the toggle
  is present but unticked (one click away) vs. this star is below the Kraft break (no rotating
  track exists). A measured `min-height` (100 px desktop / 64 px phone) makes it **absorb** the
  slack rather than float at the top of a void; it is sized to the *tightest* state that shows
  it (1.35 M☉, track unticked — 198 px of the 316 px floor used at 1440 and 512, 234 px at 390),
  so it can only ever eat space that is already reserved and already empty. Verified over the
  state space that actually selects the note's text — **[Fe/H] × mass, not mass alone**, since
  the toggle's visibility (and therefore which of the two texts shows) moves with metallicity:
  `gatenote.mjs`, 6 × 9 × 3 widths = 162 states, **zero overflows**, worst 310 of 316 px at all
  three widths. The state that looked dangerous (toggle hidden, period slider still present, so
  the *longer* text shows) occurs at low [Fe/H] where no rotating grid exists, and is clear by a
  wide margin — the toggle row and its caption leave the section at the same moment, freeing
  more than the longer text costs. The tall states are untouched and the panel's own used
  height is unchanged. The wording uses the
  code's ~1.2 M☉ Kraft break, **not** this plan's earlier "≳ 1.3 M☉", which never matched the gate.
- **The shrink claim is RETRACTED.** This row used to promise "the panel's height on the Sun
  shrinks by ~150 px". It cannot: `.controls-panel`'s 992 px floor is the thrice-requested
  "panels never change size on slider/click" rule, and the reservation must cover the tallest
  state the section can reach. Empty pixels on the Sun go 182 → ~144 (the note claims the middle
  of the slot); they cannot go to zero without cutting the reservation. Screenshots:
  `temp/star-sim-perf/panel-{before,after2}/`.

### V1b. The reserved floors are UNDERSIZED — three measured jumps · *open, needs a decision*

Found while measuring V1, pre-existing, and **not** caused by it (the numbers below reproduce
with the note reverted). `jumpcheck.mjs` records every panel's box before/after a state change,
so these are confirmed movements of neighbouring panels, not bookkeeping:

| Trigger | 1440 | 512 | 390 | What moves |
|---|---|---|---|---|
| Mass → 6.5 M☉ at [Fe/H] −1.5 (the two-sided uncertain-fate hedge) | +60 px | +137 px | +145 px | 5–6 panels below |
| Ticking the rotating track at 1.35 M☉ | 0 (absorbed) | +33 px | +21 px | 6 panels below |

- **Why.** `.rot-control`'s 316 px floor was set from a single "311 px at ~512 px" measurement
  taken before the inclination facet grew its orientation-grid row; it now needs 351 / 369 /
  405. And `.controls-panel`'s 992 / 1060 floors miss the gateway's tallest state entirely —
  `panelmax.mjs` puts max non-rotation content at 717 / 794 / 870 (at 6.5 M☉, [Fe/H] −1.5,
  where the hedge caption alone is 158 / 196 / 253 px).
- **The arithmetic.** Required panel floor = max(non-rotation content) + rotation floor →
  **1129 base / 1205 phone** against today's 992 / 1060.
- **The trade, and why it is not obvious.** Closing the jumps costs ~137 px (desktop) and
  ~145 px (phone) of *permanent* bottom slack on every star — more whitespace than the ~180 px
  V1 was opened to remove. Raising the floors and V1 pull in opposite directions.
- **A third option — with a hard limit on it.** Both floors are dominated by ONE caption: the
  two-sided uncertain-fate hedge in the gateway (`panelmax.mjs` prints `gateway`). Shortening it
  would shrink the jump *and* the reservation instead of trading one for the other. **But its
  length is a CONSTRAINT, not the variable being optimised.** That caption is the 3rd honesty
  gate — hedged on both sides deliberately, with a measured lower edge and a cited 8 M☉ ceiling
  ([[star-sim-uncertain-fate-band]]) — and it is 158/196/253 px tall because refusing to give a
  false verdict takes words. Trimming a hedge to fit a pixel budget is the "never paint a false
  caption" rule inverted, and it is the failure this project keeps re-learning. The floors move
  to fit the caption; the caption does not shrink to fit the floors. Whoever picks this row up
  may re-word for density only if the hedge still refuses the verdict on both sides — and if it
  cannot, the answer is to leave every number here alone and close the row as "measured → skip".
- **Acceptance.** `jumpcheck.mjs` reports no moved panels in either trigger, at all three widths.

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
