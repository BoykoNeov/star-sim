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
| `gatenote.mjs` | the `#incl-gate-note` floor against the state space that actually selects its text — **[Fe/H] × mass**, not mass alone, because the rotating-track toggle's visibility moves with metallicity — at 1440 / 512 / **481** / 390, reading the floor off the page rather than hardcoding it | `node gatenote.mjs` |
| `jumpcheck.mjs` | whether a state change actually **moves a neighbouring panel** — every panel's top/height before and after the two known overflow states. The difference between a real jump and a floor that is merely undersized on paper | `node jumpcheck.mjs` |
| `innerjump.mjs` | whether the rotation section overflowing its floor moves anything **inside** the Controls panel (age slider, gateway). `jumpcheck.mjs` only snapshots `main > section`, so it is blind to a within-panel shove — at 1440 the panel's own floor absorbs the growth and jumpcheck reports clean while the age slider drops 36 px | `node innerjump.mjs` |
| `notefit.mjs` | how tall `#incl-gate-note` may be for a given `.rot-control` floor: the content above the note in the **tightest note-showing** state, measured order-independently so it stays right if the note stops being the last child | `node notefit.mjs` |
| `edge481.mjs` | both base-rule maxima at **481 px**, the binding width for the default rule (the phone rule starts at 480), with the rotating-track click **asserted** — an unasserted click that silently fails is indistinguishable from a short state | `node edge481.mjs` |
| `phonegap.mjs` | a child-by-child breakdown of the Controls panel in one state, when a floor comes out short and you need to know which term is wrong before raising the constant | `node phonegap.mjs` |
| `panelshot2.mjs` | the Controls panel in the **three states that vary** (default star · the hedge caption · the rotating track ticked) at 1440 / 481 / 390 — `panelshot.mjs` shoots only the Sun, which cannot show a reservation change in the states that drove it | `node panelshot2.mjs <suffix>` → `panel2-<suffix>/` |
| `panelshot.mjs` | just the Controls panel, desktop + phone, so a reserved-space change can be compared without diffing a 4000 px full-page shot | `node panelshot.mjs <suffix>` → `panel-<suffix>/` |
| `panelfloor.mjs` | **any** panel's floor (`ctlfloor.mjs` generalised): natural max **and min** (the min is what the floor costs in blank), the **rendered** height with the floor in place (`min === max` is the acceptance line), the tallest state's child-by-child breakdown, and **each child's own max over the sweep** — the number that decides "raise one element's reserve" vs "raise the panel". Each panel is swept over **its own** controls, not the star's | `node panelfloor.mjs <observer\|structure> [width …]` |
| `rowgaps.mjs` · `rowgaps2.mjs` · `rowgaps3.mjs` · `rowgaps4.mjs` · `rowgaps5.mjs` | the dashboard's **dead space between wrap rows** — per row, per panel, per width. `rowgaps` measures the page as served; `2` compares candidate orders; `3` sweeps four star states; `4` adds the **round-trip check** that exposes half-settled boxes after a JS reorder; **`5` is the one to trust** — it loads the old commit's `index.html` through a request intercept, so both orders are measured natively | `node rowgaps5.mjs [width …]` |
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

### V1b. The reserved floors were UNDERSIZED — three measured jumps · **shipped 2026-09-06**

Found while measuring V1, pre-existing, and **not** caused by it (the numbers below reproduce
with the note reverted). `jumpcheck.mjs` records every panel's box before/after a state change,
so these were confirmed movements, not bookkeeping:

| Trigger | 1440 | 512 | 390 | What moved |
|---|---|---|---|---|
| Mass → 6.5 M☉ at [Fe/H] −1.5 (the two-sided uncertain-fate hedge) | +60 px | +137 px | +145 px | 5–6 neighbouring panels |
| Ticking the rotating track at 1.35 M☉ | +36 px | +53 px | +89 px | the age slider + gateway, **inside** the panel |
| …the same click, measured at panel level | 0 | +33 px | +21 px | 6 neighbouring panels |

**The 1440 row is the one the original write-up got wrong.** It read "0 (absorbed)", because
`jumpcheck.mjs` only snapshots `main > section` and at that width the panel's own floor swallowed
the growth — no neighbour moved. `innerjump.mjs` (new) watches the panel's *children* and shows
the age slider and the whole endgame gateway sliding 36 px down under the cursor. A panel-level
acceptance check could never have caught it, which is why acceptance now needs both scripts.

