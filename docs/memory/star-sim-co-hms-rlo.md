---
name: star-sim-co-hms-rlo
description: POSYDON CO-HMS_RLO compact-object binary sibling (posydon_co.py + /co_binary_track) — Phase 1 Chunks 1a/1b/1c (CO-HMS_RLO) + Chunks 2a/2b/2c (CO-HeMS/CO-HeMS_RLO, the double-compact-object/GW-merger channel) of the CE/compact-object-tail plan, ALL BUILT — PHASE 1 COMPLETE. Chunk 2c = the full 8-bucket [Fe/H] axis for both He grids (data + tests only, NO runtime-logic or frontend code change — the routes were already snap-always + the picker already reads available_feh; mirrors 1c/4d). The mandatory Eddington re-derivation across all 8 He buckets: ≤3.65× (co-hems-rlo at feh=−4.0; co-hems uniform 3.47×), and the He grids are genuinely CLEANER than CO-HMS_RLO (ZERO ungated rows >5× anywhere — no unstable_MT artifact, unlike CO-HMS_RLO's 505,221×). +6 gated tests (available_feh honesty; axis-is-real via the EVOLVED-track fingerprint since POSYDON reuses the same initial grid per Z — co-hems final He-star mass falls 16.46→8.42 M☉ from Z-winds; DCO honest degradation at low Z). 379 pytest. A compact object (NS/BH/WD) orbiting a still-H-rich star (CO-HMS_RLO) or a bare He star (CO-HeMS/CO-HeMS_RLO, the GW-merger progenitor). posydon_co.py is parameterized by a `kind` arg (VALID_KINDS) over per-kind baked dirs; Chunk 2a added the DCO classifier (dco_classification: predicted S1 remnant + known S2 → BH+BH/NS+BH/NS+NS or honest no-DCO); Chunk 2b = a `kind` selector in the existing .co-binary-view (Option A), He-surface comp per step, DCO-endpoint caption (data.dco.label verbatim). The accretion-luminosity cue (η·Ṁ·c²) is gated THREE ways (not-detached AND not-unstable_MT AND not-WD). Optional SN-scalar load = no BAKE_VERSION_CO bump. The CO-HeMS index-identity check was loosened (5e-2) — the strict 1e-3 was dropping ~20% of good He-star tracks to benign wind drift. Next = Phase 2 (initial-He/Y axis).
metadata:
  type: project
  originSessionId: 1cedfc45-b5c5-40d2-976c-236b41653d9c
---

Phase 1 of `docs/plans/tempered-lineage-inspiral.md` (a 3-phase plan: this CE/compact-object
tail, then initial-helium, then α-enhanced evolution — see [[star-sim-rotation-subpop-atlas]]'s
Tier-D items). Chunk 1a (schema recon + bake + runtime sibling + route + tests, the backend
vertical) is BUILT 2026-07-08. See [[star-sim-binary-stripped]] for how this fits the broader
binary arc.

**Schema recon (measured against the real extracted solar `CO-HMS_RLO` HDF5, 9069 runs) —
the decisive finding that settled the Chunk-1a architecture question:**
- `history2` (the compact-object side's stellar-structure history) is **absent in every
  sampled run, unconditionally** — not a stub, not NaN-filled, the HDF5 key genuinely doesn't
  exist. Confirmed grid-wide (not just sampled): `has_h2 == 0` across all 9069 runs. `S1` is
  always the normal star (real `history1`, evolutionary state labels like
  `H-rich_Shell_H_burning`/`stripped_He_...`); `S2` is always the compact object
  (`final_values.S2_state` in `{"BH", "NS", "WD", "None"}` — never variable, never the other
  way around).
- This means `bake_posydon.py`'s existing gate (`{binary_history,history1,history2} ⊆
  run.keys()`) would drop **100%** of runs on this grid — not a drop-in extension. The real
  decision, framed by layer: bake INPUT reading is ~80% reusable (track metadata, `_decimate`,
  RLOF-keep, index-identity check), but the OUTPUT schema is genuinely new (one star + a
  companion mass-timeseries + type label, not two stars). Went with a **CO-aware branch in
  `bake_posydon.py`** (shares helpers) writing to a **separate baked dir**
  (`data/posydon/baked_co/`) + a **new `/co_binary_track` route** (not `/binary_track` reused)
  — forced by `posydon.py`'s runtime doing `BAKED_DIR.glob("*.npz")` and treating every file as
  HMS-HMS; a CO npz dropped in the same dir would be silently misread as a two-normal-star track.
- No `eccentricity` column here either — same circularization-at-RLO-onset story as HMS-HMS
  (measured, not the "post-SN kicks might leave real ecc" speculation floated during design —
  that turned out false). `ecc=0.0` stays a documented sentinel.
- The compact object's mass is a REAL per-row column (`binary_history.star_2_mass`) that
  GROWS via accretion — measured on one `stable_MT` run: 4.19→4.99 M☉ over the track. A real,
  distinguishable accretion phase, not a placeholder — this is the Gate-1 payoff.
- `binary_history.lg_mstar_dot_2` is the CO's own accretion rate (more direct than the donor-
  side `lg_mtransfer_rate`, which is pre-`xfer_fraction` loss) — feeds the accretion-luminosity
  cue.
- `rl_relative_overflow_2` is always ≤0 on this grid (the point-mass CO can't itself overflow a
  Roche lobe) — `mt_state` here is effectively only `"detached"`/`"RLOF1"`, never
  `"RLOF2"`/`"contact"`.
- CO masses are physically sane per type: NS 1.00–2.45 M☉, BH 1.20–307 M☉ (median 30). **WD is
  suspicious**: all 145 sampled WD-companion runs show exactly `1.00` M☉ — looks like an
  unimplemented/placeholder channel in POSYDON's own model, not real data; flagged, not fixed
  (nothing to fix on this side — it's the source grid's own gap).

**Extraction gotcha (bit once, now documented):** the CO grid lives in the SAME per-metallicity
tarball at internal path `POSYDON_data/CO-HMS_RLO/<Z-label>.h5` (`--wildcards
--strip-components=2`), but **`-C <destdir>` must come BEFORE the wildcard pattern** in the tar
invocation — putting it after silently extracts into the current working directory instead (the
first extraction attempt landed a duplicate `1e+00_Zsun.h5` in `data/Posydon/` itself, caught
by checking file presence/size, NOT by mtime — `tar` restores each file's original archive mtime,
so an `mtime`/`find -newer` check is blind to a just-completed extraction). Extract to a
**separate** directory (`data/posydon/CO-HMS_RLO_<Z-label>/`), never into the HMS-HMS grid's own
dir — `bake_posydon.py main()`'s `glob("*.h5")[0]` would silently grab whichever sorts first.

**Architecture built:**
- `bake_posydon.py` gained `bake_co()` + `BAKE_VERSION_CO=1` + a `--grid-type {hms-hms,co-hms-rlo}`
  CLI flag (default `hms-hms`, byte-unchanged). Reuses `_decimate`/the RLOF-keep/index-identity
  check; drops the `history2` read entirely; new `_CO_BINARY_COLS` (adds `lg_mstar_dot_2` to the
  usual binary-history set). Output axes are `(M_star_init, M_co_init, P_init)` — a compact
  object's mass is a real physical value, not a mass ratio, so no `q` column.
- **`posydon.py`'s per-row helpers were promoted from private to public** (`_state_from_row` →
  `state_from_row`, `_phase_label` → `phase_label`, `_logg` → `logg_from_mass_radius`,
  `_mt_state` → `mt_state_label`) so the new sibling could reuse them without duplicating logic
  — mirrors the project's existing sibling-calls-sibling pattern (`structure.py` →
  `lane_emden.solve_lane_emden`). Zero behavior change (verified: full pre-existing
  `test_posydon.py` suite green before and after the rename).
- **New sibling `star_sim/posydon_co.py`**: `CoBinaryStep`/`CoBinaryTrack` dataclasses (one real
  `StellarState` per step, not two — plus `co_mass_msun`/`co_type`/`mdot_msun_yr`/
  `accretion_lum_lsun` routing scalars), `_BakedCoGrid`, snap-only lookup in **(log M_star, log
  M_co_init, log P)** space (§6 — the axis swap from `posydon.py`'s (M1, q, P), since CO mass is
  its own physical axis here). `co_binary_track()`/`co_binary_track_meta()`/
  `co_binary_track_payload()` mirror `posydon.py`'s shapes.
- **The accretion-luminosity cue** (`accretion_lum_lsun`): standard `L = eta * Mdot * c^2`,
  `ACCRETION_EFFICIENCY = 0.1` (a round literature number for a NS/BH accretor, not fit to this
  grid) applied to the CO's own served `lg_mstar_dot_2`. Explicitly schematic/labeled — same
  honesty tier as the corona/wind shaders elsewhere in this project.
- **New API routes** `/co_binary_track` + `/co_binary_track_meta`, bypassing `PROVIDER` exactly
  like `/binary_track` (a compact-object-companion result can't fit the single-star interface
  either). 422 on structurally invalid input, 503 on missing bake.
- **New tests** `test_posydon_co.py` (18) + `requires_posydon_co_data` conftest marker, mirroring
  `test_posydon.py`'s discipline: snap honesty (exact-node round-trip over a 300-sample check per
  bucket), no duplicate nodes / no non-finite values across the whole baked grid, per-step
  `StellarState` validity, the Gate-1 regression (CO mass genuinely grows; RLOF fires then
  detaches; the donor ends heavily stripped and hot), route shape + 422s.

**A characterization catch worth remembering (advisor-flagged, real):** an early ad-hoc bulk
check of the accretion-luminosity cue across the WHOLE grid hit `RuntimeWarning: overflow` and
returned `inf`/`nan` — looked at first like the cue could reach absurd (10⁹×-Eddington)
magnitudes. Root cause: iterating the baked npz's raw **float32** row arrays directly, then
Python's `10.0 ** float32_scalar` under NEP 50's weak-scalar-promotion rules stays float32,
and `mdot_g_s * c^2` (~10²¹ × ~10²¹) overflows float32's ~3.4×10³⁸ ceiling — a numpy dtype
artifact, NOT a physics finding. The *production* code path (`co_binary_track()`) was always
safe because it explicitly casts each value to Python `float` (float64) per row before doing
math. Re-characterizing with the same float64-cast discipline gave the real, sane distribution:
median ~2.4×10⁶ L☉ (~2.5× the CO's own Eddington luminosity), p99 ~2.7×10⁷ L☉ (~3.4×
Eddington), max ~3.5×10⁷ L☉ (~3.46×) — zero rows above 10× Eddington, across the WHOLE grid.
This is the known mildly-super-Eddington regime real ULX/X-ray-binary literature describes, not
an unbounded number — no cap was needed. Pinned as a permanent regression test
(`test_accretion_luminosity_stays_within_a_few_eddington_across_the_grid`) so a future bake/
column change can't silently reintroduce an unphysical value unnoticed. **Lesson for next time:**
when bulk-characterizing a baked `.npz`'s raw arrays for a sanity check, cast to float64 first
(mirror however the production code casts) — a naive vectorized pass over float32 columns can
produce a false alarm that looks like a real physics finding.

**A second, subtler advisor catch on the SAME cue — the bound is conditional, not intrinsic.**
The "2-3.5× Eddington, no cap needed" characterization above only covers rows where `mt_state
!= "detached"` (i.e. `rl_relative_overflow_1 > 0` — real Roche-lobe overflow). Over ALL rows,
including detached ones, `lg_mstar_dot_2` reaches values (max 2.40, i.e. ~251 M☉/yr) that push
the SAME formula to ~10¹⁴ L☉ — a numerical/model artifact of a non-transferring row, not
physics. The bound holds **because** `co_binary_track`'s `active` gate excludes those rows, not
because `_accretion_luminosity` is intrinsically bounded — and the regression test uses the
SAME gate, so it can't catch a future change that widens the gate and re-admits the artifact
tail. Consequence: **the cue is scoped to RLOF-phase accretion only.** Wind-fed accretion (the
plan's own motivating example, Cygnus X-1 — a BH accreting its O-star companion's stellar
wind, genuinely NOT Roche-lobe overflow) is NOT captured by this grid or this cue; a detached
CO orbiting a normal star shows no accretion cue here, even though a real wind-fed X-ray binary
would show one. If Chunk 1b (or later) ever widens the `active` gate to add wind-fed accretion,
the Eddington bound must be RE-DERIVED, not assumed to still hold — this is documented inline
at the `active` gate in `posydon_co.py` and in the regression test's docstring specifically so
it isn't silently lost.

**Chunk 1b BUILT 2026-07-08 (frontend render + one backend addition, 330 pytest [+2],
Playwright-verified 1440+390 zero console errors).** The standalone curated demo the Chunk-1a
consult settled on (NOT chained from an SN): a **sibling demo row inside stripped-mode**
(`.co-binary-demo-row`, one button "Star + black hole → X-ray binary" for the Gate-1 system
27.6 M☉ + 14.7 M☉ BH), its OWN body class `.co-binary-view` **mutually exclusive** with the
HMS-HMS `.binary-view` (each view's CSS hides the other's demo row; plus a race fix below).
The age slider becomes a system-time scrubber over the pre-fetched steps (index-linear, "scrub
is free").
- **Backend (the one addition):** `co_binary_track_payload` now folds in per-step Roche geometry
  by reusing `binary.track_roche_geometry` (sibling-calls-sibling) via a `SimpleNamespace` adapter
  — the engine duck-types on `m1_current_msun`/`m2_current_msun`/`separation_rsun`, so each
  `CoBinaryStep` maps `star_current_msun→m1` (donor/origin), `co_mass_msun→m2` (accretor at (1,0)),
  giving q=m_co/m_star. Measured: q sweeps 0.53→1.18 (star heavier → BH heavier after strip+accrete),
  the lobes swap, the star fills its lobe on every RLOF1 step. +2 tests (`test_posydon_co.py`): the
  route carries a non-null roche block per step + the Gate-1 reshape/lobe-swap regression.
- **HR (`hr.js`):** `setBinaryTrack(states, null, {s1:"star"})` — the CO is a point mass with NO
  photosphere, so it gets NO HR luminosity point (advisor); parameterized the hardcoded "donor"
  label so the star marker reads "star". Only the living star's track + one marker draw.
- **3D (`star.js`):** a new `CO_MARKER_FRAG` + `coMarker` mesh — a schematic point-mass glyph
  beside the living star via the existing two-body `applyCompanionScale` layout. BH = a persistent
  dark disc rimmed by a bright ring (deliberately NOT the SN remnant's "winks out" — this is an
  ongoing companion, advisor); NS/other = a tiny hot point + halo. `opts.coMarker` string-gated,
  byte-identical when absent.
- **Roche (`roche.js`):** a `drawLiveCo` branch — the CO side renders as the same schematic marker
  (never a Teff disc); the lobe is still drawn (the accretion target). CO-specific caption.
- **Accretion-luminosity cue** surfaced in the age-slider caption **relative to the star's own L**
  (advisor: an accreting CO can outshine its donor) — measured ~2.5× the star's L during RLOF1.
- **A real race caught + fixed (Playwright):** each view's demo button is only CSS-hidden once the
  OTHER view's class is set, which happens AFTER its `/…_track` fetch resolves — so during a slow
  in-flight fetch (the 142 MB HMS-HMS grid's first load) the other button is still clickable. Both
  `enterBinaryView`/`enterCoBinaryView` now bump the OTHER view's token UNCONDITIONALLY (not only
  when that view is already active), and `exitBinaryView` bumps `binaryToken`, so a late-resolving
  fetch can't re-open its view on top of the one you switched to.
- **A false-data leak caught by the advisor + fixed:** the STATE READOUT, the true-size SCALE strip
  and the MK class line are single-star consumers NOT wired to the per-step CO scrub — left visible
  they showed the FROZEN stripped-snapshot's numbers (a 10 M☉ subdwarf beside the animating 27.6 M☉
  system). Now CSS-hidden in `.co-binary-view` (same treatment as comp/spectrum/sed/structure); the
  3D star canvas + HR + Roche stay (they DO animate). Note: the HMS-HMS `.binary-view` has the same
  latent wart (its readout/scale also freeze) — left as-is (pre-existing, out of Chunk-1b scope).

**Chunk 1c BUILT 2026-07-08 (data + frontend + one backend correctness fix, 332 pytest [+3],
Playwright-verified 1440+390 zero console errors).** The metallicity axis + free sliders — the
CO grid's catch-up to the HMS-HMS Chunk 4c/4d rollout. **NO runtime-logic change was needed for
the axis itself** (`co_binary_track`/`co_binary_track_meta` were already snap-always over the WHOLE
baked grid, §6, and `available_feh` was already served) — exactly like HMS-HMS 4c/4d.
- **Data:** extracted + baked the 7 non-solar CO-HMS_RLO buckets → the **full 8-bucket axis**
  ([Fe/H] −4.0/−3.0/−2.0/−1.0/−0.69897/−0.34679/0.0/+0.30103, coextensive with the HMS-HMS
  axis — exact `--feh` values reused so `available_feh` aligns). All 8 grids non-empty + clean
  (7208–8329 tracks each, ~38–49 MB npz). Extraction batch = the Chunk-1a gotcha verbatim
  (`-C <destdir>` BEFORE the wildcard, separate `CO-HMS_RLO_<label>` dir, verify by SIZE;
  extracted h5 deleted after each bake to reclaim ~1 GB). Measure-first (Gate-1-at-a-new-Z):
  the SAME (20 M☉ + 8 M☉ BH, P=300 d) system → "stripped + BH companion" at solar vs "unstable
  mass transfer onto BH" at [Fe/H]=−2.0 — a real outcome change, not a relabel.
- **Frontend (`main.js`/`index.html`, mirrors 4c/4d):** a `<select id="co-binary-feh">` populated
  from the real `available_feh` (never hardcoded — the [[star-sim-hosted-data-assets]] lesson) +
  a "Custom system…" button revealing three **log-scale** sliders. **The CO custom axis is
  (M_star, M_co, P), NOT (M1, q, P)** — a compact object's mass is a real physical value (~1.2–307
  M☉), not a <1-dex ratio like the HMS-HMS q, so M_co is its own log slider. `ensureCoBinaryMeta`/
  `refetchCoBinaryTrack`/`_applyCoBinaryTrackData`/`_coBinaryParamsFor` are the CO twins of the
  HMS-HMS meta/refetch/apply/params functions. [Fe/H] applies to EITHER demo (curated or custom);
  M_star/M_co/P only drive "custom". A bucket change invalidates the cached meta + re-fetches it
  FIRST (each POSYDON metallicity is its own grid with different M_star/M_co/P spans — the exact
  4d stale-slider bug) before re-fetching the track. Pre-warmed in `enterStripped()` so the picker
  is populated + the custom system instant. The stale narration claim ("Mass and [Fe/H] are fixed
  for this demo") was corrected.
- **THE ONE REAL BUG the full-grid pytest caught (the honesty payoff of "existing tests ARE the
  gate"):** the Chunk-1a accretion-luminosity Eddington-bound regression (characterized on
  SOLAR-ONLY as 2–3.5×, "no cap needed") FAILED on the new buckets — feh=−3.0 reached 11.5×, and
  a full-grid characterization found feh=−4.0 at **505,221× Eddington** and +0.30 at 2789×. Root
  cause (measured, not assumed): **all three outlier rows are on POSYDON `interpolation_class ==
  "unstable_MT"` tracks** — dynamically-unstable mass transfer → common-envelope/merger, where the
  parametrized `lg_mstar_dot_2` spikes to runaway values (the served cue would have shown ~10^13×
  the star's own L in the caption — a caption-poisoning false-data leak the Chunk-1c [Fe/H] picker
  + custom sliders newly make REACHABLE). The cue models a STABLE X-ray-binary accretion
  luminosity, which an unstable-MT episode physically is NOT. **Fix (prefer-gate-over-cap, motivated
  by POSYDON's own instability label — not a magic-number cap):** `co_binary_track`'s `active` gate
  now ALSO requires `not is_unstable_mt` (the snapped track's `interpolation_class != "unstable_MT"`).
  With it, the cue is bounded to **≤3.46× Eddington across all 8 buckets / 2.5M rows** (median
  ~2.3–2.6×), the honest ULX regime. The Gate-1 payoff is preserved (the stable-transfer curated demo
  still surfaces 162 cues peaking at 3.3× the star's L). Two tests updated/added: the Eddington-bound
  test now mirrors the two-part gate (excludes unstable_MT, ceiling tightened 10→5×), and a NEW
  served-level regression asserts `accretion_lum_lsun is None` on an unstable_MT track through the real
  runtime. **Lesson (added to the existing float32 one):** the "2–3.5×, no cap needed" bound was a
  SOLAR-ONLY characterization; the metal-poor grids carry a class of artifact solar didn't. The bound
  holds because of the GATE (now two-part: not-detached AND not-unstable_MT), never as an intrinsic
  property of the formula — widening the gate (wind accretion, re-admitting unstable MT) re-opens an
  unbounded tail and must re-derive the bound.
- **Not built:** Phases 2 (initial-He) and 3 (α-enhanced evolution) of the parent plan. `CO-HeMS`/
  `CO-HeMS_RLO` (the double-compact-object channel) also remain deferred — a separate grid extraction.

**Chunk 1c advisor follow-up BUILT 2026-07-08 (backend-only, 335 pytest [+2], no frontend change).**
Re-ran the advisor after the overload; it confirmed the unstable_MT gate call was correct
(prefer-gate-over-cap using POSYDON's own `interpolation_class` is principled, not a magic number)
and raised two checks the self-verification hadn't reached:
- **Check 2 (the one that needed the commit) — the WD accretor.** The SAME artifact class the
  unstable_MT gate fixed was ALSO leaking through the **`co_type == "WD"`** channel: `ACCRETION_EFFICIENCY
  = 0.1` is a NS/BH *deep-potential-well* efficiency (GM/Rc²); a white dwarf's surface potential is
  ~2–3 dex shallower (η ~ 1e-3…1e-4), so η=0.1 overstates a WD accretor's accretion luminosity by
  100–1000×. Measured: **94 WD-companion tracks surfaced a non-None cue up to ~55,000 L☉** through the
  real runtime — and the frontend caption (`refreshCoBinary`, main.js ~3094) paints `accretion_lum_lsun`
  UNCONDITIONALLY whenever non-null (the WD caveat only annotated the *mass* note, not this cue). The WD
  channel is a documented placeholder anyway (every WD node frozen at exactly 1.0 M☉), so the honest fix
  is to **defer the cue entirely** rather than paint a 3-dex-wrong number. Gated it: `co_binary_track`'s
  `active` mask now also needs `not is_wd` (`co_type != "WD"`), making the gate **three-part** (not-detached
  AND not-unstable_MT AND not-WD). Backend-only — the served field goes `None`, so the frontend caption
  omits it naturally (no main.js change). +1 served-level regression `test_accretion_cue_is_none_on_wd_companion_tracks`.
- **Check 1 (tighten, didn't block) — the bound test recomputed instead of reading the served cue.**
  `test_accretion_luminosity_stays_within_a_few_eddington_across_the_grid` computed Eddington from the raw
  `lg_mstar_dot_2` columns and re-applied its OWN parallel gate mask — so the test-gate and the production
  gate could silently diverge (a string-compare mismatch / off-by-one / WD-vs-NS branch bug would pass both).
  Closed with a NEW `test_served_accretion_cue_is_bounded_and_only_in_regime` that asserts the ≤5× bound on
  `co_binary_track`'s OWN served `accretion_lum_lsun` (sampled over the cue-BEARING population — stable NS/BH
  tracks — seeded per bucket, so the bound branch is genuinely exercised on served output; every non-None
  served cue must be ≤5× Edd AND belong to an NS/BH-stable track the gate should admit). The exhaustive
  grid-wide bound test was ALSO updated to mirror the now-three-part gate (its parallel mask now excludes WD
  too) + its docstring bumped to "ALL THREE conditions", so it stays a faithful mirror. Measured after the
  fix: 0 WD tracks serve a cue; the grid-wide served bound is exactly **3.46× Eddington** (unchanged — the
  WD tracks were bounded in ratio anyway at ~1.68×, but wrong-regime by 2–3 dex in absolute L, which the
  ratio alone hid).
- **Lesson (third on this cue, after float32 and solar-only-unstable_MT):** a bounded Eddington *ratio* does
  NOT imply a valid cue — a WD's ratio looked tame (1.68×) only because its mass is the placeholder-frozen
  1.0 M☉; the absolute luminosity was still 2–3 dex too bright because η was the wrong regime. Check the
  *regime* (which η, which accretor type), not just the ratio. And: assert bounds on the SERVED value, not a
  reimplementation of the gate, or the two drift.

**Chunk 2a BUILT 2026-07-08 (CO-HeMS / CO-HeMS_RLO backend, solar, +38 tests → 373 pytest; no
frontend).** The double-compact-object channel — the He-star twins of CO-HMS_RLO. The stage AFTER
CO-HMS_RLO: the surviving secondary has ALSO been stripped to a bare He star orbiting the compact
object — the direct progenitor of a BH-BH / NS-BH / NS-NS gravitational-wave-merger binary
(LIGO/Virgo source).
- **Schema recon (measured against both real extracted solar HDF5s) confirmed a clean drop-in
  twin of CO-HMS_RLO:** `history2` absent in every sampled run; every `_HISTORY_COLS`/`_CO_BINARY_COLS`
  column present → `bake_co()` + `state_from_row()` drop in unchanged. S1 is a bare He star
  (`stripped_He_*` states; measured surface X_surf≈0, He4≈0.986 for less-evolved, or C/O-dominated
  WC/WO-like for evolved massive ones — the defining trait is H-DEPLETION, not He-dominance, which the
  test asserts). CO-HeMS = 14256 runs `no_MT`-dominated (the detached inspiral — DCO payoff home);
  CO-HeMS_RLO = 5319 runs `stable_MT`+`initial_MT` (the He-donor Case-BB/BC accretion payoff). Both
  BH-companion-dominated.
- **Parameterize-don't-fork (advisor-confirmed):** `posydon_co.py` gained a `kind` arg
  (`VALID_KINDS = co-hms-rlo | co-hems | co-hems-rlo`, `DEFAULT_KIND="co-hms-rlo"` so the live surface
  is behavior-compatible — the default payload only GAINS additive `kind`/`dco` keys, `dco` None there)
  selecting one of three per-kind baked dirs (`baked_co`/`baked_co_hems`/
  `baked_co_hems_rlo`). `co_binary_track`/`_meta`/`_payload` all take `kind`; `_resolve_kind` validates
  against the explicit set (never string-slice — the one-letter **co-hms-rlo vs co-hems-rlo** hazard;
  the API maps its ValueError → 422; a regression test asserts the two kinds resolve to distinct grids).
- **`bake_posydon.py`** gained `--grid-type co-hems`/`co-hems-rlo` (both through the SAME `bake_co()`),
  plus a new per-track SN-model scalar block (`SN_MODEL_DEFAULT = "S1_SN_MODEL_v2_01"` — POSYDON's own
  prediction of what S1 becomes at collapse: CO_type/SN_type/mass/f_fb/spin). Baked CO-HeMS_RLO solar
  FIRST (4997 tracks — the drop-in proof) then CO-HeMS (11100). **NO `BAKE_VERSION_CO` bump:** the SN
  arrays are ADDITIVE and read OPTIONALLY (`_load_baked` guards `"track_sn_CO_type" in npz.files`), so
  the 8 pre-existing CO-HMS_RLO npzs (baked without them, their extracted h5s deleted at Chunk 1c) still
  load — re-baking them would cost real time for nothing (advisor-confirmed).
- **The DCO classifier (`dco_classification` → `DcoClassification`, He kinds only; None for co-hms-rlo,
  gated on `kind in _HE_KINDS` NOT on scalars-present):** combines POSYDON's predicted S1 remnant with
  the KNOWN existing S2 → "BH + BH"/"NS + BH"/"NS + NS" merger progenitor, or honest **no-DCO** when
  either ends a WD or is unresolved (run demos: 16.6 M☉ → BH(5.90)+BH(5.99); a WD-remnant node →
  "no double-compact merger"). **Keys off the remnant TYPE (BH/NS/WD/None), not `sn_type`** — so a
  low-Z pair-instability SN (massless remnant → CO_type None) falls through to the honest unresolved
  branch for free when Chunk 2c reaches the metal-poor buckets. **No kick model, no merger TIME** (that
  needs the post-second-SN orbit — a natal-kick prescription this grid doesn't serve, two prescriptions
  deep; deliberately deferred, honesty-tier note in the docstring). Prescription labeled BY INDEX
  (`v2_01` of 24; caption-owned — the boron-b8 discipline, since index→mechanism isn't verifiable from
  the grid file). **S2's DCO mass = the FINAL-row (post-accretion) mass, not `m_co_init`** (advisor).
- **The Eddington bound was RE-DERIVED, NOT inherited (the explicit task requirement):** He-star
  Case-BB/BC transfer could differ from an H donor, so 3.46× was not assumed. Measured across BOTH He
  SOLAR grids under the same three-part `active` gate → max **3.47×** Eddington (the same physical ULX
  ceiling — POSYDON caps stable transfer). **SOLAR-SCOPED** in the docstring + test: the metal-poor He
  buckets carry the same `unstable_MT` artifact class CO-HMS_RLO's did (Chunk 1c: solar clean,
  metal-poor 505,221×), so Chunk 2c MUST re-derive across all 8 He buckets — don't re-ship the 1a→1c
  mistake. (Even ungated the solar He max was 3.47×, i.e. the gate doesn't bite at solar — but it's
  load-bearing at other Z and independently correct for the WD-regime η argument.)
- **Advisor trap #1 (positive presence, not tolerance):** the optional SN-scalar load degrades
  SILENTLY (a missing scalar → `dco=None`, no error), so the DCO regression asserts `dco is not None`
  + the correct label on a known BH+BH node, not just tolerance.
- **The CO-HeMS index-identity tolerance (`_CO_INDEX_IDENTITY_RTOL = 5e-2`, advisor-flagged pre-2c):**
  the strict 1e-3 check (fine for near-ZAMS HMS-HMS) was dropping ~20% of CO-HeMS runs (2798, all
  index-identity, 0 length-mismatch) — measured as BENIGN He-star WIND drift: the point-mass CO's
  `star_2_mass` matches EXACTLY, only the bare He star's `star_1_mass` drifts ≤0.24% and the orbit
  widens ≤1.1% between the `initial_values` grid point and the first saved row. Concentrated in `no_MT`
  (the DCO-payoff home). Loosened to 5e-2 (still far below the ≥40%-in-M1 inter-node spacing, so a real
  misindex is caught; star_2 kept at strict 1e-3). CO-HeMS re-bake: 11100 → 13898 tracks. CO-HeMS_RLO
  unaffected (0 drops either way — its RLOF He stars don't drift as far). Lesson: an unexplained
  high drop rate is the measure-first anomaly to understand, not wave past.
- **Tests:** `test_posydon_co_he.py` (38, gated `requires_posydon_co_he_data` — both He grids baked)
  + `requires_posydon_co_he_multifeh` (for 2c). 4 pure `dco_classification` unit tests are UNGATED
  (no data). [[star-sim-supernova-remnant-endgame]] for the NS/BH remnant vocabulary the DCO
  classifier reuses.

**Chunk 2b BUILT 2026-07-09 (frontend render — CO-HeMS / CO-HeMS_RLO; frontend-only, NO backend
change, 373 pytest unchanged, Playwright-verified 1440+390 zero console errors).** The He-star
double-compact-object channel gets its UI. Navigation was the one open design call
(plan flagged it): **advisor-endorsed Option A — a grid-`kind` `<select>` inside the EXISTING
`.co-binary-view`, NOT a parallel `.co-he-binary-view`** — mirrors the backend's
parameterize-don't-fork (`kind` param on the same routes), so every consumer (HR-star-only, the
schematic CO glyph, the accretion cue, the live Roche panel) is byte-identical across kinds.
- **The `kind` axis (orthogonal to `[Fe/H]`):** a `coKind` state var (default `co-hms-rlo`,
  byte-compatible) threaded into BOTH the `/co_binary_track` AND `/co_binary_track_meta` fetch URLs
  as `&kind=`. The three options carry PHYSICAL labels (Compact object + H-rich star / + He star
  inspiral→merger / + He star mass transfer), not the POSYDON grid jargon (advisor). The meta cache
  now keys on **`(kind, feh)`** not feh alone (`ensureCoBinaryMeta` + new `coBinaryMetaKind`/
  `coBinaryMetaPromiseKind`) — each kind is its OWN grid with its own M_star/M_co/P spans, so
  switching kind at unchanged feh must re-fetch bounds (the 4d stale-slider bug class). A kind change
  is a fresh grid: reset the custom triple to that kind's curated demo, invalidate meta, re-fetch
  meta THEN track, and swap the demo-button label + demo-row `?` tooltip via `applyCoKindUi()`.
- **The three BLOCKERS the advisor flagged, all closed:** (1) the narration + tooltip were hardcoded
  H-rich ("hydrogen-rich companion") — a false-caption class → a He-kind narration block
  `endgame-narrate-co-hems` gated on a `co-he-kind` body class + per-kind tooltip text in
  `CO_KIND_UI`; (2) the curated demo triples are the EXACT Chunk-2a-verified nodes pulled from
  `test_posydon_co_he.py` (`CO_BINARY_DEMOS` map: CO-HeMS 16.559711/5.990075/0.561443 → BH+BH DCO;
  CO-HeMS_RLO 1.422924/10.248538/0.045189 → He-donor XRB, cue fires ≈205–610× the star's own L) —
  NEVER guessed (a guess can snap to a WD/`unstable_MT` node where the payoff is gated off → a dead
  demo); (3) the meta cache key (above).
- **The DCO-endpoint caption** (`#co-binary-dco-note`, He kinds only) prints the classifier's OWN
  served one-liner **verbatim** (`data.dco.label` — advisor: can't drift from the backend), + a
  friendly gloss of the index-labeled prescription (`S1_SN_MODEL_v2_01` → "core-collapse prescription
  v2_01"): "Endpoint: BH + BH merger progenitor (…)." / "no double-compact merger — the He star
  ends as a white dwarf."
- **He-surface comp** — the panel (CSS-hidden on the H-rich kind via `.co-binary-view .comp-panel`)
  comes back on for He kinds (`body.co-binary-view.co-he-kind .comp-panel`, higher specificity)
  driven per scrub-step by `comp.setStripped(s, {source:"posydon"})`. **comp ALONE** (spectrum/sed/
  structure stay hidden — out of 2b scope, advisor). The `co-he-kind` body class is set off the
  SERVED `data.kind` in `_applyCoBinaryTrackData` (authoritative, can't desync from the shown track).
- **The advisor-caught false caption I'd WRONGLY hand-waved (the load-bearing fix):** the flagship
  CO-HeMS BH+BH demo scrubs from He 99% (step 0) → **Z≈72% carbon/oxygen** (step 19, a WC/WO
  surface); the reused `drawStripped`'s `heRich = Y>X` was still true there, so it falsely printed
  "helium-rich surface" + "the bared core is helium" over a 72%-Z bar — the SAME false-caption class
  the narration blocker existed to kill, just in a different panel. I'd dismissed it as "minor
  cosmetic"; the advisor (who saw the transcript) was right that it wasn't. Fixed `drawStripped` with
  a three-way **`surfKind = Z>Y ? "co" : Y>X ? "he" : "h"`** (the `co` branch → "carbon/oxygen-rich
  surface" + "The helium has burned to carbon & oxygen — a Wolf–Rayet (WC/WO) surface") AND a
  **`source`-aware caption**: the Götberg "(Götberg 2018) … one representative state (halfway through
  core-helium burning)" attribution is FALSE on a time-varying POSYDON track, so `strippedCaption`
  now takes a `source` ("gotberg"|"posydon") — the posydon caption says "The MEASURED surface
  abundances from the POSYDON binary track … a real evolving step (scrub the time slider to watch it
  change)." **The single-star Götberg stripped snapshot path is byte-unchanged** (`setStripped(state,
  opts={})`, source defaults to "gotberg"; Götberg `Z_surf≈0.014` never trips the `co` branch — the
  he/h branches are identical to before). **Lesson (mine, not the code's): when a plan says "reuse
  view X for a new regime," look at the NEW regime's states through X before declaring it a drop-in —
  the He-dominant recon example didn't stress-test the C/O-dominant late scrub.**
- **Not built:** Chunk 2c (full 8-bucket [Fe/H] axis for both He grids — currently solar-only;
  re-derive the Eddington bound across all 8 He buckets, the exact step that caught the 505,221×
  `unstable_MT` artifact for CO-HMS_RLO in Chunk 1c). Phases 2 (initial-He) & 3 (α-enhanced). **Next
  = Chunk 2c.** [[star-sim-supernova-remnant-endgame]] for the NS/BH remnant vocabulary the DCO
  classifier reuses; [[star-sim-binary-stripped]] for the `comp.setStripped` He-surface view 2b reuses.

**Chunk 2c BUILT 2026-07-09 (data + tests only — NO runtime-logic or frontend code change; 379
pytest [+6], Playwright 1440+390 zero console errors). PHASE 1 IS NOW COMPLETE.** The full
8-bucket [Fe/H] axis for BOTH He grids — the He twin of Chunk 1c, and just as clean a drop-in.
- **Data:** extracted + baked the 7 non-solar buckets for CO-HeMS AND CO-HeMS_RLO → the full
  8-bucket axis ([Fe/H] −4.0/−3.0/−2.0/−1.0/−0.69897/−0.34679/0.0/+0.30103, coextensive with
  CO-HMS_RLO and HMS-HMS; the exact `--feh` values reused so `available_feh` aligns). One tar scan
  per bucket extracting BOTH He grids together (they share the tarball at `*/CO-HeMS/*.h5` and
  `*/CO-HeMS_RLO/*.h5` — the `-C` before the wildcard gotcha; `'*/CO-HeMS/*.h5'` cannot match
  CO-HeMS_RLO, no `/CO-HeMS/` substring), bake both, delete the h5 to reclaim disk. All clean
  (only expected `not_converged`/`missing-history` drops; CO-HeMS ~13.9k tracks/bucket, CO-HeMS_RLO
  ~4.7k). npzs gitignored (GitHub-Release-hosted later, [[star-sim-hosted-data-assets]]).
- **NO runtime-logic change (mirrors 1c/4d):** `co_binary_track`/`_meta` were already snap-always
  over the whole per-kind baked grid and served `available_feh`; the frontend `#co-binary-feh`
  picker (Chunk 1c) already populates from the real `available_feh` with the meta cache keyed on
  `(kind, feh)` (Chunk 2b). So the He kinds picked up all 8 buckets with ZERO code edit — verified
  end-to-end via Playwright: both `co-hems` and `co-hems-rlo` pickers now list 8 buckets (were
  solar-only), a bucket switch re-fetches meta+track, the DCO-endpoint caption re-computes, zero
  console errors at 1440 + 390.
- **The MANDATORY Eddington re-derivation across all 8 He buckets** (ungated, float64-cast, full
  grid over both He grids — the exact step that caught the 505,221× `unstable_MT` artifact in
  CO-HMS_RLO Chunk 1c; NOT skipped): the accretion cue holds at **≤3.65× the CO's own Eddington**
  (co-hems-rlo at the metal-poor floor feh=−4.0; co-hems uniform 3.47× at every bucket) — the
  metal-poor buckets edge the solar 3.47× up only slightly, well under the test's 5.0 ceiling.
  **Key measured finding: the He grids are genuinely CLEANER than CO-HMS_RLO** — the ungated pass
  finds ZERO rows above 5× ANYWHERE (no `unstable_MT`/WD artifact in the magnitude window),
  `BIG_ADMITTED=0` at every bucket → no new artifact class. So unlike CO-HMS_RLO (whose metal-poor
  grids hit 505,221×), the He grids never had the artifact — but the re-derivation was mandatory
  precisely because that couldn't be assumed. (Characterization script:
  `M:\claud_projects\temp\chunk2c\eddington_rederive.py`.)
- **Tests (+6, gated `requires_posydon_co_he_multifeh` = ≥2 buckets baked per He grid; parametrized
  ×2 He kinds):** (1) `available_feh` reflects the real baked bucket set per kind; (2) the axis is
  real — the SAME (M_star, M_co, P) request resolves to a genuinely different EVOLUTIONARY TRACK
  across buckets. **A test-design correction (mine, caught on first run):** POSYDON reuses the SAME
  initial (M_star, M_co, P) grid at every Z, so an exact-node demo (co-hems 16.56+5.99, P=0.56 d)
  snaps to the identical INITIAL coordinates at all 8 buckets — the CO-HMS_RLO analogue happened to
  use a request that snapped to different nodes, but the physically robust signal is the *evolved*
  track, not the initial node. Fingerprint = (node, nstep, final donor & CO mass); measured the
  co-hems final He-star mass falls MONOTONICALLY 16.46→8.42 M☉ across the axis (metal-poor weak
  winds → metal-rich strong winds — real Z-dependent wind physics, not a decimation quirk). (3) the
  DCO classifier degrades HONESTLY (no nan leak, no crash, non-empty label) over a whole metal-poor
  grid. The existing `test_accretion_cue_within_a_few_eddington_across_he_grids` AUTO-covers all 8
  buckets (it loops `_available_grids(kind)`); its docstring was updated from "3.47× solar-scoped"
  to the re-derived all-8-bucket ≤3.65× number + the "He grids cleaner than CO-HMS_RLO" finding.
- **The recurring wrong-bucket-test hazard ([[star-sim-hosted-data-assets]]) was checked and does
  NOT bite here:** every Chunk-2a He test iterates `for grid in _available_grids(kind)` and fetches
  with `grid.feh` — none assume a single/solar grid (`_available_grids(kind)[0]` or hardcoded
  `feh=0`), so opening the axis to 8 buckets can't silently run an assertion against the wrong
  metallicity. The He test file was bucket-safe from the start.
- **Not built:** Phases 2 (initial-He / Y axis) & 3 (α-enhanced evolution) of the parent plan —
  Phase 2 is next in the plan's sequential order.

**Prior "Not built" note (superseded by Chunk 1c above):** Chunk 1c was more metallicities + custom
sliders; both now built.

See [[star-sim-binary-stripped]] for the parent binary arc, [[star-sim-hosted-data-assets]] for
how the raw POSYDON tarballs got onto disk, [[star-sim-supernova-remnant-endgame]] for the
NS/BH-formation physics this eventually ties into (the compact object here is the SAME kind of
object that arc's remnant-branch classifier produces).
