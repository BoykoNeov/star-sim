---
name: star-sim-binary-stripped
description: "Binary-stripped-star sibling (binary.py + /binary) — Götberg 2018 hot He-star, the ~70% WR channel; path (a) Chunks 1–3 complete. Path (b) Chunks 1–4b built the POSYDON co-evolved-binary time-series sibling (posydon.py + /binary_track) with a two-star TIME render (both HR markers cross, Roche panel live off per-step geometry). Chunk 4c (frontend-only, no backend change — /binary_track was always general) BUILT: free M1/q/P sliders behind a fourth 'Custom orbit' picker, log-scale for M1/P + linear for q, snap-honesty note always states the TRUE nearest POSYDON node. Chunk 4d (frontend-only, no backend change) BUILT: a [Fe/H] metallicity-bucket picker wiring the frontend up to the full 8-bucket POSYDON axis [[star-sim-hosted-data-assets]] finished hosting — applies to whichever demo (curated or custom) is showing. Path (b) arc is now fully complete (all of 1–4d built); only richer-outcomes/population-overlay follow-ons remain, unscoped."
metadata: 
  node_type: memory
  type: project
  originSessionId: a40a18b8-efa2-4928-bdcf-1d34c29ef543
---

The **binary-stripped-star** feature — the hot, He-rich core a close companion exposes
by Case-B Roche-lobe overflow (Götberg+2018). This is the *dominant* observed channel
for stripped/WR stars (~70%, Sana+2012), so it retires the caveat the single-star WR
demo keeps writing ("shows the minority channel"). It is the first build from the atlas's
Tier-D **binarity** item — path (a), the stripped-star endpoint (not the full two-star
co-evolution, path (b), deferred). Plan `docs/plans/stripped-consort-unveiling.md`.

**Architecture — a SIBLING, not a provider** (settled): a binary product can't go through
the single-star `StellarStateProvider`/`StellarState` interface without discarding the
companion or mutating the dataclass (both §3 violations). So it mirrors `supernova.py`/
`structure.py`: `binary.py` imports only `state.StellarState`, `/binary` bypasses `PROVIDER`.

**Chunk 1 BUILT 2026-07-02 (backend vertical, solar-first, 266 pytest):**
- `backend/star_sim/data/gotberg_z014.csv` — the verified **Z=0.014** table COMMITTED
  inside the package (23 rows: M_init, M_strip, Teff_kK, logL, logg, R_eff, X_H, X_He +
  provenance header). Two-source provenance: spectra on VizieR (gitignored under
  `data/gotberg_stripped/`), these *structural params* = the paper's Table 1, transcribed
  then VERIFIED against the on-disk SEDs (≤0.07 dex, all 23 rows). The 3 non-solar Z
  tables (0.006/0.002/0.0002) append later — grid data-shape is **1D-in-Minit** per Z
  (Gate 0a resolved; period P is a fixed function of mass, snap key = (Z, Minit)).
- `binary.py` — own CSV parser; `stripped_star(mass, feh)` snaps (Z, Minit)→nearest,
  never interpolates (§6); returns `StrippedStar` = the §3-clean `StellarState` + routing
  scalars (`m_strip_msun` [CURRENT mass — no home on the state, which has only mass_init],
  snapped m_init/Z, feh_snapped, mass/feh `_snapped_far`, mass_grid_min/max). Adding a Z =
  drop a CSV + one tuple in `_GRID_TABLES`; [Fe/H]=log10(Z/`GOTBERG_SOLAR_Z`=0.014).
- `/binary` route — **snap-always** (advisor): out-of-grid snaps + flags `*_snapped_far`
  in-band; 422 only for mass≤0. hide-below-2/note-above-18.2 is a Chunk-2 UX read.
- `test_binary.py` (12) + `requires_gotberg_data` marker (guards the gitignored SEDs).

**Gotchas baked in (build them into Chunk 2+ too):**
- **Teff/Reff, NEVER T★** — T★ is the inner hydrostatic (evolutionary) temp; for a star
  with a wind it differs from the spectroscopic Teff. Teff/Reff are the self-consistent
  Stefan-Boltzmann pair that place the marker (same evolutionary-vs-spectroscopic gap that
  bit WR spectra 7a). Feeding T★ misplaces it.
- **Z_surf = grid Z**, NOT 1−X−Y (table X rounded to 2 dp → would zero Z). Renormalize the
  (X_H, X_He) pair to close at 1−Z. He-rich surface is the headline (Y_surf ≳ 0.7 high-mass;
  low-mass end ~2 M☉ is still H-rich sdB-like — honest subdwarf↔WR sequence).
- **mdot=None, no lifetime** in Chunk 1 — neither is in the verified 8-col table (measure-
  first discipline; the SED free-free tail is a Chunk-2 call for this FAST-wind regime).
- `age_yr`/`eep` are a documented sentinel (`REPRESENTATIVE_AGE_YR`) — ONE representative
  state ("halfway through core-He burning"), not a time-track, not age zero.

**The advisor's correctness catch (the one that would've bitten):** the visibility gate
keys on **Teff + Y_surf ONLY, never L**. A stripped star is sub-luminous *for its Teff*,
but M_strip ≪ M_init makes it a He-star of a different mass, so the L comparison FLIPS SIGN
across the grid (logL 0.6 vs single ~1.05 at 2 M☉ → sub-luminous; 4.9 vs ~4.4 at 18 M☉ →
over-luminous). `stripped.L < single.L` would FAIL at high mass. Always-hotter +
always-He-enriched are the robust discriminators.

**Chunk 2 BUILT 2026-07-02 (frontend-only, 266 pytest UNCHANGED, Playwright 1440+390 zero
console errors):** the reversible what-if `mode="stripped"`.
- **Entry point (i), settled:** a mass-gated TOGGLE (`#stripped-toggle`, mirrors the Ap/Bp
  control) shown for eligible progenitors (2–18.2 M☉) in live mode + while active — a MID-LIFE
  FORK, not an end-of-life gateway (so a toggle, not a gateway button), but still a reversible
  MODE snapping the whole display, fetched from `/binary` (snap-always, no vvcrit). **One exit:**
  the SHARED endgame-bar "Back" (=`exitEndgame`); unchecking calls the same. `exitEndgame`
  captures `prevMode` and pins-to-end ONLY for real endgames — the fork returns to the age it
  forked FROM (ageValue is untouched inside the mode; `els.age.disabled=true` — one representative
  state, no lifetime).