**What shipped.** Every constant re-measured at each regime's binding width and raised:

| | `.rot-control` | `.controls-panel` | `#incl-gate-note` |
|---|---|---|---|
| base (> 480 px) | 316 → **376** | 992 → **1214** | 100 → **160** |
| phone (≤ 480 px) | *(none)* → **412** | 1060 → **1308** | 64 → *(none needed)* |

- **The arithmetic is exact, not conservative.** Once a rotation floor covers that section's
  tallest state, the section renders at exactly the floor in *every* state — so the panel needs
  `max(content outside the section) + that floor + 19`, and the sum is the requirement rather
  than an upper bound. Measured: base `813 + 376 + 19 = 1208 → 1214`, phone `870 + 412 + 19 =
  1301 → 1308`. The margin is applied once, at the end, so it is not double-counted.
- **The +19 is the panel's own bottom padding + border + trailing margin,** and leaving it out
  is the mistake this row made on its first pass. The measured "content" term runs from the
  panel's box top to its lowest child's bottom: it carries the *top* padding but not the bottom
  one, while `min-height` is a border-box height that must cover both. Symptom: the phone still
  jumped 13 px after the raise. Any future floor derived from a `panelUsed`-style number owes
  the same +19.
- **481 px is the binding width for the default rule, not 512.** The phone rule only starts at
  480, and those 31 px of extra wrapping cost the gateway caption another 19 px (813 vs 794).
  Sizing at 512 — which is what every earlier floor here did — leaves the rule short over its
  own narrowest 32 px, and the acceptance run passes anyway because it never visits them. 481
  is now in `jumpcheck.mjs`'s width list. The phone rule is sized at 390; 360 measures
  identically, so 390 covers the narrow end.
