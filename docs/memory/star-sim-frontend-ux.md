---
name: star-sim-frontend-ux
description: "Star Simulator frontend UX layer — single-source age window (track as driver), snap-tick strips + editable inputs, hover-revealed pedagogy (? glyphs + glyph-free status tooltips), canvas.js HiDPI helper, halved diagram sizes; age-slider left end labeled ZAMS; + the 2026-07 HR pass (Teff-colored living track, glowing marker, O·B·A·F·G·K·M class bands) + the tier-2 pass (past/future track split, swallowed-orbit rings, starfield backdrop, first-load skeletons) + the polish pass (iso-radius HR diagonals, comp boundary dots + brighter phase labels, tick/SED label legibility, header tag ZAMS → remnant)."
metadata: 
  node_type: memory
  type: project
  originSessionId: 07b91de6-07d5-49ba-b9eb-dbdac40d86b4
---

The Phase-1 frontend UX pass (`frontend/src/main.js`, `index.html`, `styles.css`,
plus `comp.js`/`hr.js`/`canvas.js`). Non-obvious decisions worth not re-litigating:

- **Age window is read off the `/track` result itself** (its first/last row's
  `age_yr`), NOT a separate `/age_range` fetch. `refreshTrack()` is the DRIVER for
  mass/[Fe/H] changes: the new track sets `ageMin/ageMax` + rebuilds the landmark
  ticks, then calls `refresh()`. One token-guarded fetch decides both the panels'
  track and the slider's domain, so they can't drift. The old bug ("composition
  ends before the age slider, or vice-versa") was an *unguarded* `/age_range`
  staleness racing the guarded track. `/age_range` still exists (tests use it) but
  the frontend no longer calls it. Reading the window off the track is §3-clean —
  `age_yr` is a StellarState field. See [[star-sim-composition-panel]].
- **Default star lands at ~4.6 Gyr via `firstTrackLoaded`:** since the window no
  longer starts at age 0, a raw 0.46 fraction ≠ 4.6 Gyr. On the first track only,
  `ageFraction = (4.6e9 − ageMin)/(ageMax − ageMin)`.
- **Sliders snap to landmarks; number inputs bypass snap.** `snap()` magnetizes
  within 1.5% of range to round masses / solar+grid [Fe/H] / evolutionary
  landmarks (read off the track: phase transitions + the max-R RGB tip). Each
  slider also has a visible custom **tick strip** (`.ticks`, inset left/right 8px ≈
  thumb radius so a mark at pos% sits under the thumb); labels are collision-
  skipped in normalized space. Editable `.val-input` number fields are the
  arbitrary-precision escape hatch; `setNum` won't overwrite a field while it's
  `document.activeElement` (don't fight the user mid-type).
- **Pedagogy is hover-revealed, one CSS `data-tip` tooltip mechanism:** a `?`
  glyph (`.help`, circle) on panel headings, control labels and every readout row;
  AND glyph-free dotted-underline hovers (`.tip`) on the status-line tokens
  (`OK` / phase / provider). Controls-column tooltips open leftward (`.help-left`);
  status-line tooltips open upward (`.tip-up`) since the line sits low. Panels keep
  `overflow: visible`. `data-tip` is a plain-text attribute — inline tags don't
  render (e.g. write "Teff", not with a `<sub>`), and `&`/`<`/`>`/`"` must be
  escaped (`escAttr`). The phase tooltip is a PMS/MS/SGB/RGB/CHeB map keyed on
  `s.phase`, so it updates as age scrubs.
- **`canvas.js` = shared `fitCanvas(canvas, cssW, cssH)` HiDPI helper** used by both
  `hr.js` and `comp.js`: sizes the backing store to devicePixelRatio, scales the
  context, returns `{ctx, W, H}` in logical units. The diagrams were halved to a
  fixed display box (320px star; HR/comp sized by JS) — fixes the earlier blur and
  oversized canvases.
- **Launcher:** `start.bat` (Windows double-click) + `start.sh`, documented in
  `README.md` — venv + uvicorn + open browser, for a non-CLI launch.
- **The age slider's left end is labeled "ZAMS", not zero** (user: "why can't age go
  to zero?"). The window starts at the zero-age main sequence (`t[0].age_yr`), which
  for a low-mass star is hundreds of Myr (0.3 M☉ ≈ 0.45 Gyr; the Sun ≈ 42 Myr; 20 M☉
  ≈ 0) — the pre-main-sequence contraction is clipped by the deliberate spec ZAMS→EAGB
  window (extending to literal birth = un-clipping PMS + adding PMS EEPs to the §6
  interp; rejected as scope creep). `rebuildAgeTicks()` prepends a **strip-only**
  `{pos01:0,label:"ZAMS"}` so the non-zero floor reads as a physical landmark, not an
  arbitrary cutoff. pos 0 is already a `snapAge` target; the age `?` tip explains it.

**The HR pass (2026-07, hr.js-only — visual-review items 4–5, follow-up to the
[[star-sim-phase2-shaders]] shading rework):**
- **Living track colored per-segment by local Teff** (`teffToCSS` of the segment's
  mean — the exact idiom `drawEndgameTrack` already used), at `globalAlpha 0.75` /
  1.5px so the marker stays the brightest thing on it. The endgame view's faint-grey
  living-context copy was deliberately left grey ("faint grey = the part of the
  story you're not focused on").
- **Marker glow:** one `drawMarker(x, y, teffK)` helper now serves both `draw()` and
  `drawSupernova()` (the dot was previously duplicated). Radial gradient r2→20 at
  0.55 alpha in the star's own color, **clipped to the plot frame** — a marker riding
  an axis edge must not bleed onto tick labels; the 7px dot stays unclipped as
  before. `teffToRGB` returns 0–1 floats — ×255 before building the rgba() strings.
- **Spectral-class bands (`drawClassBands`):** standard MK Teff cuts (30000/10000/
  7500/6000/5200/3700/2400), each letter tinted by a mid-class `teffToCSS` hue so the
  row doubles as an axis legend. Three placement decisions: (1) letters sit **above
  the top frame line** in the padding strip — inside the frame they collide with the
  overlay's "LBV / S Dor" label (measured: both land at y≈38–42) and with luminous
  tracks; (2) **living view only** — MK classes don't apply to the WD/WR remnant
  regimes the auto-fit endgame axes span (a 30 kK WD is a D-class object, not a B
  star — the honesty rule); (3) O's hot edge is **the frame edge, however far it
  expands** (`hotEdgeX` carried through the loop), so a ≳120 M☉ expanded frame widens
  the O band instead of leaving an unlabeled hot gap. Min visible band = **9px, not
  12** — 12 dropped the G letter at phone width (the G band is the narrowest at
  0.062 dex ≈ 10.5px on a 300px canvas), and the Sun's own class is the one letter a
  teaching app can't shed.

**The tier-2 visual pass (2026-07, follow-up to the HR pass — four review items,
frontend-only, commit after b2fb6e9):**
- **Past/future HR track split (`hr.js`):** the traversed portion draws solid (1.8px /
  α0.9), the future dimmer (1.1px / α0.3); same split on the endgame cooling/stripping
  track (2/1.0 vs 1.3/0.35). Split point = `splitIndex(list)`: `list.indexOf(marker)`
  is EXACT because the marker IS an element of the drawn array in every scrub mode
  (live: `refresh()` picks `currentTrack[i]`, the same array `setTrack` received;
  WD/WR: `refreshWD/WR` pick `endgame.states[i]`, the same array `setEndgame` got) —
  with an age-monotone fallback for any state from elsewhere. Physics note: the Sun's
  past is geometrically tiny in log-space (ZAMS→4.6 Gyr moves ~nothing on the HR), so
  the split only "pops" once the star leaves the MS — correct, not a bug.
- **Swallowed-orbit rings (`scale.js` drawOrbits):** an orbit with `R ≥ o.r` renders
  engulfed — the open blue ring fills with the star's own `teffToCSS` tint (α0.9),
  stem+label dim to ~0.4. The caption already narrated swallowing; this makes it
  visible, and in SN mode the expanding fireball engulfs the rings one by one.
  **Demo gotcha:** the 1 M☉ track's exposed window ends at EAGB R≈83 R☉ — one solar
  radius UNDER Mercury's 83.2 R☉ orbit (the bigger RGB-tip swell is mid-track), so
  demo with ≥2 M☉ (5 M☉ EAGB-end → 327 R☉ = Mercury+Venus+Earth filled, Mars at
  328 R☉ still open).
- **Starfield backdrop (`star.js` makeStarfield):** deterministic (seeded mulberry32 —
  byte-stable screenshots), STATIC (no drift — must never read as the star moving),
  a flat ±20 scatter sheet at z=−40, NOT a shell (a radius-60 shell puts ~97% of its
  points outside the fixed camera's 40° cone — measured before building; the canvas is
  CSS-locked square so aspect stays 1 and ±20 overfills the ±17.5 frustum). Two layers
  (240 dim + 42 brighter), additive Points, `depthWrite:false` + depthTest on so the
  opaque star disk occludes them; corona/glare/wind/fireball quads (renderOrder ≥1)
  just glow over them. Pure backdrop — encodes no StellarState, no honesty cost. The
  CSS vignette rides `#star-canvas`'s background (color + radial-gradient in the
  shorthand — the color is explicit so the loading override can't drop it). Bonus
  narrative beat: in the SN winks-out/failed reveals the sky REMAINS — verified.
- **First-load skeletons:** markup ships `<body class="loading">`; `endFirstLoad()`
  (main.js) removes it on the first `paintState` AND on both first-load error paths
  (a dead backend must show its error, not shimmer forever). The sheen rule MUST use
  per-ID selectors (`body.loading #hr-canvas`, …): the canvases' own `#id` rules set
  the `background` SHORTHAND, which resets `background-image` at ID specificity, so a
  class-level rule loses the cascade. `prefers-reduced-motion` kills the animation.
  Verify via computed style (`animationName === "skeleton-sheen"` while a Playwright
  route holds `/track` open, `none` after first paint) — a still screenshot can't
  prove a moving sheen.

**The polish pass (2026-07, the review's last batch — iso-radius lines + three
small-polish items; frontend-only, commit after c598252):**
- **Iso-radius diagonals (`hr.js` drawIsoRadius):** dotted constant-R lines,
  `logL = 2·logR + 4·(logT − log 5772)`, decades 0.001–10000 R☉ clamped to the frame
  in both axes (off-frame decades skip analytically — no clip needed). Drawn right
  after `drawAxes()` in the living AND endgame views (never SN — its x-axis is time).
  Labels 9px, rotated to the on-screen slope, tucked at each line's COOL (lower-right)
  end — they form a tidy column along the right edge; skipped when the visible segment
  is shorter than the label. Verified payoffs: the Sun sits ON the 1 R☉ line; the WD
  cooling track slides DOWN a single iso-R line (constant radius, just fading — why
  "dwarf"); the 120 M☉ expanded frame regenerates the lines on the new bounds. The HR
  `?` tooltip gained the L=4πR²σT⁴ sentence.
- **Comp boundary dots + brighter acts (`comp.js`):** `drawBoundaryDots` puts
  dark-ringed white dots where the cursor crosses the bulk view's H→He and He→Z
  stack boundaries (both sub-charts, values read straight off the marker row — bulk
  view only, the line views have no bands). Phase labels went semibold `#aab4c6`
  (they name the acts, not tick furniture), dividers α0.30→0.40, cursor 1.5→1.75px
  `#f4f7fc`.
- **Label legibility:** `.tick-label` 9.5px→10.5px + `#a7b0c2` (safe: the strip's
  collision logic is normalized MIN_GAP, no pixel measurement); SED band names
  10px→11px + `#98a2b8`, fit-skip threshold 26→29px (the "visible" sliver was
  already skipped at 12px wide — covered by Wien-peak/detailed-spectrum labels).
- **Header tag:** "Phase 5 · spectra" (stale build-phase tag) → **"ZAMS → remnant"**,
  a durable scope statement now the build phases are complete.
- **Controls-panel height is reserved so a mass/[Fe/H] drag doesn't shove the age
  slider (user request 2026-07).** The five live-mode what-if controls (Ap/Bp,
  stripped, helium, α, rotation) used to `hidden`/remove themselves off their
  eligibility band → the panel jumped ~74px as the mass slider crossed a band. Now
  they are **present-but-greyed** out of regime: a shared `reserveWhatIf(control,
  toggle, note, opts)` helper renders the four simple toggles disabled + `.rot-toggle-row
  .disabled` (opacity 0.5) with a "**Appears for … M☉**" note that teaches when the knob
  activates. **Three hide-reasons, three treatments (advisor):** out-of-regime → GREY
  (reserve); **data-absent** (`heliumHasGrid`/`alphaHasGrid`/`rotation_status.has_grid`
  false — feature not in this deployment) → still **HIDE** (a knob that can never activate
  is the genuinely-dead knob the honesty gates avoided — this REVERSES the old "absent, not
  a dead knob" comments for these controls, by user request); **endgame/stripped mode**
  → still HIDE. Greying must not strand an active HR overlay: `updateHeliumControl`/
  `updateAlphaControl` tear the overlay down FIRST (`if (!eligible && heliumOn) heliumOff()`)
  then render greyed. Stripped stays special (visible+checked in stripped-mode as its exit).
  **Rotation is the hard one** (period-SLIDER vs vvcrit-TOGGLE are different widgets, not the
  same control appearing) → the SECTION stays present in live mode with a placeholder note
  when no facet applies, and a **`.rot-control` min-height (130px desktop / 150px mobile)**
  reserves the taller period-facet height so the massive↔cool transition doesn't jump; the
  rare ~1.3 M☉ both-facets overlap (above Kraft AND cool) legitimately exceeds it.
  **Verified (Playwright, the regression gate):** controls-panel height 884–891px across a
  0.5→200 M☉ sweep at 1440 (was 74px+ jumps), 1033–1036px at 390; helium ON→drag-out tears
  down + greys (no strand); 390 body-overflow is the pre-existing structure-panel one, not
  Controls. **Deliberately NOT reserved:** the toggle-ON captions (helium τ_MS, the
  population caption) are an intentional disclosure, not the mass-drag jump (a 2-line reserve
  cost ~93px of permanent height for a partial fix — reverted); and the **gateway fate-note**
  (SN "core collapse…") is bottom-anchored below the age slider — it grows DOWNWARD into empty
  space and shoves no interactive control, so reserving it would leave a large dead gap for the
  ~majority of non-SN stars.

- **Overlay-controls-relocated + SED-legend-clickable + stripped-button + calm-binary-layout batch
  (2026-07-11, user-reported):** a batch of "controls act where you can't see the effect" and
  "panels jump" fixes. (1) **Relocated the overlay what-ifs onto the panels they drive** — the
  helium-/α-enhanced + cluster-isochrone controls into `.hr-panel`, the coeval-population control
  into `.sed-panel` — via `relocateOverlayControls()` (a boot-time `appendChild`, IDs unchanged, the
  layout.js panel-drag precedent; NOT an HTML move — the giant data-tip strings made that error-prone).
  A `.controls-overlay-pointer` note stays in Controls saying where they went. **Canvas dims verified
  IDENTICAL before/after (hr 654×320, sed 654×300) — controls added below a JS-width-driven canvas
  don't resize it; hr/sed panel heights rock-stable across a mass sweep (614/588).** (2) **Observer
  CMD "B/V unavailable" fix** (`cmd.js`): the notice keyed SOLELY on the locus fetch's `has_bv`, so it
  could contradict its own readout (which prints a real (B−V)₀) and flash during the pre-load gap.
  Split "not-yet-loaded" (`locusLoaded`) from "known-absent", and never show it when the marker carries
  a valid B−V. Backend always returns `has_bv:true` (filters.json has B/V) — this is defensive + the
  real cause is a stale cached cmd.js on a no-bundler SPA (hard-refresh). (3) **SED legend clickable**
  (`sed.js` `toggleSeries` + `hiddenSeries` Set, mirroring comp.js's per-element toggle): each
  legend entry carries `data-series` (blackbody/visible/wien/activity/rotline/wind); main.js wires a
  delegated click → hide that curve + strike the entry through (`.sed-legend span[data-series].off`).
  The "non-thermal edges" entry is conceptual (no data-series). SED height stays 588 across toggles.
  (4) **Stripped what-if is now a BIG gateway-style BUTTON** (`#stripped-btn .gateway-btn.fork-btn`,
  a distinct CYAN hue because it's a MID-LIFE fork not the yellow end-of-life gateway) — one-way ENTER
  (exit = the endgame Back bar), disabled+present out of the 2–18.2 M☉ band (reserve). Replaced the
  checkbox `#stripped-toggle`; `updateStrippedControl` hides it in stripped-mode (was visible+checked).
  (5) **Calm the stripped/binary layout** (the user's "big jumping" complaint): `body.stripped-mode
  .lane-panel, .structure-panel, .sed-panel, .observer-panel { display:none }` — hides them across
  EVERY sub-scenario (snapshot, co-evolve `binary-view`, CO-binary `co-binary-view` all layer on
  `stripped-mode`), so switching merger⇄stripped⇄wide⇄star+black-hole no longer adds/removes whole
  panels. **Fixed the explicit "Lane-Emden in stripped binary screens" bug.** Also extended the
  co-binary readout/scale/star-class hide to `binary-view` (both animated views leave those frozen on
  the snapshot — `refreshBinary` never updates them, a latent false-data leak) so the two are now
  panel-IDENTICAL (`DIFF bin vs co: []` verified). (6) **Amplified the Ap/Bp peculiar spots** (star.js:
  dip 0.4→0.55, caps smoothstep 0.45→0.30/0.85→0.80) — they were wired but near-invisible; now a clear
  dark abundance patch (evocative, so amplifying costs no honesty). **`*/` inside a CSS comment
  (`update*/drop*`) prematurely closed it and silently broke the panel-hide rule** — a Playwright
  "rule present but not applied" symptom; reword to avoid `*/`. (7) **3D spin-axis inclination cue**
  (star.js, the user's chosen option): a faint schematic rod + arrowhead caps through the poles
  (`spinAxis` Group, sibling of `star` so the oblate scale doesn't distort it; `MeshBasicMaterial`
  `depthTest:false` so it overlays the disk, caps poke ~0.35·R into dark space to read over a blazing
  O-star) that TILTS with the viewing inclination via a NEW `axisTiltForView()` — ungated on
  oblateness (unlike the star SHAPE's `tiltForView`), so it reads the pole orientation on EVERY star,
  even a round one (rotationally symmetric → no other cue). i=0 pole-on → a dot at disk centre; i=90
  edge-on → a vertical double-arrow; i=60 → a tilted 3/4 view. `star.setSpinAxis(showIncl)` from
  `updateRotControl` shows it exactly when the inclination control is available (a rotating
  gravity-darkenable star); update()'s `!eg` gate is the mode-switch safety net. Zero console errors
  at 1440+390.

**Why:** these are the UX forks (single-source window especially) a future session
shouldn't silently undo. **How to apply:** keep deriving the age window from the
track; keep new pedagogy on the `data-tip` tooltip (plain text, escaped); reuse
`fitCanvas` for any new canvas panel; relocated controls stay declared in Controls
HTML and moved at boot (don't "fix" that back into the HTML); never put `*/` inside
a CSS comment.
