---
name: star-sim-binary-stripped
description: "Binary-stripped-star sibling (binary.py + /binary) — Götberg 2018 hot He-star, the ~70% WR channel; path (a) Chunks 1–3 complete. Path (b) Chunks 1–3 built (HR reversal, 3D companion, Roche geometry off the Götberg snapshot); Chunk 4a BUILT — the POSYDON co-evolved-binary time-series sibling (posydon.py + /binary_track), Gate 0 closed. Chunk 4b (frontend two-star time render) next."
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

**PATH (b) CHUNK 4a BUILT 2026-07-07 (backend vertical, solar-first, 302 pytest [+15]):** the
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
  no-crash, route shape + 422s. 302 pytest total (was 287).
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

**Path (a) is COMPLETE** (Chunks 1–3); **path (b) Chunks 1–3 (HR reversal, 3D companion sphere, Roche
geometry) are BUILT off the Götberg snapshot, and Chunk 4a (the POSYDON co-evolved-binary backend, Gate
0 closed) is now BUILT too** — only Chunk 4b (the frontend two-star time render) remains before the
full two-star co-evolution movie is real end-to-end. Related:
[[star-sim-phase5-spectra]] (the sibling spectrum cubes), [[star-sim-wr-wd-endgame-plan]] (the WR/WD
spectrum cubes this mirrors + the single-star WR it complements), [[star-sim-rotation-subpop-atlas]]
(Tier D binarity), [[star-sim-supernova-remnant-endgame]] (sibling pattern).
