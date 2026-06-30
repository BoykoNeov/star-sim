# Plan: Rotation & the subpopulation-control atlas

## Status: DISCUSSION CAPTURED (nothing built). A landscape, not a single feature.

This is a survey of **what extra controls would let the sim show different
subpopulations of stars**, prompted by the rotation question below. Unlike the
other plan docs it is not one chunked build — it is the menu we choose builds
from. Per the user: **"nothing is out of scope."** So the old spec §2/§9 walls
(no binary engine, no live solver) are recorded here as *candidate directions
with a cost*, not as forbidden. The project's honesty culture stays: every entry
is tiered by **what data actually backs it**, never by what we wish it showed.

## Context — the question that started this

The user was discussing a **rotation slider to narrow the X-ray emission** of a
star (the SED Chunk 3 work, `magnetic-ember-broadcast.md`). They then observed:
for **Wolf–Rayet stars, rotation combined with age affects more than just the
X-rays** — it touches many of their parameters. And asked the general question:
does rotation affect other stars too, and **what other sliders would meaningfully
reveal different subpopulations?**

The short answer: **rotation reshapes the entire evolutionary track, not just the
corona** — and for WR stars it is arguably the headline parameter. And there is a
whole family of subpopulation controls beyond rotation, each honest at a different
tier.

## Measured grounding (facts on disk / verified this session — re-check if grids change)

- **MIST v2.5 ships a rotating grid.** `discover_tarball_url(vvcrit="0.4")`
  resolves `MIST_v2.5_feh_p000_afe_p0_vvcrit0.4_EEPS.txz` on the live server
  (verified this session). So rotation-as-real-data is *available*, not
  hypothetical. The fetch tool already takes `--vvcrit` (`fetch_mist.py`).
- **One rotating grid is now on disk** (fetched this session for the gate):
  `feh_p000_afe_p0_vvcrit0.4` (171 tracks). The other four metallicities are still
  non-rotating only. **All 12 feh codes publish a `vvcrit0.4` tarball** (verified via
  `discover_tarball_url` with no download), so the rotation axis can match the
  existing m100/m075/m050/p000/p050 set whenever we fetch the remaining four.
- **The provider does NOT carry rotation as an axis.** `_feh_from_path` keys grids
  by `[Fe/H]` only (`feh_([mp])(\d{3})`); `_find_eep_dirs` globs every dir with
  `*.track.eep`. Two grids at the same feh but different vvcrit (`..._vvcrit0.0` vs
  `..._vvcrit0.4`) would extract the **same** feh key and collide. Adding rotation
  is real provider work — a third axis, mirroring how `[Fe/H]` was added in Phase 1.
- **The surface-N payoff is already plumbed.** `_Track` carries surface nitrogen
  (`Ns`) and the full metals dict. Today surface N rises only *post*-MS (first
  dredge-up); rotating tracks enrich surface N (and He) **on the main sequence** —
  so the comp panel could show that signature with no new field, just rotating data.
- **`star_mdot` (mass-loss rate) is on the track + in the cache** (`CACHE_VERSION`
  9, added for the endgame). Relevant because rotation ↔ mass loss ↔ WR stripping
  are coupled, and the SED wind-radio piece already needs Ṁ.
- **Spectral bake resolution ≈ R 2400** (2400 λ points over ~3000–9000 Å). So
  rotational line broadening (v sin i) is only visible above **~125 km/s** — fast
  rotators (Be/A/B, 200–300 km/s) show it; Sun/typical G–K (a few km/s) are
  correctly sub-pixel. This bounds the v sin i idea below.
