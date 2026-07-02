---
name: star-sim-rotation-subpop-atlas
description: "Star Sim — rotation axis + subpopulation controls; gate SETTLED (rotation mass-ramped at ~1.2 Msun), Chunks 1-4 ALL BUILT (provider keying, honesty gate, frontend unified control + API + real v_rot_kms, and Chunk 4 fetched the remaining rotating feh grids → rotating axis now spans the full -1.0..+0.5 [Fe/H] axis). Rotation arc complete. Tier-B v sin i line broadening now ALSO BUILT (client-side Gray-profile convolution driven by v_rot_kms, edge-on). NEXT atlas thread = [alpha/Fe] spectral axis: Gate-0 MEASURED (2026-07-02) — CAP18-large is 73GB + Docker/pymsg (expensive); cheaper Coelho-2014-via-SVO ASCII path found (host-baked WD/WR precedent, matched [a/Fe]=0/+0.4); Gate-1 visibility measurement still pending. User said \"nothing is out of scope.\""
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

**v sin i line broadening — BUILT (2026-07-01, Tier B, the rotation-axis spectral
follow-on).** `spectrum.js` ONLY, no backend touch. `rotBroaden(lam, flux, vsini)`
convolves the served flux with Gray's rotation profile (ε=0.6 linear limb darkening;
weight ∝ 2(1−ε)√(1−x²)+(πε/2)(1−x²) over x=Δλ/Δλ_L∈(−1,1)); **per-pixel variable
width** Δλ_L=λ·v sin i/c (constant in velocity, wider in the red — the grid is uniform
2.5 Å/linear, R≈2400), **normalized to sum=1** so equivalent width is conserved (lines
go shallower+wider, not weaker). Driven by the marker's real `v_rot_kms` (the MIST
vvcrit axis) taken **EDGE-ON (sin i=1)** — the maximum projection. **Advisor settled
the one open decision AGAINST an inclination slider**: it'd be incoherent here (the 3D
star doesn't go oblate, Teff/L don't shift — gravity darkening is deferred Tier-C), so
only the spectral lines responding to a "tilt" implies a viewing-geometry model that
exists nowhere else; revisit a slider only if oblateness ever lands. Caption framed as
the *maximum* broadening (upper bound), not the textbook "v sin i is a lower bound on
v". **Scoped to the main absorption cube only** — WD (slow, Stark-dominated remnant;
progenitor v_rot meaningless), WR (intrinsically wind-broadened), SN (placeholder) all
exempt via `data.isWD/isWR` guards in `mainFlux()`. **No refetch** — `update()`
re-broadens the cached flux + redraws when only v_rot moved (same Teff/logg/feh key);
memoized on (source array, v_rot) so `resize()` doesn't reconvolve. Caption note gated
≥120 km/s (the ~1-pixel visibility floor). **Measured visible through the runtime path
("don't label a non-feature"):** reachable rotators run 200–420 km/s (peak ~418 at
100 M☉/[Fe/H]−1.0 vvcrit0.4); on the real served spectrum of a 2.5 M☉ vvcrit0.4 star
(v sin i 212 km/s) Ca K core depth 0.43→0.30, Hβ 0.67→0.60, Balmer lines shallow+widen
while EW is exactly conserved; the Sun (v_rot=0) is byte-identical. Playwright-verified
1440 px, zero console errors. Plan: `whirling-cohort-atlas.md` Tier B. See
[[star-sim-phase5-spectra]].