- **The three false-data leaks blocked (advisor's #1 point):** HR keeps the progenitor's living
  track faint + drops the marker BLUE-LEFT (reuses `hr.setEndgame([s],"stripped")` auto-fit — NO
  hr.js change); **comp = a NEW single-state SURFACE view** (`comp.setStripped`/`drawStripped` —
  the measured He-rich bar H/He/Z; the core is by-construction so NOT drawn — the bulk/cno/light
  views need an EEP track a single state lacks); **spectrum → honest placeholder** (the main cube
  is H-atmosphere models → a He-star's Teff/logg would paint a FALSE O-star Balmer spectrum);
  **structure → NOT called** (keeps its last profile, like wd/wr/sn — else it'd fetch a normal
  ZAMS profile for the progenitor mass). classify=`strippedLabel` (sdO/B < 1.5 M☉ → He-star above,
  keyed on the CURRENT `m_strip` via `opts.mStrip`); scale radius-based (the mass_init audit worry
  was MOOT — scale reads no mass); readout=`renderStrippedReadout` (current m_strip + progenitor +
  He surface).
- **SED tail off + honest for free:** `mdot=None` → `sed.js computeWindTail` returns null (no
  line), and a fast wind wouldn't crest the floor anyway — no gating code needed (the measure-first
  concern resolved in the data).
- **Re-snap (`tryStrippedResnap` in `tryResnap`):** UNLIKE wd/wr/sn there's no fate to revert on
  (snap-always) → a drag past the grid edges snaps + shows an in-band snapped-far caption note,
  never reverts.
- **The composition-honesty catch (advisor blocker, caught post-first-verify — the "verified the
  easy He-rich 8 M☉ end, generalized to the whole range" trap):** the surface is NOT always He-rich.
  The LOW-mass end is **hydrogen-rich** (measured: 2–3 M☉ progenitors → X_surf≈0.99, Y_surf≈0.0 —
  an sdB-like hot subdwarf that keeps a thin H envelope; the crossover is ~3.5–4 M☉). Hardcoding
  "helium-rich surface" would ship a FALSE measured label (boron-b8/VO-7400 discipline) AND
  contradict `classify` (which already branched on Y vs X). Fix: EVERY per-state surface label
  derives from `heRich = Y_surf > X_surf` — `comp.drawStripped` (tag/contrast-line + a
  `strippedCaption(heRich)` function), `classify.strippedLabel` (sdB/O H-rich → sdO/He-star He-rich),
  `renderStrippedReadout` (Class + help), the `refreshStripped` caption; the static narration/tooltip
  say the surface "flips H→He with mass." Verified at BOTH mass=2 (H-rich) and mass=8 (He-rich).
- **Files (frontend-only, no backend touch):** `main.js` (orchestration), `comp.js`
  (`setStripped`/`drawStripped`), `classify.js` (`strippedLabel`), `index.html` (toggle + bar
  title/narration + `.age-stripped`), `styles.css` (stripped-mode rules mirror wd/wr/sn).

**Chunk 3 BUILT 2026-07-02 (backend + frontend, 273 pytest, Playwright 1440+390 zero console
errors):** the stripped-star SPECTRUM panel — the real CMFGEN spectrum replacing the Chunk-2
placeholder. A FOURTH spectrum sibling `/stripped_spectrum` over the Götberg CMFGEN cube.
- **`scripts/bake_stripped_spectra.py`** → a **flat-node** cube (like WR, NOT rectangular
  Teff×logg) keyed on the grid node `(Z, M_init)` — the SAME snap identity `binary.py` uses.
  **Solar-only** (grid_014, 23 nodes; grid-generic `--grids` for the non-solar Z later). Reads
  `normalised_spectrum.txt` = CMFGEN **continuum-normalized** Fnorm → NO continuum estimation
  (unlike WR). `spectra.py _StrippedSpectra` + `stripped_spectrum_data(minit, feh)`; route
  snap-always; `STRIPPED_GRID_FILENAME` + `requires_stripped_spectra_data` marker; 7 tests.
- **Two measured gotchas (both verified on disk):** the spectra are **VACUUM** (Balmer minima
  match vacuum <0.1 Å, off air 1.1–1.7 Å) → vac→air (Morton 2000, TMAP/PoWR precedent); **sort by
  λ before binning** (CMFGEN band-concat CAN be non-monotone — the solar files measured monotone
  but the empty-bin interp fallback needs it; cheap insurance).
- **Advisor's tightest constraint — state↔spectrum consistency:** snap to the node `/binary`
  already resolved, NOT the raw slider mass. `spectrum.js updateStripped` reads `state.mass_init_msun`/
  `feh_init` (which binary.py sets to the snapped node) → the panel spectrum is guaranteed the SAME
  star as the marker (binary's node list = the CSV, the cube's = the VizieR dirnames; re-snapping raw
  mass independently could drift at a midpoint).
- **The measure-first gate CLOSED through the runtime (advisor BLOCKER, ran before any frontend):**
  the absorption→emission sequence is real & monotone — 2 M☉ (20 kK) pure absorption (He II 4686 flat
  1.0, Hα 0.50) → 6.66 (54 kK) hybrid (He II 4686 emits 1.15) → 18.17 (101 kK) strong emission (He II
  4686 **7.19×**, Hα 3.21). Distinct from the false O-star Balmer spectrum the placeholder protected
  against (the hot nodes are >55 kK where the main cube is a clamped "no model" anyway) — the
  justification for a fourth cube, measured. Götberg's abstract IS this: "a continuous sequence
  bridging subdwarf-type stars at the low-mass end and Wolf-Rayet-like spectra at the high-mass end."
- **Frontend:** a **bidirectional** `drawStripped` (mirrors `drawWR`: rainbow shade + dashed continuum
  line at 1.0 + backend `display_max` y-cap floored 1.2/capped 8, but absorption dips below AND
  emission peaks above), `STRIPPED_LINES` guides (He II 4686 diagnostic + Balmer/He I, no up/down
  gate), regime-branched caption ({absorption/hybrid/emission}). `main.js applyStrippedModel` swaps
  `showPlaceholder`→`updateStripped(s)`.
- **Bonus bug the screenshot pass caught:** the `.spectrum-zoom` zoom-preset row LEAKED into every
  endgame + stripped mode — `hidden=true` (set by updateWD/WR/updateStripped/showPlaceholder) silently
  failed because `.spectrum-zoom{display:flex}` beat the UA `[hidden]{display:none}` (missing the
  `[hidden]` re-assertion the `.alpha-toggle-row`/`.rot-toggle-row` rules have). Fixed with one CSS line
  `.spectrum-zoom[hidden]{display:none}`. Nuance (advisor): the leaked buttons were DEAD only in WR/SN/
  stripped (those draw paths ignore the band window); in WD they actually WORKED (WD renders through the
  main draw path), but `updateWD` explicitly hides them anyway, so the fix restores that intent uniformly.

**PATH (b) CHUNK 1 BUILT 2026-07-02 (backend + frontend HR two-marker reversal, 279 pytest,
Playwright 1440+390 zero console errors):** "the companion drawn" — the second star of the Algol
system on the HR, the mass-ratio reversal made visible. **NO new dataset** (POSYDON/BPASS NOT
needed — the advisor's key steer): reuse the Götberg stripped DONOR (path (a)) + the single-star
`PROVIDER` for the COMPANION (accretor).
- **Measure-first gate PASSED through the real consumers** (mirrors path (a) Gate 0) across the
  whole grid: reversal real at every node (`M_strip < M2_init`, 0.35<1.60 … 6.72<14.54), companion
  a sane MS star at every node (Teff 7.3–27.4 kK, phase MS, at the donor's MS lifetime), donor always
  hotter (blue-left). Bonus: the **L-ordering FLIPS** — low mass the companion OUTSHINES the
  sub-luminous donor ("the optically bright companion", Götberg), high mass the donor wins; donor
  always hotter. (The path (a) L-sign-flip, now a teaching payoff on the HR.)
- **Two advisor correctness catches, baked in:** (1) baseline companion = `M2_init = 0.8·M_init`
  (the grid's fixed **q=0.8**, confirmed in the ReadMe; non-conservative → NO accretion-efficiency
  guess; `ΔM=M_init−M_strip` is NOT the companion's — it's wind + non-conservative RLOF loss, and
  critically-rotating accretors reject most of it). (2) the companion age/phase trap is DEFUSED by
  that baseline — being *less massive* it lives longer, so at the donor's MS lifetime (=elapsed
  system age, TAMS on the donor track) it's still mid-MS, never degenerate/off-track.
- **Architecture — `binary.py` stays a PURE §3 sibling** (never imports/fetches the companion, which
  needs `PROVIDER`): the composition is in the ROUTE. New **`/binary_pair`** = `stripped_star`
  (donor) + `PROVIDER.state_at(0.8·M_init, feh, τ)` (companion, τ=`_donor_ms_lifetime`=age at first
  post-MS row); `binary.binary_pair_payload` assembles donor (verbatim /binary shape) + a `companion`
  block (`mass_msun`, `mass_ratio_init`=0.8, `mass_ratio_final`=M2/M_strip >1, `elapsed_age_yr`;
  BOTH ratios are companion÷donor — one convention, so the reversal reads as crossing 1.0. The
  advisor caught the first cut mixing conventions [init=M2/M1, final=M_strip/M2] → a self-
  contradictory readout; pytest checked the number + Playwright the row's existence, neither the prose).
  Both stars at the snapped system Z (`feh_snapped`). `/binary` (path (a)) byte-unchanged.
- **Frontend — an opt-in "Show companion" toggle** in the endgame bar (stripped-mode only, CSS-gated)
  = the literal path (a)→(b) transition. Path (a) is the default (byte-unchanged when off). On: the
  stripped fetch routes to `/binary_pair`; `hr.js` `setCompanion(state)` draws a 2nd Teff-colored
  marker (dashed ring vs the donor's solid, a dotted link + labels "stripped star"/"companion"),
  re-fitting the axes to enclose it (low-mass brighter companion would else clip); caption narrates
  the reversal; readout gains Companion + Mass-ratio(now) rows. Reversible; resets on enter/exit.
  `hr.js` companion added to `fitBounds`+`clearEndgame`+the export.
- **Files:** `binary.py`, `api.py`, `test_binary.py` (+6), `hr.js` (`setCompanion`/`drawCompanion`/
  `markerLabel`), `main.js` (`companionOn` + toggle + route + caption/readout), `index.html`, `styles.css`.

**PATH (b) CHUNK 3 BUILT 2026-07-06 (backend + frontend, 287 pytest [+8], Playwright 1440+390 zero
console errors):** "the mass-transfer geometry / Roche lobes" — a genuinely new TWO-STAR render: the
orbital-plane cross-section at the moment of Case-B RLOF (the CAUSAL story behind the stripped star).
- **Option B, advisor-settled:** the RLOF *moment* (a distinct, labelled evolutionary snapshot), a 2D
  orbital-plane figure-of-eight (NOT 3D Roche surfaces — the topology only reads in the plane),
  separation from `P_init` via Kepler. The 3D companion sphere (Chunk 2) shows the POST-strip product;
  this panel shows the earlier RLOF moment.
- **The blocker the advisor flagged — cross-panel mass-ordering REVERSAL (same class as the Chunk-1
  q-bug):** at RLOF the donor is M1, the HEAVIER star (5.45 M☉) overflowing its BIGGER lobe onto the
  lighter companion M2=0.8·M1 (4.36); but every other panel shows the POST-strip donor as the LIGHTER
  object (readout: stripped 1.27 < companion 4.36, ratio 3.4). The SAME "donor" is heavier here /
  lighter elsewhere. **Owned by BOTH the panel intro AND the dynamic caption** ("here the donor is
  still the heavier star; by the stripped state shown elsewhere the mass ratio has reversed"). Nice
  consistency that makes it non-contradictory: the COMPANION mass is 4.36 in both views (accretor
  ~unchanged, non-conservative baseline); only the donor's mass changes — so the reversal reads as the
  donor sliding under the companion, not two panels disagreeing.
- **Honest geometry, schematic donor colour:** the lobe SHAPE depends only on q (=0.8, known); the
  separation is Kepler on the node's real (M1, M2, `P_init`). The donor at RLOF is a bloated COOL post-MS
  giant of UN-MODELLED temperature (the Götberg table is the stripped product) → drawn with a neutral
  WARM schematic tint, NEVER the stripped Teff (that would be a false hot-blue claim). The companion is
  drawn at its REAL modelled radius (from `/binary_pair`) — compact, deep inside its own lobe (only the
  donor overflows). The stream is a schematic Coriolis arc. Caption owns all three soft spots + that
  `P_init` is the *initial* period (RLOF-onset approx).
- **Backend:** `gotberg_z014.csv` gains a 9th `P_init` column (transcribed from the VizieR model dir
  names `M1_<M>q0.8P<P>Z0.014`, all 23 verified against `ls`); `binary.py` `_StrippedModel.p_init` +
  parser `len(row)!=9` fix (the advisor's code gotcha) + a PURE `roche_geometry(mass,feh)` (no PROVIDER
  — pure orbital mechanics): dimensionless Kopal potential (donor at origin, companion at (1,0), q=M2/M1),
  L1/L2/L3 by bisecting dΦ/dx on the 3 axis intervals, lobe outlines by radial-march-per-angle to the
  critical equipotential. **The L1-tangent bug + fix:** along the axis toward the companion Φ is TANGENT
  to `crit` at L1 (a maximum, not a transversal crossing), so a strict `≥crit` test misses it and the
  march leaks across L1 into the companion's well (donor lobe reached x=1.385!) → fix: stop at the first
  of (crit-crossing) OR (Φ turnover), which pins the cusp at L1 so the two lobes kiss. Folded into
  `binary_pair_payload` (`payload["roche"]`, one fetch; companion sphere size comes from the route's real
  companion state). 8 new tests in `test_binary.py` (P_init parse, snap consistency, donor-heavier-at-RLOF,
  Kepler separation sane ≈43.7 R☉ @5.45, L-point ordering, lobes-kiss-at-L1 + donor-bigger + no-leak,
  Eggleton fill, route carries roche + companion-fits-its-lobe).
- **Frontend:** new `roche.js` (a pushed-data consumer — main.js hands it the `roche` block + companion
  state; never fetches) drawing the equal-aspect (undistorted) figure-of-eight: filled donor lobe (warm
  schematic) + faint companion lobe + companion disc at real relative radius + L1/L2/L3 ×'s + CoM + stream
  arrow + separation scale bar + the reversal-owning caption. New `#roche-panel` in index.html
  (`data-panel-id="roche"`), CSS-gated `display:none` → `body.stripped-mode.companion-on .roche-panel`
  (a mode-hidden `.panel` is safe with layout.js — still enumerated, just hidden; canvas fit on first
  draw since fitCanvas measures 0×0 while hidden). main.js: import + instantiate + RESPONSIVE entry +
  `applyStrippedModel` draws/clears + toggles `.companion-on` body class + `exitEndgame` clears.
- **Files:** `data/gotberg_z014.csv`, `binary.py`, `test_binary.py` (+8), `roche.js` (new), `main.js`,
  `index.html`, `styles.css`.

**PATH (b) CHUNK 4a BUILT 2026-07-07 (backend vertical, solar-first, 306 pytest [+19]):** the
POSYDON on-ramp, built. User landed ALL 8 metallicity tarballs + auxiliary (~84 GB) under
`data/Posydon/` (not just one, as the design doc assumed) — the other 7 sit ready for later
chunks; only solar is extracted (`data/posydon/1Zsun/1e+00_Zsun.h5`, 4.79 GB) + baked so far.
- **Recon correction (measured, overturns the design doc's assumption):** the raw grid HDF5 is
  already organized PER RUN (`grid/run<i>/{binary_history,history1,history2}`, `grid/
  initial_values`/`final_values` for the axes + final classification) — NOT POSYDON's packed
  `PSyGrid` format. So the host-side POSYDON-loader demux step the design doc planned for was
  UNNECESSARY: `scripts/bake_posydon.py` reads the raw file directly with plain h5py (bulk
  per-group reads, not per-column — 39712 runs in ~85s), no POSYDON install needed anywhere.
- **The bake:** filters `interpolation_class=="not_converged"` (762/39712) + runs missing/
  misaligned `binary_history`/`history1`/`history2` (5466 + 363) + verifies the run{i}↔
  `initial_values[i]` index identity per run (an advisor catch — don't assume the correspondence).
  Decimates tracks >300 rows (uniform stride, keeps first/last). Trims ~54 raw columns to the
  ~15 a `StellarState` needs. Writes a flat CSR-style `.npz` (`track_row_start/count` index into
  shared flat row arrays — no ragged/pickled arrays): **33,121 tracks, 1.48M rows, 142 MB** from
  the 4.79 GB source. `BAKE_VERSION` discipline (must match `posydon.py`'s, like MIST's
  `_parsed_tracks.npz`).
- **Two real schema gaps vs the design doc's guess (pinned against the ACTUAL columns, not
  assumed — boron-b8 discipline):** NO eccentricity column (HMS-HMS binaries are tidally
  circularized in this grid — `BinaryStep.ecc` is a documented 0.0, not fabricated); composition
  is **C/N/O only** (`surface_c12/n14/o16`, `center_c12/n14/o16`) — a 3-key partial
  `metals_surf`/`metals_core` dict, never MIST's 16-metal breakdown. Also: no per-row phase label
  (POSYDON's `S1_state`/`S2_state` are FINAL-row-only) — `posydon.py` derives a coarse per-row
  phase from the burning-fraction columns that ARE per-row (center H1/He4 + surface H1), a
  different (honestly labeled) vocabulary than MIST's EEP-window phases.
- **`star_sim/posydon.py`** — the runtime sibling, ZERO h5py/POSYDON imports (numpy + stdlib
  only): `binary_track(m1, q, p, feh)` snaps to the nearest track in **normalized log-M1 /
  log-P / linear-q space** (advisor-settled metric — raw axes span x73/x1/x5e4, log-normalizing
  keeps no single axis from dominating), never interpolates (§6 — no row-for-row correspondence
  between tracks). Per-step: two `StellarState`s (current mass rides as a `BinaryStep` routing
  scalar, mirroring `m_strip_msun`; `mass_init_msun` on the state is the STAR's own constant
  initial mass) + orbital scalars (`period_d`, `separation_rsun` straight off `binary_separation`,
  `ecc=0.0`, data-derived `mt_state` from `rl_relative_overflow_1/2` signs: detached/RLOF1/RLOF2/
  contact). Track-level `outcome` from the FINAL-row `S1_state`/`S2_state`/`interpolation_class`:
  "merger" (a state=="None") / "stripped + companion" / "stable mass transfer" / "unstable mass
  transfer" / "detached (no interaction)". A defensive truncate-on-non-finite-mass guard exists
  for `star_2` going `None` mid-track (the endgame terminal-row precedent) but is NOT observed to
  fire on this grid — mergers here just show up as short tracks that stop early, not a null-star
  row; `star_2: StellarState | None` stays forward-compatible, not a claim this grid uses it.
- **Gate 0 CLOSED through the real runtime** (measured off the raw grid FIRST via a direct h5py
  probe, then reproduced bit-for-bit through `posydon.py` — `test_posydon.py`'s demo system,
  POSYDON's own `run86`: M1=8.83, q=0.6, P=3.73 d, 271 rows): the mass ordering crosses at
  step 16/271 (donor 8.83→1.07 M☉, companion 5.30→5.94 M☉ — the Algol reversal happening LIVE,
  not just true at the endpoints); the period widens 3.73→6.94 d as separation grows 24.4→29.3
  R☉; `mt_state` fires a genuine detached→RLOF1→detached sequence; `outcome="stripped +
  companion"`; the donor ends hot (Teff>400 kK by the last rows — a stripped-core terminal
  contraction, flagged for the Chunk-4b frontend to decide clip-vs-honor, the endgame-terminal-
  row precedent) and He-rich (Y_surf>0.5).
- **`/binary_track` + `/binary_track_meta`** — bypass `PROVIDER` (a time-series two-body result
  can't fit the single-star interface, AND it's the first genuine TIME SERIES among the
  siblings). Snap-always (the `/binary` precedent): 422 only on structurally invalid input
  (m1≤0, q outside (0,1], p≤0), `*_snapped_far` honesty flags in-band, 503 if unbaked.
- **`requires_posydon_data`** marker (conftest.py) + **15 tests** in `test_posydon.py`: snap
  honesty, both-states-valid at every step, mass_init constant vs current-mass routing scalar,
  the Gate-0 regression (crossing/widening/RLOF-fires/outcome) through the route, merger-track
  no-crash, route shape + 422s. 306 pytest total (was 287).
- **h5py** is a HOST-ONLY dependency (the bake script + `fetch_posydon.py`'s validator) — not
  added to `pyproject.toml`'s `dependencies` or `dev` extras, matching the existing precedent
  that `pymsg`/astropy (the spectra bakes) aren't declared there either; `pip install h5py` into
  the venv when baking, documented in the module docstrings.
- **Next = Chunk 4b** (the two-star TIME render, frontend): a system-time scrubber (age slider
  repurposed like the WD/WR/SN scrubs), both HR markers tracing live + crossing, the Roche panel
  (already built off the Götberg snapshot, Chunk 3) going LIVE off the track's real q(t)/a(t)/
  `mt_state`, curated demo systems before free q/P sliders. Plan
  `docs/plans/entwined-consort-inspiral.md` (§"Chunked build", Chunk 4b onward — architecture
  unchanged by the 4a build, now unblocked).

**PATH (b) CHUNK 4b BUILT 2026-07-07 (frontend, backend addition too — 310 pytest [+4],
Playwright 1440+390 zero console errors):** the two-star TIME render — the payoff Chunk 4a
unlocked, now visible end-to-end.
- **Entry — a deeper reveal INSIDE stripped-mode, not a new top-level mode** (mode stays
  `"stripped"` throughout, mirroring the WD thermal-pulse showcase precedent): a "Co-evolve
  the system through time" button row in the endgame bar offers **three curated demo
  systems** (the plan's de-risk choice over free q/P sliders) — the SAME donor
  (M1=8.83, q=0.6), only the initial period differs: P=0.1 d → merger, P=3.73 d → the
  Gate-0 stripped+companion system, P=5179 d → detached (never interacts). Fetches
  `/binary_track` once; "← Back to the snapshot" returns to the plain single-state donor
  view without leaving stripped-mode. Mass/[Fe/H] sliders DISABLE while a demo is live
  (POSYDON's grid is a separate axis from the MIST progenitor grid this demo isn't keyed
  on) — guarded in `tryResnap()` too so a stray resnap can't desync the display.
- **The age slider becomes a system-time scrubber** — plain index-linear over the
  pre-fetched steps (the WR sub-track idiom: no fetch per frame, no snapping, every row
  gets equal travel — the whole point is every in-between frame is real).
- **`hr.js` gains a genuinely new drawing mode** (`setBinaryTrack`/`updateBinaryIndex`/
  `clearBinaryTrack`, checked before `endgameMode`): BOTH stars' full tracks drawn
  Teff-colored with an INDEPENDENT past/future split at the scrubbed index each (star_2's
  array may run shorter after a merger — truncated at the first null, never `.filter()`ed,
  so index alignment with star_1 is preserved for every index before it). Markers labeled
  by FIXED IDENTITY ("donor"/"companion"), never by which currently masses more — the
  Algol reversal is the two markers crossing, never a relabel (the Chunk-1/Chunk-3
  convention-mismatch bug class, avoided by construction here). Axes auto-fit the WHOLE
  movie (both full tracks), unlike `setEndgame`'s marker-relative fit.
- **The Roche panel (Chunk 3) goes LIVE** — `roche.js` gained `drawLive` alongside the
  untouched static `drawPanel`. This needed a **backend addition** (advisor-flagged as the
  one genuine architectural fork, not deferrable — "Roche panel goes live" is IN the
  chunk's own definition): `binary.py`'s Roche engine refactored into a pure
  `_roche_geometry_from_params(q, m1, m2, separation_rsun, n_samples)` (donor at origin,
  companion at (1,0) — verified sane across q∈[0.1,9], well past the CSV path's fixed
  q=0.8) + a new `track_roche_geometry(steps)` that `posydon.py` **imports from
  `binary.py`** (a sibling calling a sibling — mirrors `structure.py`'s import of
  `lane_emden.solve_lane_emden`, so it does NOT violate the "no PROVIDER" rule; posydon.py
  stays h5py/POSYDON-free) and folds a `roche` block into every `/binary_track` step's
  JSON. **Decimated angular resolution** (40 vs the CSV path's 160 samples — measured
  ~2ms/step vs ~14ms/step; a naive full-res per-step computation would have cost ~3.8s on
  the 271-step Gate-0 track, an unacceptable request latency) keeps a full-track fetch
  under ~1s. No `BAKE_VERSION`/`CACHE_VERSION` bump (computed at request time from
  already-baked columns, the OSTAR-splice precedent).
- **Two real upgrades over the static Chunk-3 snapshot, both honesty-motivated:** (1) BOTH
  stars have a REAL modelled Teff/R at every POSYDON step (no "unknown donor giant
  temperature" gap the static panel has to schematic-tint around) — both draw as real
  Teff-colored discs, always. (2) whichever star `mt_state` flags as CURRENTLY overflowing
  (RLOF1→donor, RLOF2→companion, contact→both) gets its lobe filled (translucent, its own
  color) + the stream; the other stays an unfilled outline. **Measured gotcha, caption-
  owned:** the real photospheric radius does NOT itself cross the lobe outline during RLOF
  (measured on the Gate-0 track: R/a during RLOF1 ≈0.75–0.84× the lobe's own extent toward
  L1) — Roche overflow is a LOCAL excess at L1, not whole-photosphere inflation past the
  mean lobe radius, so the fill is an explicitly labeled schematic "transferring now" cue,
  not a naive radius-vs-lobe visual claim.
- **3D is free** — `star.update(s1, {companion: s2})` is the EXACT Chunk-2 companion call
  (`opts.companion`, `!eg` gate), now driven every scrub frame instead of once; zero
  `star.js` changes needed.
- **Advisor catch, fixed pre-commit:** comp/spectrum/sed/structure are NOT wired to the
  per-step scrub — they'd stay frozen at the Götberg stripped SNAPSHOT while HR/3D/Roche
  visibly animate beside them (unlike Chunk 2's fully-static mode, where a frozen panel
  matched a frozen everything-else). Fixed by CSS-hiding all four during `.binary-view`
  (auto-reverts on exit, the roche-panel mode-hidden precedent) rather than showing stale,
  misleading data.
- **Tests:** `track_roche_geometry` (duck-typed on 3 attributes, so no real POSYDON bake
  needed to test the geometry math) gets 4 new tests in `test_binary.py` (matches the
  single-node CSV engine at the same params; donor/companion lobe extents swap across a
  synthetic pre/post-reversal pair; `None` on a degenerate step, mixed-list index
  preserved) + 2 in `test_posydon.py` gated `requires_posydon_data` (the Gate-0 track's
  REAL lobes reshape + swap dominance through the real runtime; the `/binary_track` route
  carries a non-null `roche` block with the expected keys on every step).
- **Files:** `binary.py` (`_roche_geometry_from_params`, `track_roche_geometry`),
  `posydon.py` (imports + folds `roche` into the payload), `hr.js` (`setBinaryTrack` et
  al.), `roche.js` (`drawLive` + shared helpers factored out of the static path),
  `main.js` (`BINARY_DEMOS`, `enter/exitBinaryView`, `refreshBinary`, the age-slider
  dispatch branch, `tryResnap` guard), `index.html` (demo row + binary narration +
  `.age-binary`), `styles.css` (`.binary-demo-row`, `.age-binary`,
  `body.binary-view` rules).
- **Next = Chunk 4c (optional, unbuilt):** richer mass-transfer outcomes (common envelope,
  compact-object channels), more metallicities, free q/P sliders instead of the three
  curated demos, a population overlay (BPASS, out of this arc). None of these block the
  path (b) arc from reading as complete — the core "both stars co-evolving through time"
  payoff is now real end-to-end.

**PATH (b) CHUNK 4c BUILT 2026-07-07 (frontend-only, NO backend change, 310 pytest
UNCHANGED, Playwright 1440+390 zero console errors):** free M1/q/P sliders — the "free
q/P sliders" half of the optional follow-on list above (richer CE/CO-channel outcomes and
more metallicities are still unbuilt/unscoped).
- **Why no backend touch:** `/binary_track` was already fully general (snap-always over the
  WHOLE POSYDON grid, §6) — Chunk 4b's three curated demos were a UI de-risking choice, not
  a backend limitation. Confirmed by reading `posydon.py`/`api.py` before writing any code:
  `binary_track(m1, q, p, feh)` already accepts arbitrary floats and snaps to the nearest
  real track; `/binary_track_meta` already reports the grid bounds. So this chunk is a pure
  frontend addition: a fourth "Custom orbit…" button beside the three curated demos, revealing
  three sliders (M1, q, P) that drive the SAME `enterBinaryView`/`refetchBinaryCustom` path.
- **Slider math:** M1 and P span wide dynamic ranges (measured via `/binary_track_meta`:
  M1 3.92–286.4 M☉ ≈1.9 dex, P 0.1–5179.5 d ≈4.7 dex) — log-scale 0..1 position sliders, the
  ⁵⁶Ni-slider (`mniFromPos`/`posFromMni`) idiom, reused verbatim in shape
  (`customM1FromPos`/`posFromCustomM1`, `customPFromPos`/`posFromCustomP`). q spans <1 dex
  (0.05–0.99) and is a plain ratio, so its `<input type=range>` binds the physical value
  directly (min/max/value = the real q, no position indirection needed) — simpler where a
  simpler mapping is honest, not log-scaling by reflex.
- **Grid bounds fetched once, lazily:** `ensureBinaryMeta()` fetches `/binary_track_meta?feh=0`
  on first use (memoized promise, mirrors the pattern of fetching-once-then-caching elsewhere)
  and clamps the starting `customM1/Q/P` (seeded from the Case-B demo's node, 8.83/0.6/3.73)
  into the real bounds before configuring the sliders — never hardcodes the grid span.
- **Honesty line, not the raw drag:** `updateBinaryCustomNote()` always states the TRUE
  snapped node the backend actually returned (`m1_init_msun`/`q_init`/`p_init_d`/`outcome`),
  never the dragged number, plus an off-grid note built from the `*_snapped_far` flags
  `/binary_track` already computes — the same "report the true node" discipline as every
  other snap-to-grid control in this project (WD/WR mass re-snap, the stripped-star toggle).
- **A real timing bug caught by the FIRST Playwright pass, fixed before commit:** the initial
  draft revealed the custom-sliders panel (`els.binaryCustomControls.hidden = false`)
  immediately on click, BEFORE the `/binary_track` fetch resolved. A drag during that
  "Fetching…" window landed while `binaryView` was still `false`, and `refetchBinaryCustom`'s
  own `!binaryView` guard silently dropped it — the slider's `customM1/Q/P` state updated, but
  no fetch fired, so the panel looked live but wasn't (confirmed via a Playwright script:
  the note stayed empty/stale for ~1.5–2.5s on the FIRST-ever custom entry, since that request
  also cold-loads the 142 MB baked `.npz` into the module-level cache). **Fixed by moving the
  panel reveal to AFTER `binaryView = true`** (the same point the demo buttons/Back button
  already become interactive via the `body.binary-view` CSS class) — nothing in this view is
  clickable until the fetch actually lands, now including the sliders.
- **Verified via a Playwright script** (poll-based waits on the note text actually changing,
  not fixed timeouts — the cold-load timing above would have flaked a fixed-timeout test too):
  entering "Custom orbit" shows the Case-B default (M₁=8.83, q=0.6, P=3.73 → stripped +
  companion); dragging P to the log-scale floor re-snaps to the REAL merger node (P=0.1 →
  outcome "merger"); dragging M1 to the ceiling re-snaps far off-grid (M₁=202, q=0.45 →
  "merger", flagged "snapped far off-grid on M₁, q" — an honest report, not a silent clamp);
  the age/system-time scrubber stays live throughout; "← Back to the snapshot" hides the
  panel; re-entering "Custom orbit" preserves the last-dragged values. Zero console errors at
  1440×1000 and 390×844. A full-page screenshot confirmed the panel lays out cleanly under the
  three curated-demo buttons and the Roche/HR/3D panels keep animating correctly beside it.
- **Files (frontend-only):** `index.html` (`#binary-demo-custom` button + the
  `#binary-custom-controls` sliders block), `styles.css` (`.binary-custom-controls`/
  `.binary-custom-row` layout), `main.js` (`binaryMeta`/`ensureBinaryMeta`, the
  `customM1/Q/P` state + log-scale mapping helpers, `configureBinaryCustomSliders`,
  `updateBinaryCustomNote`, `_applyBinaryTrackData` factored out of `enterBinaryView`,
  `refetchBinaryCustom`, the debounced slider listeners, `enterBinaryView`'s `"custom"`
  branch, the panel-hidden resets in `exitBinaryView` + the two other binary-state-reset
  sites).
- **Path (b) is now fully built end to end (Chunks 1–4c).** What remains is explicitly the
  UNSCOPED tail of the optional list: richer mass-transfer outcomes (common envelope, the
  CO-HMS/CO-HeMS compact-object grids — ties to the SN/remnant arc), the other 7 downloaded-
  but-unbaked metallicity tarballs, and a population overlay (BPASS, a separate sibling). None
  of these were attempted this pass — each needs its own recon/gate before a build, the same
  discipline every prior chunk followed.

**PATH (b) CHUNK 4d BUILT 2026-07-08 (frontend-only, NO backend change, Playwright 1440+390
zero console errors):** the [Fe/H] metallicity-bucket picker — the frontend catch-up once
[[star-sim-hosted-data-assets]] finished baking+hosting the FULL 8-bucket POSYDON axis
([Fe/H] ≈ −4.0…+0.30, up from just solar).
- **Why no backend touch:** `/binary_track`/`/binary_track_meta` already took a `feh` param
  and `binary_track_meta` already served `available_feh` (the sorted bucket list) — `main.js`
  just had it hardcoded to `feh=0` at both fetch call sites (`enterBinaryView` and the old
  `refetchBinaryCustom`). Confirmed by reading `posydon.py`/`api.py` before writing any code.
- **A `<select id="binary-feh">`** in `binary-demo-row`, populated from the real
  `available_feh` list (never hardcoded — a future bucket just appears). Deliberately
  **NOT** gated by `body.binary-view .binary-demo-btn { display:none }` like the curated/
  custom demo buttons — `.binary-feh-label` is excluded from that hide rule, so it stays
  visible and usable WHILE a co-evolving movie is showing, letting a user compare
  metallicities without leaving the view.
- **Orthogonal axis, mirroring the MIST mass/[Fe/H] split:** a new `_binaryParamsFor(demoKey)`
  helper resolves ONLY (m1,q,p) — curated table lookup or the custom sliders — and [Fe/H] is
  applied separately by the caller via `customFeh`. `refetchBinaryCustom` was renamed/
  generalized to **`refetchBinaryTrack`**: it now re-fetches whichever `binaryDemoKey` is
  currently active (curated OR custom), not just "custom" — so the [Fe/H] select can drive a
  live re-fetch of a curated demo too, which the old custom-only function couldn't do.
- **Bounds are per-bucket, so ordering matters:** each POSYDON metallicity is its own baked
  grid with its own M1/q/P extent (measured: they turned out similar in this case, but not
  guaranteed). The `[Fe/H]` `change` handler AWAITS `ensureBinaryMeta()` (which re-fetches
  `/binary_track_meta` for the new bucket, clamps `customM1/Q/P` into its bounds, and
  repositions the custom sliders) BEFORE calling `refetchBinaryTrack()` — avoiding a moment
  where the just-fetched track reflects the OLD bucket's dragged values while the slider has
  already silently jumped to a new clamped position.
- **A new always-visible `binary-feh-note`** (unlike the M1/q/P `binary-custom-note`, which
  stays inside the "Custom orbit"-only hidden block) states the TRUE snapped `[Fe/H]` bucket
  the backend returned, plus a snapped-far flag — visible for every demo, curated or custom,
  since metallicity now applies universally. `updateBinaryCustomNote` also gained
  `feh_snapped_far` in its far-flag list for the custom-orbit case.
- **Verified end-to-end via a Playwright script against a live `uvicorn` dev server** (not
  just unit/syntax-checked): `/binary_track_meta?feh=0` confirmed all 8 real buckets
  (`[-4.0, -3.0, -2.0, -1.0, -0.69897, -0.34679, 0.0, 0.30103]`); the select populates with
  exactly these; entering the curated "Case-B" demo at solar then switching to [Fe/H]=−1.0
  fires BOTH `/binary_track_meta?feh=-1` and `/binary_track?...&feh=-1` and the note updates;
  on "Custom orbit" with M1 dragged to 280 (snaps to the grid ceiling ~286 M☉, outcome
  "stripped + companion" at solar) switching to the most metal-poor bucket ([Fe/H]=−4.0) at
  the SAME (M1,q,P) genuinely changes the outcome to **"stable mass transfer"** — real
  physics from the metallicity axis, not a cosmetic label swap. Zero console errors at
  1440×1000 and 390×844; screenshots confirmed the `[Fe/H]` select + note lay out cleanly on
  both widths, wrapping under the demo-back button on phone width without overlap.
- **Files (frontend-only):** `index.html` (`#binary-feh` select + `#binary-feh-note`),
  `styles.css` (`.binary-feh-label`/`.binary-feh-note`, the `.binary-demo-btn`-hide-rule
  exclusion), `main.js` (`customFeh`/`binaryMetaFeh`/`binaryMetaPromiseFeh` state,
  `populateBinaryFehOptions`, `_binaryParamsFor`, `refetchBinaryTrack` (renamed/generalized
  from `refetchBinaryCustom`), `updateBinaryFehNote`, the select's `change` listener, the
  `ensureBinaryMeta()` prewarm call added to `enterStripped`).

**PATH (b) CHUNK 4 RECON DONE 2026-07-06 (superseded by Chunk 4a BUILT above):**
the on-ramp to a real binary grid = "both stars co-evolving on the HR *through time*" (the one thing the
Götberg snapshot can't give). **Advisor-steered discriminator, measured: POSYDON, NOT BPASS.**
- **POSYDON** (Fragos+2023 / v2 Andrews+2024) = individual **co-evolved binary TRACKS** — MESA-binary
  HDF5 with the full time history of BOTH stars + the orbit (`history1`/`history2`/`binary_history`,
  cols off `dtype.names`; `final_profile1/2`, `initial/final_values`). **The target.** Zenodo DR2 (DOI
  10.5281/zenodo.15194708, code v2.0.0, CC-BY): 8 metallicities, ~10 GB tarball each (gitignored,
  never committed), 2 single + 5 binary grids per Z; the relevant one is **HMS-HMS**; axes M1, q=M2/M1,
  P (2D-in-(q,P) per M1 — richer than Götberg's 1D-fixed-q=0.8).
- **BPASS** = population synthesis (integrated SEDs / counts / SN rates vs age & Z) — NOT individual
  tracks → a *different feature* (a population-spectrum sibling), a separate future thread. Don't conflate.
- **`fetch_posydon.py` BUILT** = the fetch recipe + h5py validator (host-side USER handoff, `fetch_gotberg`
  precedent — multi-GB/gated → recipe not headless pull; prints the real HDF5 schema once a slice lands).
- **Architecture note (the scope the user weighs):** every sibling so far snaps to ONE state; a POSYDON
  track is a TIME SERIES of a two-body system → a real time axis + paired-state shape = materially bigger
  than `binary.py` (own h5py parser, no POSYDON/provider import; likely a new `posydon.py`+`/binary_track`
  emitting paired states; open Q = how a two-star inspiral rides the frontend).
- **DESIGN PASS DONE (user chose "draft the build design first"):** full architecture in a dedicated plan
  `docs/plans/entwined-consort-inspiral.md` — the time-series two-body sibling `posydon.py` + `/binary_track`
  (paired StellarStates + orbital scalars per step), Gate-0 measure-first, chunks 4a (data+parser) / 4b
  (system-time HR inspiral + LIVE Roche panel: lobes/stream driven by real q(t),a(t),RLOF flags) / 4c
  (CE/merger/CO channels). **Advisor catch baked in:** "no POSYDON" is a RUNTIME rule, NOT extraction —
  the raw Zenodo grid is packed `PSyGrid` (`oneline`+`history`, all tracks concatenated; the clean
  `history1`/`history2` shape is the `PSyRunView` code API), so extraction may use POSYDON's own loader
  HOST-SIDE to export flat per-track files (the MESA-structure precedent); only runtime `posydon.py` stays
  POSYDON-free. Separation = the `binary_separation` column directly (Kepler fallback). **The BUILD is not
  started — gated on the ~10 GB data handoff (a fetch I cannot run) + the user's slice choice.**

**PATH (b) CHUNK 2 BUILT 2026-07-06 (frontend-only, 279 pytest UNCHANGED, Playwright 1440+390 zero
console errors):** "the companion drawn in 3D" — the accretor as a REAL second sphere beside the
stripped donor. **NO backend touch** (the companion `StellarState` is already served by `/binary_pair`).
- **The honesty split (the load-bearing call, advisor-settled):** the companion *sphere* is Tier 1/2
  honest — a real modeled single-star state (from `PROVIDER`), so drawn with the FULL surface shader
  (real Teff color, real relative size, granulation, limb darkening, exposure), UNLIKE the evocative
  corona/wind/fireball. What is NOT modeled is the geometry BETWEEN the stars (no separation/orbit/system-
  inclination in the data) → the side-by-side placement is SCHEMATIC, caption-owned (the un-drawn-orbit
  precedent): "Each star is a real modeled star, but their side-by-side placement is schematic — the
  separation and orbit are not modeled."
- **`star.js`:** a 2nd `companion` sphere (own `ShaderMaterial` reusing `SURFACE_VERT/FRAG` — per-star
  uniforms differ, can't share `surfaceMat`) + a `companionGlare` quad (the 7–27 kK accretor would blaze;
  an un-glaring companion beside a blazing donor misreads as "less real"); NO 2nd corona (a hot star is
  near-glowless). `update(state, opts)` gains `opts.companion`: donor LEFT / companion RIGHT via direct
  `mesh.position.x` (camera-facing quads stay parallel under an x-shift → no billboard math), relative
  log-size PRESERVED (the companion reading BIGGER than the compact donor IS the Algol reversal in 3D),
  then a single shared `applyCompanionScale` fit factor shrinks both to the tighter frame axis (horizontal
  binds on phone, the WR `FRAME_HALF_H` precedent), re-run every frame in `animate()` so a live resize
  refits. Both glares TEMPERED ×0.6 (the glare-merge trap — two additive blooms washing the lane between
  the stars). `companionMat.uTime` driven in `animate()` (else the boil freezes — the fireball precedent).
  All offsets + `.visible` set UNCONDITIONALLY → toggle-off re-centers the donor + hides the companion =
  byte-identical (advisor code-traced: unconditional scale writes + the `else` branch's `position.x=0`).
- **`main.js`:** `refreshStripped` threads `{ companion: strippedData.companion.state }` to `star.update`
  when `companionOn`; the caption gains the schematic-layout honesty sentence.
- **Measured across the grid (the advisor's high-mass concern, answered by the data):** the stripped donor
  stays COMPACT at every node (R 0.16→0.88 R☉, mass 2→18) while the MS companion is large (1.83→7.76 R☉),
  so "companion bigger" reads everywhere; low-mass = a clean color contrast (2 M☉: donor blue-white 20 kK,
  companion warm-yellow 7 kK — the sub-luminous donor beside the optically brighter, cooler companion).
- **Scope call on record (advisor-accepted):** NO 3D text labels this chunk — the caption + HR labels +
  size/color carry identity; left=donor is a convention matching the HR's blue-left.
- **Files (frontend-only):** `star.js` (companion sphere + `companionGlare` + `applyCompanionScale` + the
  two-body block in `update` + the `animate` uTime/refit), `main.js` (`refreshStripped` thread + caption).
- **Next (path (b) Chunk 3+):** the mass-transfer geometry / Roche lobes (a genuinely new two-star render),
  then the on-ramp to a real binary grid (POSYDON/BPASS).

**Path (a) is COMPLETE** (Chunks 1–3); **path (b) Chunks 1–4d are ALL BUILT** — the Götberg-snapshot
chunks (HR reversal, 3D companion sphere, Roche geometry), the POSYDON co-evolved-binary arc
(Chunk 4a's backend + Chunk 4b's frontend two-star TIME render, the Roche panel gone live),
Chunk 4c's free M1/q/P sliders (a fourth "Custom orbit" picker beside the three curated demos,
no backend change — `/binary_track` was always general), and Chunk 4d's [Fe/H] metallicity-bucket
picker (frontend-only, wiring the UI up to the full 8-bucket POSYDON axis the backend had already
baked+hosted — [[star-sim-hosted-data-assets]]). The core "both stars co-evolving through
time, the Algol reversal as a movie" payoff is real end-to-end, and now explorable at ANY real grid
node AND any real metallicity bucket, not just solar. What remains is explicitly unscoped: richer
mass-transfer outcomes (CE/compact-object channels), a population overlay (BPASS). Related:
[[star-sim-phase5-spectra]] (the sibling spectrum cubes), [[star-sim-wr-wd-endgame-plan]] (the WR/WD
spectrum cubes this mirrors + the single-star WR it complements), [[star-sim-rotation-subpop-atlas]]
(Tier D binarity), [[star-sim-supernova-remnant-endgame]] (sibling pattern).
