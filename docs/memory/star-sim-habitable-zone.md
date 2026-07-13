---
name: star-sim-habitable-zone
description: "Axis D of the outward quartet — the circumstellar habitable zone from L+Teff (Kopparapu 2014). D1 = the band on the true-size scale bar (hz.js + scale.js). D2a = the HZ-HISTORY panel (hzhist.js, distance-vs-age hockey stick, LINEAR age not log). D2b = the Continuously Habitable Zone annulus + measured Earth-exit deadline in hzhist.js. ALL BUILT (D1/D2a/D2b); axis complete."
metadata: 
  node_type: memory
  type: project
  originSessionId: 80959481-33ff-4949-b37d-cc40d832fdb4
---

**Axis D — the habitable-zone band. D1 BUILT 2026-07-10** (frontend-only, no backend
change, 412 pytest unchanged, Playwright 1440+390 zero console errors). The third of the
outward quartet's four axes to ship (after [[star-sim-isochrone-cluster]] Axis B); the
scope-edge axis (edges toward planets).

## What it is
The circumstellar liquid-water zone drawn on the true-size **scale bar** (rides
`scale.js`, like the swallowed-orbit rings). A pure **VIEW** of two `StellarState`
numbers — **L + Teff** — that never touches the HR marker. The payoff is watching the
band **march outward** as the star brightens up the giant branch (Earth's fate: the zone
sweeps past 1 AU, then the swelling giant engulfs Earth).

## Architecture (the split)
- **`frontend/src/hz.js`** — the PURE compute: `habitableZone(Teff, L)` → the four edge
  distances in AU, or `null` out of range; `inRange(Teff)` gate; `TEFF_MIN/MAX`. A
  helper-to-a-drawing-module (the SED/gravdark precedent), unit-checkable in isolation.
- **`scale.js`** — the DRAW half: `setHZ(on)` (retained flag, redraws from the scale
  bar's retained Teff/L/R — the `sed.js setPopulation` idiom), `drawHZ()`, the caption
  branch `describeHZ()`, and axis widening in `update()`/`redrawFromRetained()`.
- **`main.js`** — `hzOn` state, `#hz-toggle` listener (guarded to live mode),
  `dropHZForModeSwitch()` in the shared `dropHeliumForModeSwitch()` chokepoint.
- **`styles.css`** — `.hz-toggle-row` hidden in wd/wr/sn/stripped modes.

## The physics (Tier-2, labeled)
**Kopparapu et al. 2014** (ApJ 787, L29 — the *corrected* update, NOT 2013), 1 M⊕:
`S_eff = S_eff⊙ + a·T* + b·T*² + c·T*³ + d·T*⁴`, `T* = Teff − 5780 K`, then
`d = √((L/L⊙)/S_eff)` AU. **Four internally-consistent edges** drawn as nested bands:
- solid **conservative** band: runaway greenhouse (inner) → maximum greenhouse (outer)
- dashed **optimistic** edges: recent Venus (inner) → early Mars (outer)
- **moist greenhouse DROPPED** — the 2014 runaway revision moved *inside* the un-revised
  2013 moist edge, so mixing them is inconsistent; the 2014 paper itself omits it.

Coefficients (verify against the solar anchor if ever re-touched — Sun T*=0 → runaway
**0.95 AU**, maxGH **1.68 AU**, recent Venus 0.75, early Mars 1.77; these 4 numbers are
the guard on any transcription). Pulled from the paper via ar5iv, NOT memory.

## The two load-bearing honesty gates (advisor-driven)
1. **Measure-first: validate coefficients against the solar anchor BEFORE drawing.** A
   wrong coefficient is a plausible-but-wrong band a screenshot can't catch. Ran a
   standalone `node` check of `hz.js` first (Sun → 0.95/1.68 exactly) → only then wired
   the canvas.
2. **The quartic DIVERGES outside 2600–7200 K** (not just loses accuracy — T*⁴ explodes,
   S_eff goes negative, √ → NaN/absurd distance that breaks the draw). So `inRange()`
   skips the compute AND the band entirely, never extrapolates. The band honestly
   **blinks off** for hot stars (Teff>7200) with an out-of-range caption — an evolving
   star crossing 7200 K is expected, the caption owns it. A 1 M☉ MS→RGB stays in range.

## Scoping decisions (what's IN vs OUT, and why)
- **Only L + Teff enter.** Mass/gravity/composition/rotation do NOT enter Kopparapu —
  deliberately excluded (the "don't fake a feature" rule).
- **Spectrum enters THROUGH Teff** — the near-IR albedo/absorption climate effect IS the
  Teff-dependence of the coefficients. NO `/spectrum` coupling (would fake precision).
- **UV/X-ray/flares OUT of the band** — a separate, speculative habitability hazard (not
  the liquid-water energy-balance zone). Owned by the caption caveat (M-dwarf flares).
- **Planet mass fixed at 1 M⊕** — no planetary sandbox (restrained overlay).
- **R_rsun** doesn't set the edges but drives engulfment (the scale bar's swallowed-orbit
  rings) — the "giant swallows Earth" story.