- **VERIFIED (the build-gate, settled this session): v2.5 ramps rotation in by mass.**
  Diffing the same-mass track between `vvcrit0.0` and `vvcrit0.4` at solar [Fe/H]:
  **bit-identical at ≤ 1.20 M☉** (max|Δ| = 0 across log Teff, log L, age, surface
  N/He/C, every EEP), **diverges at ≥ 1.25 M☉** — i.e. the turn-on is the classic
  **~1.2 M☉ Kraft break** (envelopes go convective→radiative, magnetic braking shuts
  off, so a fixed initial spin becomes physical). So the rotation control **does
  literally nothing at the Sun** and is honest only above ~1.2 M☉. The payoff is real
  where it bites: at 20 M☉ the **MS surface N¹⁴ rises ~5×** (0.0008→0.0044) and surface
  He enriches on the main sequence (the Hunter-diagram signature). Consequences for the
  build: the control must be a **two-state toggle that data-derives its own active
  domain** (meaningful only where a rotating grid exists *and* the rotating track
  differs from the non-rotating one at the selected mass — below threshold the tracks
  are bit-identical, so "rotation negligible for this star" is a true, checkable
  statement), **not** a slider implying continuous v/vcrit.
- **Mass footprint is identical** across vvcrit (both grids: 171 tracks, 0.1–300 M☉),
  and **EEP counts align per mass** (1721/1721, 808/808). So adding rotation stays a
  **2D (mass × feh) domain per bucket** — no 3D non-rectangular `mass_range`, and
  blend-then-invert works unchanged *within* a vvcrit bucket. The honest move is
  snap/toggle **between** buckets (no third grid to interpolate toward).
- **The collision is now live and MUST be fixed first.** With the 0.4 grid on disk,
  `_feh_from_path` keys both the `vvcrit0.0` and `vvcrit0.4` solar grids to `feh=0.0`
  → `provider._fehs = [-1, -0.75, -0.5, 0.0, 0.0, 0.5]`, a duplicate/degenerate axis
  point. `pytest` still passes (the §10 Sun anchor is 1.0 M☉ → bit-identical → can't
  detect it), but intermediate-mass solar tracks are silently contaminated. Keying by
  `(feh, vvcrit)` is therefore **required to restore correctness**, not just a feature.
- **`StellarState` already carries `v_rot_kms`** — a field to surface the selected
  rotation through the spine without a new field (today it is unused/0 for MIST).

## The physics — how rotation reshapes a star (the multi-parameter answer)

Rotation is not a cosmetic spin. It changes observables across the board:

1. **Rotational mixing (the big one).** Meridional circulation + shear bring
   core-processed material to the surface *during the main sequence*: **N up, C
   down, He up** — the "Hunter diagram" signature. This is a genuinely *different
   surface composition* for a fast rotator at the same mass/age, and we already
   carry the fields to show it.
2. **Longer MS lifetime & shifted tracks.** Mixing feeds the core extra fuel →
   the star lives longer and sits at a different HR position. The whole track moves.
