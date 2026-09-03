---
name: star-sim-he-ignition-cliff
description: The He-ignition honesty gate — `he_ignition_status()` + `/he_ignition_status` + the HR-panel caption confessing that a blended CHeB loop is smoothed across the helium flash boundary.
metadata:
  type: project
---

The **He-ignition-cliff caption** — the second data-derived honesty gate on the spine
(sibling of the rotation gate in [[star-sim-rotation-subpop-atlas]]). Built 2026-09-03;
it was item 3 on the `science-hurdles.md` §6 NEXT list. It changes **no physics**: the
CHeB residual is exactly what it was (see §1.3 of that plan), and this is the sentence
that admits it.

**What it confesses.** Around ~2 M☉ helium ignition switches character: below, the He
core is electron-degenerate and cannot burn until it has grown to a near-universal
~0.47 M☉ (the helium *flash*); above, it is non-degenerate and lights quietly at a much
smaller core. The core-He-burning loop on the HR diagram changes shape just as sharply,
so blending two neighbouring tracks across the transition **smooths a loop that is
really sharper**. The caption says so, only where it is true.

**The measured band (Gate 0, the part that decided the design).** The signature is the
**He-core mass at helium ignition** — `HeCore` at the first FSPS phase-3 row. It sits on
a flat plateau ≈0.47 M☉ across every low mass, then falls off a cliff to ≈0.31 M☉. The
band = last mass still on the plateau (10 % of the way down the fall) → the mass at the
minimum. Over all ten grids on disk: **1.65–2.10 M☉ solar non-rotating**, 1.80–2.10 at
[Fe/H] = −1, 1.70–2.20 rotating at +0.5 — all straddling the textbook M_HeF ≈ 2 M☉, and
shifting the right way with metallicity and rotation. The RGB-tip luminosity drop is the
same physics but a noisier discriminator; the core-mass version won. **Both columns were
already parsed, so no `CACHE_VERSION` bump** — that constraint (not physical elegance)
picked the criterion, since a bump invalidates every user's `.npz` and re-parses ~180 MB.

**Two design corrections against the original plan** (which said "within ±0.15 M☉ of the
boundary, frontend-only" — both halves were wrong):

1. **It is a band, not a boundary**, and its width is data, not a guess. Hence
   `_he_ignition_band(axis, grid)`, cached per `(vvcrit, [Fe/H])`.
2. **On an exact grid node there is nothing to confess.** A mass landing on a grid track
   is a *real* MIST track (blend weight 0), so a caption there would be a false label —
   the defect class this project guards hardest. `active` = `in_band` **AND**
   `interpolated`, where interpolated means the mass falls between two grid masses **or**
   the [Fe/H] falls between two grids (whose bands sit at different masses). Verified in
   the running app: at exactly 2.00 M☉ in CHeB the caption stays hidden; at 1.97 M☉ it
   fires.

**Where it lives.** `he_ignition_status(mass, feh, vvcrit)` is a **`StellarStateProvider`
Protocol method** — so `stub.py` and `mesa.py` implement it too, both returning
`has_data: False` (neither blends across mass, so neither has anything to confess). The
`/he_ignition_status` route goes through `PROVIDER` and never raises: off-grid answers
"no data" and the caption simply hides. The third gate is the consumer's —
`phase == "CHeB"`, a plain `StellarState` field, because the provider method has no age.

**Frontend.** `#hr-cliff-caption` is the **last element in the HR panel**, on purpose:
appearing mid-scrub, it can only grow the panel downward into the slack `.hr-panel`'s
`min-height` already holds, so nothing above it moves (measured identical element
geometry before/after at 1440 and 390 px — no per-note `min-height` reserve needed, the
discipline in [[star-sim-frontend-ux]]). Fetched **unawaited** from `refreshTrack` (it
decorates, it gates nothing, so it must never delay `/track`) and repainted against
`lastPainted` when it lands. Cleared by the shared mode-switch chokepoint
(`dropCliffCaptionForModeSwitch`) — a WD is past the loop, a WR/SN never had the
degenerate kind.

Related: [[star-sim-mist-provider]] (the interpolation this confesses),
[[star-sim-rotation-subpop-atlas]] (the gate it is modeled on).