## Axis widening (the SN idiom)
The scale bar maxes at 1500 R☉ (~7 AU), but a luminous giant's HZ is tens of AU ≈
thousands of R☉. When `earlyMars·215 > R_MAX`, `hzWide` extends `logHi` to fit it and
`drawOrbits` swaps in the outer-planet set (Mercury→Neptune, reuses `ORBITS_SN`) so the
band lands against Neptune's orbit, not a bare edge. `logLo` stays at `LOG_LO` so the
star's own radius marker always shows. SN mode always wins (HZ never composes with it).

## Gate 0 (PASSED through the runtime)
- Sun: 0.98–1.7 AU (evolved; standalone ZAMS = 0.95/1.68) straddling Earth's ring.
- Same 1 M☉ at old age → **34–65 AU past Neptune**, axis widened, Earth "left inside the
  conservative inner edge."
- K/M dwarf zones correctly **closer in** (0.55 M☉ → 0.24–0.45 AU).
- Hot star (Teff 12637 K) → out of range, no band, honest caption.
- Teardown verified: entering stripped-mode hides the toggle + drops the band (no leak).

## Advisor's caught bug (fixed before commit)
The faint-star caption clause said "the zone lies **farther out**" — BACKWARDS. A faint
star's HZ is **closer in** (smaller AU); Earth is too cold *because* the zone is closer.
Hits most K/M dwarfs. Fixed to "this faint star's zone lies closer in." (I'd truncated the
K-dwarf screenshot caption, so it slipped my own Gate 0 — read captions in full.)

## D2a — the HZ-history panel. BUILT 2026-07-13 (frontend-only, no backend, Playwright 1440+390, zero console errors)
The **temporal twin** of the scale-bar band (D1 is spatial/single-age; D2 is all-ages-at-once). A
dedicated panel `#hz-history-panel` (`frontend/src/hzhist.js`) plotting the whole life's HZ as
**distance vs age** so the outward march is legible on ONE static figure — the iconic hockey stick
(slow MS creep, then the giant-branch blow-up to ~68 AU). **A pure pushed-data consumer like
`cmd.js`/`roche.js`** (NOT a hz.js-importing sibling): `main.js` `buildHZSeries(currentTrack)` maps
each row through the SHARED `hz.js` `habitableZone()` → `{age, …4 edges}` or `{age, oor:true}`, pushed
via `hzhist.setTrack`; the age scrub pushes `hzhist.setNow(age)`. No fetch, no backend, no StellarState
touch. Governed by the **SAME `#hz-toggle`** as the scale-bar band (one concept, two views — the
population-toggle idiom; `syncHZHistory()` shows/hides + pushes, `dropHZForModeSwitch` tears both down).

**THE X-AXIS WAS RE-DECIDED against a real Sun render (advisor catch — the plan's "log yr" was
BACKWARDS).** Log *compresses* late ages: measured on 1 M☉, the giant march (inner edge 1.5→10 AU)
falls between log-age fraction **0.985 and 0.998** — log-X crushes the entire payoff into the last
~1.5% against the right frame. **LINEAR age** spreads the giant cliff over the last ~8% AND keeps the
slow MS creep + Earth's ~5.05 Gyr inner-edge crossing readable mid-axis (serves both D2a and the future
D2b). **y = log AU** (edges span ~2 decades, 0.8→~70 AU). *Always inspect the real `age_yr` array +
a marquee render before committing an axis — a screenshot can't catch a wrong axis scale.*