- **The gate note's two regimes coincide.** Its ceiling is `floor − content above it − its top
  margin`: `376 − 198 − 12` and `412 − 234 − 12` both give 166 → 160. So the ≤ 480 override is
  gone rather than duplicated. `gatenote.mjs` now reads the floor off the page instead of
  hardcoding it, and reports 6 px headroom and zero overflows across the whole [Fe/H] × mass
  sweep at **all four** widths — 481 included, where the section's lines turn out not to rewrap
  (370 used, same as 512). **The coincidence is a coupling:** the single note value is safe only
  because the two rotation floors and the two content-above values differ by the same 36 px.
  Change either floor and both must be re-derived; the CSS comment says so.
- **The cost, stated plainly.** +222 px (desktop) and +248 px (phone) of *permanent* bottom slack
  on every star — more than the ~140 px this row estimated, and more than the ~180 px V1 was
  opened to remove. The estimate was low because it read the raw observed panel heights out of
  `jumpcheck.mjs` instead of adding the two reservations. This is the honest price of "panels
  never change size on slider/click" and it is now paid in full. **V2 (row-height pairing) is the
  mitigation** — a taller Controls panel makes the pairing worse — but it is a separate row and
  was not folded in here.
- **The hedge caption was not touched.** It remains the single dominant term (215 px at 481, 253
  at 390) and the 3rd honesty gate ([[star-sim-uncertain-fate-band]]). The third option this row
  recorded — shorten it — was declined: the floors move to fit the caption, never the reverse.
- **One artefact seen and explained.** At an intermediate value (1196) the seismology panel's own
  height changed by 19 px between the two states while its top stayed put. It is a flex-row
  stretch effect — a taller Controls panel re-pairs the wrap rows — and it disappeared at the
  final 1214. Nothing moved in either case; it is V2's subject, not a floor bug.
- **Acceptance (met).** `jumpcheck.mjs` reports **no moved panels** in either trigger at
  **1440 / 512 / 481 / 390**, *and* `innerjump.mjs` reports nothing moving inside the panel at
  all three widths (only the gateway's own caption reflowing ±3 px in place, with nothing below
  it). Zero console errors throughout. Screenshots: `temp/star-sim-perf/panel2-{before,after2}/`,
  three states × three widths.

### V2. Row-height imbalance in the two-column layout · **shipped 2026-09-06**

- **What it was.** `main` is a flex-wrap grid; a wrap row is as tall as its tallest panel,
  so every shorter panel in that row leaves a hole beneath it until the next row starts.
  The authored order paired short with tall throughout (state readout 303 px beside
  Controls 1024, Composition 464 beside Observer 675, Spectrum 487 beside SED 830).
- **Option (b) was already spent.** The row's first suggestion — `align-items: flex-start`
  so panels stop stretching — has been on `main` since the dashboard was built. Panels were
  already ragged-bottom; the dead space was never *inside* a panel, it was **between rows**.
  Measure before quoting a plan row: the fix it proposes may already be in the file.
- **Measured** (`rowgaps.mjs`, new — per row, per panel, through the served page): at 1440
  the old order left **1453 px** of dead space on a 5070 px page. A pure tallest-first sort
  takes that to **424 px** — the size of the prize.
- **Shipped** the authored order in `index.html` (a pure block move; `layout.js` reads the
  DOM order as the default *before* applying a saved one, so anyone who has dragged panels
  keeps theirs): star + HR · composition + spectrum · Controls + interior/MESA · SED +
  Lane–Emden · observer + seismology · **readout last and alone** (the shortest panel, so
  standing by itself costs nothing).
- **Every packing regime, both orders loaded natively** (`rowgaps5.mjs`) — the dashboard packs
  2 columns to ~1590 px, 3 to ~2050, 5 at 2560, and one column on a phone:

  | width | dead space (old → shipped) | page height (old → shipped) |
  |---|---|---|
  | 1280 | 1435 → **416** | 5070 → **4267** |
  | 1440 | 1453 → **434** | 5070 → **4267** |
  | 1600 | 2015 → **1438** | 3660 → **3300** |
  | 1920 | 2243 → **1541** | 3660 → **3300** |
  | 2560 | 2275 → **2174** | 2824 → **2297** |
  | 390 | 0 → 0 | 8697 → 8697 |

  The white-dwarf endgame improves on the same order (905 → **287 px** at 1440). **Read both
  columns at the wide end:** at 2560 the dead-space win collapses to ~100 px while the page
  still gets **527 px shorter** — with five panels per row the holes move between rows rather
  than disappearing, so dead space stops being the metric a reader feels and page height is.
- **Held to a defensible reading order, and the cheaper option rejected in writing.** The
  best-packing order (`C`: Controls, interior, SED, Lane–Emden, observer, seismology,
  spectrum, composition, readout) is **identical at 1280/1440** and only wins at ≥ 1600 px
  (1136 vs 1541 at 1920, 1729 vs 2174 at 2560) — and it buries the composition panel tenth,
  when the spec's three core views are the 3D star, the HR diagram and composition. **The
  price of refusing it is width-dependent and largest on very wide monitors**: nothing at
  1280/1440, ~400 px at 1920, ~450 px at 2560. Still not worth demoting a core view, but say
  so as a range rather than as one number; the arithmetic is in the `index.html` comment so
  the next person does not re-derive it.
- **Robust across the star, because the floors already made it so.** Sun / 15 M☉ / 0.3 M☉
  give *identical* numbers — V1b's and V6's reserved floors hold every panel's height fixed,
  which is what makes a static authored order meaningful at all. The endgame, which tears
  down the living-only panels, improves on the same order rather than needing its own.
- **The phone is untouched in packing and changed in sequence.** 390 px is one column,
  0 px of dead space before and after; what does change there is the reading order, and the
  state readout moves from 7th to last. Accepted: on a phone the pinned strip already
  carries mass, `[Fe/H]` and age, and a drag reorders anything a user prefers.
- **The one hidden panel a click can reach was measured too.** `#hz-history-panel` and the
  Roche panel were *placed* by judgement (both are hidden by default). The habitable-zone
  toggle un-hides the first, so it was swept: shipped beats the old order in that state at
  every width (1440 **749 vs 1317**, 1600 1620 vs 1936, 1920 1778 vs 2519, 2560 2417 vs 2729).
  It costs 315 px against the no-HZ layout, because it lands on the readout's otherwise-free
  last row. The **Roche panel's position is still unmeasured** — it needs binary mode — and
  the `index.html` comment says so rather than letting the whole comment read as measured.
