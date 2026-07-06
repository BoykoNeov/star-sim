---
name: star-sim-binary-stripped
description: Binary-stripped-star sibling (binary.py + /binary) — Götberg 2018 hot He-star, the ~70% WR channel; path (a) Chunks 1–3 complete (backend + what-if mode + spectra), path (b) Chunks 1–2 built (the companion drawn on the HR via /binary_pair, then as a real 3D sphere beside the donor; no new dataset).
metadata:
  type: project
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

**Path (a) is COMPLETE** (Chunks 1–3); **path (b) Chunks 1–2 (HR reversal + 3D companion sphere) are now
BUILT** — the full two-star co-evolution (Roche geometry, a real binary grid) continues in path (b) Chunks 3+. Related:
[[star-sim-phase5-spectra]] (the sibling spectrum cubes), [[star-sim-wr-wd-endgame-plan]] (the WR/WD
spectrum cubes this mirrors + the single-star WR it complements), [[star-sim-rotation-subpop-atlas]]
(Tier D binarity), [[star-sim-supernova-remnant-endgame]] (sibling pattern).
