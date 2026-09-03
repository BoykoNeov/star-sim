---
name: star-sim-sun-residual-note
description: The Sun-residual honesty gate — the readout's L row confesses, from the LIVE state, that the model's Sun is ~7 % over-luminous; the [Fe/H] +0.07 fact lives in the provider token.
metadata:
  type: project
---

The **Sun-residual note** — the *fourth* honesty gate, after the rotation gate
([[star-sim-rotation-subpop-atlas]]), the He-ignition cliff
([[star-sim-he-ignition-cliff]]) and the uncertain-fate band
([[star-sim-uncertain-fate-band]]). Built 2026-09-03; it was item 1 on the
`science-hurdles.md` §6 NEXT list. Frontend-only, no backend change, and **nothing was
retuned** — a forced L = R = 1 would be the stub's fake green check.

## The thing it confesses

The app's **default star is the model's Sun**, and its readout has always shown
`L 1.07 L☉` — where 1 L☉ is *defined* as the Sun's luminosity. That gap is MIST v2.5's
own residual (see [[star-sim-mist-provider]]); it is the same common-mode ~3 % offset
that makes the seismology panel ring below 3090 µHz ([[star-sim-asteroseismology]]) —
one root, not two bugs.

## Two rules this feature exists to demonstrate

1. **It was a relocate, not an add.** `providerTip`'s MIST branch already carried
   "L≈1.07, R≈1.01". A second tooltip would have shipped two differently-worded copies
   of one fact (7 % vs 6.7 %), and they would drift. **One home per fact:**
   - the **live figure** → the readout's **L row** (`sunResidualNote(s)` in `main.js`);
   - the **where-its-Sun-sits** fact → the **`MISTProvider` status token**, which is
     already provider-gated. That tooltip no longer restates the numeric residual.
2. **Compute it, never hardcode it.** `(L−1)×100` off the served `StellarState` is true
   under MIST, MESA *and* Stub. A literal "7 %" goes false the moment `PROVIDER` swaps —
   `test_stub_provider.py` and `test_mesa_provider.py` each have their own, different Sun.
   This is the project's named defect class (a caption the data can't support).

## Measured (2026-09-03, through the live provider)

| request (age 4.567 Gyr unless noted) | L | Teff | R |
|---|---|---|---|
| 1.00 M☉, [Fe/H] 0 | 1.0668 | 5833.7 | 1.0125 |
| 0.99 M☉, [Fe/H] 0 | 1.0037 | 5800.2 | 0.9935 |
| **1.00 M☉, [Fe/H] +0.07** | **0.9999** | **5770.0** | 1.0020 |

The +0.07 node lands on the Sun **to four figures** (defined 1 / 5772) — better than the
plan's "sits near +0.07", so the provider tooltip now states it exactly.

## Why the gate is tight

`sunResidualNote` fires only for **phase MS, mass within ±0.005 M☉ of 1, |[Fe/H]| ≤ 0.01,
age within ±0.15 Gyr of 4.567**, and needs |ΔL| > 1 %. The reason is that L is steep in
both axes, and *most of the variation is real evolution, not residual*:

| off-solar | L | reads as |
|---|---|---|
| age 3.5 Gyr | 0.9733 | −2.7 % |
| age 5.2 Gyr | 1.1309 | +13.1 % |
| 1.02 M☉ | 1.2090 | +20.9 % |
| 1.10 M☉ | 1.9626 | +96.3 % |

A looser gate would let the note say "+13 % above the defined 1" for a 5.2 Gyr Sun — a
*false* caption, since that star genuinely is brighter. So it **disappears rather than
being relabeled**.

## Shape

A **tooltip, not a caption** — zero layout cost (contrast the He-cliff caption, which
needed an anti-jump pass), and `renderReadout` regenerates every refresh, so it needs no
entry in the mode-switch chokepoint. Verified in the running app at 1440 and 390 px:
fires at the default state, gone at 1.1 M☉, zero console errors.
See [[star-sim-frontend-ux]] for the tooltip layer itself ([[star-sim-tooltip-singleton]]).
