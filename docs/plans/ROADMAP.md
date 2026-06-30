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
| Instability-strip / variable-class HR overlay | **done** | Shipped: an opt-in toggle on the HR panel shades the classical instability strip (δ Scuti / RR Lyrae / Cepheids, one tilted κ-mechanism band) + LBV and Mira zones as a labeled, schematic *view*. Frontend-only (`hr.js` `setOverlay`). | `whirling-cohort-atlas.md` (bonus) |
| SED Chunk 1 — cool-star coronal X-ray + radio **band** | ✅ done | Shaded `L_X/L_bol` 10⁻⁷…10⁻³ envelope in `sed.js`, frontend-only; **placement is Teff-only** (L_bol cancels via the blackbody effective width 1.521·λ_peak). Güdel–Benz radio = a compact floor marker (it buries on the Fλ axis — kept FLOOR_DECADES=14; the real radio-above-floor payoff is Chunk 2's wind tail). Gated Teff+logg (cool / hot-wind-shock / A-gap / cool-giant). | `magnetic-ember-broadcast.md` §Chunk 1 |
| SED Chunk 3 — band → **line** (age-derived + slider) | ✅ done | Shipped: gyrochronology (Ballesteros→MH08→Wright, all-Wright calibration, Sun→10⁻⁶·²) collapses the band to a cool-blue line for MS cool stars (default-from-age) + a user rotation-period slider (drag-to-override); ±dex fuzz, gated redward of the (B−V)=0.495 singularity, line only in the cool branch. Frontend-only (`sed.js`). | `magnetic-ember-broadcast.md` §Chunk 3 |
| Endgame Chunk 2 — reversible WD gateway + WD mode shell | **done** | Shipped: the "→ Continue: White Dwarf" button at the slider limit, reversible `wd-mode`, 3-zone log-cooling scrub (pulses→central star→cold cinder), live mass/[Fe/H] re-snap, the Teff-coloured WD cooling track on the wide HR axes. Frontend-only. | `smoldering-cinder-gateway.md` §Chunk 2 |
| Endgame Chunk 3 — WD 3D shader + structure panel | **done** | Shipped: smooth degenerate-sphere shader (granulation off via a log g gate so the TPAGB giant still boils; corona off; cooling color from Teff) + a data-driven layered structure cross-section (C/O core + DA atmosphere from the model; He buffer & thicknesses schematic, envelope thinning with log g; crystallization in the CORE with a log g-gated onset). Frontend-only. | `smoldering-cinder-gateway.md` §Chunk 3 |
| Endgame Chunk 4 — WR mode shell + HR + composition | ✅ done | Shipped: reversible `→ Continue: Wolf–Rayet` gateway (feh-threshold-gated), index-linear scrub over the φ9 sub-track (WN→WC landmark), HR axes to ~316 kK / logL 7, the **normal comp views** carrying the stripped-surface WN→WC→WO story from real data, WN/WC/WO subtype from surface composition, mass-stays-live re-snap, end caption narrates the un-modeled core-collapse. 3D = smooth hot-sphere placeholder (Chunk 5 owns the wind shader). 31/31 Playwright. | `smoldering-cinder-gateway.md` §Chunk 4 |
| Endgame Chunk 5 — WR 3D wind shader | ✅ done | Shipped: optically-thick-wind look (`star.js` `WIND_FRAG` + `wind` mesh) — limb-brightened electron-scattering haze + outward-advected value-noise filaments over the opaque hot sphere; reach/density read from `Z_surf` (smooth WN → clumpy WC/WO), honest Teff color (no chemistry hue — it'd contradict the spectrum placeholder), clamped-L intensity (not a measured Ṁ); **fit-to-frame extent** because the WR scrub opens on a huge R≈33 R☉ star that would clip. Frontend-only. Closes the on-hand-data endgame work. | `smoldering-cinder-gateway.md` §Chunk 5 |
| v sin i line broadening | sketched | Frontend convolution of the baked spectrum with a rotation kernel; honest but **narrow** (visible only >125 km/s at R≈2400) — pairs with the rotation axis. | `whirling-cohort-atlas.md` (Tier B) |
| Nine user-reported UX refinements (HR clipping · endgame captions/buttons · readout panel · panel jitter · gateway auto-appear · age-slider remap) | **A–E done ✅** | Triaged + chunked into 5 sessions: **A ✅** HR framing (items 5/6) — endgame views auto-fit to `fitBounds`; living view a **hybrid** (fixed teaching frame, expand only raw-overflow edges — preserves the inter-star scale cue, per advisor) not the planned widen-to-7; + WD living preview dashed→solid-grey **directional leader** (AGB tip→hot knee, `→ white dwarf`, SN-suppressed) fixing the "clipped/unclear" diagonal. **B ✅** endgame quick-wins — 7 WR SED caption now branches on `endgameWR` (wind-not-dynamo, core-collapse not WD; the surviving "white dwarf" is a corrective negation) · 8 Lane–Emden-for-WR = *generic intro adequate, no fix* (WR shows generic, WD shows polytrope hint) · 9 `.endgame-back` restyled to compact filled-accent yellow. **C ✅** layout (items 1/4) — 1 readout split into its own draggable `readout` panel (saved layouts append it last; Reset restores authored order); 4 jitter cured by a **user redirect**: instead of reserving *empty* space, the WD/WR gateway button is **always placed but `disabled`/greyed until end-of-life**, where it enables and "lights up" (same box → no resize) — the SN dead-end note likewise foreshadows from ZAMS (user-confirmed). **D ✅** gateway auto-appear (item 3) — repro **disproved the "never appears" logic bug**: post-C the button *does* auto-appear (~0.6 s, no age nudge). Root cause is **latency/perception** — `refreshTrack` clears the gateway children then the ~1 MB `/endgame` fetch (serialized after `/track`, + a redundant double-fetch) leaves the reserved slot **blank** for ½–2 s, reading as "nothing happened." Fix (2 parts, 2nd advisor consult): a muted *"Computing the star's fate…"* placeholder (gated on an in-flight `endgameLoading` flag, **not** `!!eg` — the `!!eg` first cut was dead code that stuck the spinner on a fetch failure) **+ a safe de-dup** (`refreshTrack` tail `updateLiveGateway()`→`updateGateway()`) that stops the redundant 2nd `/endgame` from discarding the already-landed preview response → button **+474 ms vs +628**; touches no token internals. + the **deferred resnap note now moved below the sliders** (grows the panel downward, not shoving the controls). Verified across WD↔SN↔WR both ways + a `/endgame`-abort (no stuck spinner). Then the true root was **also done (user opted in)** — a type-only **`/endgame?meta=1`** (~120 B vs ~1 MB; adds `has_states`) + a purely-additive frontend `fetchEndgameMeta()`/separate cache that **structurally decouples** the button from the 1 MB (it lights from the tiny meta while the full fetch still pre-warms preview/enter — the load-bearing slam-to-end prefetch stays eager, so bandwidth is unchanged). Warm-localhost saving is **modest (~15–30 ms on the /endgame hop**; the "66%" earlier claim was a cross-session artifact), bigger when the full is cold/contended; cold first call unchanged (placeholder covers it). + advisor-caught **enable-gating** (`disabled=!atEnd||!eg`) so the button can't dead-click in the meta→full gap (the exit→re-enter path). 1 meta+1 full per change (no double-fetch), all abort combos no-stuck-spinner, 138 pytest. **E ✅** age-slider remap (item 2) — the slider is now **linear in EEP, not age**: the marker is **picked straight from the already-fetched track by row** (no `/state` fetch — like the WD/WR scrubs), so the dead MS plateau (85–90% of the old linear-age slider) is gone and every phase gets fair, **mass-invariant** travel (post-MS = a constant 58.5%; the MIST track is a fixed 606 rows split MS 42/RGB 25/CHeB 17/EAGB 17% at every mass). Advisor reframed it as two decisions, both settled by measurement: (1) the marker MUST come from the EEP coordinate, not an age round-trip — flat-age bands (the 1 M☉ CHeB **blue loop** = 48 EEP rows over ~4,800 yr) would be degenerate under `/state?age=`, killing age-fetch/log-age/piecewise-in-age; (2) **linear-in-EEP** (matches `comp.js` `xOf(eep)` exactly → age thumb & comp marker in lockstep), not piecewise. Pick-from-track over a backend eep-fetch: no Protocol change, fetch-free instant scrubs, and it *simplifies* — landmarks position by row index, `ageValue` is a derived honest readout, the razor-sharp off-by-one is obsoleted. Preserve-absolute-age on a mass change (thumb jumps; spring-back kept). Both advisor gates verified in the running app: dead bands animate (CHeB Teff×~1400 K/L×~50, RGB Teff 9–12 kK; EEP strictly advances), Sun on the §10 anchor under nearest-row (L=1.07/Teff=5835/4.63 Gyr — within 0.3%/0.6 K of exact, no scalar-interp needed); gateway greyed through MS/EAGB, enables only at the true end; zero page errors. Frontend-only. | `polished-cinder-frame.md` |

### 2. Backend / data touch — real, bounded effort

| Item | Status | Hook | Where |
|---|---|---|---|
| SED Chunk 2 — hot-star **wind free–free radio** from Ṁ | planned | The one *predictive* non-thermal piece; needs `mdot_msun_yr` on the spine (`star_mdot` already in cache v9, not yet blended). Solid line vs the evocative band. | `magnetic-ember-broadcast.md` §Chunk 2 |
| Rotation `vvcrit` axis (0.0 ↔ 0.4) | sketched | The headline subpopulation control — MS surface-N/He enrichment, lifetime shift, lowered WR threshold, CHE. Real MIST v2.5 data, a **third provider axis**; 2-point ⇒ toggle/snap. **Gated on the one-time mass-ramp diff** (does v2.5 ramp rotation in by mass?). | `whirling-cohort-atlas.md` (Tier A) |
| [α/Fe] spectral axis | idea | Thick-disk/halo subpopulation via a **CAP18-*large*** re-bake (axis-generic bake drops it in like the CAP18 swap). Spectrum-only — the *track* won't follow α (that's Tier D). | `whirling-cohort-atlas.md` (Tier B) |
| Spectra density bump / hot-end / B-star detail | idea | Re-bake at higher res (CAP18 `high`/`ultra`, OSTAR `medium`/`high`) or splice **BSTAR2006** (NLTE B-star, 15–30 kK) — pure data work; runtime stays axis-generic. | `graceful-toasting-thimble.md` §Next |
| Endgame Chunk 6a — WD spectra (**Koester DA**) | ✅ done | Separate rectangular (82 Teff × 13 log g) Koester DA cube, pure-H (no [Fe/H]), host-baked (no Docker/pymsg). New `/wd_spectrum` sibling + `fetch_koester.py` + `bake_wd_spectra.py`; DC-below-floor + 80 kK no-model honesty edges; phase-aware switch at log g 6.0; 15 tests. | `smoldering-cinder-gateway.md` §Chunk 6; recipe §8 |
| Endgame Chunk 6b — hot WD/CSPN spectra (**TMAP**) | planned | Fills the >80000 K no-model gap (the ~107 kK central star): NLTE H+He, 50–190 kK, an LTE↔NLTE seam at 50–80 kK, the ×π×10⁸ TMAP unit gotcha, vacuum λ. Splices as the hot slab of the *same* WD cube (Chunk 0 scoping ✅: conditional GO, SVO bulk only). | `smoldering-cinder-gateway.md` §Chunk 6 (6b) |
| Endgame Chunk 7 — WR spectra (PoWR) | planned | **Highest risk** — PoWR's wind axis (T\*, Rt) must be assumption-mapped from MIST's Ṁ; own cube + emission-line panel. Honest placeholder if it sinks. | `smoldering-cinder-gateway.md` §Chunk 7 |
| **Core-collapse SN + NS/BH endgame** (fills the dead SN branch) | idea | **NOTED by the user, no design yet.** Turn the current core-collapse `type="SN", states=[]` dead-end into a real arc: a **⁵⁶Ni-powered semi-analytic light curve** (Arnett-style ⁵⁶Ni→Co→Fe) + **homologous ejecta expansion** + neutron-star/black-hole remnant (another mass threshold above WD↔SN) + *maybe* light nucleosynthesis. **Explicitly NO explosion mechanism** (hydro = infeasible — model the aftermath, not the bounce). **Verification = real observed light curves** (project honesty rule). Needs a **new data source** (MIST ends at collapse). **Type Ia is NOT this arc** — it's a thermonuclear WD event that needs the **binarity engine** (§3) and branches off the WD endgame, not core-collapse. | new memory `star-sim-supernova-remnant-endgame.md`; no plan doc yet |
| Real interior structure (MESA `profile.data`) | idea | The honest successor to the Lane–Emden panel: ingest MESA *radial* profiles — ρ(r), T(r), P(r), composition(r), and the **real convective/radiative boundaries** the polytrope's single `n` only fakes — for the *selected* star, and overlay the true ρ(r) on the polytrope to *show* how good the idealization is. A **new radial-profile object** (not a `StellarState` scalar set, not the polytrope sibling) + a sibling route; MIST has no profiles at all ⇒ MESA-only (a live structure solve is ruled out by spec §2/§9); age-coupling ⇒ per-age profile snapshots (storage cost — MESA's grid is sparse/opt-in). | CLAUDE.md (Lane–Emden); no plan doc yet |

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

1. ~~**Instability-strip HR overlay**~~ — **done** (zero new data, immediate subpopulation payoff).
2. ~~**SED Chunk 3**~~ — **done** (gyrochronology + rotation-slider line collapsing the Chunk-1 band, frontend-only).
3. ~~**Endgame Chunks 4–5**~~ — **done** — the full WR/WD gateway on data already on disk (backend Chunk 1 + frontend Chunks 2 & 3 ✅ + **Chunk 4 ✅** = the WR mode shell + HR + stripped-surface WN→WC→WO composition + WN/WC/WO subtype + **Chunk 5 ✅** = the WR 3D optically-thick-wind shader). **On-hand-data endgame work is complete**; what remains is the data-gated spectra (Chunks 6–7).
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
