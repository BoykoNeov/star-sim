---
name: star-sim-frontend-ux
description: "Star Simulator frontend UX layer — single-source age window (track as driver), snap-tick strips + editable inputs, hover-revealed pedagogy (? glyphs + glyph-free status tooltips), canvas.js HiDPI helper, halved diagram sizes; age-slider left end labeled ZAMS."
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

**Why:** these are the UX forks (single-source window especially) a future session
shouldn't silently undo. **How to apply:** keep deriving the age window from the
track; keep new pedagogy on the `data-tip` tooltip (plain text, escaped); reuse
`fitCanvas` for any new canvas panel.