**[α/Fe] spectral axis — Gate 0 MEASURED (2026-07-02); Gate 1 pending.** The atlas's
designated NEXT (Tier B, spectrum-only — MIST evol is solar-scaled so the *track* won't
follow α). **The plan's "drops in like the CAP18 swap" was the optimistic-framing trap
(this feature class has repeatedly tripped the "don't label a non-feature" gate — SED
Chunk 2 was 4 dex too bright, PoWR 7a narrow-GO, v sin i only cleared the R≈2400 floor
>120 km/s).** Advisor-gated two-gate discipline: **Gate 0** = env/data exists?
**Measured: the α axis lives ONLY in CAP18-*large* (73 GB)**, and baking the *main* cube
needs the **Docker + from-source pymsg/MSG** env (unlike the host-baked WD/WR ASCII cubes)
— Docker Desktop was NOT running, `msg_spike` container survival unknown; α is a 4th cube
axis (size multiply, likely a `BAKE_VERSION` bump → full main-cube re-bake). So CAP18-large
= a **multi-session infra lift**, and even the cheap Gate-1 measurement is blocked behind
it. **CHEAPER PATH FOUND (Gate-0 alternative research):** **Coelho 2014** (arXiv 1404.3243,
MNRAS 440, 1027C) carries a clean matched **[α/Fe]=0.0 AND +0.4** across (Teff 3000–25000 K,
log g −0.5…5.5, [Fe/H] −2.5…+0.5), 2500–9000 Å, and is on the **SVO Theoretical Spectra
Server** as ASCII — the **exact host-baked SVO-ASCII precedent of the Koester (6a) / TMAP
(6b) WD cubes** (bulk SSAP fetch + custom reader + a *separate* α-cube sibling, numpy/scipy,
NO Docker/pymsg/73 GB). Teff 3000–25000 K = exactly the cool/solar/A window where α
metal-lines matter (washes out hot = the Teff-gated honesty predicted, like He I/II
`minTeff` / TiO `maxTeff`). Castelli-Kurucz ODFNEW also has α+0.4 but only [Fe/H]≤−0.5 (not
a clean full-grid pair). **Design rule:** compare Coelho-α=0 vs Coelho-α=+0.4 (same
atmosphere code) — NEVER a Coelho α spectrum beside a CAP18 solar one (atmosphere-code seam
would contaminate the α signal). **Gate 1 CLOSED — GO (2026-07-02).** Fetched
matched Coelho `coelho_highres` α=0 vs +0.4 (SVO SSAP, 3727 models, ~10.7 MB/model ASCII),
binned to the 2.5 Å runtime grid: **α is clearly VISIBLE & Teff-gated** — deepens Ca I 4227
(Δdepth up to **+0.16**), Ca II K (+0.03…+0.12), Mg b (+0.06), Ca II triplet 8542 (+0.03…
+0.06), TiO 7053 (+0.045@4000K) in the **cool→F window**; **marginal at A (~9000 K, Ca II K
only), DEAD ≥12000 K** (all Δ≤0.006 — metals wash out). **Both controls pass:** Na D (odd-Z)
moves **OPPOSITE (shallower, Δ −0.04…−0.09)** — an α-heavier mix raises H⁻ continuum, weakens
non-α lines — so it's genuine differential chemistry, NOT a global-normalization artifact
(which moves everything the same way); hot stars null. Comparable at [Fe/H]=0 & −0.5.
**Giant check (logg=2.0) confirms + stronger** (Ca II triplet, the classic giant α indicator,
Δ +0.036…+0.056 across 4000–5500 K). Scratch: `M:\claud_projects\temp\alpha-gate1\`
(`gate1.py`/`gate1_giants.py`/`RESULTS.md`). **THREE build-design decisions (advisor-settled):**
(1) **the toggle bakes BOTH baselines from Coelho** — pure-α (Coelho α0↔α0.4), NEVER code+α
(don't show Coelho-α beside CAP18-solar — atmosphere-code seam masquerades as the α signal;
*the* load-bearing constraint); (2) **spectrum-only "what-if"** — `comp.js` shows solar-scaled
MIST metals so the α toggle deepens Mg/Ca/Ti in the *spectrum* but NOT the comp panel → label
it a spectrum-only hypothesis (extend cross-cutting #4 to comp); track/comp don't follow α
(that's Tier-D α-evolution); (3) **scope the fetch Teff≲10 kK** (the hot-null payoff bounds it)
**+ hand off to the main cube hot** (α-cube cool / main cube hot, mirroring the WD-gravity
`refreshWD` switch). Build shape = a separate host-baked Coelho α-cube sibling (WD/WR-cube
precedent: `fetch_*`+`bake_*`+the axis-generic `_Spectra` runtime).
Recipe `backend/docs/msg_spectra_build_recipe.md` §5/§8 (Koester/TMAP host-baked precedent).

**Chunk 1 (backend data+runtime vertical) BUILT — 2026-07-02, 254 pytest.**
`star_sim/fetch_coelho.py` (SVO `coelho_highres` SSAP bulk fetch, `--teff-max 10000`
cool-subset, matched-α `select()` — drops a node lacking BOTH α, else a toggle clamp-lies
on flip; **cp1252 gotcha: no α/em-dash in `print()`** — Windows console, twice-bitten);
`scripts/bake_alpha_spectra.py` (**4-axis** Teff×logg×[Fe/H]×[α/Fe] cube; Coelho's grid is
ragged in (Teff,logg) → a **log g clamp-fill**, the WD `_interp_logg` precedent, keeps
Teff/[Fe/H]/α exact, only substitutes gravity at ragged edges; **47% of cells clamp-filled**,
all at unphysical extreme-logg corners NOT reachable loci); `spectra.py` `alpha_spectrum_data()`
+`_load_alpha()`+`ALPHA_GRID_FILENAME` (reuses axis-generic `_Spectra` verbatim as a 4-D grid,
**NO `BAKE_VERSION` bump** — new separate file, WD-cube precedent); `/alpha_spectrum` route;
`test_alpha_spectra.py` (15 tests, `requires_alpha_spectra_data` marker) = **Gate 1 as
regression** measured through the real route (α deepens Ca I 4227/Mg b/Ca II triplet at both
[Fe/H] nodes; **Na D control does NOT deepen** = the anti-normalization-artifact gate;
Teff-gated). MVP cube on disk = [Fe/H] {−0.5, 0.0}, Teff 3000–10000 K, all logg, both α (834
Coelho models ≈ 8.4 GB → 13.3 MB `alpha_spectra_grid.npz`, both gitignored). **Widen [Fe/H]
to {−1.0, +0.2} = pure data re-bake** (`fetch_coelho --feh -1.0,-0.5,0.0,0.2` + re-bake, no
code change — CAP18/PoWR precedent). Advisor confirmed the test points are REAL Coelho nodes
(not clamp-filled) so the physics tests measure true spectra.

**Chunk 2 (frontend α toggle in the spectrum panel) — NEXT.** Two advisor carry-forward
decisions: (1) **the α-mode-OFF baseline routing** (the one undecided point) — a cool star
with α-mode off shows either the main CAP18 cube (engaging α then swaps CAP18→Coelho-α0, a
visible atmosphere-code change before any α change) OR Coelho whenever the cube exists (every
cool star's default silently drops CAP18→Coelho); decide explicitly, don't let routing code
decide it; (2) **spot-check baseline fidelity** — the tests verify the α *differential* (clean
since both α slabs clamp-fill identically) NOT that reachable cool MS/giant (Teff,logg) loci
land on real nodes vs gravity-substituted corners (the 47%-fill risk); check real loci vs the
node list before wiring. Plus: Teff-gate the control off ≥~9–10 kK (like TiO `maxTeff`),
spectrum-only "what-if" label (comp/track don't follow α), hand off to main cube hot.
See [[star-sim-phase5-spectra]], [[star-sim-wr-wd-endgame-plan]].

**The atlas (tiers):** A (real, changes track) = **rotation vvcrit 0.0↔0.4** (the
headline; 2-point so toggle/snap not continuous; payoff = MS N-enrichment, lifetime
shift, lowered WR threshold, CHE at low Z). B (real, spectrum-only) = **[α/Fe]**
(thick-disk/halo; MIST evol is solar-scaled so track won't follow; **cheaper path
= Coelho-2014-via-SVO ASCII, NOT CAP18-large/Docker — see the Gate-0 block above**),
**v sin i broadening** (frontend convolution, fast rotators only),
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

Suggested order if picked: instability-strip overlay ✓ → rotation toggle ✓ (after the
mass-ramp diff) → v sin i broadening ✓ → **[α/Fe] via Coelho-2014/SVO** (Gate 0 done,
Gate 1 pending — NOT the CAP18-large/Docker path) → binarity/live-solver.

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
