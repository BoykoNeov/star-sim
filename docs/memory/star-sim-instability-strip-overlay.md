---
name: star-sim-instability-strip-overlay
description: "Frontend-only HR-diagram variable-star overlay (instability strip + LBV + Mira) — the ROADMAP's \"cheapest honest win\"; the first \"show a subpopulation\" feature."
metadata: 
  node_type: memory
  type: project
  originSessionId: 5767b1da-ad63-48af-8cad-3b1f2648a48c
---

The instability-strip / variable-class HR overlay — the ROADMAP's "cheapest honest
win" and the **first "show a subpopulation" feature** — is **done** (frontend-only,
pytest unchanged at 137). An opt-in **"Variable-star zones" toggle** on the HR panel
(default **off**, so the default minimal HR look is unchanged) shades a labeled map of
**where variable stars live on the HR diagram**.

**What shipped:**
- `hr.js` gained `setOverlay(on)`: zones drawn **behind the track + marker** (live star
  stays legible on top) and **clipped to the plot frame**. Wired into `draw()` between
  `drawAxes()` and `drawTrack()`; added to the returned API.
- **Classical instability strip** = ONE tilted band (κ-mechanism / He II ionization
  zone) carrying **δ Scuti / RR Lyrae / Cepheids** at rising luminosity. Its edges
  genuinely **curve** (steeper near the MS, shallower at Cepheid L), so given as
  **piecewise-linear `(logL, Teff_blue, Teff_red)` control points** (`STRIP` array),
  NOT one straight line — a single straight band misfits RR Lyrae by ~500 K. Tilts
  **cooler-at-higher-L** (δ Sct hot/low → Cepheids cool/high) — the real strip tilt.
- Two more clearly-separate labeled zones: **LBV / S Dor** (Humphreys–Davidson upper-L
  limit) and **Miras / LPV** (cool luminous AGB), as simple `(logL, Teff_K)` corner
  polygons.
- **WR deliberately NOT added** as a variable-class zone — it belongs to the endgame
  work ([[star-sim-wr-wd-endgame-plan]]); WR variability is a different, messier story,
  and a hot-left zone would over-claim.

**Honesty (the project rule):** labeled **schematic** everywhere — "illustrative class
positions, not a metallicity-calibrated strip" and "WHERE such stars sit, **not** a
claim that this star is variable" (the marker just happens to fall in/out of a zone).

**UI** mirrors the comp-panel toggle pattern: a single non-radio `.mode-btn` flips its
own `active`/`aria-pressed` + a `.hr-panel.show-vars` class that reveals a 5-entry
`.legend-vars` (per-class hover pedagogy). Touched `index.html` (toggle row + legend +
extended panel `<h2>` tip), `styles.css` (`.hr-modes` + `.legend-vars` reveal),
`main.js` (toggle wiring). No backend/API/spine touch.

**Verified** via Playwright bundled Chromium (the `chrome --headless` hijack caveat —
see [[star-sim-phase4-cno]]) on the real served UI: default-off clean; toggle on →
overlay+legend, off → hidden; Sun sits just cool of the strip (correct — not a strip
variable); an **in-strip 1.8 M☉ star's marker lands on the strip** (the payoff demo);
phone (390) re-fits the canvas (ResizeObserver → `hr.resize`, the `fitCanvas` inline-
width pattern from [[star-sim-draggable-responsive-panels]]) + legend wraps 2 rows; only
the pre-existing favicon 404, no JS errors. The screenshot pass IS the regression check
(no JS test harness). Design/status: `docs/plans/whirling-cohort-atlas.md` (Bonus,
now marked DONE) + `docs/plans/ROADMAP.md`. Part of the atlas survey
[[star-sim-rotation-subpop-atlas]].
