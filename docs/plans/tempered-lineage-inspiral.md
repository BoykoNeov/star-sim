# Plan: Three subpopulation axes — post-SN compact-object binaries, initial-helium, α-enhanced evolution

## Status: Phase 1 Chunks 1a/1b/1c (CO-HMS_RLO) + Chunks 2a/2b/2c (CO-HeMS/CO-HeMS_RLO) ALL BUILT — Phase 1 COMPLETE.
Phase 1 Chunk 2a (CO-HeMS / CO-HeMS_RLO backend + DCO classifier, solar) is **BUILT** (2026-07-08),
Chunk 2b (frontend render — the `kind` selector + He-surface comp + DCO-endpoint caption) is
**BUILT** (2026-07-09), and Chunk 2c (full 8-bucket [Fe/H] axis for both He grids + the re-derived
Eddington bound) is **BUILT** (2026-07-09) — see "Chunk 2a"/"Chunk 2b"/"Chunk 2c" under "Phase 1
(cont.)". **Phase 1 (the CE/compact-object tail) is now COMPLETE.** Phases 2 and 3 not yet built.
Sequential order (also the efficient order): **Phase 1** binary CE/compact-object tail (Chunk 1
CO-HMS_RLO done → Chunk 2a CO-HeMS backend done → 2b frontend done → 2c [Fe/H] axis done) →
**Phase 2** initial-helium (Y) axis → **Phase 3** α-enhanced evolution axis (reuses Phase 2's
plumbing).

## Scope and non-goals

This plan covers exactly the three roadmap items chosen by the user, developed one after
another:
1. The binarity **CE / compact-object tail** — the POSYDON `CO-HMS_RLO`/`CO-HeMS` grids
   (post-SN NS/BH binaries), extending path (b) past `entwined-consort-inspiral.md`.
2. **Initial-helium / multiple populations** — a He-enhanced "second generation" what-if.
3. **α-enhanced evolution** — letting the *track*, not just the spectrum (Coelho, already
   shipped), respond to [α/Fe].

**Explicitly out of scope:** a BPASS population overlay (a separate future sibling — genuinely
different physics, population synthesis not individual tracks); real common-envelope
hydrodynamics (POSYDON's α_CE·λ energy prescription is what's available, same honesty caveat
as everywhere else 1D binary codes appear); a live nuclear-network solver.

## Data & licensing — settled up front, no new downloads anywhere in this plan

- **Phase 1: zero new downloads.** All 8 POSYDON metallicity tarballs are already on disk
  (~84 GB, `data/Posydon/`, CC-BY, Zenodo DOI 10.5281/zenodo.15194708). Per
  `star-sim-hosted-data-assets` memory, each per-metallicity tarball "holds 6 grid types × 2
  file formats each" — only `POSYDON_data/HMS-HMS/<Z>.h5` has been extracted so far.
  `CO-HMS_RLO`, `CO-HeMS`, `CO-HeMS_RLO` are already inside the same tarballs; extraction is a
  local `tar -x --strip-components` of additional subdirectories, not a new fetch.
- **Phases 2 & 3: zero new downloads.** Per your call, sourced via **self-run MESA (Docker)**,
  the same pattern as `MESAProvider` and the interior-structure snapshots. This is your own
  compute output, so there's no third-party redistribution question (unlike the excluded
  "bearums" MESA data, which is someone else's copyrighted grid).
- **Hosting:** per your call, once baked, Phase 2/3 output is hosted publicly on GitHub
  Releases (new tag(s)) alongside the existing six datasets — casual users won't need Docker
  MESA themselves.
- **The only thing needed from you in this whole plan is compute, not bandwidth:** running a
  handful of MESA Docker batches for phases 2 & 3 once I hand you the exact inlist diffs.
  Phase 1 needs no user action beyond review at the one open design decision (entry/navigation,
  below).

## Baking discipline (every phase, per the instruction to keep size down)

