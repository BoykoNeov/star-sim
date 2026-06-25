# Roadmap — the cross-plan index of future additions

**This is the canonical, single-page view of everything proposed-but-not-yet-built**,
gathered from the four detailed plan docs + CLAUDE.md's status bullet. It is a *thin
index*, not a fifth plan: the linked doc + chunk is always the source of truth for
design detail. The value here is the **one cross-plan priority view** no single plan
has — SED + endgame + atlas + stragglers in one place.

When you pick something to build, read its linked chunk; when a plan changes, update
the plan and only the one-line hook here. CLAUDE.md's "what's next" points at this file.

## Status legend

- **done** — shipped (listed only where it's a dependency for unbuilt work).
- **planned** — designed and chunked in a plan doc; ready to implement.
- **sketched** — a concrete approach exists (atlas entry / plan sketch) but not chunked.
- **idea** — named with a rationale; no design yet.

## The cross-plan view (grouped by readiness, not by source doc)

### 1. Ready now — designed, on-hand data, mostly frontend (cheapest honest wins)

| Item | Status | Hook | Where |
|---|---|---|---|
| Instability-strip / variable-class HR overlay | idea | Shade Cepheid / RR Lyrae / δ Scuti (+ WR/LBV) zones as a labeled *view* — zero new data, pure frontend; the cheapest "show a subpopulation" payoff. | `whirling-cohort-atlas.md` (bonus) |
| SED Chunk 1 — cool-star coronal X-ray + radio **band** | planned | Shaded `L_X/L_bol` 10⁻⁷…10⁻³ envelope + Güdel–Benz radio band; frontend-only (needs only `L`, `Teff`). The honest band (no rotation ⇒ no single line). | `magnetic-ember-broadcast.md` §Chunk 1 |
| SED Chunk 3 — band → **line** (age-derived + slider) | planned | Collapse the band via gyrochronology (MS cool stars) + a user rotation/activity slider, honestly gated; frontend-only, depends on Chunk 1. | `magnetic-ember-broadcast.md` §Chunk 3 |
| Endgame Chunk 2 — reversible WD gateway + WD mode shell | planned | The "→ Continue: White Dwarf" button, log cooling-age axis, live mass re-snap, WD cooling track on the HR diagram. Backend done (Chunk 1 ✅). | `smoldering-cinder-gateway.md` §Chunk 2 |
| Endgame Chunk 3 — WD 3D shader + structure panel | planned | Degenerate-sphere shader (Earth-scale, cooling-color shift) + WD-semantics composition/cooling-curve panel. | `smoldering-cinder-gateway.md` §Chunk 3 |
| Endgame Chunk 4 — WR mode shell + HR + composition | planned | WR gateway branch (feh-threshold-gated), HR axis to ~250 kK, stripped-surface WN→WC→WO composition (already on the track). | `smoldering-cinder-gateway.md` §Chunk 4 |
| Endgame Chunk 5 — WR 3D wind shader | planned | Optically-thick-wind look (radial outflow, emission-line glow); closes the on-hand-data endgame work. | `smoldering-cinder-gateway.md` §Chunk 5 |
| v sin i line broadening | sketched | Frontend convolution of the baked spectrum with a rotation kernel; honest but **narrow** (visible only >125 km/s at R≈2400) — pairs with the rotation axis. | `whirling-cohort-atlas.md` (Tier B) |

### 2. Backend / data touch — real, bounded effort

| Item | Status | Hook | Where |
|---|---|---|---|
| SED Chunk 2 — hot-star **wind free–free radio** from Ṁ | planned | The one *predictive* non-thermal piece; needs `mdot_msun_yr` on the spine (`star_mdot` already in cache v9, not yet blended). Solid line vs the evocative band. | `magnetic-ember-broadcast.md` §Chunk 2 |
| Rotation `vvcrit` axis (0.0 ↔ 0.4) | sketched | The headline subpopulation control — MS surface-N/He enrichment, lifetime shift, lowered WR threshold, CHE. Real MIST v2.5 data, a **third provider axis**; 2-point ⇒ toggle/snap. **Gated on the one-time mass-ramp diff** (does v2.5 ramp rotation in by mass?). | `whirling-cohort-atlas.md` (Tier A) |
| [α/Fe] spectral axis | idea | Thick-disk/halo subpopulation via a **CAP18-*large*** re-bake (axis-generic bake drops it in like the CAP18 swap). Spectrum-only — the *track* won't follow α (that's Tier D). | `whirling-cohort-atlas.md` (Tier B) |
| Spectra density bump / hot-end / B-star detail | idea | Re-bake at higher res (CAP18 `high`/`ultra`, OSTAR `medium`/`high`) or splice **BSTAR2006** (NLTE B-star, 15–30 kK) — pure data work; runtime stays axis-generic. | `graceful-toasting-thimble.md` §Next |
| Endgame Chunk 6 — WD spectra (Koester DA + TMAP hot WD/CSPN) | planned | Separate WD cube at log g 7–9 (Chunk 0 scoping ✅: Koester DA = GO, TMAP = conditional, Koester DB = no-go). New `/wd_spectrum` sibling route + reader/converter. | `smoldering-cinder-gateway.md` §Chunk 6 |
| Endgame Chunk 7 — WR spectra (PoWR) | planned | **Highest risk** — PoWR's wind axis (T\*, Rt) must be assumption-mapped from MIST's Ṁ; own cube + emission-line panel. Honest placeholder if it sinks. | `smoldering-cinder-gateway.md` §Chunk 7 |

