---
name: star-sim-supernova-remnant-endgame
description: Core-collapse SN + NS/BH endgame arc — DESIGNED + chunked, Chunk 0 measure-first gate DONE (verdict shape-GO/scale-via-slider); plan docs/plans/radioactive-afterglow-requiem.md. Fills the dead type="SN" branch. Constraints the user fixed: ⁵⁶Ni light curve, homologous ejecta expansion, *maybe* light nucleosynthesis, EXPLICITLY no explosion mechanism, observed light curves as verification. Hybrid sibling (classify on the spine, compute in supernova.py + /supernova).
metadata:
  type: project
---

The user wants an endgame for **core-collapse supernovae + their compact remnants
(neutron stars & black holes)** — the successor to the branch the current endgame
classifier reaches but leaves un-rendered (`type="SN", states=[]`).
**Status: DESIGNED + chunked. Chunk 0 (measure-first gate) DONE; Chunks 1–5 are
specified/sketched, not yet built.** Plan: `docs/plans/radioactive-afterglow-requiem.md`
(sibling to `smoldering-cinder-gateway.md`). This file holds the locked constraints +
the gate's measured verdict; the plan is the design source of truth.

**Architecture (advisor-affirmed): a HYBRID sibling.** Classification stays in
`PROVIDER.endgame()` (it already returns `type="SN"` + progenitor scalars — §3-clean
routing metadata; do NOT relocate it). A new sibling **`supernova.py` + `/supernova`**
(bypasses `PROVIDER`, like `lane_emden`/`spectra`) does the light-curve **computation**,
emitting BOTH photosphere `StellarState`s (feed the existing 3D/SED/scale consumers —
the expanding photosphere has L/Teff/R) AND a light-curve object (a new panel). So the
SN state is a `StellarState` *and* a sibling object — the open §3 question, resolved.
Progenitor inputs ride **scalar fields on `EndgameResult`** (`pre_sn_radius_rsun`,
`he_core_msun`, `co_core_msun`, `h_retained`) — a `CACHE_VERSION` bump to parse the
`he_core_mass`/`c_core_mass`/`o_core_mass` columns; `StellarState` untouched.

**The 3-tier honesty framing IS the arc:** Tier-1 = the ⁵⁶Co tail slope (0.0098 mag/d,
set only by τ_Co=111.3 d) — bulletproof, zero free params, THE verification anchor (not
the peak). Tier-2 = plateau L & duration from MIST M_ej/R₀ + canonical E,κ (Popov/Kasen-
Woosley) — robust shape, ±dex level. Tier-3 = peak/tail height ∝ M_Ni — NOT MIST-derivable
(0.001–0.3 M☉), so a **free slider** (default 0.06), explicitly not predicted.

**Chunk 0 gate — measured over the full MIST grid (the scope-setting findings):**
- **The SN bucket is PURELY Type II** (all 279 SN-classified tracks retain H, surf-H
  0.30–0.75; **zero Ib/c** — the stripped stars classify as **WR**, 329 of them). ⇒ v1
  SN arc = **Type II / IIP**. Stripped-envelope **Ib/c is the WR endpoint** (a follow-on
  chunk: "→ Continue: Supernova" off the WR scrub, pure Arnett no-plateau), NOT v1.
- **Core masses present & sane** (0 unphysical) → clean ejecta/remnant split. Progenitors
  are **red supergiants** (final-phase R₀ ≈ 400–1100 R☉) → IIP plateau valid; use the
  **final-phase-median R₀** (terminal EEP row is a low-gravity artifact for some tracks).
- **Canonical 15 M☉ solar curve lands in regime:** plateau 1.5e42 erg/s / 133 d, Co-tail
  slope 0.00976 mag/d (= analytic = textbook 0.0098). **Verdict: shape-GO, scale-via-
  slider** (the SED-Chunk-2 pattern). Cite Nadyozhin(1994) ε_Ni/ε_Co, Kasen-Woosley(2009).

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