- **Column-trim** to only what `StellarState`/the frontend actually reads — mirrors
  `bake_posydon.py`'s existing practice and the MIST bake's ~27x reduction (don't ship
  `history.data`'s ~100 raw columns when the app reads ~12).
- **Row-decimate** long tracks, but force-keep the physically interesting rows: RLOF/CE
  episodes for Phase 1 (the existing `bake_posydon.py` precedent already does this for
  HMS-HMS), the full MS→endpoint span for Phases 2 & 3 (short tracks, decimation may not even
  be needed at 1-6 masses × 2 compositions).
- **float32 + gzip** on every `.npz` (already standard here).
- **Raw source never committed or hosted** — only the derived cube, same as every other
  dataset in this project. Raw POSYDON/MESA output stays under gitignored `data/`.

## Phase 1 — Binary CE / compact-object tail (POSYDON `CO-HMS_RLO`, `CO-HeMS`)

### Physics

The built path (b) covers only the *first* mass-transfer episode between two normal,
hydrogen-burning stars. This phase covers what happens **after one star dies**:

- **`CO-HMS_RLO`** — a compact object (NS/BH, left by the primary's collapse) orbiting a still
  hydrogen-rich secondary. If the secondary later overflows onto the compact object, the
  result is an **X-ray binary** (Cygnus X-1's configuration — BH + O-star donor): accretion
  releases gravitational potential energy as X-rays, a genuinely new luminosity mechanism for
  this sim (not photospheric).
- **`CO-HeMS`/`CO-HeMS_RLO`** — the next stage: the secondary has *also* been stripped to a
  bare He star (the same Case-B physics path (a) already models), now orbiting the compact
  object — the direct progenitor configuration for a **double compact object (DCO)** binary
  (NS-NS/NS-BH/BH-BH), i.e. a gravitational-wave-merger progenitor.
- **Common envelope (CE):** dynamically unstable RLOF (extreme mass ratio, deep convective
  donor envelope) engulfs the companion; drag spirals the orbit in, either ejecting the
  envelope (tight surviving binary) or merging. POSYDON parameterizes this with an
  α_CE·λ energy formalism — a 1D prescription, not real hydrodynamics. Must be captioned as
  such, exactly like the project's other schematic/prescription physics (corona, wind shader).
- **Natal kicks:** core collapse gives the newborn NS/BH an asymmetric kick, which can unbind
  the binary outright — ties directly into the already-built SN/remnant sibling's NS/BH
  formation, now in a binary context where the kick decides whether the system survives.

### Architecture

- **New data shape (advisor-flagged, not in the original binarity design):** a `BinaryStep`
  is two `StellarState`s. A post-SN CO-binary step is **one real `StellarState`** (the
  surviving star) **+ a point-mass companion scalar block** (`mass_msun`, `type: "NS"|"BH"`,
  and — if the schema supports it — an accretion-luminosity cue from the RLOF mass-transfer
  rate, a standard `L = η·Ṁ·c²` estimate). This is closer to the existing merger case
  (`star_2=None`) than to a normal `BinaryStep`, but not identical — a compact object is a
  labeled point mass, not an absent star. Decide the render (schematic marker, no
  photosphere/shader) before coding.
- **Schema-first, not schema-assumed:** `bake_posydon.py` assumes
  `run<i>/{binary_history,history1,history2}`. The CO-grid layout must be validated against
  the *real* extracted HDF5 before writing a bake path — one side of a CO binary has no
  stellar evolution history, so the schema may genuinely differ from HMS-HMS, not just swap
  column names.
- **Entry/navigation (the biggest open UX question, settle via a chunk-time advisor
  consult — the project's established pattern):** does a user reach the post-SN phase by
  *chaining* an HMS-HMS track that ends in supernova into a CO-HMS_RLO continuation (mirrors
  POSYDON's own population-synthesis chaining), or via a **standalone curated demo** that
  picks a CO-HMS_RLO track directly? **Recommendation: start standalone** — lower risk, and
  mirrors how Chunk 4b started with curated demos before Chunk 4c's free sliders. Only build
  the chained version if the standalone proves the payoff is worth the extra plumbing.

### Chunked build

**Chunk 1a — schema recon + bake (backend, solar-first) — BUILT 2026-07-08**
- Extracted `CO-HMS_RLO` from the already-downloaded solar tarball (`CO-HeMS`/`CO-HeMS_RLO`
  deferred — not needed for this chunk's scope).
- Schema recon (measured, not assumed): `history2` is absent in ALL 9069 sampled runs,
  unconditionally — S1 is always the normal star, S2 always the compact object. This settled
  the architecture: a genuinely new sibling, not a `posydon.py` branch.
- Built: `bake_posydon.py` gained `bake_co()` + `--grid-type co-hms-rlo` (reuses input-reading
  helpers, writes to a separate `data/posydon/baked_co/` dir); `posydon.py`'s per-row helpers
  promoted to public (`state_from_row`/`mt_state_label`/etc.) for reuse; new sibling
  `posydon_co.py` (`CoBinaryStep`/`CoBinaryTrack`, snap-only in (log M_star, log M_co, log P));
  new `/co_binary_track` + `/co_binary_track_meta` routes (bypass PROVIDER, mirror
  `/binary_track`'s snap-always + 422/503 discipline).
- The accretion-luminosity cue was built (`L=eta*Mdot*c^2`, `ACCRETION_EFFICIENCY=0.1`) and
  characterized across the WHOLE baked grid (not just spot-checked): 2-3.5x Eddington, a real
  bounded super-Eddington/ULX-like regime — pinned as a permanent regression test.
- Tests: `test_posydon_co.py` (18 new, gated `requires_posydon_co_data`) — schema/snap honesty,
  no NaN/duplicate nodes across the whole bake, the accretion-cue sanity + Eddington-bound
  regression, the Gate-1 measure-first regression (CO mass genuinely grows via accretion; RLOF
  fires then detaches; the donor ends heavily stripped and hot), route shape + 422s.
- Full detail + the float32-overflow characterization gotcha: `star-sim-co-hms-rlo.md` (memory).
- **Not done in this chunk:** `CO-HeMS`/`CO-HeMS_RLO` extraction, more metallicities (Chunk 1c).

**Chunk 1b — frontend render — BUILT 2026-07-08** (frontend + one backend addition, 330 pytest
[+2], Playwright-verified 1440+390 zero console errors)
- Extended the binary-track HR/Roche/3D machinery to the new step shape: one real Teff-colored
  star + one schematic point-mass marker. HR shows ONLY the living star (a point mass has no
  photosphere → NO luminosity point — advisor); 3D + Roche draw a schematic CO glyph (BH = a
  persistent dark disc + bright ring, deliberately NOT the SN "winks out"; NS = a hot point).
- Backend addition: `co_binary_track_payload` folds in per-step Roche geometry by reusing
  `binary.track_roche_geometry` (sibling-calls-sibling) via a `SimpleNamespace` adapter
  (star→donor/origin, CO→accretor at (1,0), q=m_co/m_star). +2 tests.
- Entry point = the settled **standalone curated demo** (Chunk-1a consult, NOT SN-chained): a
  sibling demo row inside stripped-mode, its own `.co-binary-view` body class, mutually exclusive
  with the HMS-HMS `.binary-view`.
- Honest captions: CE/SN steps named-not-modeled; the accretion-luminosity cue labeled as a
  standard η·Ṁ·c² formula on the served Ṁ (not a measured X-ray spectrum), surfaced in the
  age-slider caption RELATIVE to the star's own L (~2.5× during RLOF1).
- Two bugs caught+fixed during verification: a slow-in-flight-fetch mutual-exclusivity race
  (both enter funcs now bump the other view's token unconditionally); an advisor-flagged
  false-data leak (the readout/scale/MK-class single-star consumers froze on the unrelated
  stripped snapshot — now CSS-hidden in `.co-binary-view`, like comp/spectrum/sed/structure).
- **Not done:** custom M_star/M_co/P sliders (the demo is one hardcoded solar system) and more
  metallicities — both fold into Chunk 1c.

**Chunk 1c — the full [Fe/H] axis + free M_star/M_co/P sliders — BUILT 2026-07-08**
(data + frontend + one backend correctness fix, 332 pytest [+3], Playwright 1440+390 zero
console errors). Mirrors the HMS-HMS Chunk 4c/4d rollout; **no runtime-logic change for the
axis itself** (`co_binary_track` was already snap-always over the whole grid, §6).
- Extracted + baked the **7 non-solar buckets** → the full 8-bucket axis (coextensive with
  the HMS-HMS [Fe/H] axis, −4.0…+0.30, exact `--feh` values reused). All 8 grids non-empty
  + clean. Measure-first passed: the same (M_star, M_co, P) flips outcome across [Fe/H].
- Frontend: a `#co-binary-feh` picker (populated from the real `available_feh`) + a "Custom
  system…" picker revealing three **log** sliders — the CO axis is **(M_star, M_co, P), not
  (M1, q, P)** (a CO's mass is a physical value, not a ratio). CO twins of the HMS-HMS
  meta/refetch/apply/params helpers; bucket change re-fetches meta (per-bucket spans) before
  the track. WD-placeholder + snapped-far honesty in the custom note; narration corrected.
- **The one real fix (the full-grid pytest caught it):** the Chunk-1a accretion-cue Eddington
  bound was SOLAR-ONLY characterized (2–3.5×, "no cap needed"); the metal-poor grids reach
  505,221× on a few rows — ALL on POSYDON `unstable_MT` (CE/merger) tracks, where the
  parametrized ṁ is not a real accretion luminosity. Gated the cue off `unstable_MT` (the
  `active` mask now needs `not is_unstable_mt`) → bounded ≤3.46× Eddington grid-wide, the
  stable X-ray-binary payoff preserved. Detail: memory `star-sim-co-hms-rlo.md`.

**Chunk 2 — `CO-HeMS` / `CO-HeMS_RLO` (the double-compact-object channel) — PLANNED, recon
done 2026-07-08, not yet built.** See "Phase 1 (cont.)" below for the full chunked plan.

### Measure-first gate (Gate 1, mirrors Chunk 4a's Gate 0)

Before any control ships: verify through the real runtime that a CO-HMS_RLO/CO-HeMS track
shows something a plain HMS-HMS track cannot — a distinguishable X-ray-binary accretion
phase (different physical mechanism from RLOF onto a normal star), and/or a real orbital
discontinuity at the SN transition if the chained path is built.

## Phase 1 (cont.) — CO-HeMS / CO-HeMS_RLO (the double-compact-object channel)

The last link in POSYDON's massive-binary relay:
`HMS-HMS → CO-HMS_RLO → **CO-HeMS / CO-HeMS_RLO** → double compact object (GW merger)`.
Where CO-HMS_RLO is "compact object + still-H-rich star," this is the stage after the
*second* star has also been stripped to a bare **He star** orbiting the compact object — the
direct progenitor configuration for a BH-BH / NS-BH / NS-NS binary, i.e. a
gravitational-wave-merger source (LIGO/Virgo). This is the payoff that makes the channel
worth building beyond "another accretion grid": it closes the story on the LIGO source.

### Schema recon — DONE 2026-07-08 (measured, not assumed; the project discipline)

Both grids extracted from the already-on-disk solar tarball
(`data/Posydon/CO-HeMS_1Zsun_recon/`, `CO-HeMS_RLO_1Zsun_recon/`) and measured directly:

- **It is a confirmed drop-in twin of CO-HMS_RLO.** `history2` is absent in every sampled
  run (S1 = the real star, S2 = the point-mass CO) — the *same* single-real-star schema, so
  this is a `posydon_co.py`-family sibling, **not** a `posydon.py` two-`StellarState` branch.
  `history1` carries **every** `_HISTORY_COLS` column and `binary_history` carries **every**
  `_CO_BINARY_COLS` column → `bake_co()` and `state_from_row()` drop in unchanged.
- **The surviving star is a He star** (`S1_state ∈ {stripped_He_Central_C_depletion,
  stripped_He_Central_He_depleted, stripped_He_Core_He_burning, stripped_He_non_burning}`).
  Measured surface at mid-track: **H1 = 0.0000, He4 = 0.986**, Teff ≈ 56 kK, R ≈ 0.26 R☉ —
  a hot compact WR-like He star. The composition measure-first gate is therefore essentially
  **pre-passed**: reuse the existing Götberg stripped-star He-surface comp view
  (`comp.setStripped`), don't build a new one.
- **The two grids are complementary, both worth baking:**
  - `CO-HeMS` — **14256 runs, `no_MT`-dominated (8937)**: the *detached* post-mass-transfer
    inspiral phase. The accretion cue honestly stays `None` here (RLOF-scoped). This grid is
    the home of the **DCO / GW-progenitor payoff**.
  - `CO-HeMS_RLO` — **5319 runs, `stable_MT`(2570)+`initial_MT`(2100)-dominated, no `no_MT`**:
    the RLOF episode. Accretion-onto-CO cue fires (measured: CO mass grows, e.g. +0.44 M☉
    with 35 RLOF rows on a stable_MT run) — the exact CO-HMS_RLO payoff with a **He** donor.
  - S2 (CO type) is BH-dominated on both (CO-HeMS: BH 9630 / NS 1865 / WD 371; CO-HeMS_RLO:
    BH 2278 / NS 523 / WD 102) — this is predominantly the **BH-companion** channel.
  - Snap axes match CO-HMS_RLO — `(M_star_He, M_co, P)`: M_star 0.50–191.9 M☉,
    M_co 1.00–307.5 M☉, P 0.020–1147 d.
- **WD-placeholder caveat recurs** — both grids carry WD companions. Verify the frozen
  1.0-M☉ placeholder pattern at bake time; the existing three-part cue gate (`not detached
  AND not unstable_MT AND not WD`) carries over unchanged and handles it.

### The honesty-tier decision (advisor-settled 2026-07-08 — the load-bearing call)

The tempting "GW merger time" cue is **NOT** the same honesty tier as the accretion cue, and
the difference is the *input*:

- **Accretion cue** = a formula (η·Ṁc²) on a **real served rate** (`lg_mstar_dot_2`). Input
  measured → Tier-1/2. Carries over to CO-HeMS_RLO unchanged.
- **Peters (1964) merger time** = a formula on the **post-second-SN orbit**, which this grid
  **does not contain**. Recon confirmed: `final_values` orbital columns (`period_days`,
  `binary_separation`) are the *pre-collapse* orbit — the track ends at the He star's
  C/He-depletion, before it collapses. The DCO orbit forms only *after* S1's core collapse,
  and depends on the **natal kick** — a modeling layer this grid does not serve. So a merger
  time would be *two prescriptions deep* (a kick model feeding a Peters integral), not one.

**Therefore, the payoff tiers for Chunk 2:**
- **Tier-1/2 (real, ships in core scope):**
  1. The He-star `StellarState` history (Teff/L/R + He-rich composition from real tracks).
  2. The accretion-onto-CO cue on **CO-HeMS_RLO** (η·Ṁc² on the served `lg_mstar_dot_2`,
     the existing three-part NS/BH-stable gate) — a He-donor X-ray binary.
  3. **DCO-progenitor classification** — the novel, honest GW payoff. POSYDON serves its own
     SN-model prediction of what the He star becomes (`S1_SN_MODEL_v2_XX`: remnant `mass`,
     `SN_type`, `CO_type`, `spin`, `f_fb`). Combining S1's predicted remnant with the *known*
     S2 (the existing CO) classifies the endpoint: **BH+BH / NS+BH / NS+NS** — or **WD → no
     DCO** (run25's S1 SN model actually predicts a 0.74-M☉ WD, so the classifier must be
     honest that not every CO-HeMS system makes a merger). This reuses the already-built
     SN/remnant sibling's remnant vocabulary and needs **no kick model**. Caption-owned
     choice: POSYDON ships **24 SN-model prescriptions** (`_v2_01`…`_v2_24`, e.g. Fryer
     rapid/delayed) — pin one documented default, label it, exactly like every other
     prescription in this project.
- **Evocative / captioned stretch (optional, explicitly two-prescriptions-deep — recommend
  DEFER out of core scope):** a "would it merge within a Hubble time?" flag. Only if built,
  it must be captioned as depending on an un-served natal kick + a Peters estimate, at the
  corona/wind honesty tier — never presented as measured POSYDON output.

### Architecture (follows from the payoff, per the advisor: decide payoff, architecture falls out)

Because the machinery is a confirmed drop-in and the only CO-HeMS-specific logic is (a) the
He-comp view reuse and (b) the DCO-classification readout, the leanest path is
**parameterize, don't fork**:

- **Bake:** `bake_posydon.py` gains `--grid-type co-hems` and `--grid-type co-hems-rlo`,
  reusing `bake_co()` verbatim (same column trim, RLOF-keep decimation, index-identity check,
  float32/gzip). New output dirs `data/posydon/baked_co_he/` and `baked_co_he_rlo/` (or a
  single dir with a grid-type tag — settle at chunk time). Additionally record the
  `S1_SN_MODEL_v2_<default>_{mass,SN_type,CO_type,spin,f_fb}` scalars per track (the DCO
  classifier's inputs — the `Mcur`/`endgame()`-scalar precedent: cached, read off the snapped
  track, never blended). **`BAKE_VERSION_CO` can be shared** — the output shape is identical
  (a few extra per-track scalar arrays don't change the row schema; bump only if that proves
  false).
- **Runtime:** the smallest change is a **grid-type parameter on `posydon_co.py`** (a `kind`
  arg selecting the baked dir + the outcome vocabulary) rather than a near-duplicate module —
  `co_binary_track`, `_snap_*`, the accretion-cue gate, and the Roche-geometry fold-in are all
  reused. A thin `dco_classification(s1_sn_model, s2_co_type)` helper is the only genuinely new
  logic. If this bloats `posydon_co.py` uncomfortably, split into a small `posydon_co_he.py`
  that imports the shared helpers — but start parameterized.
- **Routes:** `/co_binary_track` + `/co_binary_track_meta` gain a grid-type/`kind` query param
  (default the existing CO-HMS_RLO, so the live surface is behavior-compatible — additive
  keys only), mirroring the
  `vvcrit`-param-defaults-to-old-behavior precedent.

### Chunked build

**Chunk 2a — bake + backend sibling (solar-first, RLOF-first) — BUILT 2026-07-08** (backend-
only, no frontend, +38 tests in `test_posydon_co_he.py`). Renamed the recon dirs to canonical
`CO-HeMS_1Zsun` / `CO-HeMS_RLO_1Zsun`; extended `bake_posydon.py` (`--grid-type co-hems`/
`co-hems-rlo`, both through the existing `bake_co()` + a new per-track SN-model scalar block —
`SN_MODEL_DEFAULT = S1_SN_MODEL_v2_01`, the DCO classifier's inputs). Baked CO-HeMS_RLO solar
FIRST (4997 tracks, the drop-in proof — accretion cue fires unchanged), then CO-HeMS (11100).
Parameterized `posydon_co.py` with a `kind` arg (`VALID_KINDS = co-hms-rlo | co-hems |
co-hems-rlo`, default behavior-compatible — additive `kind`/`dco` payload keys only): per-kind
baked dirs, an optional SN-scalar load (NO
`BAKE_VERSION_CO` bump — the 8 CO-HMS_RLO npzs weren't re-baked), the `dco_classification`
helper + a `DcoClassification` on `CoBinaryTrack` (He kinds only), and the `kind` route param
(422 on an unknown kind).
- **Gate 2a CLOSED through the real runtime:** CO-HeMS_RLO shows a He-donor (Case BB/BC)
  accretion episode (demo 1.42 M☉ He star + 10.2 M☉ BH: 31 active rows, CO grows +0.72 M☉);
  CO-HeMS classifies a real DCO endpoint (demo 16.6 M☉ → BH(5.90) + BH(5.99) = "BH + BH merger
  progenitor"), and honestly reports "no DCO" when POSYDON predicts a WD remnant.
- **Eddington bound RE-DERIVED (the task's explicit requirement — NOT assumed to inherit
  3.46×):** measured across BOTH He solar grids under the same three-part `active` gate → max
  **3.47×** Eddington (the same physical ULX ceiling as CO-HMS_RLO — POSYDON caps stable
  transfer). SOLAR-SCOPED in the docstring + test: the metal-poor He buckets carry the same
  `unstable_MT` artifact class CO-HMS_RLO's did (Chunk 1c: solar clean, metal-poor 505,221×), so
  2c must re-derive across all 8 — do not re-ship the 1a→1c mistake.
- **The DCO classifier** keys off the remnant TYPE (BH/NS/WD/None), not `sn_type` — so a
  low-Z PISN (massless → CO_type None) falls through to the honest unresolved branch for free
  at 2c. Prescription labeled BY INDEX (`v2_01`, of 24; caption-owned), the boron-b8 discipline.
  S2's DCO mass is the FINAL-row (post-accretion) mass, not `m_co_init`.
- **Index-identity tolerance loosened for the He bake (`_CO_INDEX_IDENTITY_RTOL = 5e-2`, an
  advisor-flagged pre-2c diagnostic):** the strict 1e-3 check dropped ~20% of CO-HeMS runs
  (2798, ALL index-identity, 0 length-mismatch) — measured as BENIGN He-star WIND drift (the
  point-mass CO's `star_2_mass` matches exactly; only the bare He star's `star_1_mass` drifts
  ≤0.24% and the orbit widens ≤1.1% between the grid point and the first saved row), concentrated
  in `no_MT` (the DCO home). 5e-2 admits it while staying far below the ≥40% inter-node spacing.
  CO-HeMS re-bake 11100 → 13898 tracks; CO-HeMS_RLO unaffected (0 drops either way).
- Tests (`requires_posydon_co_he_data`, both He grids baked): 4 UNGATED pure classifier unit
  tests (BH+BH/NS+BH/NS+NS labels, WD/None → no DCO, nan-mass); parametrized-over-kind snap/parse
  honesty, whole-grid no-NaN/no-dupe, per-step StellarState + He-stripped-surface validity; the
  RLO accretion regression; the DCO POSITIVE-presence regression (assert `dco is not None` +
  label, advisor trap #1); the re-derived Eddington bound (raw + served-level); the `kind` axis +
  the one-letter co-hms-rlo/co-hems-rlo hazard guard; route shape + 422 (incl. unknown kind).

**Chunk 2b — frontend render — BUILT 2026-07-09** (frontend-only, NO backend change, 373 pytest
unchanged, Playwright-verified 1440+390 zero console errors). Settled navigation = **a `kind`
`<select>` inside the EXISTING `.co-binary-view`** (advisor-endorsed Option A — sub-selector, not
a parallel `.co-he-binary-view`), the axis orthogonal to `[Fe/H]`, mirroring the backend's
parameterize-don't-fork: three physical-label options (Compact object + H-rich star / + He star
inspiral→merger / + He star mass transfer) driving the same routes with `&kind=`. A `coKind` state
var (default `co-hms-rlo`, byte-compatible), threaded into BOTH the track and meta fetch URLs; the
meta cache now keys on **`(kind, feh)`** (each kind is its own grid with its own M_star/M_co/P
spans — switching kind at unchanged feh must re-fetch bounds, the 4d stale-slider bug class). A
kind change is a fresh grid: it resets the custom triple to that kind's curated demo, invalidates
the meta cache, re-fetches meta then track, and swaps the demo-button label + the demo-row `?`
tooltip (both were hardcoded H-rich — a false-caption class the advisor blocked).
- **Curated demo triples are the exact Chunk-2a-verified nodes** (`test_posydon_co_he.py`), NOT
  guessed — a guess can snap to a WD / `unstable_MT` node where the payoff is gated off (a dead
  demo). CO-HeMS = 16.559711/5.990075/0.561443 (BH+BH DCO); CO-HeMS_RLO = 1.422924/10.248538/
  0.045189 (He-donor X-ray binary — the accretion cue fires, measured ≈205–610× the star's own L).
- **The DCO-endpoint caption** (`#co-binary-dco-note`, He kinds only) prints the classifier's OWN
  served one-liner **verbatim** (`data.dco.label`, advisor: can't drift), + a friendly gloss of the
  index-labeled prescription: "Endpoint: BH + BH merger progenitor (POSYDON core-collapse
  prescription v2_01)." / honestly "no double-compact merger — the He star ends as a white dwarf."
- **He-surface comp** — the panel (CSS-hidden on the H-rich kind) comes back on for He kinds via a
  `co-he-kind` body class set off the SERVED `data.kind`, driven per scrub-step by
  `comp.setStripped(s, {source:"posydon"})`. **comp ALONE** (spectrum/sed/structure stay hidden —
  out of 2b scope, advisor). **The reused `drawStripped` was made honest for the new C/O regime**
  (advisor-caught false caption on the flagship demo's LATE state, which I'd wrongly hand-waved):
  the CO-HeMS BH+BH demo scrubs from He 99% → **Z≈72% carbon/oxygen** (a WC/WO surface), where the
  old `heRich = Y>X` label falsely read "helium-rich / the bared core is helium." Added a three-way
  `surfKind` (Z>Y → "carbon/oxygen-rich surface (Wolf–Rayet WC/WO)") AND a `source`-aware caption
  (the Götberg "one representative state" attribution is false on a time-varying POSYDON track).
  The single-star Götberg snapshot path is byte-unchanged (opts defaults to `gotberg`; its
  Z_surf≈0.014 never trips the `co` branch).
- HR-star-only + the schematic CO glyph + the accretion cue + the live Roche panel all reused
  UNCHANGED from CO-HMS_RLO (byte-identical across kinds — the point of Option A). A He-kind
  narration block (`endgame-narrate-co-hems`) swaps in for the H-rich one via the `co-he-kind`
  class. All co-he-kind class + DCO-note cleanup wired into `exitCoBinaryView` + the two
  snapshot-reset spots. Mobile 390 stacks single-column, no overflow.

**Chunk 2c — the full [Fe/H] axis. BUILT 2026-07-09 (data + tests only; NO runtime-logic or
frontend code change, 379 pytest, Playwright 1440+390 zero console errors).** Extracted + baked
the 7 non-solar buckets for both He grids (zero new downloads — the 8 tarballs were on disk),
giving the full 8-bucket [Fe/H] axis (−4.0…+0.30103), coextensive with CO-HMS_RLO. Mirrored
Chunk 1c: **no runtime change** — `co_binary_track`/`_meta` were already snap-always over the
whole grid and the existing `#co-binary-kind`-scoped `#co-binary-feh` picker already populates
from the real `available_feh` (meta cache keyed on `(kind, feh)`), so the frontend picked up all
8 buckets for the He kinds with no edit (verified end-to-end via Playwright: both He kinds' picker
lists 8, a bucket switch re-fetches meta+track, the DCO-endpoint caption re-computes). **The
mandatory Eddington re-derivation** (ungated, float64-cast, full-grid over both He grids × all 8
buckets): the accretion cue holds at **≤3.65× the CO's own Eddington** (co-hems-rlo at the
metal-poor floor feh=−4.0; co-hems uniform 3.47×) — the metal-poor buckets edge the solar 3.47×
up only slightly, well under the test's 5.0 ceiling. **Notable measured finding:** the He grids
are genuinely CLEANER than CO-HMS_RLO — the ungated pass finds ZERO rows above 5× anywhere (no
`unstable_MT`/WD artifact), unlike the metal-poor CO-HMS_RLO grids that hit 505,221× — so the
re-derivation was mandatory and the result is a genuine "no artifact" confirmation, not an
assumption. Tests: +3 metallicity-axis tests (×2 He kinds = +6 gated on `requires_posydon_co_he_multifeh`):
`available_feh` reflects the real baked set per kind; the same request resolves to a genuinely
different real *track* across buckets (the axis-is-real regression — POSYDON reuses the same
initial grid per Z, so the fingerprint is the *evolved* track: co-hems final He-star mass falls
monotonically 16.46→8.42 M☉ across the axis from Z-dependent winds); and the DCO classifier
degrades honestly (no nan leak, no crash) over a whole metal-poor grid. The existing
`test_accretion_cue_within_a_few_eddington_across_he_grids` auto-covers all 8 buckets (it loops
`_available_grids(kind)`); its docstring was updated from "3.47× solar-scoped" to the re-derived
all-8-bucket number.

### What's needed from you

Nothing but review — **zero new downloads** (the tarballs and even the solar CO-HeMS grids are
already on disk) and no compute. The one decision to confirm before Chunk 2a codes: **is the
DCO-classification readout the intended core payoff, and is the Peters merger-time flag
deferred** (recommended) or wanted as an explicitly-captioned evocative stretch?

## Phase 2 — Initial-helium (Y) axis, self-run MESA

### Physics

Globular-cluster CMDs (ω Centauri, NGC 2808) show split/broadened main sequences and
horizontal branches attributed to a **second stellar generation enhanced in initial helium**
(Y≈0.35–0.40 vs. primordial ≈0.25) at the *same* [Fe/H] as the first generation — He
enrichment tracks H-burning pollution, not supernova iron, so it's an axis genuinely
independent of Z. At fixed mass/[Fe/H], raising Y raises the mean molecular weight μ; by the
standard homology scalings a star is **more luminous, hotter (bluer), and shorter-lived**
(L rises steeply with μ, so τ_MS = M/L falls) — exactly the effect that also resolves the
horizontal-branch "second-parameter problem."

### Architecture (advisor-mandated)

- **A what-if overlay sibling, not a new PROVIDER axis** — mirrors the Ap/Bp and gravity-darkening
  pattern. A toggle overlays a He-enhanced MESA track against a **MESA baseline** track at the
  same mass/[Fe/H], **never against the live MIST spine** — comparing self-run MESA to MIST
  would conflate the He effect with the already-documented MESA-vs-MIST systematic
  (`test_mesa_vs_mist.py` exists precisely to keep those comparisons honest).
- **Reuse `MESAProvider`'s existing `history.data` parser** rather than writing a third one —
  check header/column compatibility against the new runs before assuming it drops in as-is.
- **MESA batch:** for a handful of masses (recommend reusing `MESAProvider`'s existing solar-Z
  set — 1/2/6 M☉ — for a natural before/after story against data already validated), run
  **two** inlists per mass at solar [Fe/H]: baseline (`initial_y` from the default Y(Z)
  relation) and enhanced (`initial_y`≈0.35–0.40, the observed ω Cen/NGC 2808 range). **Change
  `Zbase` too, not just `initial_z`** (the exact gotcha already documented in
  `mesa_structure_recipe.md` — otherwise Y/Z decouple wrong).
- New sibling (extends `mesa.py`'s parsing helpers, or a small new module) — bypasses
  `PROVIDER` like every other what-if in this project.

### Chunked build

**Chunk 2a** — MESA batch + bake. **BUILT 2026-07-09 (Claude ran the batch in Docker MESA).**
The six runs (`inlist_{base,enh}_{1,2,6}`, enhanced **Y=0.40** vs baseline explicit **0.2704**,
`Zbase=initial_z=0.0152` in both — the Y axis leaves Z fixed) converged (exit 0, ~100–130
exposed rows each) and landed at `data/mesa_helium/{baseline,enhanced}/<M>Msun/history.data`
(gitignored, MESA-local like `data/mesa/` — the hosted-data-assets pattern excludes MESA, so
tests skip via `requires_helium_data`). **No bespoke npz bake** (advisor): 4 MB of `history.data`
is read directly by the reused MESA parser, like `MESAProvider`. **Gate-2 PASSED emphatically at
every mass** (measured through the real runs, matched-phase): enhanced-Y is hotter, brighter, and
shorter-lived — 1 M☉ 5752→6559 K / 0.80→1.86 L☉ / τ_MS 8.33→3.03 Gyr (2.7×); 2 M☉ 9491→11152 K /
17.9→33.8 L☉ / 0.86→0.41 Gyr (2.1×); 6 M☉ 19611→22312 K / 1069→1839 L☉ / 0.055→0.029 Gyr (1.9×).
Recipe `backend/docs/mesa_helium_recipe.md`.

**Chunk 2b** — backend sibling + route. **BUILT 2026-07-09.** `star_sim/helium.py` (a §3 sibling
like `binary.py`/`structure.py` — imports only `state.StellarState` + the MESA parser's free
helpers `_build_track`/`_state_from_track`, never `PROVIDER`) globs the pairs, keys each member by
its **ZAMS surface He** (`Ys[0]`, not dir name), and pairs lower-Y=baseline / higher-Y=enhanced
(asserts exactly two per mass so a stray run fails loudly). `helium_overlay(mass)` snaps to the
nearest grid mass (1/2/6, solar Z) and returns both tracks as §3 `StellarState` lists + each's
ZAMS Teff/L and **windowed τ_MS**. `/helium?mass=` bypasses `PROVIDER`, snap-always (in-band
`mass_snapped_far`), 422 on mass≤0. Refactor: lifted `_state_from_track` out of `MESAProvider` to
module level (uses no `self`) so the sibling reuses it; the method now delegates (byte-behavior
unchanged, 18 MESA tests green). **+8 tests** (`test_helium.py`, gated `requires_helium_data`):
per-mass Teff/L/τ_MS Gate-2 assertions, the observed ΔY range, §3-StellarState validity,
snap-always honesty, route shape/422, and an AST-level sibling-imports-no-PROVIDER check. 387 pytest.

**Chunk 2c** — frontend overlay. **BUILT 2026-07-09 (Playwright-verified 1440+390, zero console
errors).** A **light HR overlay, not a mode-swap** (advisor): a mass/[Fe/H]-gated `#helium-toggle`
(shown in live mode, mass 0.7–7, |[Fe/H]|≤0.25 — the solar-Z grid) fetches `/helium` and hands both
tracks to a new minimal `hr.setHeliumOverlay(baseline, enhanced, {yBase,yEnh})` (its own draw mode,
NOT a bent `setBinaryTrack`): two full Teff-coloured MESA trails, each labeled at its ZAMS, **the
MIST living track hidden** while on (the load-bearing honesty rule — the comparison is MESA-vs-MESA,
never MESA-vs-MIST). Static (no scrub marker). 3D/spectrum/comp stay on the current star (they draw
no tracks — no comparison trap; the live HR calls are guarded off by `heliumOn`). **τ_MS — invisible
on an HR diagram (no time axis, advisor catch) — is surfaced in the `#helium-note` caption** with
both lifetimes + the ratio ("τ_MS 3.03 Gyr vs. 8.32 Gyr (2.7× shorter)"). Latest-wins `/helium`
refetch on mass change; drifting out of the band (or entering any endgame/stripped view) tears the
overlay down and restores the live track (`dropHeliumForModeSwitch` at each mode-entry +
`heliumMode=false` resets in the other `hr` mode-entries). **Phase 2 (initial-helium / Y axis) is
COMPLETE.**

### Measure-first gate (Gate 2)

From the two self-run MESA tracks at matched mass/Z: confirm the enhanced-Y ZAMS is
measurably bluer/brighter than baseline, and its MS lifetime is measurably shorter — same
code, only Y differs. If the shift isn't visible at the masses tried, don't ship a control
for it (the honesty-tiering rule already governing every other axis here).

## Phase 3 — α-enhanced evolution axis, self-run MESA (the heaviest of the three)

### Physics

[α/Fe] (O, Ne, Mg, Si, S, Ca, Ti vs. Fe-peak) is a star-formation-history clock: core-collapse
SNe deliver α-elements promptly, Type Ia SNe deliver iron with a ~1 Gyr delay, so
fast-formed old populations (halo, thick disk, globular clusters, massive ellipticals) lock in
high [α/Fe] (~+0.3–0.4) while slow, extended star formation (thin disk, dwarf galaxies) pulls
[α/Fe] toward solar. O and Mg dominate the metal *mass* budget more than Fe does, so
α-enhancement at fixed [Fe/H] effectively raises true Z — increasing envelope opacity and
shifting the track **cooler/redder** at fixed mass (the opposite sign from the He effect).
This is the standard reason isochrone libraries (BaSTI, Dartmouth, PARSEC) ship dedicated
α-enhanced grids: fitting an α-enhanced population with solar-scaled tracks biases derived
ages. The spectral α-axis (Coelho) is already shipped; this phase closes the gap by letting
the *evolutionary track itself* respond to [α/Fe], not just the emergent spectrum.

### Architecture

- Same what-if-overlay pattern as Phase 2, **reusing its plumbing** (parser, bake discipline,
  overlay UI) — this is also why Phase 2 comes first even independent of the requested order.
- **Heavier setup than Phase 2** (flagged explicitly, not a repeat of Phase 2's recipe):
  α-enhancement isn't a single knob like `initial_y` — it needs an **α-enhanced opacity table**
  (OPAL/OP at the target [α/Fe]) plus a **custom abundance mixture** (`zfracs`/isotope
  fractions boosting O/Ne/Mg/Si/S/Ca/Ti relative to Fe), both of which MESA supports but which
  require real inlist/table setup, not a flag flip. Budget real time here.
- Same baseline-vs-enhanced comparison discipline as Phase 2: identical mass/[Fe/H], only
  [α/Fe] differs.

### Chunked build

**Chunk 3a** — MESA batch (baseline solar-scaled vs. α-enhanced [α/Fe]≈+0.4, same
mass/[Fe/H] pairs as Phase 2 where practical, for a consistent before/after story) + bake.

**Chunk 3b** — backend sibling extension, reusing Phase 2's plumbing where the schema allows.

**Chunk 3c** — frontend overlay, explicitly paired in caption with the existing spectrum-only
Coelho α-toggle ("this is the same [α/Fe] axis, now also moving the track").

### Measure-first gate (Gate 3, stricter than Gate 2)

Confirm the α-enhanced track is measurably cooler/redder at fixed mass/[Fe/H] — a smaller
opacity-driven shift than the He effect, so this gate has less margin: if it isn't visible at
any mass tried, this phase gets flagged as a labeled non-feature, not silently shipped with a
control nobody can see working.

## Honesty tiering (the project rule, applied)

- **Tier 1/2 (real, measured):** Phase 1's stellar physics (L/Teff/R/composition from real
  POSYDON tracks, the X-ray-binary mass-transfer rate); Phases 2 & 3's baseline-vs-enhanced
  comparison (real self-run MESA, matched-everything-but-one-variable).
- **Schematic/evocative (caption-owned):** Phase 1's compact-object marker + any
  accretion-luminosity cue (a standard formula on served Ṁ, not a measured spectrum); Phase
  1's CE energetics (a prescription, not hydrodynamics); any illustrative kick/inspiral easing.
- **Never:** comparing a self-run enhanced MESA track against the live MIST spine as if the
  difference were purely the physical effect under test — that's the trap this plan is
  designed against.

## Sequencing & dependencies

Strictly sequential per the request, but Phase 3 depends on Phase 2's plumbing (parser reuse,
bake pattern, overlay UI), so 2-before-3 is the efficient order as well as the requested one.
Each phase is independently shippable and revertible — Phase 1 doesn't block 2/3 or vice versa.

## What's needed from you, phase by phase

- **Phase 1:** no download, no compute — review/approval at the entry-point (navigation)
  design decision (Chunk 1a).
- **Phase 2:** run a Docker MESA batch (a handful of masses × 2 compositions) once inlists are
  handed over; review at the measure-first gate before the overlay UI gets built.
- **Phase 3:** same shape as Phase 2, larger inlist/opacity-table setup on my side; review at
  the measure-first gate given the effect is subtler and the gate is stricter.

## Open questions (settle as they come up, the project's established pattern)

1. Phase 1: does the CO-grid schema differ enough from HMS-HMS to need a genuinely separate
   parser, or does it drop into `bake_posydon.py` with a branch? Schema-first, not assumed.
2. Phase 1: chain-from-SN vs. standalone demo entry — advisor consult at chunk time.
3. Phases 2/3: confirm the mass set (recommend reusing MESAProvider's existing 1/2/6 M☉ solar
   set) before running the first Docker batch.
4. Phase 3: exact [α/Fe] target and opacity-table source (OPAL vs. OP) — settle once the MESA
   α-enhanced setup is being configured.

## References

POSYDON: Fragos et al. 2023 (ApJS 264, 45); Andrews et al. 2024 (POSYDON v2). Data: Zenodo
10.5281/zenodo.15194708 (DR2, CC-BY). Multiple populations: Gratton, Bragaglia & Carretta 2012
(ARAA 50, 50); Bastian & Lardo 2018 (ARAA 56, 83). ω Centauri split MS: Bedin et al. 2004.
Chemical evolution / [α/Fe] clock: Tinsley 1979; Matteucci 2012 (review). NS/BH X-ray binary
accretion: Cyg X-1 (Webster & Murdin 1972); standard accretion luminosity L=η·Ṁ·c². See also
`stripped-consort-unveiling.md` and `entwined-consort-inspiral.md` (the parent binarity arc),
`whirling-cohort-atlas.md` (Tier D, where these three items were first recorded as real-but-
uncosted directions).
