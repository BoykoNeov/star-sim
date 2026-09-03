---
name: star-sim-rossby-activity
description: The corona's `activity` proxy is now driven by the SED panel's Rossby number (one dynamo, two views) — and the measured reason the planned P_rot = 2πR/v formula is dead (MIST zeroes v_rot below the Kraft break).
metadata:
  type: project
---

The **Rossby-flavoured `activity` proxy** — built 2026-09-03, the last item from spec
§11 and item 1 on the `science-hurdles.md` §6 NEXT list. **Frontend-only**: no provider,
no `StellarState` field, no backend test changed. Still **T4/evocative** (spec §7) — it
sets how far the 3D corona reaches, not a predicted X-ray output.

## The one-line summary

The 3D star's corona is drawn from a 0–1 `activity` value. It used to be a pure
temperature ramp. It is now the **same Rossby number the SED panel's coronal X-ray line
is drawn from**, wherever that line is honest — so one rotation drives both views and
they can never disagree on screen. Off that regime the provider's ramp still stands.

## The measurement that killed the planned formula (keep this — it stops a re-proposal)

`science-hurdles.md` §1.6 originally said to compute `P_rot = 2πR/v` from the served
`v_rot_kms`. **That input does not exist where the feature needs it.** Measured through
the provider, `v_rot_kms` is exactly `0.000` for every cool star on *both* rotation
buckets — MIST only spins stars up above the Kraft break:

| M☉ | vvcrit 0.0 | vvcrit 0.4 |
|---|---|---|
| 0.3 / 0.5 / 0.8 / 1.0 / 1.2 | 0.000 | **0.000** |
| 1.5 | 0.000 | 103.2 km/s |
| 5.0 | 0.000 | 218.5 km/s |
| 15.0 | 0.000 | 251.5 km/s |

The irony is exact: rotation exists in the grid **only for radiative-envelope stars,
which have no convective dynamo**, and is absent for every star the Rossby number is
about. At the default Sun the formula is a divide by zero, not a small number. See
[[star-sim-rotation-subpop-atlas]] for what the vvcrit axis *is* good for.

## What was built instead

`sed.js` already owned the honest chain for exactly the cool-MS dynamo regime (see
[[star-sim-nonthermal-sed-plan]]): Teff→(B−V) (Ballesteros 2012) → gyrochronology
`P_rot` (Mamajek–Hillenbrand 2008) **or** the user's pinned period slider → Wright (2011)
`τ_conv(M)` → Ro. Reused, not rebuilt:

- **`sed.activityLevel()`** maps that Ro to 0–1 and `main.js` passes it to
  `star.update(s, {activity})`. The gate is exactly `activityLine() != null` — the corona
  changes only where the blue X-ray line is actually drawn.
- **No new free parameter.** The 0–1 map is Wright's own span normalized: saturated
  ceiling 10⁻³·¹³ → 1, the panel's quiet floor 10⁻⁷ → 0.
- **No `rossby.js` extraction** (advisor call): the effective period depends on
  `userProt`, which is slider state living inside `sed.js`, so a pure module would still
  need an accessor back in — and `main.js` already calls `sed.rotationAllowed()`.
- **`sed.update()` moved ABOVE `star.update()`** in `paintState`, or the glow lags the
  marker by one paint. The slider itself doesn't go through `update()`, so `createSED`
  takes an `onRotation` callback → `refreshCoronaActivity()`.
- **The readout prints the value the corona uses** (`activityValue`/`activityTip`), or
  the two would contradict each other — the project's false-caption trap.

## The three traps it had to clear (all measured through the served runtime)

1. **`activity` drives corona GEOMETRY, not just brightness** — `extent = 1.12 + 1.4·act`
   in `star.js`. A range shift would silently resize the glow on load. At the default Sun
   the derived value is **0.212 against the ramp's 0.190**: an unforced agreement, so
   nothing resizes. Where it now differs it says something the ramp could not — the Sun at
   1 Gyr reads 0.46 and at 8 Gyr 0.12 (the ramp was flat ~0.19 across both).
2. **The handoff back to the ramp must not pop.** MH08's `(B−V − 0.495)^0.325` is steeply
   sensitive just redward of its singularity, so the derived value fades in over the first
   0.15 mag past the cutoff (`ACT_BLEND_BV_HI = 0.70`) — a *stability* measure, not a
   cosmetic one. Fixed-MS sweep 0.8 → 1.3 M☉: 0.60 · 0.60 · 0.51 · 0.38 · 0.23 · 0.17
   (derived) → 0.048 · 0.032 · 0 (ramp). No step.
3. **Endgame teardown** — solved by construction rather than by a `drop*ForModeSwitch`
   hook: **nothing is cached on either side.** `star.js` reads the override per `update()`
   call, so an endgame (which passes none) cannot inherit a living value; and
   `sed.activityLevel(servedActivity)` takes the provider's ramp **as an argument from the
   state the caller is painting** rather than storing a copy. The stored form was a real
   bug (advisor catch): the rotation slider never goes through `sed.update()`, so a cached
   base would still hold the giant's ~0.82 on the first slider move after Back from an
   endgame. Verified in the runtime — after Back the readout shows 0.82 (the *ramp's*
   answer for a 3600 K AGB giant), and scrubbing to the MS then moving the slider
   immediately gives 0.089 → 0.60, uncontaminated.

## The payoff, measured on the pixels

Playwright at 1440 and 390 px, zero console errors: dragging the period **70 d → 1 d**
moves activity **0.083 → 0.65** and the lit fraction of the 3D frame **0.31 → 0.73** (the
glow's area more than doubles); dragging back returns to 0.3072 exactly, no drift. The
radial luminance profile stays monotone (limb 171, then 66 vs 26 just outside at fast vs
slow) — no bright ring. That "does the glow actually move" check is the gate: if the
slider doesn't visibly move the corona the feature isn't there, whatever the math says.
