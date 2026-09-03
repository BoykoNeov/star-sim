# Science hurdles — the measured limits of the model, and the plan for each

**What this is.** A single, tiered ledger of every place the simulator's physics is
approximate, missing, or data-limited — with the *measured* size of each gap and a
decision (fix / gate / accept / defer) attached. It replaces the scattered "honest
caveat" notes in the memory files as the place to look **before** claiming a number
is right or proposing a "more physics" feature. Detail stays in the topic files
(`docs/memory/`); this page holds the verdicts.

**Tiering (the project rule, spec §7 / CLAUDE.md).**

| Tier | Meaning | Rule |
|---|---|---|
| **T1 — measured residual** | The model is real physics and the offset from truth is known and pinned by a test. | Report the residual in the caption if the user could notice; never retune to hide it. |
| **T2 — data-limited** | The physics exists in the grid but coverage stops (no node, no column, no phase). | Snap or blank *in-band*; a `*_snapped_far` flag or a visible "no model" frame. |
| **T3 — parametrized aftermath** | A known-simplified model with named free parameters (SN light curve, remnant cut). | Free parameters are sliders or captions, never hidden defaults. |
| **T4 — evocative** | Drawn to look right, not computed (corona, wind filaments, NS dot). | Labeled as such wherever it appears. |
| **OOS — out of scope** | Spec §2 non-goals (live solver, network) or blocked data. | Recorded so nobody re-proposes it without new information. |

Every row below carries a tier, the measured number(s), and one of four verdicts:
**FIXED** (this branch), **GATED** (honest in-band already), **ACCEPT** (residual
documented, no action), **NEXT** (a concrete, bounded improvement worth building).

---

## 1. The spine — MIST provider, EEP interpolation, age↔EEP

### 1.1 Mass interpolation weight — **FIXED (2026-09-02)**  · T1

Cross-mass blending at fixed EEP used a weight **linear in mass**. Stellar
quantities are near power laws in M, so at fixed EEP log L, log Teff and log age
are far closer to linear in **log M** — the assumption a two-point blend makes.

Measured on the full solar grid (every interior node held out, rebuilt from its two
neighbours, compared row-by-row against the real track — 169 nodes):

| | linear-in-M | log-M |
|---|---|---|
| mean of per-node median \|Δlog L\| | 0.0033 dex | **0.0021 dex** |
| nodes where log-M is better on L | — | 126 / 169 |
| 0.2 M☉ (bracket 0.15 / 0.25) | 0.036 | **0.0095** |
| 0.25 M☉ | 0.018 | **0.0028** |
| 25 M☉ (bracket 20 / 30) | 0.025 | **0.0067** |
| 30 M☉ | 0.019 | **0.0074** |
| 2.5 M☉ (0.1-M☉ spacing) | 0.0015 | 0.0003 |

Exact grid hits are untouched (w = 0), so the Sun anchor, every snapped endgame and
the [Fe/H] axis are byte-identical. Where the two weightings disagree most is where
the grid is coarsest (the 0.1–0.4 M☉ dwarfs and the 20–40 M☉ supergiants) — the
regimes the mass slider spends the least rows on and where a user drag is most
likely to land off-node. Pinned by
`test_mass_interpolation_held_out_grid_nodes`, whose bounds sit *between* the two
measurements so a regression to linear weighting fails at 0.2 / 25 / 30 / 120 M☉.

Not done (measured, not worth it): the 0.35–0.45 M☉ nodes are slightly *worse*
under log-M (0.018→0.026 at 0.35). That is the fully-convective transition, where
neither weighting is right; the fix there is grid density, not weighting.

### 1.2 The Sun anchor — **ACCEPT, docstring corrected**  · T1