- **A measurement trap worth more than the row.** The first candidate sweeps reordered the
  live DOM and measured 500 ms later. That is wrong at 3+ columns: reordering changes each
  panel's WIDTH, and the canvas heights follow width through a `ResizeObserver`, so the boxes
  are still settling. It reported the shipped order at 1282 px dead at 1600 where a native
  load measures 1438. **A round-trip caught it** — re-apply the order the page already has
  and it must reproduce its own native numbers; at 1600 and 2560 it did not. The fix is
  `rowgaps5.mjs`: intercept the *document* request and fulfil it with the old commit's
  `index.html` while the modules and API come from the live server. That commit changed
  nothing else under `frontend/`, so it is the old page, loaded natively. (A second uvicorn
  on the old commit was tried first and is a dead end — the venv's editable install resolves
  `star_sim` to the working tree, so it would serve the *new* frontend.)
- **Acceptance.** 1440 full-page screenshot (`shots.mjs v2order`), both orders loaded
  natively at five widths plus the phone, 73 JS tests unchanged, zero console errors.

### V3. Verify the parked render loop against the screenshot pass · **verified 2026-09-06 (with V2)**

The loop now parks when `#star-canvas` leaves the viewport. Playwright's element
screenshot scrolls the element into view and the observer restarts the loop on the next
tick, so a `canvas.screenshot()` taken *immediately* after a scroll could capture the last
frame before restart (still a valid frame, just not the newest uniforms). If a future
screenshot pass ever sees a stale star, add a `page.waitForTimeout(100)` after the scroll
— do not remove the gate.

**Checked with V2's acceptance run:** `shots.mjs` at 15 M☉ late returns a red-supergiant
disk (dim granulation, warm limb), not the previous star's frame, at both 1440 and 390.
No `waitForTimeout` was needed; the row stays here as the diagnosis to reach for *if* a
future pass ever does capture a stale frame.

### V4. Things checked and found fine (do not re-propose)

- The 3D star at 358 px on a 390 px phone: granulation resolves, the AA fade works.
- The M1 I red supergiant: the disk reads as a giant (dim granulation, warm limb).
- HR class bands, iso-radius diagonals, the "→ white dwarf" leader: legible at both widths.
- Real-GPU frame time is vsync-bound in every state measured.

### V5. The three primary controls pinned above every panel · **shipped 2026-09-06**

- **The report.** "Make the 3 main controls always on top and scroll with the page,
  because many panels change with them and it is not convenient to scroll to only the
  panel that changes them." Every panel is a function of mass, `[Fe/H]` and age, so the
  one panel that carried them was the one you had to keep scrolling back to.
- **What shipped.** Mass, `[Fe/H]` and age (label + slider + tick strip + `datalist`,
  plus `#endgame-age-caption` and `#endgame-resnap-note`, which explain those two
  sliders) left `.controls-panel` for `#primary-controls`, a `position: sticky` strip
  between `<header>` and `<main>`. **Moved as markup, not duplicated and not relocated
  at boot** — every id is unchanged, so all 23 `wire*()` handlers, `buildTickStrip`,
  `commitNumber` and the `body.*-mode` age tags work untouched, and the three CSS rules
  that were scoped to `.controls-panel` were **widened**, not copied. A pointer note
  stays behind in the panel, the `.controls-overlay-pointer` idiom.
- **`relocateOverlayControls()` is the same complaint with the other answer**, and the
  split is now written down in both places: a control that drives ONE panel moves to
  that panel; a control that drives EVERY panel has no panel to move to, so it is
  pinned.
- **Two floors, because a pinned box is stricter than a panel** — it sits *over* the
  content, so a reflow inside it moves the whole page at once, and unlike a panel it
  cannot grow into a flex row's slack.

  | | live | endgame (`wd`/`wr`/`sn`/`stripped`) |
  |---|---|---|
  | measured tallest | 128 px | 169 px |
  | `min-height` | **136 px** | **176 px** |

  Live is **114 px in 1,015 of 1,020 states sampled** (`stripmax3.mjs`: 17 `[Fe/H]` ×
  60 masses) and 128 px in five — around `[Fe/H]` +0.45, ~36 M☉, where the age landmarks
  crowd enough to stagger the tick labels onto a second row. That 1-in-200 state is
  exactly what a coarse sweep misses; three rows never occur. **One floor for both modes
  was rejected**: the endgame caption is `display:none` while the star is alive, so a
  single floor would hold dead *pinned* space in the view the user actually scrolls.
