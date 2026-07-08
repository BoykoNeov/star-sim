# Plan: Three subpopulation axes — post-SN compact-object binaries, initial-helium, α-enhanced evolution

## Status: Phase 1 Chunk 1a BUILT (2026-07-08, backend vertical) — see below. Phases 1b/1c,
2, and 3 not yet built. Sequential order (also the efficient order):
**Phase 1** binary CE/compact-object tail → **Phase 2** initial-helium (Y) axis →
**Phase 3** α-enhanced evolution axis (reuses Phase 2's plumbing).

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

**Chunk 1c — extend to more metallicities** (drop-in, mirrors the HMS-HMS metallicity
rollout) once 1a/1b are validated on solar.

### Measure-first gate (Gate 1, mirrors Chunk 4a's Gate 0)

Before any control ships: verify through the real runtime that a CO-HMS_RLO/CO-HeMS track
shows something a plain HMS-HMS track cannot — a distinguishable X-ray-binary accretion
phase (different physical mechanism from RLOF onto a normal star), and/or a real orbital
discontinuity at the SN transition if the chained path is built.

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

**Chunk 2a** — MESA batch (needs you to run Docker MESA; exact inlist diffs handed over when
ready) + bake (baseline+enhanced pairs, column-trimmed/decimated/float32/gzip).

**Chunk 2b** — backend sibling + route serving both tracks for a requested mass.

**Chunk 2c** — frontend overlay toggle: a paired-track HR overlay (Teff-colored,
baseline/He-enhanced labeled), a Y readout on the composition panel.

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
