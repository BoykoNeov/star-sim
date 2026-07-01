---
name: star-sim-rotation-subpop-atlas
description: "Star Sim — rotation axis + subpopulation controls; gate SETTLED (rotation mass-ramped at ~1.2 Msun), Chunks 1-4 ALL BUILT (provider keying, honesty gate, frontend unified control + API + real v_rot_kms, and Chunk 4 fetched the remaining rotating feh grids → rotating axis now spans the full -1.0..+0.5 [Fe/H] axis). Rotation arc complete. User said \"nothing is out of scope.\""
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
  download). On disk now (post-Chunk 4): **all 5 rotating grids m100/m075/m050/p000/p050
  at vvcrit0.4** (matching the 5 non-rotating grids) — the rotating [Fe/H] axis is
  complete over −1.0→+0.5. **Low-Z (m100/m200) is the highest-value grid** — CHE
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
- **Chunk 4 — BUILT (arc complete).** Fetched m075/m050/p050 vvcrit0.4 (171/169/170 tracks) via
  `fetch_mist --feh m075,m050,p050 --vvcrit 0.4`, so the **rotating axis now spans the full
  [Fe/H] axis −1.0→+0.5** (m100/m075/m050/p000/p050) — coextensive with non-rotating. Cold parse
  cache rebuilt (`CACHE_VERSION` 11, unchanged — pure data add). `rotation_status.has_grid` now
  honest across the whole axis (was capped at the partial −1.0…0.0 span); absence is honest only
  *beyond* it (feh>+0.5). MS surface-N enrichment confirmed real at the new grids: 20 M☉ rot/non-rot
  N ratio 5.5×/4.6×/1.8× at feh −0.75/−0.5/+0.5. **Two `test_rotation_axis.py` assertions that
  encoded the *incomplete* axis** (`test_rotation_status_absent_where_no_grid` + the API route test,
  both asserting `has_grid` False at +0.5) **flipped to the completed truth** (+0.5 present; absence
  re-tested at +0.75, beyond the axis). 192 pytest. Data is gitignored (`data/feh_*_vvcrit0.4/`).
  **Deferred gap — NOW CLOSED (post-Chunk-4 follow-up).** The missing within-bucket [Fe/H]
  interpolation coverage on the rotating axis is filled: **two new `test_rotation_axis.py`
  tests** mirror the non-rotating pair (`test_mist_provider`):
  `test_feh_interpolation_lies_between_metallicities_rotating` (structural lies-between at
  vvcrit=0.4, first rotating bracket −1.0/−0.75, mass 3.0) and
  `test_feh_interpolation_tracks_held_out_grid_rotating` (hold out rotating p000, interpolate
  feh=0/vvcrit=0.4 from rotating m050/p050, compare to the real rotating p000 3.0 track —
  measured L median 0.7%, Teff 1.8%). **Advisor's key correction (heeded):** lies-between alone
  is a *weak discriminator* here — rotation's logL/Teff signature is far subtler than its
  surface-N one (only ~1/25 age samples diverge in logL, ~16/25 in log Teff at this bracket), so
  blend-then-invert convexity (axis-agnostic code) makes it pass *by construction* the moment the
  non-rotating one does. So: (1) the **held-out accuracy test is the one with teeth** (catches
  blend-weight/feh-mapping/rotating-grid drift; non-rotating interp vs the rotating truth is
  ~2.6% = 3.6× worse, so a contamination bug collapses the rot/non-rot ratio to 1 → the `>2×`
  clause fails); (2) lies-between **also carries a contamination-style discrimination clause**
  (on log-Teff-divergent rows the interp must sit closer to the *rotating* blend). Both gated
  **mass 3.0 (above the Kraft break)** — at 1.0 M☉ the rotating track is bit-identical so the
  test would silently degenerate. Raw reader targets `...vvcrit0.4` *explicitly* (a feh-only
  glob silently grabs the non-rotating dir). New conftest markers
  `requires_mist_rotation_multifeh` / `requires_mist_rotation_heldout_feh`. **194 pytest** (+2).

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

**UX correction (2026-07-01):** the vvcrit **track toggle now HIDES** where it is a
data-derived no-op (below the ~1.2 M☉ Kraft break, `!rotStatus.active`) instead of showing
**greyed** — `showToggle = has_grid && active` in `updateRotControl` (`main.js`). A greyed,
dead toggle sitting under the same "Rotation" header as the live **period slider** (e.g. at
the Sun, where both facets would show) read as a confusing dead knob (user feedback). This
**supersedes the earlier "greyed-not-hidden, user-settled" design** — the comment in
`main.js` + the `index.html` rotation comments were updated. At the Sun only the self-labeled
"Rotation period" slider now shows; matches the control's own "absent, not a dead knob" rule.
`active` is mass/[Fe/H]-derived (age-stable), so hiding it never reflows mid-age-scrub. No
data-path change (`effVvcrit` still gates on `has_grid`; below-break tracks are bit-identical
so a stray vvcrit=0.4 is a no-op). Verified Playwright 1440 + 390 px, zero console errors.
