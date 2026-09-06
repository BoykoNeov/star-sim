---
name: star-sim-pinned-primary-controls
description: The sticky strip that pins mass, [Fe/H] and age above every panel — why the sliders MOVED rather than being duplicated, the two measured floors, and the Controls-panel floor that had to shrink with them.
metadata:
  type: project
---

**Shipped 2026-09-06.** Mass, `[Fe/H]` and age left the Controls panel and became a
`position: sticky` strip (`#primary-controls`) between `<header>` and `<main>`.

## Why

User report: "many panels change with them and it is not convenient to scroll to only
the panel that changes them." Every panel on the page is a function of those three
numbers, so the one panel that carried them was the one place you had to keep coming
back to. This is the *same* complaint that produced `relocateOverlayControls()` — a
control whose effect is off-screen reads as "nothing happened" — and the two have
**different answers**:

- a control that drives **one** panel moves **to that panel** (the He / α / isochrone /
  population overlays);
- a control that drives **every** panel has no panel to move to, so it is **pinned**.

That split is now written at `relocateOverlayControls()` in `main.js`, because the next
person to add a control will ask which of the two shapes theirs is.

## The rules the build had to obey

- **Move, never duplicate.** Two copies of a slider is a synchronisation bug waiting to
  happen. Everything moved as plain markup with **every id unchanged**, so all 23
  `wire*()` handlers, `buildTickStrip`, `commitNumber` and the endgame body-class CSS
  keep working untouched. No JS relocation at boot: unlike the overlays there is no
  "which panel does this drive" question to answer at runtime.
- **Move the whole block, not the slider.** Label + `.slider-wrap` + tick div +
  `datalist`, and for age also `#endgame-age-caption`. The mode tags (`.age-wd`,
  `.age-sn`, …) survived because they are scoped to `body.*-mode`, never to
  `.controls-panel` — three rules that *were* panel-scoped (`label`, `label span`,
  `input[type=range]`, and the `.help` glyph override) were **widened** to cover
  `.primary-control` rather than copied.
- **`#endgame-resnap-note` came too.** Its whole job is to explain a mass/[Fe/H] drag
  that reverted; left behind it would explain it from off-screen, which is the
  complaint that moved the sliders in the first place. It stays *below* the sliders so
  it can only grow the strip downward.

## The floors (measured, `stripmax*.mjs` in `M:\claud_projects\temp\star-sim-perf`)

A pinned box is stricter than a panel: it sits **over** the content, so a reflow inside
it moves every panel at once. Two floors, not one:

| | live | endgame |
|---|---|---|
| measured tallest | 128 px | 204 px |
| `min-height` | **136 px** | **216 px** (`body.wd-/wr-/sn-/stripped-mode`) |

- **Live is 114 px in 1,015 of 1,020 sampled states** and 128 px in five — `[Fe/H]`
  ≈ +0.45, ≈ 36 M☉, where the age landmarks crowd enough to stagger the tick labels
  onto a second row. A 1-in-200 state is exactly what a coarse sweep misses and a user
  finds. Three tick rows never occur.
- **One floor for both modes would waste ~90 px of pinned space in the live view** —
  the endgame caption reserves two lines and the re-snap note two more, and both are
  `display:none` / `hidden` while the star is alive. Splitting the floor by body class
  costs one extra rule and keeps the live strip honest.

## Sticky only above 800 px

Three 230 px columns + two 22 px gaps = 734 px of content, so the strip holds one row
down to a 782 px viewport and wraps below it. A **wrapped** pinned strip costs more
viewport than the scrolling it saves (215 px at 761, 316 px at 390), so under 800 px it
becomes an ordinary block at the top of the page — one property, no second layout.

## The knock-on: the Controls panel floor had to shrink

`.controls-panel`'s 1214/1308 px floors were measured with those three rows *in* the
panel ([[star-sim-visual-performance]] V1b). Left alone they would have held ~300 px of
void. Re-measured the same way — the panel's own `min-height` set to 0 inline and
`offsetHeight` read, which includes the child margins a bounding-box sweep drops — and
lowered to the new tallest state: **1214 → 1024** (measured 1017 at 481 px, the default
rule's binding width) and **1308 → 1140** on the phone (measured 1130 at 390). The
tallest is still the two-sided uncertain-fate hedge at 6.5 M☉ / `[Fe/H]` −1.5, not any
endgame. Net: 190 px of dead panel height returned on a desktop, 168 on a phone, against
136 px the strip costs.

**Trap, hit once:** a fetcher measuring the served app reads `index.html` off disk, so
**editing a served file while a Playwright sweep is running** can hand the browser a
half-written page — it failed with `#feh-num` not found, which looks like a real
regression and is not. Don't touch `frontend/` while a harness run is in flight.

Related: [[star-sim-visual-performance]] (the floors and the harness),
[[star-sim-frontend-ux]] (the anti-jump reservation discipline),
[[star-sim-mainjs-guards-chokepoint]] (the `wire*()` split the ids feed).
