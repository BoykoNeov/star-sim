---
name: star-sim-rotation-subpop-atlas
description: "Star Sim — rotation axis + subpopulation controls; gate SETTLED (rotation mass-ramped at ~1.2 Msun), Chunks 1-3 BUILT (provider keying, honesty gate, frontend unified control + API + real v_rot_kms), only Chunk 4 (fetch remaining rotating feh) remains. User said \"nothing is out of scope.\""
metadata: 
  node_type: memory
  type: project
  originSessionId: d6e84098-c905-486b-85f4-edc0b6e21d37
---

**DISCUSSION CAPTURED, nothing built.** Plan doc:
`docs/plans/whirling-cohort-atlas.md`. Prompted by the user noticing that for
Wolf–Rayet stars rotation+age affects far more than the X-ray emission
(`magnetic-ember-broadcast.md` SED Chunk 3 rotation slider), and asking what
other sliders would reveal different subpopulations. **User directive: "nothing
is out of scope"** — so the old spec §2/§9 walls (no binary engine, no live
solver) are now recorded as candidate directions *with a cost*, not forbidden.
Honesty tiering stays (tier by what data backs it, not by what we wish it showed).

**BUILD GATE SETTLED this session (the headline result):** MIST v2.5 **ramps
rotation in by mass.** Diffed same-mass `vvcrit0.0` vs `vvcrit0.4` tracks at solar
[Fe/H]: **bit-identical at ≤1.20 M☉** (max|Δ|=0 across log Teff/L, age, surface
N/He/C, every EEP), **diverges at ≥1.25 M☉** — the turn-on is the **~1.2 M☉ Kraft
break** (convective→radiative envelope; magnetic braking shuts off → a fixed spin
becomes physical). So the rotation control **does nothing at the Sun**; it's a
massive-star/WR feature. Payoff confirmed where it bites: 20 M☉ **MS surface N¹⁴ up
~5×** (0.0008→0.0044) + MS He enrichment (Hunter signature). ⇒ build a **two-state
toggle that data-derives its own active domain** (meaningful only where a rotating
grid exists AND the rotating track differs at that mass — bit-identical below the
break = honest "negligible"), NOT a slider.

**Other measured facts (re-check if grids change):**
- **All 12 feh codes publish a `vvcrit0.4` tarball** (`discover_tarball_url`, no
  download). On disk now: `feh_p000_..._vvcrit0.4` (171 tracks, fetched for the gate)
  + the original 5 non-rotating grids. To match the feh axis, fetch m100/m075/m050/
  p050 at 0.4 (~180 MB each). **Low-Z (m100/m200) is the highest-value grid** — CHE
  blue divergence is a low-Z + high-rotation effect; the headline lives at low Z.
- **Mass footprint identical** across vvcrit (both 171 tracks, 0.1–300 M☉) + **EEP
  counts align per mass** (1721/1721, 808/808) ⇒ stays a **2D (mass×feh) domain per
  bucket** (no 3D non-rectangular `mass_range`); blend-then-invert unchanged *within*
  a bucket; snap/toggle *between* buckets.
- **COLLISION IS LIVE — must fix first.** With the 0.4 grid on disk, `_feh_from_path`
  keys both solar grids to feh=0.0 → `_fehs=[-1,-0.75,-0.5,0,0,0.5]`, a degenerate
  axis point. `pytest` STILL PASSES (the §10 Sun anchor is 1.0 M☉ → bit-identical →
  can't detect it) but intermediate-mass solar tracks are silently contaminated.
  Keying by `(feh, vvcrit)` is **required to restore correctness**, not just a feature.
- **`StellarState` already has `v_rot_kms`** (unused/0 for MIST today) — surface the
  selected rotation through the spine without a new field.
- Bake resolution ≈ R 2400 → v sin i broadening visible only above ~125 km/s.

**Chunked plan (in the plan doc, gate settled):**
- **Chunk 1 — BUILT.** Provider keys grids by `(feh, vvcrit)`: partitions into one
  `_Axis` per rotation rate (vvcrit from dir name + authoritative track header `rot`,
  cached → `CACHE_VERSION` 9→10), **snaps between vvcrit buckets** and interpolates
  mass×[Fe/H] *within* a bucket (feh helpers `_bracket_feh`/`_interp_window`/
  `_state_from_row` now take an `_Axis`). `track()/state_at()/endgame()/mass_range()/
  age_range()` gained `vvcrit=0.0` (default non-rotating → live spine byte-unchanged);
  Protocol + Stub + MESA carry it (Stub/MESA accept-and-ignore). `parameter_ranges()`
  exposes `vvcrit:{available:[...]}`. Back-compat `_grids`/`_fehs` properties = default
  axis. **The real gate is the off-grid-feh test**, NOT the feh=0.0 grid-point one:
  `track(3.0, feh=0.25, vvcrit=0.0)` must blend non-rot solar+p050; the duplicate-0.0
  bug would bracket the *rotating* solar grid (20% N diff). The feh=0.0 check does NOT
  discriminate the bug (buggy bracket lands non-rotating-first by sort order) —
  **advisor-caught; don't regress to it.** 178 pytest (+8 `test_rotation_axis.py`,
  `requires_mist_rotation` marker). api.py untouched (Chunk 3 wires the query param).