`state_at(1.0, 0.0, 4.567 Gyr)` reads **L = 1.067, Teff = 5834 K, R = 1.012,
log g = 4.427** against the defined 1 / 5772 / 1 / 4.438. The old provider note
blamed "an interpolated request carrying a leftover composition offset" — **that
was wrong**: (1.0 M☉, [Fe/H] = 0) is an *exact grid node*, no blend happens. The
residual is MIST v2.5's own published p000 1.00 M☉ track (ZAMS X/Y/Z =
0.7135 / 0.2702 / 0.0164). The same grid puts L = 1.00 at [Fe/H] ≈ +0.07 or at
M ≈ 0.99 M☉.

Verdict stays: **do not retune** (a forced L = R = 1 would be the stub's fake green
check). What changed on this branch: the header docstring now states the true
cause. Downstream, the same ~3 % common-mode offset is what makes the seismology
panel ring 2984/132 µHz vs 3090/135 (memory: asteroseismology) — one root, not two
bugs.

**SURFACED (2026-09-03)** — the NEXT is spent; the residual is now pedagogy in-band,
split so each fact has exactly one home:

* **The live figure → the readout's L row.** `sunResidualNote(s)` in `main.js` appends a
  confession to the luminosity row's `?` when the star on screen *is* the model's Sun.
  It is **computed from the served `StellarState`**, never hardcoded — the stub and MESA
  each have their own, different Sun, so a literal "7 %" would go false on a `PROVIDER`
  swap. Default state fires it (L = 1.07, "about 7 % high", Teff 5835 K vs the defined
  5772, R 1.01 vs 1).