- **The endgame floor was wrong twice, both times for the same reason — one width.** The
  first pass measured 204 px at 1440 and reserved 216. Re-measured across the whole pinned
  regime (`endfloor.mjs`), the *steady* endgame strip was 164 px at 1440 but **242 px at
  800**, because `#endgame-age-caption` sat inside the age COLUMN — a ~150-character
  sentence in a 236 px column is six lines. So 216 was simultaneously ~50 px of dead
  pinned space on a desktop **and 26 px short** where the rule actually has to hold. Two
  changes fixed both:
  - **the caption now spans the strip** instead of one column — one or two lines at every
    pinned width (35–38 px), which is what makes a small floor affordable;
  - **the re-snap note moved out of flow**, hanging below the strip with its own opaque
    background. It is a one-shot message after a reverted drag; reserving its two lines in
    a pinned box cost ~40 px of permanent blank in every endgame view. Out of flow it can
    neither shove the mass slider under the cursor nor move a panel — verified: the note
    fires and **no panel's box changes** at 1440 / 800 / 390 (`resnapshot.mjs`).

  After both: 151 / 166 / **169** px at 1440 / 1024 / 800, floored at **176**. The worst
  case is checked against the caption text, not just an age sweep: `capmax.mjs` injects the
  seven longest strings the code can build — including the stripped-star "Snapped:" and the
  co-binary accretion clause, which the three gateway buttons cannot reach — and the tallest
  is still 38 px.
- **Sticky only above 800 px.** Three 230 px columns + two 22 px gaps = 734 px, so the
  strip holds one row down to a 782 px viewport. Wrapped it measures 215 px at 761 and
  316 px at 390 — more viewport than the scrolling it saves — so below 800 px it drops
  to `position: static` and is simply the first block on the page.