- **Chunk 2 — BUILT.** `rotation_status(mass,feh) → {has_grid, threshold_msun, active}`
  on the Protocol (Stub/MESA → has_grid=False). `has_grid` = rotating axis's feh span
  covers feh (else honestly absent); `threshold_msun` = rotation-onset mass **derived by
  scanning** (`_rotation_threshold`/`_track_diverges` on logL+surface-He, first grid mass
  where rotating≠non-rotating — NOT hardcoded 1.2; measured **1.25** at solar AND low-Z,
  cached per feh); `active` = has_grid AND mass≥threshold. Centerpiece test ties the gate
  to reality ("don't label a non-feature"): active=False ⟺ tracks bit-identical, active=True
  ⟺ they differ. 188 pytest (+10). **m100 (low-Z) rotating grid fetched** — gate works at
  [Fe/H]=−1 (where CHE lives). `requires_mist_rotation` / `requires_mist_rotation_lowz`
  markers. API endpoint deferred to Chunk 3.
- **Chunk 3 — BUILT** (3 commits 3a/3b/3c). **3a (backend/API):** `vvcrit` query param on
  `/state`/`/track`/`/endgame`(+`meta`)/`/mass_range`/`/age_range` (default 0.0 → live spine
  byte-unchanged) + new `/rotation_status` route (gate through PROVIDER). **`v_rot_kms` is now
  REAL**: `surf_avg_v_rot` (km/s) → `_Track.Vrot`, interp'd across mass/[Fe/H] like the other
  living quantities, `CACHE_VERSION` 10→11. It's 0 non-rotating AND below the Kraft break (MIST
  zeroes rotation there → consistent with active=False, NO "spinning-but-identical" nuance),
  real above it (~224 km/s @ 20 M☉ MS). Payoff PROVEN via `track()` before UI: 20 M☉ solar MS
  N ~2.3×+He+longer life; m100 40 M☉ CHE blue divergence (rot logTeff 3.94 vs non-rot 3.70).
  **3b (toggle):** two-state toggle below [Fe/H]; `effVvcrit()=rotationOn&&has_grid?0.4:0.0`
  (falls back off-grid → no `/track?vvcrit=0.4` 422); `/rotation_status` fetched awaited+token-
  guarded atop `refreshTrack`; greyed `!active`, hidden `!has_grid`; vvcrit in `egKey()`+all
  endgame fetches. **3c (UNIFY, user-settled):** toggle + the SED rotation/activity slider are
  now ONE "Rotation" control in Controls with TWO regime-gated facets (advisor's regime-adaptive
  design — NOT a shared continuous unit, which is lossy/dishonest): vvcrit **track** toggle
  (massive, gated by `rotation_status`) + rotation-**period** slider (cool-MS activity, the
  relocated `#sed-rot`, gated by NEW `sed.rotationAllowed()` = the dynamo domain). Regimes barely
  overlap → usually one facet shows; at the Sun BOTH (track greyed/no-op, activity live). SED
  panel keeps the X-ray line + a pointer. **GOTCHA:** `.rot-toggle-row{display:flex}` beat the UA
  `[hidden]{display:none}` → off-grid facet wouldn't hide; needed `.rot-toggle-row[hidden]{display:none}`.
  +4 tests (192 pytest). Verified via Playwright. See [[star-sim-nonthermal-sed-plan]].
- **Chunk 4 (only one left)** = fetch remaining rotating metallicities. **m100 done (Chunk 2)**;
  m075/m050/p050 vvcrit0.4 remain (~180 MB each; user: fetch m100 now, rest later). On disk now:
  p000 + m100 rotating. (Until then the toggle is honestly absent off [-1, 0] — by design.)

**The atlas (tiers):** A (real, changes track) = **rotation vvcrit 0.0↔0.4** (the
headline; 2-point so toggle/snap not continuous; payoff = MS N-enrichment, lifetime
shift, lowered WR threshold, CHE at low Z). B (real, spectrum-only) = **[α/Fe]**
(CAP18-large re-bake; thick-disk/halo; MIST evol is solar-scaled so track won't
follow), **v sin i broadening** (frontend convolution, fast rotators only),
microturbulence ξ. C (evocative) = gravity darkening/oblateness (von Zeipel),
the SED activity band→line slider, magnetic Ap/Bp. D (needs a new engine, was "out
of scope") = **binarity/mass transfer** (the biggest — ~70% of WR are binary-
stripped; also blue stragglers/Algols/stripped-He/GW pop; needs a binary engine or
BPASS/POSYDON grid), initial-He/GC multiple populations, α-enhanced *evolution*,
live solver. Bonus zero-data = **instability-strip overlay** on the HR diagram
(Cepheid/RR Lyrae regions — a view, not a slider; cheapest honest win).

**Key physics points:** rotation reshapes the whole track (mixing→MS N/He up,
longer life, HR shift), not just X-rays; for WR it's the headline (lowers WR
threshold, sets subtype/final mass/remnant spin, CHE). **Rotation+age splits by
type:** cool stars spin DOWN via magnetic braking (gyrochronology → age predicts
rotation, basis of SED Chunk 3); hot/WR stars have NO braking (radiative envelope)
→ rotation set by winds+binaries, so age does NOT predict their rotation. So
"rotation" wears two hats: selects a different track (vvcrit, real for all masses)
vs pins activity/X-ray (age-derivable only for cool MS stars). See
[[star-sim-nonthermal-sed-plan]] and [[star-sim-wr-wd-endgame-plan]].

Suggested order if picked: instability-strip overlay → rotation toggle (after the
mass-ramp diff) → v sin i broadening → [α/Fe] re-bake → binarity/live-solver.