* **Where the model's Sun sits → the `MISTProvider` status token.** Measured through the
  provider on this branch: **[Fe/H] = +0.07 gives L = 0.9999 and Teff = 5770.0 K** — the
  Sun to four figures (the old note's "near +0.07" understated how exact it is). That
  fact is MIST-specific, so it stays in the already-provider-gated tooltip, which no
  longer restates the numeric residual.

**The gate is deliberately tight** (mass within ±0.005 M☉, |[Fe/H]| ≤ 0.01, phase MS, age
within ±0.15 Gyr of 4.567). Solar-MS luminosity climbs ~9 % per Gyr, so the *same* track
reads +13 % at 5.2 Gyr and −3 % at 3.5 Gyr — real evolution, not a residual — and mass is
sharper still (1.02 M☉ is already +21 %). Outside that shell the sentence would be false,
so it disappears rather than being relabeled. Nothing was retuned; the Sun anchor test is
untouched.

### 1.3 The He-ignition cliff (~2.0–2.1 M☉) — **GATED (2026-09-03)**  · T1

Cross-mass CHeB interpolation across the degenerate → non-degenerate He-ignition
boundary: whole-window median < 1 %, CHeB sliver ~8 % median with peaks in the
hundreds of % (was ~23 % on the old 0.5-M☉ bracket). Intrinsic morphology change;
density helped, weighting does not (2.0 M☉: 0.0017 → 0.0013 dex median only).
Convexity (lies-between) still holds so it is *smoothed, not wrong*. Pinned by
`test_transition_mass_interpolation_reduced_not_eliminated` (needs raw tracks).

**GATED (2026-09-03) — the confession is now in-band.** The residual is unchanged
(nothing was retuned); what shipped is the HR-panel caption that says so, plus the
data-derived gate behind it.

*Not* the ±0.15 M☉ rule this plan originally proposed — two corrections came out of
building it:

* **It is a band, not a boundary.** The transition is broad and metallicity- and
  rotation-dependent, so the gate measures it per grid instead of assuming a width:
  the **He-core mass at helium ignition** (the first FSPS phase-3 row) sits on a flat
  degenerate plateau ≈0.47 M☉ at low mass and falls off a cliff to ≈0.31 M☉ across the
  transition. The band runs from the last mass still on the plateau (10 % of the way
  down the fall) to the mass at the minimum. Measured over all ten grids on disk:
  **1.65–2.10 M☉ at solar non-rotating**, 1.80–2.10 at [Fe/H] = −1, 1.70–2.20 rotating
  at [Fe/H] = +0.5 — every one straddling the textbook M_HeF ≈ 2 M☉. Both columns
  (`HeCore`, `phase`) were already parsed, so no `CACHE_VERSION` bump.
* **On an exact grid node there is nothing to confess.** A mass that lands on a grid
  track is a *real* MIST track (blend weight 0), so a caption there would be a false
  label — this project's most-repeated defect class. The gate therefore ANDs
  `in_band` with `interpolated` (mass between two grid masses, or [Fe/H] between two
  grids); the consumer adds the third condition, `phase == "CHeB"`, which is the only
  phase the smoothing distorts.

Shipped as `MISTProvider.he_ignition_status()` (a `StellarStateProvider` Protocol
method, sibling of `rotation_status`; stub/MESA answer `has_data: False` because
neither blends across mass), the `/he_ignition_status` route, and the
`#hr-cliff-caption` note last in the HR panel — placed last so it can only grow the
panel downward into the slack `.hr-panel`'s min-height already holds, verified
non-shifting at 1440 and 390 px. Cleared by the shared mode-switch chokepoint.

### 1.4 [Fe/H] interpolation — **ACCEPT**  · T1

Held-out [Fe/H] = 0 from m050/p050: L median ~3.3 % (max ~11 %), Teff ~0.7 %. A
1-dex bracket has real curvature. The rotating axis measured 0.7 % (vs 2.6 % for a
wrong-axis blend). The grid now holds m100/m075/m050/p000/p050, so a request
between nodes is at most 0.25 dex from one — the real-use error is well under the
held-out 1-dex figure. No action.

### 1.5 Window and phases — **GATED**  · T2

- Living window ZAMS → end of early-AGB. TPAGB (30–100 log L reversals per track)
  is exposed only through the snapped endgame; never cross-mass interpolated.
- MIST v2.5's third dredge-up never makes a carbon star (surface C/O stays ~0.3);
  the composition panel must never say "carbon star".
- "EAGB" is nominal for 15–40 M☉ (zero-width phase 4 above ~8 M☉) — reported as
  MIST tags it.
- Super-solar low-mass dead corner: `mass_range(feh)` floors at ~0.5 M☉ for
  [Fe/H] > 0.

### 1.6 `activity` proxy — **SHIPPED (2026-09-03), closes the spec §11 question**  · T4

A pure Teff ramp `clamp((6500−Teff)/3500)`. It is honest as a *visual* knob but is
the one place spec §11 is still unanswered.

**The proposed formula is dead — measured 2026-09-03 (recorded so nobody re-proposes it).**
This plan's NEXT said to build `activity = f(Teff) · g(P_rot/τ_conv)` with
`P_rot = 2πR/v` from the served `v_rot_kms`. Gate 0 through the provider says that input
does not exist where the feature needs it. **MIST spins up only stars above the Kraft
break**, so `v_rot_kms` is exactly `0.000` for every cool star on *both* rotation buckets:

| M☉ | v_rot @ vvcrit 0.0 | v_rot @ vvcrit 0.4 |
|---|---|---|
| 0.3 / 0.5 / 0.8 / 1.0 / 1.2 | 0.000 | **0.000** |
| 1.5 | 0.000 | 103.2 km/s |
| 5.0 | 0.000 | 218.5 km/s |
| 15.0 | 0.000 | 251.5 km/s |

The irony is exact: rotation exists in the grid **only for radiative-envelope stars,
which have no convective dynamo**, and is absent for every star the Rossby number is
about. `P_rot = 2πR/v` is not "small" at the default Sun — it is a divide by zero.

**SHIPPED — driven from the SED panel's existing chain instead.** `sed.js` already owned
a real, self-consistent rotation–activity path for exactly the cool main-sequence regime:
Teff→(B−V) (Ballesteros 2012) → gyrochronology `P_rot` (Mamajek–Hillenbrand 2008) *or*
the user's pinned period slider, over Wright (2011) `τ_conv(M)`, gated by
`dynamoLineAllowed()`. `sed.activityLevel()` now maps that same Rossby number to the 0–1
`activity` the 3D corona is drawn from. **One dynamo, two views** — the corona and the
coronal X-ray line can no longer disagree, because they are the same number.

Four things the build had to get right, each measured through the served runtime:

* **No second Rossby path, and no new free parameter.** The 0–1 mapping is Wright's own
  span normalized: the saturated ceiling 10⁻³·¹³ → 1, the panel's quiet floor 10⁻⁷ → 0.
  The gate is exactly `activityLine() != null` — the corona changes only where the blue
  X-ray line is actually drawn.
* **The backend `activity` field was left alone** and is still the fallback everywhere
  the chain isn't honest (hot stars, giants, off-MS, spin-unconverged young stars). No
  provider, no `StellarState` field and no test changed; this is frontend-only.
* **`activity` drives corona GEOMETRY, not just brightness** (`extent = 1.12 + 1.4·act`),
  so a range shift would silently resize the glow on load. Measured before wiring: at the
  default Sun the derived value is **0.212 against the ramp's 0.190** — an unforced
  agreement, so nothing resizes. Elsewhere it now says something the ramp could not: the
  Sun at 1 Gyr reads 0.46 and at 8 Gyr 0.12 (the ramp was flat at ~0.19 across both),
  and an old 0.3 M☉ M dwarf drops 0.89 → 0.44, which is the honest direction.
* **The handoff back to the ramp is continuous.** MH08's (B−V − 0.495)^0·³²⁵ is steeply
  sensitive just redward of its singularity, so the derived value is faded in over the
  first 0.15 mag past the cutoff — a stability measure, not a cosmetic one. Measured on a
  fixed-MS mass sweep: 0.60 → 0.60 → 0.51 → 0.38 → 0.23 → 0.17 (derived) → 0.048 → 0.032
  → 0 (ramp) across 0.8 → 1.3 M☉. No step.

**The payoff, measured on the actual pixels** (Playwright, both 1440 and 390 px, zero
console errors): dragging the period 70 d → 1 d moves activity 0.083 → 0.65 and the lit
fraction of the 3D frame **0.31 → 0.73** (the glow's area more than doubles); dragging
back returns to 0.3072 exactly, no drift. The radial profile stays monotone (limb 171,
then 66 vs 26 just outside at fast vs slow). The WD endgame enters and exits clean —
**nothing is cached on either side**: `star.js` reads the override per `update()` call,
and `sed.activityLevel(servedActivity)` takes the provider's ramp as an argument from the
caller's own state rather than storing a copy (the stored form was a real bug — the slider
never goes through `sed.update()`, so a cached base still held the giant's 0.82 on the
first slider move after Back). After Back the star reads 0.82, the *ramp's* answer for a
3600 K AGB giant; scrubbing to the MS and moving the slider immediately gives 0.089 →
0.60, uncontaminated.

Still **T4/evocative** — it sets how far the corona reaches, not a predicted L_X, and the
readout tooltip says so in both branches.

### 1.7 Composition — **GATED**  · T2

Read off, never integrated (spec §2). Cr/Mn/Ni absent from the MIST network; B is
only the radioactive b8 floor (excluded); 13 elements sum to ~0.99 Z. Na dredge-up
(×1.41 at the 3 M☉ RGB tip) is real but sub-pixel. No action.

### 1.8 MESA-vs-MIST cross-validation — **ACCEPT**  · T1

Solar-Z (MESA r24.03.1 vs MIST v2.5): 1 M☉ |Δlog L| ≤ 0.014, |ΔTeff| ≤ 0.04 %,
|ΔR| ≤ 1.5 %; 2 M☉ ≤ 0.045 / 2.0 % / 9.9 %; 6 M☉ ≤ 0.069 / 1.4 % / 8.5 %. The gap
grows toward TAMS (overshoot / mixing-length differences) and its **sign is not
uniform** — never assert "MESA brighter". Metal-poor grid: late-MS |Δlog L| ≤ 0.126.
This is the honest reason the He/α what-ifs are MESA-vs-MESA only.

---

## 2. Endgame — WD / WR / core-collapse

| Item | Tier | Measured / stated | Verdict |
|---|---|---|---|
| SN explosion mechanism | OOS | Aftermath only; no bounce, no shock breakout (first sample 0.5 d). | ACCEPT — caption owns it. |
| ⁵⁶Co tail slope | T1 | 0.00976 mag/d on `L_radio` (theory 0.00975). | Pinned. |
| IIP plateau (Popov/KW) | T3 | Shape from MIST M_ej, R₀; canonical E = 10⁵¹, κ = 0.34 → **±dex in level**. | GATED — "±dex" is in the caption. |
| M_Ni | T3 | Not derivable from MIST; free slider 0.001–0.3 M☉. | GATED. |
| NS/BH/failed cut | T3 | `smoothstep(CO 7 → 12)`; label flips at remnant 2.5 M☉. Real explodability is non-monotonic (Sukhbold+2016). | ACCEPT — caption says "averaged trend". **NEXT:** optional Ertl+2016 two-parameter (M4, μ4) overlay is *not* possible — MIST ends before the Fe core, so M4/μ4 do not exist. Recorded to stop re-proposing. |
| Fe core / inner onion | T2 | MIST v2.5 stops before Si-burning; inner shells are canonical, disk is enclosed-mass (radial order inverted). | GATED — caption. |
| SN/WD boundary | T2 | The grid flips in ONE step at every ([Fe/H], rotation): 6.5 → 7.0 M☉ at solar and +0.5, 6.5 → 7.0 at −0.5 non-rotating but 6.2 → 6.5 rotating, 6.0 → 6.2 at −1.0 (measured over all ten grids 2026-09-03). Inside the super-AGB / ECSN uncertainty. | GATED — **uncertain-fate caption shipped 2026-09-03**. `fate_boundary_status()` + `/fate_boundary_status`: band = the **measured** heaviest-WD node → a **cited** 8.0 M☉ ceiling (Poelarends+2008, Doherty+2015/2017; MIST models neither super-AGB pulses nor electron capture, so its width is not measurable). Hedges **both** verdicts in-band. |
| WR spectra coverage | T2 | PoWR covers only the cool WNh entry (~10 % of rows); stripped core at T* 150–262 kK is off any observed grid. | GATED — "no model" frame. |
| WD spectra edges | T2 | DC continuum below ~5 kK; TMAP to 190 kK; Koester DB is non-redistributable. | GATED. |
| WD cooling scrub | T1 | Real MIST rows; TPAGB compressed to 12 % of the slider; pulse view gated at 0.15 dex. | GATED. |
| Type Ia | OOS | Needs a binary channel off the WD branch. | Deferred with rationale. |

---

## 3. Siblings

| Item | Tier | Measured / stated | Verdict |
|---|---|---|---|
| Interior profiles (MESA) | T2 | 8 mass slices, [Fe/H] axis only at 0.8–1.0 M☉ (measured to its edges: 0.6 too flat, 1.1 fragments). Runs not solar-calibrated. | GATED (snapped-far notes). Window closed by measurement. |
| Polytrope overlays | T1 | Canonical n = 1.5 / 3, never fitted; 0.25 M☉ hugs n = 1.5 to 1–5 %. | ACCEPT. |
| Spectra hot end | T2 | Cube ceiling 55 kK (hottest draggable ~78 kK) → blank + caption. | GATED. |
| Spectral resolution | T2 | 2.5 Å bins ≈ 1 bin/px at full width; Na D at 2.4 bins. | ACCEPT (measured non-feature); per-band re-bake only if the zoom dots show under-sampling. |
| [α/Fe] spectra | T2 | Coelho α = 0 only at {−1.0, −0.5, 0, +0.2}. | GATED. |
| α-enhanced tracks | T1 | Salaris Z-equivalence, not a mixture ("track-equivalence claim"). | ACCEPT — caption says so. |
| Götberg stripped star | T2 | One state; q = 0.8 fixed; companion not in the table; X_core = 0 by construction. | GATED. |
| POSYDON HMS-HMS | T2 | No eccentricity; C/N/O only; no per-row phase. | GATED. |
| Accretion cue | T3 | η = 0.1 schematic; artifact rows (505,221× Edd on `unstable_MT`) gated → ≤3.46× grid-wide. | GATED — re-derive the bound if the gate changes. |
| DCO merger time | OOS | Needs natal kicks — two prescriptions deep. | Deferred. |
| Photometry | T1 | Cube ends 8999 Å → no G/RP/JHK; B-band ZP offset 0.04 mag common-mode; M_V,☉ = 4.832. | ACCEPT. **NEXT:** extend the bake to 2.5 µm with the same PHOENIX/CAP18 sources to unlock Gaia G/RP + 2MASS — the observer panel's most-asked-for gap. Data-gated (host bake). |
| Habitable zone | T2 | Kopparapu quartic diverges outside 2600–7200 K → band blanks. Liquid-water only. | GATED. |
| Asteroseismology | T1 | Scaling relations only; rings 3 % low (the §1.2 root). M/R "recovery" is the principle, never a measurement. | ACCEPT. |
| Isochrone turnoff | T1 | Bluest MS-phase row (naive max-Teff is off 20–50× on old isochrones). | Pinned. |
| BPASS overlay | T1 | Z☉ = 0.020 vs MIST 0.0142 → ~0.15 dex labeled systematic. | ACCEPT. |

---

## 4. Frontend evocative layer — **all T4, all labeled**

Corona / glare / wind filaments / fireball boil / NS dot / Ap–Bp spots / the
instability-strip class positions / the schematic MK typing. Rule unchanged: a
T4 element never borrows a T1 caption. The two recurring traps (from the memory
files): an evocative colour read as a Teff, and a "helium-rich" tag on a carbon
surface. The false-caption check is part of every feature's Gate 0.

---

## 5. Test contract for the science (what CI enforces)

- **Data-free clone must pass** (`.github/workflows/ci.yml`): the §3 architecture
  table (`tests/test_architecture.py`), Lane–Emden closed forms, the SN tiers, the
  Roche geometry, the stub anchors. 140 tests, 0 failures, everything data-gated
  skipped.
- **Two kinds of MIST gate now.** `requires_mist_data` = a working provider (the
  hosted cache-only download qualifies). `requires_mist_raw_tracks` = tests that
  read a raw `.track.eep` as ground truth. Nine tests moved to the second marker;
  they were failing, not skipping, on a cache-only clone.
- **Held-out accuracy tests come in cache-friendly form** where possible (the grid's
  own node is the truth). Prefer that form for any new accuracy test.

---

## 6. Prioritised NEXT list (bounded, honest, in order)

1. **Near-IR spectrum bake to 2.5 µm** (§3 photometry) — host-side bake + one
   `BAKE_VERSION` bump; unlocks Gaia G/RP and 2MASS on the CMD panel.
2. **Grid density at 0.3–0.45 M☉** — only if a user-visible drag artefact is ever
   measured there; MIST has no finer nodes, so this would mean MESA slices.

(Four items have left this list, all shipped 2026-09-03: the He-ignition cliff (§1.3),
the uncertain-fate band (§2), the Sun-residual tooltip (§1.2) and the Rossby-flavoured
`activity` proxy (§1.6). With the last of those, **spec §11's `activity` question is
answered** — the remaining NEXT items are both data-gated or conditional.)

Everything in **OOS** stays out until the grid approach "hits a real wall" (spec §9).