- **The knock-on the row had to pay: `.controls-panel`'s floor was now wrong.** 1214 /
  1308 px were measured in V1b *with* those three rows in the panel; left alone they
  would hold ~300 px of void. Re-measured with `ctlfloor.mjs`, which reads the panel's
  natural height by setting its own `min-height` to 0 inline and taking `offsetHeight`
  — that includes the child margins (the `.slider-wrap` tick reservations) a
  bounding-box-of-children sweep drops, so V1b's `+19` correction is not needed twice.
  The tallest state is still the two-sided uncertain-fate hedge (6.5 M☉, `[Fe/H]` −1.5),
  not any endgame: the SN narration measures ~240 px (481) / ~205 px (390) shorter.

  | width | measured tallest | old floor | new floor |
  |---|---|---|---|
  | 1440 (default rule, not binding) | 902 px | 1214 | — |
  | **481** (default rule's binding width) | **1017 px** | 1214 | **1024** |
  | **390** (phone rule) | **1130 px** | 1308 | **1140** |

  That is 190 px of dead panel height returned on a desktop and 168 px on a phone — the
  strip costs 136 px back, so the page is a little shorter overall and the Controls panel
  no longer ends in a void.
- **New in the harness:** `stripmax.mjs` (live + every endgame, entered for real through
  the gateway buttons, including forcing the re-snap note by dragging the mass into a
  fate the endgame cannot hold), `stripmax2/3.mjs` (dense live sweeps for the tick-row
  term), `ctlfloor.mjs` (the panel floor, re-measurable after any content move) and
  `stripshot.mjs` (the strip pinned vs scrolled at five widths). `jumpcheck.mjs` now
  snapshots `#primary-controls` and its three columns as well as `main > section` — the
  strip is not a `main > section`, so without that the acceptance check was blind to the
  one box whose reflow moves everything.
- **Acceptance (met).** `jumpcheck.mjs` at 1440 / 1024 / 800 / 512 / 481 / 390 — the
  first three are the whole *pinned* regime, added because a strip verified only at 1440
  is unverified over most of the widths it is pinned at; the last three exercise the
  panel's floors while the strip is static. The Controls panel
  renders at exactly its new floor (1024 above 480 px, 1140 below) in the Sun state, the
  uncertain-fate hedge state and across the rotating-track click, with **no panel moved**;
  the strip holds its floor through the two-tick-row state at every pinned width, its
  three columns unmoved. `innerjump.mjs` (now watching `#primary-controls` as well as the
  panel's own children) reports **nothing moved inside the panel** at 1440 / 512 / 390.
  The strip measures exactly 176 px in both the WD and SN endgames. Zero console errors in
  every run. Screenshots: `temp/star-sim-perf/strip-after/` (pinned vs scrolled at five
  widths), `stripend-after2/` (the two endgames) and `resnap-after/` (the out-of-flow
  note over the first panel row).
  **Two caveats stated rather than papered over.** (1) `jumpcheck`'s new third state
  compares 36 M☉ against the Sun, so the *unfloored* panels legitimately change height
  with their own content there; the diff is filtered to the strip so that noise cannot be
  misread as a jump. (2) Adding 1024 to the width list surfaced **two floors that are
  short — pre-existing, unrelated to this row, and recorded not fixed** (see V6).

### V6. Two more reserved floors are short · *fixed 2026-09-06*

Surfaced by V5's wider `jumpcheck` sweep. Neither is caused by the pinned strip — both are
panels whose own content differs from star to star. Both were short **for the same reason, and
it is the lesson worth keeping**: a floor is only as good as the state space it was swept over,
and *each panel's state space is its own controls, not the star's*. V6's first pass measured
both panels with the Controls panel's trigger (drag to 6.5 M☉ at `[Fe/H]` −1.5) and so
under-measured one of them by 18 px.

| Width | Panel | Before | After |
|---|---|---|---|
| base rule (sized at **481**) | `.observer-panel` | **no floor at all** | `min-height: 675px` |
| phone rule (sized at **390**) | `.observer-panel` | **no floor at all** | `min-height: 715px` |
| base rule (sized at **481**) | `.structure-panel` | 855 — short by **27**, not the 9 first recorded | `min-height: 890px` |
| phone rule (sized at **390**) | `.structure-panel` | 910 — natural max is 882, already covered | unchanged |

**The measured maxima** (`panelfloor.mjs`, which generalises `ctlfloor.mjs` to any panel;
natural height read by zeroing the panel's own `min-height` inline and taking `offsetHeight`):

| viewport | panel width | observer max | structure max |
|---|---|---|---|
| 1440 | 688 px (2 columns) | 643 | 742 |
| 1024 | 480 px (2 columns) | **668** | 742 |
| 512 | 464 px | 668 | 841 |
| **481** | **433 px** | **668** | **882** |
| 390 | 342 px | **707** | 882 |

**481 is the binding width and it covers everything wider for free.** The dashboard packs two
columns at *both* 1024 and 1440, so 1440 gives the **widest** panel (688 px), not the narrowest —
1024 is where the shift happened to be visible, not a wrapping regime needing a third rule.

**Two mechanisms, and which one each note gets.** The panel `min-height` is the dashboard-level
guarantee (neighbours don't move); a per-element reserve is what keeps the *within-panel* stack
still. The rule that decides between them was already written down for `#isochrone-note` /
`#population-note` and applies unchanged here: **a note that is LAST in its panel is absorbed by
the panel floor and needs no reserve of its own; one with siblings below it needs one**, because
its extra line shoves them.

- `#observer-readout` (three dust/distance sliders below it) reached **3 lines / 43 px** against
  a 2-line `2.8em` reserve → raised to `3.5em`. This is what actually caused the 1024 symptom,
  and fixing it at the source removed the variation rather than hiding it: the observer panel's
  *natural* height is now constant at 670 px across all 105 swept states at 1024.
- `#observer-note` is last in its panel → no reserve; its 18 px of growth at 390 is absorbed by
  the 715 floor.
- `#structure-caption` (readout and note below it) reaches **3 lines / 54 px** at a 433 px panel,
  while `.lane-caption`'s base reserve is 2 lines — that comment sized 2 lines for a panel
  "≥460px", and at a 481 px viewport the panel is 433. Given the phone reserve at every width,
  **scoped to the id**: `.lane-caption` is shared with the Lane–Emden and Roche captions, whose
  own longest strings were not re-measured here.
- `#structure-note` is last in its panel → no reserve.

**What the sweep had to cover, and why the first pass missed it.** `ctlfloor.mjs` sweeps mass ×
`[Fe/H]` × the rotating-track toggle because those are what move the *Controls* panel. Neither
of these panels is driven by that:
- the observer panel's two variable notes are driven by **its own three sliders** (distance,
  A_V, R_V), which that sweep never touches. Swept over those, and — the `capmax.mjs`
  discipline — the readout is *also* checked against the longest string the code can **build**
  (four sign/digit extremes injected straight into the live element), not merely whichever
  state a sweep happened to visit. Both agree on 43 px.
- the structure panel's tallest text is the snapped-far note, which needs the request off the
  partial MESA grid in **mass and metallicity at once**: 0.1 M☉ at `[Fe/H]` −1.5 measures
  **882 px**. A gateway-shaped mass list (0.3, 1, 1.35, 5, 6.5, 7, 7.5, 8, 20, 60, 200) never
  visits it, which is exactly how "short by 9" was recorded for something short by 27.

**The price, stated rather than buried.** A floor is permanent blank space in every state below
it. Against the *shortest* reachable state: the observer panel holds 0 px at 481/512/1024, 23 px
at 1440 and 24 px at 390; the structure panel holds 184 px at 1440, 62 px at 481 and 82 px at
390. **Most of that wide-width void is pre-existing**, not bought here — the old 855 floor
already held 149 px at 1440; this raise adds **35**. The structure panel is short at wide widths
because *every* text block in it un-wraps: at a 688 px panel the intro is 73 px (vs 110), the
legend 43 (vs 67), the readout 83 (vs 145) and the note 36 (vs 54), while the canvas stays 340.

A third media tier for wide viewports would genuinely recover ~140 px there, and it is the
obvious next thought — but it is **not** a safe one-liner, for a reason worth writing down:
**panel width is not monotonic in viewport width.** `.panel` is `flex: 1 1 460px; max-width:
700px` in a wrap container with 24 px dashboard padding and a 16 px gap, so two columns first fit
at a viewport of 984 px. At **983** the dashboard is one column and the panel is **700 px** wide
(and short); at **984** it becomes two columns and the panel drops to **460 px** (and tall). A
`min-width: 1200px` tier is safe; anything lower straddles that cliff. There is a second cliff
just above the binding width — a 480 px panel (1024 viewport) measures 742 px while a 464 px one
(512 viewport) measures 841, so ~16 px of width crosses several wrap boundaries at once. Sizing
at 481 covers both cliffs, which is exactly why the two-tier rule holds. Left as-is.

**Acceptance (met).** Stronger than this section's original recipe, which proposed a single
`jumpcheck 1024` state pair — a floor can still be short where jumpcheck does not look. Instead,
V5's standard: **every swept state renders at exactly the floor.** `panelfloor.mjs` at 1440 /
1024 / 512 / 481 / 390 reports the observer panel at **675 px in all 105 states** at every base
width and **715 px** at 390, and the structure panel at **890 px in all 165 states** at every
base width and **910 px** at 390 — `min === max` everywhere. Plus `jumpcheck.mjs` at all six
widths with no panel moved, and the Playwright screenshot pass at 1440 + 390.

**New in the harness:** `panelfloor.mjs <observer|structure> [width …]` — the generalised floor
measurer. It reports the natural max *and* min (the min is the price of the floor), the
**rendered** height with the floor in place (`min === max` is the acceptance line), the tallest
state's child-by-child breakdown, and **each child's own max over the whole sweep** — which is
the number you need to decide whether to raise one element's reserve or the whole panel.

**One pre-existing thing found and deliberately not fixed here:** `/photometry_track?mass=0.1&
feh=0.25` returns 422 — a real corner of MIST's non-rectangular domain. `refreshPhotometryTrack`
catches it, clears the locus and stays retryable, so the only trace is the browser's own
"failed to load resource" line; the panel's height is unaffected (the CMD canvas is fixed). It
is an honesty-gate question, not a layout one, so it is recorded rather than folded into a
reservation change.

**One limit of the structure sweep, stated so the next raise knows to close it.** The age axis
was sampled at **three points** (slider 0 / 0.5 / 1), not bounded against the set of strings it
can produce. The caption embeds the snapshot's `phase`, so a longer phase name than the three
samples happened to hit is one wrapped line — **18 px**, which the floor's 8 px of margin over
882 would not absorb. The tallest state came out at `ageFrac: 0` at every width, and the fix if
this ever matters is the `capmax.mjs` move: inject the bounded phase-string set into the live
caption rather than sampling the axis. **Re-measure if a phase name changes.** (`.lane-caption`'s
reserve is likewise ordered above the phone rule and named in its selector list — an id outside a
media query would otherwise outrank that rule in both directions, so a later raise of the phone
value would silently stop applying to `#structure-caption` while still reading as if it did.)

**The trap from the first pass still stands:** the harness measures the *served* app, which reads
`frontend/index.html` off disk on every load. Editing a served file while a sweep is in flight
hands the browser a half-written page — it failed with `#feh-num` not found, which reads exactly
like a real regression. Don't touch `frontend/` while a harness run is going.