### 3. Big engines — formerly "out of scope," now candidates *with a cost* ("nothing is out of scope")

| Item | Status | Hook | Where |
|---|---|---|---|
| Binarity / mass transfer | idea | The biggest lever — **~70% of WR are binary-stripped**; also blue stragglers, Algols, stripped-He, GW-progenitor pop. Needs a binary engine or a precomputed grid (BPASS / POSYDON / MESA-binary) behind a new provider. | `whirling-cohort-atlas.md` (Tier D) |
| TPAGB thermal pulses | idea | The deferred messy phase (φ5) — 30–100 logL reversals/track, pulses at different EEP per mass ⇒ **per-grid handling, never cross-mass interp** (snap-to-track, like the endgame). No dedicated chunk yet; the endgame's snap precedent is the path in. | CLAUDE.md §Next; spec §6 |
| Initial-helium / multiple populations | idea | GC He-enhanced second generations (the "second parameter"); needs grids that vary Y independently of Z (a He axis) or MESA runs at varied Y. | `whirling-cohort-atlas.md` (Tier D) |
| α-enhanced **evolution** | idea | α-enhanced MESA tracks so HR position + lifetimes follow α (vs the Tier-B spectrum-only version). | `whirling-cohort-atlas.md` (Tier D) |
| Live solver / reduced nuclear network | idea | The ultimate "any star" capability; large, only worth it if the grid approach hits a real wall (spec §9). | `whirling-cohort-atlas.md` (Tier D); spec §9 |

### 4. Minor / probably-skip — recorded so we don't re-propose them

| Item | Status | Hook | Where |
|---|---|---|---|
| Gravity darkening / oblateness (von Zeipel) | idea | Beautiful Regulus-look for fast rotators; evocative, partly cosmetic (corona-tier honesty). Needs rotation × inclination. | `whirling-cohort-atlas.md` (Tier C) |
| Magnetic peculiarity (Ap/Bp, magnetic O) | idea | Chemically-peculiar / spotted flavor only — evocative surface-abundance visual. | `whirling-cohort-atlas.md` (Tier C) |
| Microturbulence (ξ) | idea | Spectral line-saturation knob (CAP18-large carries it); real but thin pedagogy — likely not worth a control. | `whirling-cohort-atlas.md` (Tier B) |

## Suggested sequencing (synthesis across the plans)

The cheapest-honest-win-first order the individual docs already imply, merged:

1. **Instability-strip HR overlay** — zero new data, immediate subpopulation payoff.
2. **SED Chunk 1 → Chunk 3** — the coronal band, then its age/slider collapse (frontend-only).
3. **Endgame Chunks 2–5** — the full WR/WD gateway on data already on disk (backend Chunk 1 is done).
4. **Rotation `vvcrit` toggle** — the substantive answer to the rotation question; do the mass-ramp diff first.
5. **SED Chunk 2** (wind radio, spine touch) and **v sin i broadening** — the predictive/visible rotation follow-ons.
6. **Endgame Chunks 6–7** + **[α/Fe]** + **spectra density** — the data-gated spectrum work.
7. **The big engines** (binarity → He axis → α-evolution → live solver) — when one feature justifies the lift; binarity is highest-value and highest-cost.

Cross-cutting caution (from the atlas): every new axis multiplies the grid and the UI;
prefer **toggles for discrete real axes** and **views/overlays** over yet another slider,
and keep spectrum-only axes ([α/Fe], v sin i) visibly distinct from evolution axes so a
spectrum-panel knob never implies the star's *track* changed.

## Honesty tiering (the project rule, applied to this list)

Every entry is tiered by **what data backs it**, never by what we wish it showed —
the recurring boron-b8 / VO-7400 / invisible-Na lesson. Tier-1/2 items change the real
`StellarState` or the baked spectrum from real grids; Tier-3 engines need new data/physics;
Tier-4 are evocative-only and must be labeled like the corona (spec §7). When building any
of these, the "don't label a non-feature" check comes first: measure that the effect is
*visible and real through the runtime path* before shipping a guide/control for it.
