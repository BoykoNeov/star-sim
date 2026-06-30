# Plan: Core-collapse supernova + compact-remnant endgame

## Context

The endgame gateway (`docs/plans/smoldering-cinder-gateway.md`) renders two of the
three fates a MIST star can reach: white dwarf and Wolf–Rayet. The third —
**core collapse** — is today an honest dead-end: `MISTProvider.endgame()` returns
`type="SN", states=[]`, and the frontend shows a static note ("*Core collapse. A
N M☉ star ends as a supernova, leaving a neutron star or black hole — a remnant
this simulator doesn't model.*"). This plan turns that dead-end into a real
renderer, the way WD/WR became real renderers — the user's NOTED-but-undesigned
arc (memory `star-sim-supernova-remnant-endgame.md`).

**The key difference from WD/WR (measured, not assumed):** WD and WR were already
*on* the MIST tracks (just clipped by the `phase>=5` window). The supernova is
**not** — MIST tracks end at core collapse and carry no explosion or light-curve
data. So this is **not** a window extension and **not** a snap-to-track: it is a
**computed semi-analytic model**, parametrized by progenitor-derived inputs. That
makes it a **sibling** (like `lane_emden.py` / `spectra.py`), not a provider
extension.

## Locked constraints (from the user — treat as requirements, not suggestions)

1. **⁵⁶Ni-powered light curve** is the observable centerpiece — a *semi-analytic
   radioactive-decay* curve (⁵⁶Ni→⁵⁶Co→⁵⁶Fe deposition powering an expanding
   photosphere), **not** a hydro simulation.
2. **Homologous ejecta expansion** (v ∝ r) — the visual + the timescale that sets
   the light-curve width.
3. **"Some nucleosynthesis maybe"** — explicitly tentative. At most the ⁵⁶Ni mass +
   the decay chain, perhaps a few yield species. **No full nuclear network.**
4. **NO computational explosion mechanism** — named infeasible and ruled out. Model
   the *aftermath* (parametrized: M_Ni, M_ej, E_K → light curve), never the bounce.
5. **Observed light curves are the verification anchor** — real published SNe
   (SN 1987A ⁵⁶Co tail; SN 1999em / 2004et IIP plateau), the project honesty rule.
   Do not reconstruct peaks/slopes from memory; pull real photometry and cite.

**Type Ia is a SEPARATE path — not built off this branch.** Ia is a thermonuclear
WD event needing accretion / WD–WD merger → the **binarity engine** (ROADMAP §3),
branching off the **WD** endgame. A lone MIST star never reaches Chandrasekhar on
its own. Out of scope here; noted so future-you doesn't start it off the wrong branch.

## Architecture: a hybrid sibling (advisor-affirmed)

The arc is a **hybrid** — classification stays on the spine, computation is a sibling:

1. **Classification stays in `PROVIDER.endgame()`.** It already returns `type="SN"`
   plus snapped progenitor scalars — that is §3-clean *routing metadata*, not a
   model. Do **not** relocate the classifier into the sibling.
2. **A new sibling `supernova.py` + `/supernova` route** (bypasses `PROVIDER`, like
   `/polytrope` and `/spectrum`) does the light-curve **computation**. It *consumes*
   the progenitor scalars `endgame()` exposes (a consumer is allowed to read a
   `StellarState`/`EndgameResult`) and produces a computed model.
3. **The sibling emits BOTH** (a) photosphere `StellarState`s — the expanding
   photosphere has real L/Teff/R at each post-explosion time, so the *existing* 3D
   star, SED, and scale-bar consumers are fed StellarStates exactly as WD/WR feed
   them (§3 holds; the source is just "computed", not "provider") — **and** (b) a
   **light-curve object** (L vs days/months) that a new panel eats. This answers the
   open §3 question: the SN state can be a `StellarState` *and* a sibling object.
4. **Progenitor-input channel = scalar fields on `EndgameResult`** (lean choice over
   re-populating the deliberately-emptied `states`): `pre_sn_radius_rsun`,
   `he_core_msun`, `co_core_msun`, `h_retained` (and the existing `final_mass_msun`).
   Needs a **`CACHE_VERSION` bump** to parse the `he_core_mass` / `c_core_mass` /
   `o_core_mass` columns (confirmed present & sane — see the gate). The classifier
   and these scalars are the only spine touch; `StellarState` itself stays untouched.

## The honesty tiering — this IS the arc (lead with it)

The light curve has three tiers of trustworthiness. The build must label them so the
UI never implies the peak brightness is *predicted*:

- **Tier 1 — bulletproof, zero free parameters: the ⁵⁶Co radioactive tail slope.**
  0.0098 mag/day (≈0.98 mag/100 d), set *only* by τ_Co = 111.3 d. This is the
  verification jewel and the centerpiece anchor — **not** the peak. (SN 1987A's tail
  is the textbook match.) The gate reproduces it to 0.00976 mag/day.
- **Tier 2 — shape from the progenitor (+ one canonical E, + assumed κ): plateau
  luminosity & duration, rise time.** M_ej and R0 come from MIST; Popov(1993) /
  Kasen–Woosley(2009) give the IIP plateau from (E, M_ej, R0). Robust in *shape*,
  ±dex in *level* (the SED-Chunk-2 lesson).
- **Tier 3 — absolute scale needs a free input: peak L / tail height ∝ M_Ni.**
  *Not* derivable from MIST (0.001–0.3 M☉ observed). This is a **slider**, canonical
  default (0.06 M☉) + observed range. Label: *"the shape is your star's; the
  brightness scale is set by the (unmodeled) explosion's nickel yield — drag it, see
  where real SNe land."*

## Measured grounding — Chunk 0 gate (DONE; facts on disk, re-verify if grids change)

Ran over the full MIST v2.5 grid (5 [Fe/H] × 2 vvcrit). Scripts lived in the
scratchpad (`sn_gate.py`, `sn_lightcurve.py`); re-run against `feh_*/eeps/*.track.eep`.

1. **Whole-grid classification:** WR 329 · WD 996 · **SN 279** · none 102. Every grid
   scanned (18–39 SN tracks each, more at low [Fe/H] — weaker winds, less stripping,
   fewer WR).
2. **The SN bucket is PURELY Type II.** All 279 SN-classified tracks **retain
   hydrogen** (surface H 0.30–0.75); **zero stripped Ib/c** — because the stripped
   stars classify as **WR** (the 329). ⇒ **v1 SN arc = Type II / IIP.** Stripped-
   envelope **Ib/c is physically the WR endpoint** (the WR scrub already narrates
   "next is core-collapse"), a natural **follow-on chunk**, not part of the SN-branch
   v1. (The Xs≈0.30 tail = thin-H IIb/IIL; could sub-type by surface H later.)
3. **Core masses present & sane** (0 unphysical of 279): `he_core` 1–84 M☉, monotone
   `he ≥ c ≥ o ≥ 0`, all `< final_mass`. ⇒ clean **ejecta/remnant split** available
   (with the cache bump). Very-massive φ3-enders carry `o_core=0` (no explicit O core
   built at window end) — use `c_core` as the CO-core proxy there.
4. **The φ5 bulk (~7–30 M☉) are red supergiants** (final-phase R ≈ 400–1100 R☉) →
   IIP plateau physics applies. **But the bucket is NOT uniformly RSG** (advisor-
   caught): a **compact very-massive low-Z tail** (140–160 M☉ φ3-enders, R ≈ 75–260
   R☉, `o_core=0`) is not a red supergiant, so the Popov/KW *IIP plateau* model does
   **not** cleanly apply there — Chunk 1 scopes the plateau to the RSG bulk and routes
   the compact tail to an honest fallback (no-plateau / labeled).
   **R₀ is an OPEN calibration knob, NOT settled by the gate.** The final-phase-median
   underestimates the pre-collapse radius (it averages in the compact pre-RSG CHeB
   rows — 15 M☉: R_last=R_max=912 but R_fpMed=696), and a larger true R₀ pushes t_p
   *longer* (∝R₀^{1/6}). The terminal EEP row is a low-gravity artifact for *some*
   tracks (R_last/R_prev5 drops to ⅓ in the worst case) but is R_max for others — so
   the robust R₀ estimator (terminal vs max-near-end vs final-phase-median) is a
   Chunk-1 calibration decision, not "gate-confirmed."
5. **Canonical curve lands in regime** (15 M☉ solar: M_fin 11.98, M_ej 10.6,
   R₀≈696–912, M_Ni 0.06, E 1e51): **plateau 1.5×10⁴² erg/s, t_p 133 d**, radioactive
   tail 6×10⁴¹→6×10⁴⁰ over 50→300 d, **Co-tail slope 0.00976 mag/day** (= analytic =
   textbook 0.0098). The gate confirmed *a* curve lands in regime; t_p 133 d ran ~30%
   past typical observed IIP (~100 d, and past the quoted 80–120 d) — recorded as the
   **Tier-2 duration/level uncertainty** (sensitive to R₀, T_ion, κ), not a clean
   prediction. The Tier-1 Co-tail slope carries the predictive weight.

**Gate verdict: shape-GO, scale-via-slider** (exactly the advisor's bet, the
SED-Chunk-2 pattern). Constants cited in the implementation: Nadyozhin(1994) decay
energetics (ε_Ni 3.9e10, ε_Co 6.8e9 erg/s/g), Kasen–Woosley(2009) plateau scalings,
τ from the ⁵⁶Ni (6.075 d) / ⁵⁶Co (77.2 d) half-lives.

## Chunk breakdown

Foundation → frontend gateway+light-curve → 3D fireball→remnant → ejecta
composition → remnant branch. The gate set the honest scope; later chunks stay
sketches until their predecessor lands. Every chunk leaves `main` green (backend
tests) or a Playwright pass (frontend), per house style.

### Chunk 0 — measure-first gate (research) — ✅ DONE
See *Measured grounding* above. Verdict: shape-GO, scale-via-slider; SN branch is
Type II only; core masses + R₀ available; canonical curve in regime.

### Chunk 1 — Backend: the `supernova.py` sibling + progenitor scalars — ✅ DONE
**Built (215 pytest green; measured through the runtime path):** `EndgameResult` gained
`pre_sn_radius_rsun` / `he_core_msun` / `co_core_msun` / `h_retained` (SN branch only, `None`
elsewhere); `CACHE_VERSION` 11→12 parses `he_core_mass`/`c_core_mass`/`o_core_mass` (the
Mcur pattern — cached, read off the snapped track, never blended). `supernova.py` is a pure
sibling (imports only `state.StellarState`); `/supernova` bypasses `PROVIDER` for the compute
but calls `PROVIDER.endgame()` for the progenitor. **R₀ estimator settled = max radius over
the final-phase rows EXCLUDING the terminal EEP row** (the low-g artifact can spuriously
inflate *or* shrink it; the max beats the median, which the gate found underestimates).
Light curve = `w·L_p·rise + (1−w)·L_radio` (the blend suppresses the t=0 deposition spike a
`max()` would surface). **Measured canonical 15 M☉ solar (real snapped):** final 11.976,
R₀ 911.5, CO core 2.796 → NS 1.4, M_ej 10.58, v_phot 3083 km/s, plateau **1.83×10⁴² erg/s /
t_p 138.7 d**, Co-tail slope **0.00976 mag/day** (= analytic). **Two advisor-led test
corrections, both validated by the measurement:** (1) the Tier-3 test scales the radioactive
**tail**, not the peak — the IIP peak IS the plateau (`L_p`), which carries no M_Ni term, so
"peak ∝ M_Ni" would go red on the canonical case; (2) the Tier-1 Co-slope is measured on the
served `L_radio` **component** (0.00976) — on `L_total` the plateau cutoff bleeds in and
steepens it to 0.01023, so the clean anchor needs the component. Solar SN bucket is all-RSG
(R₀ 416–1163, no compact tail → the no-plateau fallback is unit-tested on a synthetic R₀<300
compact low-Z progenitor, the gate's 140–160 M☉ low-Z case). Remnant NS/BH from a labeled CO
cut (BH for CO > 7 M☉; solar SN crosses it at ~30 M☉). `logg` left honestly negative (−5 late;
the boiling-fireball gate is Chunk 2's `{endgame:"sn"}` signal). Photosphere composition is a
labeled H-rich placeholder (Chunk 4 does the real ejecta). **Original spec retained below.**

**Goal:** the computed light curve + photosphere states, behind a new sibling route,
fed by progenitor scalars from `endgame()`.
**Do:**
- **`EndgameResult` scalar fields** `pre_sn_radius_rsun` / `he_core_msun` /
  `co_core_msun` / `h_retained`, populated by `MISTProvider.endgame()` for the SN
  branch (the robust final-phase-median R₀; CO core = `c_core` proxy). **`CACHE_VERSION`
  bump** to parse `he_core_mass`/`c_core_mass`/`o_core_mass`. Other providers leave
  the new fields `None`. `StellarState` untouched.
- **`supernova.py`** — `supernova_model(progenitor, m_ni, e_kin)` returning a
  light-curve object (time grid in days; L_total = plateau ⊕ radioactive tail) +
  `list[StellarState]` photosphere samples (homologous R(t)=v·t, v from E_K/M_ej;
  Teff/L from the photosphere). Tier-1 Co tail + Tier-2 Popov/KW plateau + Tier-3
  M_Ni scaling, all from Chunk 0's validated formulae. **Scope the plateau to the RSG
  bulk** (R₀ in the RSG range); the **compact very-massive low-Z tail gets an honest
  no-plateau fallback** (a labeled radioactive-only curve — the plateau model assumes
  a RSG envelope it doesn't have). **Pick the R₀ estimator here** (the open calibration
  knob from the gate — terminal vs max-near-end vs final-phase-median; the final-phase-
  median underestimates). Remnant type (NS/BH/failed) from a labeled CO-core / mass cut
  (Chunk 5 refines).
- **`/supernova` route** (bypasses `PROVIDER`; calls `PROVIDER.endgame()` internally
  for the progenitor, then the sibling) returning the light curve + states + scalars
  (type, M_ej, M_Ni default+range, E_K, remnant, peak L, plateau dur).
**Tests (§10, measured through the runtime path):** Co-tail slope = 0.0098 mag/day;
plateau L & duration in regime for the canonical 15 M☉; M_ej = final − remnant;
type="II" for the H-retained branch; the route returns `none`/honest empty for a
WD/WR/none progenitor; M_Ni scales peak linearly.
**Depends:** Chunk 0.

**Deferred to Chunk 2 (user-decided at build time):** the **observed-photometry
anchor** for Tier-1. As built, Tier-1 is verified against the *analytic* ⁵⁶Co formula
(2.5/ln10/τ_Co = 0.00975) — self-consistent, but not yet against real SN 1987A
photometry, which the user's locked constraint #5 ("pull real photometry and cite")
and the gate script ("OSC tables are a Chunk-1 deliverable") both call for. The user
chose to land it **with the Chunk-2 overlays** (where the curves are actually drawn and
compared on-screen), so Chunk 2 now carries that obligation — see its "observed-SN
overlays" item, which is the deferred deliverable, NOT optional polish.

### Chunk 2 — Frontend: SN gateway + mode shell + light-curve panel ✅ DONE
**Status (built):** reversible `sn-mode` mirroring WD/WR — the dead SN note is now a
`→ Continue: Supernova` gateway button (enabled at end-of-life, foreshadowed from ZAMS);
the HR panel CSS-swaps its title to **Supernova light curve** and `hr.setSupernova()`
redraws it as **L vs LINEAR days** (the straight ⁵⁶Co tail — a log-time axis would bend it
and break the Tier-1 visual check); the age slider becomes a **linear-days time scrubber**
(`snStateIndex` → nearest homologous state); the ⁵⁶Ni-mass `sn-control` slider (Tier-3,
0.001–0.3, debounced refetch) lifts the **tail not the plateau**; and the **cited
observed-photometry overlays** (`frontend/src/sn.js` — SN 1987A ⁵⁶Co tail + SN 1999em IIP
plateau, **published bolometric fits, not raw photometry**, cited in code AND a visible
`.hr-sn-caption`) are the deferred **Tier-1 anchor** (constraint #5 met). Consumers
(3D/SED/comp/scale/readout/classify) get the photosphere `StellarState` via an explicit
`{endgame:"sn"}` signal (NOT naive reuse — the `logg≈−5` ejecta would trip the
boiling-fireball gate); `star.js` shows a smooth glowing sphere (fireball is Chunk 3),
`comp.js`/`spectrum.js` honest placeholders, entry narrates the un-modeled bounce.
Mass/[Fe/H] stay live → re-snap (`trySNResnap`; WD/WR/none revert with a note).
Playwright-verified at 1440 + 390 px (zero console errors); 215 pytest (backend untouched).

**Goal:** a reversible "→ Continue: Supernova" gateway and the L-vs-time panel (the
observable), reusing the WD/WR scaffolding.
**Do:** replace the static SN note with the gateway button (enabled at the
end-of-life, like WD/WR; the SN note still foreshadows from ZAMS); reversible
`sn-mode`; **repurpose the HR panel to L-vs-time** in SN mode (the established WD/WR
pattern — the observable light curve, with the L-Teff trace secondary); a **post-
explosion time scrubber** (days→months→years, log); the **M_Ni slider** (Tier-3,
labeled) + canonical default; **observed-SN overlays** (real photometry — SN 1987A
tail, SN 1999em plateau — **the Tier-1 anchor deferred from Chunk 1**, satisfying
constraint #5: the analytic ⁵⁶Co slope must be shown matching SN 1987A's *measured*
tail, cited, not just its own formula) as the honest anchor; mass/[Fe/H] stay live
(re-snap → a different progenitor; WD/WR/none revert with a note). The 3D/SED/scale/
readout take the photosphere `StellarState`, **but via explicit mode signals — NOT
naive reuse** (the WD/WR discipline): `logg` is meaningless for freely-expanding ejecta
(a logg≈−5 photosphere would trip the existing consumers' `clamp((4−logg)/3)` gate and
render a *boiling fireball* with full granulation/corona). Pass an explicit
`{endgame:"sn"}` so the 3D/SED branch on the mode, not on `logg`. Narrate the un-modeled
bounce at *entry* (the explosion mechanism is the gap, mirroring WD's PN-ejection note).
**Verify:** Playwright at 1440 + 390 px. **Depends:** Chunk 1.

### Chunk 3 — 3D expanding fireball → remnant ✅ DONE
**Built (frontend-only; 215 pytest still green, backend untouched; Playwright-verified at
1440 + 390 px, zero JS/page errors):** `star.js` gained a `FIREBALL_FRAG` shader on a
dedicated `fireball` sphere mesh (reuses `star.geometry`, additive, depth-write off) and a
`REMNANT_FRAG` camera-facing additive dot mesh. In SN mode the surface sphere hides
(`star.visible=!sn`, set **unconditionally** so a mode switch can't strand a stale mesh) and
the fireball shows: 3D value-noise fbm mottling on a **bounded** time orbit (boils, no
unbounded drift/seam), center-bright with a soft round silhouette, color = the **honest
blackbody at the photosphere Teff** (the one load-bearing cue — blue-white→orange→red is the
real cooling). A single back-face-culled additive layer with clamped per-fragment alpha
(≤0.8) **keeps the hue + cell structure** instead of washing to white (the advisor's white-out
trap — verified clean). `main.js` `refreshSN` drives two scrub-derived beats: **`snGrow`**
swells the ball over the first ~14% of the scrub (an evocative "expanding" beat — the true
AU-scale R rides the scale bar, the WR decoupled-extent precedent), **`snFade`** dissipates it
over the late tail (the ball breaks into sparse wisps and dims toward nothing). As `snFade`→1
the **remnant** emerges: an **NS** → a tiny hot blue-white dot (color **labeled evocative, NOT
a Teff** — a real NS's optical thermal emission is negligible, Crab pulsar V≈16 synchrotron);
a **BH / failed SN** → no dot at all (the frame goes dark — the star "winks out"). Threaded via
`{endgame:"sn", remnant, snGrow, snFade}`. A late-time caption swap narrates the nebular phase +
which remnant emerges. **Measured grounding:** a BH-on-SN progenitor exists in-grid (**30 M☉
solar** → CO core 7.68 > the 7.0 cut → BH, vs the canonical **15 M☉ solar** NS), so winks-out
is NOT dead code — both verified on-screen. Evocative/labeled throughout (the corona/WR-wind
precedent, spec §7). **Depends:** Chunk 2.

### Chunk 4 — Ejecta composition / onion-shell (sketch)
Repurpose the composition panel (WD-style `setEndgame`) for the **pre-SN onion
structure** (Fe core → Si → O → C → He → H shells) from the progenitor core masses,
and/or the ejecta yield (⁵⁶Ni + a few species). The "maybe nucleosynthesis" — keep
it the honest, bounded version. **Depends:** Chunk 2.

### Chunk 5 — Remnant branch: NS / BH / failed-SN (sketch)
The remnant as a **labeled, deliberately-simplified mass cut** (CO-core / progenitor
mass), explicitly *not* a crisp prediction (reality = "islands of explodability",
non-monotonic compactness). Add the **direct-collapse-to-BH / failed-SN** branch —
some massive progenitors give little/no optical display ("the star just winks out"),
honest and visually striking. **Depends:** Chunks 1–3.

### Follow-on (not v1) — Ib/c via the WR endpoint; SN spectra
- **Ib/c stripped-envelope SNe** chain off the **WR** scrub endpoint (the stripped
  core core-collapses) — a "→ Continue: Supernova" at the end of WR mode, reusing the
  Chunk-1 model with no H plateau (pure Arnett ⁵⁶Ni peak + tail). A natural next arc
  once the Type II branch ships.
- **SN spectra** (P-Cygni, photospheric → nebular) are data-gated and likely an
  honest placeholder for v1 (no easy grid). Omit the early shock-breakout / shock-
  cooling phase explicitly (a separate hard piece).

## Risk register

- **Scale is genuinely uncertain (M_Ni, E_K).** Mitigation = the Tier-3 slider +
  observed-SN overlays; never imply peak L is predicted.
- **NS/BH is not a clean threshold.** Mitigation = label the cut a deliberate
  simplification; add the failed-SN branch.
- **R₀ definition is unsettled** (the gate did NOT confirm one). Final-phase-median
  underestimates (averages in compact pre-RSG rows); the terminal row is an artifact
  for some tracks but R_max for others. Mitigation = pick/calibrate the estimator in
  Chunk 1 against observed plateau durations; it drives t_p (∝R₀^{1/6}).
- **Plateau model is RSG-only.** The compact very-massive low-Z tail (140–160 M☉ φ3-
  enders) has no RSG envelope → no clean plateau. Mitigation = labeled radioactive-
  only fallback for that tail; don't force a plateau where the physics doesn't hold.
- **`logg` is meaningless for ejecta.** The existing 3D/SED consumers gate on
  `clamp((4−logg)/3)` → a logg≈−5 photosphere = a boiling-fireball false render.
  Mitigation = explicit `{endgame:"sn"}` mode signals (the WD/WR precedent), not reuse.
- **Plateau model ±dex in level** (KW normalization, T_ion/κ assumptions). Mitigation
  = honest labeling; the Tier-1 tail slope carries the predictive weight.
- **Observed-photometry licensing/format.** Pull from OSC / published tables, cite,
  gitignore large data; a couple of canonical SNe suffice (no big grid).

## Open questions (resolve at build time)

- Scrub axis labeling: "days since explosion" (log) — and how far to run (the nebular
  tail goes years).
- Whether the light curve gets its own new panel or repurposes HR (lean: repurpose
  HR, the WD/WR precedent).
- How much of the onion-shell / yield to show (Chunk 4) vs keep minimal.
- Bolometric vs a band (the model is bolometric L; observed overlays are often V-band
  — reconcile honestly or stay bolometric and say so).

## Pointers / resume

- This plan: `docs/plans/radioactive-afterglow-requiem.md`.
- Constraint memory: `docs/memory/star-sim-supernova-remnant-endgame.md`.
- Precedents: WD/WR gateway (`smoldering-cinder-gateway.md`), the sibling routes
  (`lane_emden.py`, `spectra.py`), the SED Chunk-2 measure-first correction
  (`magnetic-ember-broadcast.md`), the corona (evocative + labeled).
- Gate scripts: scratchpad `sn_gate.py` (classify + progenitor scan) and
  `sn_lightcurve.py` (Arnett/Popov canonical curve).
- ROADMAP: `docs/plans/ROADMAP.md` — move the SN row from "idea" as chunks land.