**Honest gaps carry over from D1:** an out-of-range row (`oor:true`) breaks the band (never a bridge);
a hot star shows a full **no-band note** ("no habitable zone in the 2600–7200 K climate-model range")
with planet lines + now-line still drawn; a mid-mass star's hot MS is correctly blank until it cools
into range as a giant. Planet reference lines Venus 0.72 / **Earth 1** (highlighted) / Mars 1.52 are a
FIXED Solar-System reference (caption owns "not this star's planets"). The now-line draws THROUGH a gap
(marks the age, not the band — don't index null edges). Cross-panel consistency (Gate 0 ii) is
guaranteed by construction: `setNow` uses `currentTrack[i]` at the SAME row `paintState` picks.

## D2b — the Continuously Habitable Zone + Earth's deadline. BUILT 2026-07-13 (frontend-only, no backend, Playwright 1440+390, zero console errors)
The piece the single-age scale-bar view structurally cannot show: the annulus that stays habitable for
the star's **WHOLE main sequence** — far narrower than the zone at any single age. `main.js`'s
`buildHZSeries` now carries a per-row **`ms: phase==="MS"`** flag; ALL CHZ logic lives in `hzhist.js`
(`computeCHZ` + `drawCHZ` + `drawEarthExit` + a dynamic `chzSentence()`). No new toggle — rides the
same `#hz-toggle`.

**The math (kept exactly as the plan specified — advisor confirmed not to second-guess):** CHZ =
NUMERICAL intersection over the in-range MS rows, **`max(inner_edge)` / `min(outer_edge)`** across the
discrete rows (NOT the endpoint shortcut — the non-monotone Teff at the TAMS hook makes endpoints
subtly wrong). Window **static ZAMS→TAMS**. **Undefined if ANY MS row is out of Kopparapu's 2600–7200 K
range** (can't claim continuity across an undefined stretch → a hot star has no annulus, caption owns
it). Earth-exit deadline = the age the conservative inner (**runaway**) edge crosses 1 AU, **interpolated
off the track** (never a hardcoded "~1 Gyr").

**THE MEASURE-FIRST GATE REFRAMED THE RESULT (advisor — the load-bearing catch).** On the real Sun
track the conservative CHZ is **empty by only ~1%** ([1.451, 1.436] AU) — *within the climate model's
own noise*, so it is treated as **COLLAPSED, not a hard "empty"**: use an epsilon (`width < 4%` of the
distance → collapsed), and render collapse as a **dashed pinch-line at the collapse distance**, so "the
always-safe band vanished" is *visible*, not merely absent. Rendering mirrors the migrating band's
nested language: the **optimistic** annulus (outer, faint fill; robustly nonempty → always something to
shade) with the **conservative** annulus nested inside — a crisp bordered box when it survives, else the
pinch-line. **Earth-exit marker = an orange dot + ABSOLUTE-age label on the Earth line** ("Earth exits
HZ · 5.1 Gyr"); the "from now" framing stays in the CAPTION (a drawn "from now" would couple to the
slider's now-line and confuse the static figure).

**All three render paths confirmed against real MIST tracks BEFORE wiring the canvas (advisor: two of
three would otherwise ship on faith).** (1) nonempty conservative BOX — **0.4 M☉** ([0.26, 0.27] AU;
cool dwarfs brighten little over their >100 Gyr MS, so a real annulus survives — Earth at 1 AU is
*outside* it, the zone sits close-in); (2) collapsed pinch-line + optimistic box — **Sun / 0.8 / 0.15
M☉** (0.15's 1.9%-wide sliver is < the 4% floor → pinch-line, honestly "vanishingly narrow"); (3)
undefined — **2 M☉** (MS 6964–9485 K, all 230 MS rows oor; giant-phase band still draws, no CHZ box, no
exit marker, caption states it). Playwright pixel-counted the mint CHZ edge + orange exit marker per
path; captions branch correctly.

**Gate 0 PASSED (measured through the runtime, not asserted from literature):** the Sun's runaway edge
crosses 1 AU at **5.06 Gyr** (~485 Myr after today's ~4.57 Gyr Sun — consistent with Kopparapu's
~0.95–0.99 AU present-day inner edge), and Earth at 1 AU is NOT inside the CHZ. This is a *strengthening*
of the plan's expectation: the conservative annulus doesn't merely exclude Earth, it has collapsed.

Plan: `docs/plans/outward-quartet-atlas.md` §Axis D. **The outward quartet (A/B/C/D) is now fully built.**
A observer's-view CMD = [[star-sim-observer-cmd]], B isochrone = [[star-sim-isochrone-cluster]].
