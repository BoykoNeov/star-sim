---
name: star-sim-supernova-remnant-endgame
description: Future endgame arc (NOTED, nothing built, no design yet) — supernovae + neutron-star/black-hole remnants, the planned successor to the currently-dead SN branch. Constraint set the user fixed: a ⁵⁶Ni-powered light curve, homologous ejecta expansion, *maybe* some nucleosynthesis, EXPLICITLY no computational explosion mechanism (infeasible), observed light curves as the verification anchor.
metadata:
  type: project
---

The user wants a **future** endgame for **core-collapse supernovae + their compact
remnants (neutron stars & black holes)** — the planned successor to the branch the
current endgame classifier already reaches but deliberately leaves un-rendered.
**Status: NOTED only. Nothing built, no design doc, no chunking yet.** This file
exists so the requirement + its fixed constraints survive to whoever picks it up.

**Where it slots in (the existing dead-end this fills):** today `MISTProvider.endgame`
classifies an ends-at-φ5-onset track as **`type="SN"` with `states=[]`** — an honest
dead-end ("core collapse — not simulated", the gateway shows the SN mass but no
remnant line, no scrubbable sequence). See [[star-sim-wr-wd-endgame-plan]]. This arc
turns that dead end into a real renderer the way WD/WR became real renderers.

**The constraint set the user fixed (treat these as locked requirements, not
suggestions):**
- **⁵⁶Ni light curve** — the observable centerpiece. The honest, feasible path is a
  **semi-analytic radioactive-decay light curve** (Arnett-style: ⁵⁶Ni→⁵⁶Co→⁵⁶Fe
  decay deposition powering an expanding ejecta photosphere), NOT a hydro simulation.
- **Ejecta expansion** — homologous (v ∝ r) expansion, photospheric radius/velocity
  evolution; the visual + the timescale that sets the light-curve width.
- **"some nucleosynthesis maybe"** — explicitly tentative. At most the ⁵⁶Ni mass and
  the decay chain, perhaps a few yield species; **NOT a full nuclear network.**
- **NO computational explosion mechanism** — the user named this as **infeasible** and
  ruled it out. We do not simulate the neutrino-driven / hydro explosion. We model the
  *aftermath* (parametrized: Ni mass, ejecta mass, kinetic energy → light curve), not
  the bounce.
- **Observed light curves as verification** — the regression anchor must be **real
  observed SNe** (e.g. SN 1987A IIP-ish, SN 1993J IIb, Ia templates, a IIP plateau
  source), exactly the project's "verify against measured data, never against what we
  wish it showed" honesty rule (the boron-b8 / VO-7400 lesson, spec §7).

**Scope this arc as CORE-COLLAPSE + NS/BH remnants** — i.e. the massive-star φ5
branch (Type II / Ib/c; IIP has a H-recombination plateau *then* the Ni tail). That
is exactly the dead branch this fills.

**Type Ia is a SEPARATE path — do NOT build it off this branch (advisor-flagged):**
a Type Ia is a *thermonuclear* WD event, and a single MIST star produces an isolated
cooling WD that **never reaches the Chandrasekhar mass on its own** — it needs
accretion or a WD–WD merger, **both binary channels**. So Ia is gated on the
**binarity engine** (already a ROADMAP §3 item), branches off the **WD** endgame (not
this core-collapse branch), and only *then* connects to the Lane–Emden-in-WD n→3 /
Chandrasekhar hint in [[star-sim-wr-wd-endgame-plan]]. Mentioned here only so future-
you doesn't start Ia off the wrong branch or imply a lone star can do it.

**Open framing notes for the future designer (NOT decided):**
- **Remnant = another mass threshold**, like the existing WD→SN snap. The endgame
  already snaps & reports `final_mass`; NS vs BH is a further boundary above the WD/SN
  one (solar WD↔SN measured between 6.5 and 7.0 M☉; NS↔BH is higher, progenitor/
  remnant-mass dependent). MIST tracks end at core collapse — they carry **no** remnant
  or light-curve data, so this needs a **new data source / parametrized model**, not the
  existing grid (unlike WD/WR, which were already on the MIST tracks).
- **Architecture:** still no live solver (spec §2/§9). Likely the same gateway pattern
  (reversible "→ Continue: Supernova", a scrubbable time axis = days/months post-
  explosion instead of cooling Gyr), but the light curve is a **computed model + an
  observed-template overlay**, not a snap to a MIST track. Whether the SN/remnant state
  can still be a `StellarState` (a photosphere has Teff/L/R) or needs a sibling object
  (like the spectra/Lane–Emden siblings) is an open §3 question.

When this is picked up: write a real plan doc (sibling to
`docs/plans/smoldering-cinder-gateway.md`), and update `docs/plans/ROADMAP.md`
from "idea" as it gets designed.