3. **The WR connection (the user's case).** For massive stars rotation **lowers the
   mass threshold to become a WR star**, changes the **subtype** (how deep stripping
   exposes WN→WC layers), the **final mass**, and the **remnant spin**. At **low Z +
   high rotation** it triggers **chemically homogeneous evolution (CHE)** — the star
   mixes fully, stays compact & blue, skips the red-supergiant detour: a completely
   different track, and the leading single-star channel for long GRBs and merging
   binary black holes.
4. **Gravity darkening (von Zeipel).** Fast rotators are oblate with **hot bright
   poles and a cool dim equator** — a real, observed effect (Regulus, Achernar,
   Vega) that changes the apparent Teff/L *and* the spectrum, depending on
   inclination.
5. **Line broadening (v sin i).** Rotation smears spectral lines by v/c — a direct,
   clean spectral observable (bounded by our bake resolution, see above).
6. **Mass loss & critical rotation.** Near breakup, mechanical mass loss and
   decretion disks appear — the **Be-star** phenomenon.

### Rotation + age is two different stories (the coupling the user raised)

The user is right that rotation and age act *together* — but the coupling splits
by stellar type, which is itself a teaching point:

- **Cool stars (F/G/K/M, convective envelope):** magnetic braking **spins them down
  with age** (Skumanich / gyrochronology). This is the basis of the SED Chunk-3
  age→P_rot→Rossby→L_X chain. Here age *predicts* rotation.
- **Hot / massive / WR stars (radiative envelope):** **no magnetic braking.** They
  shed angular momentum through **winds and binary interaction**. Their rotation
  history is wind/binary-set, so the age→rotation law that works for a Sun **does
  not apply to a WR** — the X-ray-narrowing rotation slider can't be age-derived for
  them; it must be user-driven or wind-modeled.

So a single "rotation" concept actually wears two hats: (a) it selects a different
**evolutionary track** (the MIST vvcrit axis — real for all masses in the rotating
grid), and (b) it pins the **activity/X-ray** level (the SED slider — only
age-derivable for cool MS stars). A future unified rotation control could do both,
at their respective fidelities; see "Cross-cutting design" below.

## The atlas — candidate controls, tiered by what data backs them

### Tier A — real data, changes the actual `StellarState`/track

- **Rotation axis (`vvcrit` 0.0 ↔ 0.4).** The headline. Real MIST v2.5 data, answers
  the WR question *and* the general rotation question at once. Reveals: fast vs slow
  rotators, the **MS surface-N/He enrichment** (new — we only show post-MS dredge-up
  today), longer MS lifetimes, the **lowered WR threshold**, and (low Z) the **CHE
  blue divergence**. Caveats: it is a **2-point grid**, so a "slider" is a 0.0↔0.4
  *blend/snap*, not continuous v/vcrit; and it is a **third backend axis** (provider
  work like the `[Fe/H]` add). Gated on the mass-ramp check above. **Detailed below.**

### Tier B — real, but spectrum-only (a derived effect, not a new track)

- **[α/Fe] enhancement.** A genuine Galactic subpopulation: **α-rich thick-disk /
  halo** stars vs solar-scaled thin-disk. MIST evolution is **solar-scaled only** (no
  α axis), but the **CAP18-*large*** spectral grid carries an α axis → real metal-line
  depth changes via a re-bake (the bake/runtime are already axis-generic, so it drops
  in like the CAP18 swap). Honest, bounded to the spectrum panel — the *track* won't
  follow α. (To make evolution follow α we'd need α-enhanced MESA runs — a Tier-D
  effort.)
- **Rotational line broadening (v sin i).** Cheap **frontend convolution** of the
  baked spectrum with a rotation kernel. Honest, but **narrow payoff**: visible only
  above ~125 km/s (our bake resolution) → it lights up for genuine fast rotators
  (Be/A/B) and is correctly invisible for the Sun. Needs v·sin i (rotation ×
  inclination). A nice pairing with the rotation axis: the vvcrit axis sets *whether*
  the star spins fast; the broadening *shows* it in the lines.
- **Microturbulence (ξ).** Spectral-only line-saturation knob; CAP18-large carries
  it. Real but minor pedagogy — probably not worth a dedicated control.

### Tier C — evocative, not predictive (label like the corona, spec §7)

- **Gravity darkening / oblateness** of fast rotators in the 3D star (von Zeipel):
  oblate shape, pole-hot/equator-cool, inclination-dependent. Beautiful (the Regulus
  look), partly cosmetic; same epistemic shelf as the corona quad. Needs rotation ×
  inclination.
- **X-ray activity band → line** (the existing SED Chunk-3 rotation/activity slider).
  Already designed in `magnetic-ember-broadcast.md`; cross-referenced here because it
  is the *other* rotation control. Honest as a band; collapses to a line only where
  age-derivation is valid (MS cool stars) or the user pins it.
- **Magnetic peculiarity (Ap/Bp, magnetic O).** Chemically peculiar / spotted
  subpopulations — evocative surface-abundance/visual flavor only.

### Tier D — real subpopulations needing a genuinely new engine or data source

(Previously "out of scope." Per the user, recorded as real directions with their cost.)

- **Binarity / mass transfer — the biggest one, and central to WR.** The *dominant*
  observed channel for stripped/WR stars is **binary stripping (~70%)**, not single-
  star winds. Binarity also makes **blue stragglers, Algols, stripped He stars, novae,
  and the merging-compact-object (GW) population**. Cost: a **binary-evolution engine**
  (Roche-lobe overflow, common envelope, mass/AM transfer) — a whole new physics layer,
  or ingesting a precomputed binary grid (e.g. BPASS / POSYDON / MESA binary runs)
  behind a new provider. This is the largest single lever for "different
  subpopulations," and the honest note for any single-star WR demo is that it shows
  the *minority* channel until this exists.
- **Initial helium / multiple populations.** Globular-cluster He-enhanced second
  generations (the "second parameter"). MIST fixes Y by a Y(Z) law; this needs grids
  that vary Y independently (a He axis), or MESA runs at varied Y.
- **α-enhanced *evolution*** (vs the Tier-B spectrum-only version): α-enhanced MESA
  tracks so the HR position and lifetimes follow, not just the line depths.
- **Live solver / reduced nuclear network** (spec §9). The ultimate "any star"
  capability; large, and only worth it if the grid approach hits a real wall.

### Bonus — a subpopulation view with zero new data — **DONE**

- **Instability-strip / variable-class overlay on the HR diagram.** **Shipped.** An
  opt-in "Variable-star zones" toggle on the HR panel shades the **classical
  instability strip** — one tilted band (κ-mechanism, He II ionization zone), drawn
  cooler-at-higher-L from piecewise-linear (logL, Teff_blue, Teff_red) control points
  so each class lands near its real temperature — carrying **δ Scuti / RR Lyrae /
  Cepheids** at rising luminosity, plus two clearly-separate labeled zones (**LBV /
  S Dor** near the Humphreys–Davidson limit, and **Miras / LPV** on the cool AGB).
  Frontend-only: `hr.js` gained `setOverlay(on)` (zones drawn behind the track so the
  live star stays on top, clipped to the plot frame); `index.html`/`styles.css` add
  the toggle + a per-class legend with hover pedagogy; `main.js` wires the button.
  Labeled **schematic** throughout (illustrative class positions, not a calibrated
  strip) and "where such stars sit, not a claim this star is variable." Verified via
  Playwright (default-off clean; toggle-on overlay+legend; an in-strip 1.8 M☉ star
  lands on the strip; phone re-fits, legend wraps; no JS errors). pytest unchanged
  (137 — frontend-only). WR was deliberately **not** added as a variable-class zone
  (it belongs to the endgame work; its variability is a different, messier story).

## The rotation axis in depth (the headline Tier-A candidate)

If we build one substantive thing from this atlas, it is the **`vvcrit` rotation
axis**. Sketch (to be turned into a chunked plan if chosen):

- **Provider:** add rotation as a third selection axis alongside mass × [Fe/H].
  `_find_eep_dirs` already finds both vvcrit dirs; the work is keying grids by
  `(feh, vvcrit)` instead of feh alone (parse vvcrit from the dir name *and* confirm
  it against the track's own header, mirroring the feh "dir hint vs authoritative
  value" pattern), and deciding **snap vs interpolate** on the 2-point rotation axis.
- **Snap vs interpolate:** with only {0.0, 0.4}, a continuous slider would
  *interpolate* between two rotation states — defensible (it's a convex blend like the
  mass/feh axes) but the in-between has no physical track behind it. Honest
  alternative: a **two-state toggle** (non-rotating / rotating) that *snaps*, like the
  MESA provider's discrete grid. Leaning toggle-or-snap for honesty; a slider only if
  we also fetch intermediate vvcrit grids (MIST publishes only 0.0 and 0.4, so we
  can't — argues for the toggle).
- **The build gate:** settle the **mass-ramp** question first (see Measured
  grounding). If rotation is ramped in above ~1.2–1.8 M☉, scope the control's
  *visible* effect honestly — it's a massive-star / WR feature, not a Sun feature, and
  the UI should say so rather than show a dead toggle at 1 M☉.
- **Payoff to feature:** the **MS surface-N enrichment** in the comp panel (the
  Hunter-diagram signature, real data, not shown today), the **lifetime/HR shift**,
  and at the massive end the **lowered WR threshold + CHE** — i.e. it directly makes
  the WR endgame (`smoldering-cinder-gateway.md`) rotation-aware.
- **Relationship to the endgame & SED work:** the endgame snaps to a single track
  already; a rotation axis means it would snap within the *rotating* grid when the
  toggle is on, changing which masses reach WR. The SED Chunk-3 rotation slider is a
  *different* control (it pins activity/X-ray, a derived non-thermal quantity); see
  the cross-cutting note on whether to unify them.

## The rotation axis — chunked build plan (gate settled, ready to implement)

The gate is verified (rotation is mass-ramped at ~1.2 M☉; see Measured grounding),
so the sketch above becomes this chunked plan. Honesty spine throughout: the control
is a **two-state toggle** that **data-derives its own active domain**, never a slider.

- **Chunk 1 — provider keying `(feh, vvcrit)` + restore correctness. ✅ DONE.** Grids
  partition into one `_Axis` per rotation rate, keyed by `(feh, vvcrit)`: vvcrit parsed
  from the dir name (`_vvcrit_from_path`, hint) and confirmed against each track's
  authoritative header `rot` value, stored in the cache (so `CACHE_VERSION` bumped 9→10).
  The provider **snaps** between vvcrit buckets and interpolates mass×[Fe/H] *within* a
  bucket (the `_bracket_feh`/`_interp_window`/`_state_from_row` helpers now take an
  `_Axis`). `track()/state_at()/endgame()/mass_range()/age_range()` gained `vvcrit=0.0`
  (default = non-rotating → the live spine is byte-unchanged); the Protocol + Stub + MESA
  carry it too (Stub/MESA accept-and-ignore). `parameter_ranges()` now exposes
  `vvcrit: {available: [...]}`. Back-compat `_grids`/`_fehs` properties return the default
  axis for the white-box tests. **The real gate** (a test that *fails* on the old keying):
  the off-grid-feh contamination check — `track(3.0, feh=0.25, vvcrit=0.0)` must blend the
  *non-rotating* solar+p050 tracks; the duplicate-0.0 bug would have bracketed the
  *rotating* solar grid (20% different N here). The naive feh=0.0 grid-point check does
  NOT discriminate (the buggy bracket also lands non-rotating-first) — advisor-caught.
  178 pytest (+8 in `test_rotation_axis.py`; `requires_mist_rotation` marker).
- **Chunk 2 — the data-derived active domain + the toggle's honesty gate. ✅ DONE.**
  `rotation_status(mass, feh) → {has_grid, threshold_msun, active}` on the Protocol
  (Stub/MESA return has_grid=False). `has_grid` = the rotating axis's [Fe/H] span covers
  feh (False off it — honestly absent, not a dead toggle); `threshold_msun` = the
  rotation-onset mass **derived by scanning** (`_rotation_threshold`: the first grid mass
  whose rotating track diverges from its non-rotating twin via `_track_diverges` on logL +
  surface He — never a hardcoded 1.2, it shifts with feh; measured 1.25 at solar and low-Z,
  cached per feh); `active` = has_grid AND mass ≥ threshold. The centerpiece test ties the
  gate to reality (the "don't label a non-feature" rule): wherever active=False the rotating
  and non-rotating tracks are *bit-identical*, wherever active=True they differ — derivation
  and served tracks can't drift apart. 188 pytest (+10). Low-Z m100 rotating grid fetched
  (the gate works at [Fe/H]=−1, where CHE lives). API endpoint deferred to Chunk 3.
- **Chunk 3 — the frontend toggle + the payoff render.** A non-rotating/rotating toggle
  near the [Fe/H] control; greyed with the explanatory note where `rotation_status.active`
  is false (inert below the threshold) and absent where `has_grid` is false. Wire the API
  (a `vvcrit` query param on `/track` etc. + a `rotation_status` surface). Prove the payoff
  comes through the runtime path before shipping the control (project "don't label a
  non-feature" rule): the **MS surface N/He enrichment** in the comp panel (rotating vs non
  at ~20 M☉), the **HR track shift**, and the **low-Z CHE blue divergence** (the m100
  rotating grid is now on disk — the headline lives at low Z, not solar). **UI decision
  (user, settled): UNIFY** with the existing SED Chunk-3 rotation/activity slider into one
  rotation control that drives *both* the track selection (vvcrit, real for all masses in
  the grid) and the activity/Rossby pinning (age-derivable only for cool MS stars) — the UI
  must show each effect **only where it's honest** (e.g. the track effect gated by
  `rotation_status`, the activity effect gated by the cool-MS validity domain), so a
  spectrum/activity knob never implies the evolutionary track changed in a regime where it
  didn't. `StellarState.v_rot_kms` (still None) is surfaced here as the real selected value.
- **Chunk 4 (data, incremental) — fetch the remaining rotating metallicities.** **m100
  (low-Z) fetched in Chunk 2** for the CHE payoff; **m075/m050/p050 at vvcrit0.4 remain**
  (user: fetch m100 now, rest later) so the toggle is honest across the full feh axis.
  ~180 MB each; can interleave with Chunk 3.

## Cross-cutting design questions (decide before building any of these)

1. **How many controls before the UI drowns?** We already have mass, [Fe/H], age.
   Each new axis multiplies the grid and the cognitive load. Prefer **toggles for
   discrete real axes** (rotation on/off) and reserve sliders for genuinely continuous
   honest quantities. The instability-strip overlay adds a subpopulation *view* with
   no control at all — often the better trade.
2. **One rotation control or two?** The vvcrit axis (track) and the SED activity
   slider (X-ray) are physically the same parameter at two fidelities. A unified
   "rotation" control could drive both — selecting the rotating track *and* pinning
   the Rossby number — but they have different validity domains (vvcrit is real data
   for all masses in the grid; activity-from-rotation is age-derivable only for cool
   MS stars). If unified, the UI must show each effect only where it's honest.
3. **Snap vs interpolate on a 2-point axis** (rotation) — see above. The project has
   precedent both ways (MIST interpolates feh; MESA snaps). Honesty leans snap/toggle
   here because there is no third grid to interpolate *toward*.
4. **Spectrum-only vs evolution axes must be visibly distinct.** [α/Fe] and v sin i
   change the *spectrum panel only*; the HR diagram / 3D star won't move. Like the
   SED's two-tier rendering, the UI must not imply a spectrum-only knob changed the
   star's evolution.

## Suggested sequencing (if/when we pick from this atlas)

1. ~~**Instability-strip overlay**~~ — **DONE** (zero new data, immediate
   "subpopulations" payoff, pure frontend). The cheapest honest win — see the Bonus
   section above for what shipped.
2. **Rotation `vvcrit` toggle** — the substantive answer to the user's actual
   question; gated on the one-time mass-ramp diff. Real data, real WR relevance.
3. **v sin i broadening** — small frontend follow-on that *shows* the rotation the
   toggle selects, for fast rotators.
4. **[α/Fe] spectral axis** — a CAP18-large re-bake; real Galactic subpopulation,
   spectrum-bounded.
5. **Binarity / live solver / He axis** — the big engines, when a single feature
   justifies the lift. Binarity is the highest-value (it owns most of the WR/exotic
   subpopulations) and the largest cost.

## References

Rotation & evolution: Maeder & Meynet 2000 (rotating massive-star review); Heger,
Langer & Woosley 2000; Brott et al. 2011 (Hunter diagram, MS N enrichment); Ekström
et al. 2012 (Geneva rotating grids). CHE / GRB-BH channel: Yoon & Langer 2005; Mandel
& de Mink 2016. WR binary fraction: Sana et al. 2012; Shenar et al. 2020. Gravity
darkening: von Zeipel 1924; Espinosa Lara & Rieutord 2011. Be stars / critical
rotation: Rivinius, Carciofi & Martayan 2013. Gyrochronology & braking (cool-star
rotation–age): Skumanich 1972; Barnes 2007; van Saders et al. 2016 (see
`magnetic-ember-broadcast.md` for the full activity chain). α-enhancement spectra:
the CAP18-large grid (Allende Prieto et al. 2018). Binary-population grids: BPASS
(Eldridge et al. 2017); POSYDON (Fragos et al. 2023).
