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
  α axis), so this is spectrum-only — the *track* won't follow α (evolution-follows-α
  needs α-enhanced MESA runs, a Tier-D effort). **Gate 0 MEASURED (2026-07-02) — the
  plan's "drops in like the CAP18 swap" was the optimistic-framing trap:** the α axis
  lives ONLY in **CAP18-*large* (73 GB)**, and baking the *main* cube needs the
  **Docker + from-source pymsg/MSG** env (which — unlike the host-baked WD/WR ASCII
  cubes — was down/unverified: Docker Desktop not running, `msg_spike` container
  survival unknown), plus α is a 4th cube axis (size multiply, likely a `BAKE_VERSION`
  bump forcing a full main-cube re-bake). So the CAP18-large path is a **multi-session
  infrastructure lift**, and even the cheap Gate-1 visibility measurement is blocked
  behind it. **The cheaper path found (Gate 0 alternative research):** **Coelho 2014**
  (arXiv 1404.3243, MNRAS 440, 1027C — "scaled-solar and α-enhanced mixtures") carries
  a clean matched **[α/Fe] = 0.0 AND +0.4** pair across (Teff 3000–25000 K, log g
  −0.5…5.5, [Fe/H] −2.5…+0.5), 2500–9000 Å, and is on the **SVO Theoretical Spectra
  Server** as ASCII — i.e. the **exact host-baked SVO-ASCII precedent of the Koester
  (6a) and TMAP (6b) WD cubes**: a bulk SSAP fetch + a custom reader + a *separate*
  α-cube sibling, numpy/scipy only, NO Docker/pymsg/73 GB. Teff 3000–25000 K is exactly
  the cool/solar/A range where α metal-lines matter (and washes out hot — the
  Teff-gated honesty advisor predicted, like the He I/II `minTeff` / TiO `maxTeff`
  gates). Castelli-Kurucz ODFNEW also has α+0.4 but only for [Fe/H]≤−0.5 (not a clean
  full-grid pair). **Design note (before shipping):** compare Coelho-α=0 vs Coelho-α=+0.4
  (self-consistent, same atmosphere code) — do NOT show a Coelho α spectrum beside a
  CAP18 solar one (the atmosphere-code seam would contaminate the α comparison). **Gate
  1 (visibility through the R≈2400 runtime) still PENDING** — fetch a minimal matched
  Coelho slice, diff Mg b / Ca / Ti / O line depths α=0 vs +0.4, confirm the visible
  Teff window BEFORE any full fetch/bake.
  **Gate 1 CLOSED — GO (2026-07-02, measured through the 2.5 Å runtime binning).**
  Fetched matched Coelho highres α=0 vs +0.4 (SVO `coelho_highres`, 3727 models,
  Teff 3000–26000 K × logg −0.5…5.5 × [Fe/H] {−1.3…+0.2} × [α/Fe] {0,0.4}; ASCII
  2-col λ[air]/F_λ, ~10.7 MB/model), binned to the project's 2.5 Å/3000–9000 Å grid.
  **α is clearly visible and Teff-gated**, exactly the honest bounded feature: at the
  cool→F window it *deepens* Ca I 4227 (Δdepth up to **+0.16**), Ca II K (+0.03…+0.12),
  Mg b (+0.06), Ca II triplet 8542 (+0.03…+0.06), TiO 7053 (+0.045 at 4000 K); it goes
  **marginal at A (~9000 K, only Ca II K)** and **dead ≥12000 K** (all Δ ≤ 0.006 — the
  metals wash out). **Both controls pass:** the Na D **odd-Z control moves OPPOSITE
  (shallower, Δ −0.04…−0.09)** — an α-heavier mix raises H⁻ continuum opacity and weakens
  non-α lines — which rules out a global-normalization artifact (that would move
  everything the *same* way); and hot stars are null. Comparable at [Fe/H]=0 and −0.5
  (NOT metal-poor-only). **Giant check (logg=2.0) confirms + is stronger** — the Ca II
  triplet (the classic giant α indicator) is robust across 4000–5500 K (Δ +0.036…+0.056),
  so the panel's RGB/AGB stars are covered. (Scratch measurement:
  `M:\claud_projects\temp\alpha-gate1\` — `gate1.py`/`gate1_giants.py`/`RESULTS.md`.)
  **Three build-design decisions (advisor-settled, before implementing):**
  1. **The toggle must bake BOTH baselines from Coelho** — flipping α is pure-α (Coelho
     α0 ↔ Coelho α0.4), NEVER code+α. Do NOT show a Coelho α spectrum beside a CAP18
     solar one; the atmosphere-code seam would masquerade as the α signal. *The*
     load-bearing constraint.
  2. **Spectrum-only "what-if" — extend cross-cutting #4 to the comp panel.** `comp.js`
     shows surface metals from the *solar-scaled MIST* track; an α *spectrum* toggle
     deepens Mg/Ca/Ti in the spectrum but won't move those elements in the composition
     panel, so with both open they'd read as disagreeing. Label α as a spectrum-only
     hypothesis (the track/comp don't follow it — that's Tier-D α-enhanced evolution).
  3. **Scope the fetch to Teff ≲ 10 kK (the hot-null payoff) + hand off to the main
     cube hot.** Since α dies ≥~9–10 kK, the Coelho α-cube only needs the cool subset —
     bounds the fetch AND gives a clean regime switch: **α-cube for cool, existing main
     cube for hot**, mirroring the WD-gravity `refreshWD` switch.
  Build shape: a separate host-baked Coelho α-cube sibling (`/alpha_spectrum`) keyed
  (Teff, logg, [Fe/H], [α/Fe]) with a 2-node [α/Fe] toggle — the WD/WR-cube precedent
  (`fetch_*` + `bake_*` + the axis-generic `_Spectra` runtime), no Docker/pymsg/73 GB.

  **Chunk 1 — the data + runtime vertical (backend only) — BUILT (2026-07-02, 254 pytest).**
  `star_sim/fetch_coelho.py` (SVO `coelho_highres` SSAP bulk fetch, cool-subset-scoped
  `--teff-max 10000`, matched-α `select()` — a node needs BOTH α or it's dropped, since a
  toggle would otherwise clamp-lie on flip); `scripts/bake_alpha_spectra.py` (a **4-axis**
  `(Teff, logg, [Fe/H], [α/Fe])` cube; Coelho's grid is ragged in (Teff,logg), so a **log g
  clamp-fill** — the WD cube's `_interp_logg` precedent — squares it, keeping Teff/[Fe/H]/α
  exact and only substituting gravity at the ragged edges; **measured 47% of cells
  clamp-filled** — all at unphysical extreme-logg corners, NOT the reachable loci);
  `spectra.py` `alpha_spectrum_data()` + `_load_alpha()` (reuses the axis-generic `_Spectra`
  verbatim — a 4-D grid, **no `BAKE_VERSION` bump**, a new separate file); `/alpha_spectrum`
  route; `test_alpha_spectra.py` (15 tests, `requires_alpha_spectra_data` marker). The
  data-gated tests are **Gate 1 turned into regression**, measured through the real route:
  α deepens Ca I 4227 / Mg b / Ca II triplet at cool stars (both [Fe/H] nodes), the **Na D
  control does NOT deepen** (the anti-normalization-artifact gate), and the effect is
  Teff-gated (weaker at 9000 K). **Cube on disk = the FULL matched [Fe/H] axis {−1.0, −0.5,
  0.0, +0.2}** (widened 2026-07-02 from the {−0.5,0} MVP), Teff 3000–10000 K, all logg, both α
  (1630 Coelho models ≈ 17 GB fetched → a 26.5 MB `alpha_spectra_grid.npz`, cube 30×13×4×2×2400,
  both gitignored). **The widen was the promised pure data re-bake** (`fetch_coelho --feh
  -1.0,-0.5,0.0,0.2` then re-bake) — the CAP18/PoWR precedent — with ONE scope touch: the fetch
  `--feh` default flipped MVP→full so a fresh checkout reproduces the honest cube. Verified through
  the route at the new nodes (−1.0/+0.2 unclamped → the frontend [Fe/H]-window fallback stops firing;
  α still deepens Ca lines, e.g. −1.0 CaI 4227 +0.132). **+0.5 stays a fallback** — Coelho's α=0
  slab exists only at {−1.0,−0.5,0.0,+0.2}, so +0.5 has no matched pair to bake.

  **Chunk 2 — the frontend α toggle (spectrum panel) — BUILT (2026-07-02, frontend-only,
  254 pytest unchanged, Playwright-verified 1440 + 390 px, zero console errors; WR/SN
  endgame row-hide + the toggle-OFF round-trip explicitly asserted, not assumed).** A spectrum-only
  "what-if" TOGGLE in the spectrum panel (`#alpha-toggle`, owned by `spectrum.js` by id like
  `sed.js` owns `#sed-rot` — NO `main.js` control surface). When on + in-domain it fetches
  BOTH Coelho spectra under one token (`fetchAlpha`: `Promise.all` of `/alpha_spectrum?afe=0`
  & `afe=0.4`, single latest-wins check) and `drawAlpha()` overlays them — the α=0 (solar-
  scaled) curve shaded white/rainbow, the α=+0.4 (α-rich) curve as a coral line dipping
  DEEPER at the Ca/Mg/Ti guides (+ the Na D "↓" odd-Z control that rides ABOVE), each
  normalized to its own peak (measured to preserve both signatures). **The honest domain,
  set from `loci_check.py` (not round numbers):** `ALPHA_TEFF_MAX=9000` (α washes out hotter),
  `ALPHA_COOL_TEFF=3800` + `ALPHA_COOL_MAX_LOGG=1.0` (below 3800 K Coelho has only giant
  gravities, so a cool DWARF is gated off), **plus the [Fe/H] window enforced at RUNTIME** from
  the response's clamped `feh` vs the request (advisor blocker #1 — the cube's [Fe/H] axis is
  narrower than the slider's −1→+0.5; this auto-widens as the cube widens — proven by the
  2026-07-02 widen to {−1.0..+0.2}, which needed no frontend change). Off any of the three
  edges it falls back to the standard `/spectrum` with a specific note (hot / cool-dwarf /
  off-[Fe/H]-window). Hidden + overlay-suppressed in the WD/WR/SN endgames — the WD-giant
  scrub still routes through `update(s, {endgame:"wd"})` (real main-cube spectrum) but the α
  what-if is a living-star control. Caption is HONEST spectrum-only (the HR track/comp panel
  are solar-scaled MIST and do NOT follow α). **The settled decisions (kept):**
  1. **α-mode-OFF baseline routing → SETTLED: Option A.** Keep the main **CAP18 cube as the
     α-off default** (it has cool M dwarfs via the Göttingen splice + a full 12-node [Fe/H]
     axis); α-mode is an **explicit opt-in overlay** that plots **Coelho-α0 vs Coelho-α0.4**
     (the pure-α comparison of decision #1 — both curves from the α cube, so the α *lesson*
     is the gap between two plotted Coelho curves, not the one-time CAP18→Coelho view
     switch on engaging). Option B (route all cool stars to Coelho) was **rejected by the
     loci spot-check**: it would silently give cool M dwarfs wrong-gravity giant spectra by
     default AND degrade the default [Fe/H] fidelity (MVP Coelho = 2 [Fe/H] nodes vs CAP18's
     12).
  2. **Baseline fidelity spot-check → DONE** (`M:\claud_projects\temp\alpha-gate1\
     loci_check.py`). Reachable **cool giants (RGB/AGB) all land on REAL Coelho nodes** (dense
     there — the classic α regime); **MS dwarfs Teff ≥ 4000 K all REAL**. But **cool M dwarfs
     Teff ≲ 3800 K are NOT real** — Coelho computed only *giant* gravities (logg ≤ 1.0) below
     ~3800 K, so a 3500 K/logg 4.9 dwarf clamp-fills a *giant* spectrum. ⇒ **Chunk 2 must
     Teff-gate α off for cool dwarfs (Teff ≲ 3800–4000 K at dwarf gravity)** — an honest edge
     like the WD DC floor / WR off-grid frame; giants + MS ≥4000 K are fine.
  Plus (unchanged): Teff-gate the α control off above ~9–10 kK (hot end — like the TiO
  `maxTeff` gate), label it a spectrum-only "what-if" (decisions #2/#3 above), hand off to
  the main cube hot. So the honest α-domain = **~4000–10000 K dwarfs + all cool giants**.
- **Rotational line broadening (v sin i). ✅ DONE.** A pure **client-side convolution**
  of the baked spectrum with Gray's rotation profile (`spectrum.js` only; `rotBroaden`
  ε=0.6, per-pixel variable width Δλ_L=λ·v sin i/c, normalized so equivalent width is
  conserved → lines go shallower & wider, not weaker). Driven by the marker's real
  `v_rot_kms` (the MIST vvcrit axis) taken **edge-on** (sin i=1) — the maximum
  projection; advisor settled *against* a lone inclination slider (it would be
  incoherent with no oblateness/gravity-darkening model anywhere else, so only the
  lines would respond to a "tilt"). Honest **narrow payoff**, exactly as forecast:
  visible above ~120 km/s (the ~1-pixel floor at R≈2400), and the vvcrit toggle sets
  *whether* the star spins fast while the broadening *shows* it in the lines. Scoped to
  the **main absorption cube only** (WD/WR/SN exempt). No refetch (re-broaden cached
  flux + redraw on v_rot change, memoized). **Measured visible through the runtime
  path**: 2.5 M☉ vvcrit0.4 → v sin i 212 km/s, Ca K core depth 0.43→0.30 with Balmer
  lines shallowing; the Sun (v_rot=0) untouched. Backend byte-unchanged.
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
- **Chunk 3 — the frontend toggle + the payoff render. ✅ DONE** (three commits 3a/3b/3c).
  - **3a (backend/API):** `vvcrit` query param threaded onto `/state`, `/track`,
    `/endgame`(+`meta`), `/mass_range`, `/age_range` (default 0.0 → the live non-rotating
    spine is byte-unchanged); a new `/rotation_status` route surfaces the Chunk-2 gate
    through PROVIDER (§3-clean). **`StellarState.v_rot_kms` is now real**: `surf_avg_v_rot`
    (km/s) added as `_Track.Vrot`, interpolated across mass/[Fe/H] like the other living
    quantities (`CACHE_VERSION` 10→11). It is 0 on the non-rotating grid **and below the
    Kraft break** (MIST zeroes rotation there, so it stays consistent with the active=False
    gate — no "spinning but identical" nuance), and the real evolving equatorial velocity
    above it (~224 km/s at 20 M☉ MS). Payoff proven through `track()` BEFORE any UI (the
    "don't label a non-feature" gate): 20 M☉ solar rotating raises MS surface N ~2.3× + He
    + longer MS; m100 low-Z 40 M☉ shows the **CHE blue divergence** (rotating ends logTeff
    3.94 vs non-rotating 3.70). +4 tests.
  - **3b (frontend toggle):** a two-state non-rotating/rotating toggle below [Fe/H], with
    `effVvcrit()` = `rotationOn && has_grid ? 0.4 : 0.0` (silently falls back to
    non-rotating off the rotating grid → no `/track?vvcrit=0.4` 422). `/rotation_status`
    fetched (awaited, token-guarded) at the top of `refreshTrack` so the gate is current;
    greyed where `!active`, hidden where `!has_grid`; vvcrit in `egKey()` + all endgame
    fetches. Verified in-app: 0→249 km/s at 20 M☉, HR/comp shift, age preserved.
  - **3c (UNIFY, user-settled):** the toggle + the SED Chunk-3 rotation/activity slider are
    now **one "Rotation" control** in the Controls panel with **two regime-gated facets**
    (advisor's regime-adaptive design — *not* a single shared continuous unit, which would
    be lossy/dishonest): the vvcrit **track** toggle (massive stars, gated by
    `rotation_status`) and the rotation-**period** slider (cool-MS activity, the relocated
    `#sed-rot`, gated by `sed.rotationAllowed()` — the dynamo domain). The two regimes
    barely overlap, so usually one facet shows; at the Sun **both** do (track greyed/no-op,
    activity live), so a spectrum/activity knob never implies the track changed where it
    didn't. The SED panel keeps the X-ray line + a pointer to the relocated control.
- **Chunk 4 (data, incremental) — fetch the remaining rotating metallicities. ✅ DONE.**
  **m100 (low-Z) fetched in Chunk 2** for the CHE payoff; **m075/m050/p050 at vvcrit0.4
  fetched here** (171/169/170 tracks via `fetch_mist --feh m075,m050,p050 --vvcrit 0.4`),
  so the **rotating axis now spans the full [Fe/H] axis −1.0→+0.5**, coextensive with the
  non-rotating set — the toggle is honest across every fetched metallicity. `rotation_status`
  `has_grid` extends across the whole axis (was capped at the partial −1.0…0.0 span); absence
  is now honest only *beyond* the axis (feh>+0.5). MS surface-N enrichment confirmed real at
  the new grids (5.5×/4.6×/1.8× at 20 M☉ for feh −0.75/−0.5/+0.5). Two `test_rotation_axis.py`
  assertions that encoded the *incomplete* axis (`has_grid` False at +0.5) flipped to the
  completed truth (+0.5 present; absence tested at +0.75). 192 pytest. **The rotation arc is
  complete.** (Data is gitignored; the grids live under `data/feh_*_vvcrit0.4/`.)

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
