---
name: star-sim-co-hms-rlo
description: POSYDON CO-HMS_RLO compact-object binary sibling (posydon_co.py + /co_binary_track) — Phase 1 Chunk 1a of the CE/compact-object-tail plan, BUILT. A compact object (NS/BH/WD) orbiting a still hydrogen-rich star, the stage after posydon.py's HMS-HMS episode.
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

**Not built yet:** Chunk 1b (frontend render — a real Teff-colored star + a schematic point-mass
NS/BH marker, entry/navigation still an open UX question per the plan: chain-from-SN vs.
standalone curated demo), Chunk 1c (more metallicities — currently solar-only). Phases 2
(initial-He) and 3 (α-enhanced evolution) of the parent plan haven't started.

See [[star-sim-binary-stripped]] for the parent binary arc, [[star-sim-hosted-data-assets]] for
how the raw POSYDON tarballs got onto disk, [[star-sim-supernova-remnant-endgame]] for the
NS/BH-formation physics this eventually ties into (the compact object here is the SAME kind of
object that arc's remnant-branch classifier produces).
