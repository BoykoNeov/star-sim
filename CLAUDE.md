# Star Simulator — working notes for Claude

Interactive stellar simulator: pick a star's mass & metallicity, watch it evolve
(HR diagram + composition panel + real-time 3D star). Teaching **and** beauty.

**The full spec is `STAR_SIM_SPEC.md` — read it first.** This file is the short
operational layer on top of it; it does not repeat the spec.

## The one rule that overrides everything (spec §3)

Everything the user sees is a function of a single `StellarState`, produced
**only** through the `StellarStateProvider` interface. **No consumer may know
where the state came from.**

- `state.py` / `provider.py` define the boundary. `StellarState` is a plain
  dataclass — keep web/data-source concepts out of it.
- The HR diagram, 3D star, and composition panel consume `StellarState` only.
  A consumer (or the API) that imports a provider's internals — MIST columns,
  file formats, interpolation guts — **is a bug**, not a shortcut.
- Provider swaps happen in exactly one place: `PROVIDER` in `api.py`. Going
  deeper (Stub → MIST → live solver) must change nothing downstream.

## The gotcha that bites everyone (spec §6): interpolate on EEP, not age

Two stars of different mass at the *same age* are in different evolutionary
phases. Interpolating raw tracks against age blends a main-sequence star with a
red giant → physical nonsense. **Always interpolate at fixed EEP** (equivalent
evolutionary point), then map age ↔ EEP. The test for it: an interpolated
intermediate-mass track must lie *between* its neighbors on the HR diagram at
every phase. This matters the moment `MISTProvider` lands; the stub sidesteps it.

## Where things are

- `backend/star_sim/` — `state.py`, `provider.py` (the §3 boundary),
  `providers/mist.py` (the real v1 provider), `providers/mesa.py` (the **second**
  real provider — offline MESA `history.data`, a different on-disk format behind
  the same boundary; **multi-metallicity by snapping** — `[Fe/H]` buckets, snap
  feh-then-mass, no cross-mass/cross-feh interp; used to **validate MIST**),
  `providers/stub.py` (data-free fallback),
  `providers/_vendor/read_mist_models.py` (MIST's own parser, §6),
  `fetch_mist.py` / `fetch_mesa.py` (build-time grid fetches), `lane_emden.py`
  (the Phase 3 §8 polytrope solver — a **sibling** to the §3 spine, not a
  provider), `spectra.py` (the Phase 5 synthetic-spectrum runtime — also a
  sibling), `structure.py` (the **real interior-structure** sibling — offline MESA
  radial `profile.data` snapshots behind `/structure`; the honest successor to
  Lane–Emden, its own MESA-profile parser, snaps (mass,[Fe/H],age) to the nearest
  saved snapshot, never imports a provider), `api.py` (FastAPI, the swap point; also
  hosts `/polytrope`, `/structure` and `/spectrum`, the routes that do NOT go through
  `PROVIDER`).
- `backend/tests/` — §10 sanity checks: `test_mist_provider.py` (Sun anchor,
  ZAMS spread, EEP-between-neighbors, plus the [Fe/H]-axis tests: lies-between
  metallicities, held-out-grid accuracy, dead-corner exclusion),
  `test_mesa_provider.py`, `test_mesa_vs_mist.py` (the **measured** MESA-vs-MIST
  cross-validation, matched on Z + central-Xc via the public `track()` API),
  `test_stub_provider.py`, `test_lane_emden.py` (§8 polytrope validation),
  `test_spectra.py`, `test_endgame.py`, `test_structure.py` (the real MESA
  interior-structure sibling — convective-envelope-over-radiative-core, order-of-SSM
  central values, monotone centrally-concentrated ρ, canonical-polytrope overlay,
  honest snapping). Skip markers in `conftest.py` gate by data present
  (`requires_mist_data`, `requires_mist_multifeh`, `requires_mist_heldout_feh`,
  `requires_mesa_data`, `requires_mist_lowz`, `requires_spectra_data`,
  `requires_structure_data`, …).
- `frontend/` — static SPA (no bundler): `index.html`, `styles.css`,
  `src/{main,star,hr,comp,lane,structure,spectrum,sed,scale,classify,color,canvas,layout,tooltip,sn}.js`.
  `sn.js` is the SN endgame's cited observed-photometry dataset (SN 1987A ⁵⁶Co tail +
  SN 1999em IIP plateau, published bolometric fits — the Tier-1 overlay anchor); `hr.js`
  gains a `setSupernova()` light-curve view (L vs **linear** days → the straight ⁵⁶Co tail).
  `layout.js` is the draggable/responsive **dashboard** layer (a reorder-in-flow
  sortable over the flex-wrap panel container, see [[star-sim-draggable-responsive-panels]]).
  `comp.js` is the §5.4 composition panel — **three** views via `setMode` (bulk
  H/He/Z; per-element detail, 14 metals + linear/log `setScale`, `mode="cno"` id
  kept; light-element `mode="light"` Li/Be/F log-forced). `lane.js` is the Phase 3
  §8 Lane–Emden interior panel (a self-contained sibling driven by the polytropic
  index `n` alone, never wired into `refresh()`). `structure.js` is its **honest
  successor** — the real MESA interior-structure panel: a live consumer wired into
  `paintState` that fetches `/structure` for the marker's (mass,[Fe/H],age), draws
  ρ(r)/T(r)/X(r) center-normalized vs r/R + shaded convective zones + the two
  canonical polytrope overlays (n=1.5/3, references, not fitted), and labels the
  nearest saved snapshot (jumps between snapshots; snapped-far note when off-grid).
  `star.js` is the Phase 2 §7
  shader (Teff→color × H_p granulation × limb darkening × streak-proof rotation +
  activity corona quad). `color.js` is the reference Planck→CIE→sRGB color pipeline
  (`teffToLinearRGB` for the shader, `teffToRGB`/`teffToCSS`/`wavelengthToCSS` for
  the 2D UI). `canvas.js` is the shared HiDPI `fitCanvas` helper. Three.js via CDN
  importmap, served by FastAPI. Pedagogy is hover-revealed (a `?` glyph + dotted
  status-line tokens, all via one `tooltip.js` singleton). The age window + snap-tick
  landmarks are derived from the `/track` result itself (single source), not a
  separate `/age_range` fetch.
- `data/` — downloaded grids (gitignored). Fetch once: `python -m star_sim.fetch_mist`.

## Commands

```bash
# backend (from backend/)
python -m venv .venv && . .venv/Scripts/activate   # Windows; or .venv/bin/activate
pip install -e ".[dev]"
python -m star_sim.fetch_mist                      # one-time: fetch MIST grids (~180 MB) into data/
uvicorn star_sim.api:app --reload                  # serves API + frontend at :8000
pytest                                             # run sanity tests (MIST tests skip if grids absent)
```

Open http://127.0.0.1:8000 — drag the mass slider; the whole UI transforms.

## Current status & what's next

Phases 1–5 are built; the app is feature-complete for the current scope. This is
**current state**, not a changelog — the full per-feature history lives in git, the
`docs/memory/` topic files (detailed, recalled on demand), and `docs/plans/`
(designs). The `[[links]]` below point at the topic file that holds the detail.

### Providers (the §3 spine)
- `PROVIDER` in `api.py` is **`MISTProvider`** — the live provider. Real MIST v2.5
  tracks, EEP-fixed **2D (mass × [Fe/H])** interpolation (blend-then-invert), full
  mass grid **0.1–300 M☉** per metallicity, window **ZAMS → end of early-AGB**
  (TPAGB thermal pulses hard-stopped — §6 "messy, defer"). Non-rectangular valid
  domain (`mass_range(feh)` tightens the floor for [Fe/H]>0). Per-grid
  `_parsed_tracks.npz` parse cache (**`CACHE_VERSION` 11**; ~50–110 s cold reparse on
  a bump, ~0.35 s warm). A **third selection axis — rotation `vvcrit`** — is on the
  boundary and **wired end-to-end (rotation Chunks 1–4 DONE — arc complete)**: grids partition into one
  `_Axis` per rotation rate keyed by `(feh, vvcrit)`, the provider **snaps** between
  buckets (MIST ships only {0.0, 0.4}, no third grid to blend) and interpolates
  mass×[Fe/H] *within* a bucket. `track()/state_at()/endgame()/mass_range()/age_range()`
  take `vvcrit=0.0` (default = non-rotating, so the live spine is byte-unchanged) and the
  API exposes it as a query param + a `/rotation_status` route (the data-derived honesty
  gate). Rotation is **mass-ramped at the ~1.2 M☉ Kraft break** (bit-identical below it).
  `surf_avg_v_rot` is now surfaced as the real **`v_rot_kms`** (0 non-rotating/below the
  break, real above). Frontend: a **unified "Rotation" control** below [Fe/H] with two
  regime-gated facets — the vvcrit **track** toggle (massive, gated by `rotation_status`)
  + the rotation-**period** slider (cool-MS activity, the SED slider relocated here, gated
  by the dynamo domain). **Chunk 4 (data) done**: m075/m050/p050 vvcrit0.4 fetched, so the
  rotating axis spans the **full [Fe/H] axis −1.0→+0.5** (coextensive with non-rotating);
  `rotation_status.has_grid` honest across it. [[star-sim-rotation-subpop-atlas]], [[star-sim-mist-provider]],
  [[star-sim-composition-panel]], [[star-sim-nonthermal-sed-plan]].
- `MESAProvider` — the **second real provider** (offline MESA `history.data`, a
  different on-disk format behind the same boundary), used to **validate MIST**.
  Discrete-grid, snap-to-nearest, **multi-metallicity by snapping** (no
  cross-mass/feh interp). Two Z buckets on disk: bearums [Fe/H]≈−0.84
  (1/2/4/6/10/14/20 M☉) + a self-run solar Z=0.0152 bucket (1/2/6 M☉, Docker MESA
  r24.03.1). Payoff = **measured** MESA-vs-MIST cross-validation matched on Z +
  central-Xc. **Opt-in** (not the live PROVIDER). [[star-sim-phase4-mesa]]; recipe
  `backend/docs/mesa_solar_recipe.md`.
- `StubProvider` — data-free fallback, physically *flavored* not modeled.

### Composition (§5.4 panel)
- `StellarState` carries `metals_surf`/`metals_core` **dicts** (a breakdown of Z,
  not flat fields — `state.py` was untouched across every element add). Per-element
  set is **sixteen**: Li·Be·C·N·O·F·Ne·Na·Mg·Al·Si·P·S·Ca·Ti·Fe (sum ~0.99 Z).
  Adding more individual metals is a dead end for payoff (Na/Al/P are invisible
  floor-huggers; Cr/Mn/Ni aren't in MIST v2.5's network; boron's only isotope is
  radioactive b8). [[star-sim-phase4-cno]].

### Spectra (synthetic-spectrum panel — a **sibling**, not a provider)
- `/spectrum` bypasses `PROVIDER` (like `/polytrope`). Engine = MSG/pymsg
  **build-time bake** → void-filled flux cube `data/spectra/spectra_grid.npz`
  (gitignored) → pure-Python scipy runtime `spectra.py`. Current cube: 3-grid Teff
  axis **2300–55000 K**, **142×12×11×2400** (Göttingen cool <3500 + CAP18
  Teff/[Fe/H]/logg + OSTAR2002 hot >30000). The bake is axis-generic (single→
  multi-grid via `--cool-grid`/`--hot-grid`, **no `BAKE_VERSION` bump**). Payoffs:
  [Fe/H] deepens metal lines; He I/II `minTeff`-gated; TiO `maxTeff`-gated;
  past-ceiling no-model notice keyed off `teff_max`. **v sin i line broadening** (the
  rotation-axis spectral follow-on, `spectrum.js` only): a client-side convolution with
  Gray's rotation profile (ε=0.6, per-pixel width Δλ_L=λ·v sin i/c, EW-conserving),
  driven by the marker's real `v_rot_kms` **edge-on** (sin i=1, the max projection — no
  inclination slider, it'd be incoherent with no oblateness model); scoped to the main
  absorption cube (WD/WR/SN exempt), no refetch, caption gated ≥120 km/s (the ~1-px
  R≈2400 floor). Backend byte-unchanged. [[star-sim-phase5-spectra]],
  [[star-sim-rotation-subpop-atlas]]; recipe `backend/docs/msg_spectra_build_recipe.md`;
  plan `docs/plans/graceful-toasting-thimble.md`.

### Endgame (WR/WD — `/endgame` goes **through** PROVIDER; an endgame state IS a StellarState)
- Both endgames are already on disk in the MIST tracks (clipped by the `phase>=5`
  window). `endgame()` is on the Protocol (MESA/Stub → `type="none"`),
  `EndgameResult` dataclass, snaps both mass+feh, data-derived classify (φ9→WR /
  φ6-or-logg>7→WD / **evolved-massive→SN** [reached CHeB φ≥3 AND final mass > 1.4 M☉
  Chandrasekhar] / else none). The SN test was once a row-count artifact (`r0≤r_last`,
  "has a post-window row") that silently dropped massive ROTATING & very-massive-metal-
  poor stars into "none" → the gateway said *nothing* for stars that core-collapse;
  fixed to classify by the evolved/massive end state (the Chandrasekhar floor keeps a
  low-mass blue-HB star ending at CHeB from being mislabelled SN). WD path = a reversible gateway button
  at the slider limit → log-cooling-age scrubber + WD 3D shader + structure panel +
  mass–radius re-snap. WR path (Chunk 4) = the matching `→ Continue: Wolf–Rayet` button
  → reversible `wr-mode`: index-linear scrub over the φ9 sub-track (WN→WC→WO landmark),
  HR axes to ~316 kK / logL 7, the **normal comp views** (the stripped surface IS the
  story — no custom cross-section), WN/WC/WO subtype from surface composition, mass-stays-
  live re-snap, end caption narrates the un-modeled core-collapse. WR 3D (Chunk 5) = the
  **optically-thick-wind shader** (`star.js` `WIND_FRAG` + `wind` mesh): an additive halo
  over the opaque hot sphere — electron-scattering haze brightest at the limb (pseudo-
  photosphere) + outward-advected value-noise filaments; reach/density read from `Z_surf`
  (smooth WN → clumpy WC/WO), color = honest Teff blackbody (no chemistry hue — it'd
  contradict the spectrum placeholder), intensity a gentle clamped `L` tie (NOT a measured
  Ṁ). **Fit-to-frame extent** (`applyWindScale`, recomputed each frame) — the WR scrub opens
  on a huge R≈33 R☉ star, so a constant extent would clip the viewport. WD spectra (Chunk
  **6a**) = a **second** spectrum sibling `/wd_spectrum`: a separate rectangular Koester DA
  cube (82 Teff × 13 log g, pure-H so no [Fe/H], host-baked — no Docker/pymsg via
  `fetch_koester.py` + `scripts/bake_wd_spectra.py`), `spectrum.js` `updateWD` switched in by
  surface gravity (`refreshWD`: log g ≥ 6.0 **or Teff > 55 kK** = the main cube's OSTAR
  ceiling → WD cube, else main cube, so TPAGB-giant rows show their real spectrum and the
  contracting ~55–80 kK rise routes to the WD cube too — no "no model" flash). **DC** Planck
  continuum below the ~5000 K floor
  (no Balmer painted on a cold cinder). WD spectra (Chunk **6b**) = the **TMAP** NLTE hot
  splice: `fetch_tmap.py` (SVO `tmap` H-rich Hemass=0 slab, 72 models) → `bake_wd_spectra.py
  --tmap-dir` splices the >80 kK nodes onto the hot end of the SAME WD cube (now 93 Teff ×
  13 log g, `koester2-DA+TMAP-CSPN`), so the ~100–190 kK post-AGB **central star** shows a
  real spectrum (`regime="CSPN"`, weak Balmer on a steep blue continuum) where the old
  no-model frame was; residual no-model re-pointed at TMAP's 190 kK ceiling (only ~300–400 kK
  massive-progenitor central stars). Measured: **no ×π×10⁸** (SVO ascii is physical; seam
  ratio 1.005–1.021 → no rescale), log-linear blue-gap fill (TMAP starts 3200 Å), log g-clamp
  honest (optical Δ 0.03 vs 0.41 for a cooling DA), **no `BAKE_VERSION` bump** (OSTAR-splice
  precedent). WR spectra (Chunk **7**, the last chunk) = a **third** spectrum sibling
  `/wr_spectrum` over the **PoWR** wind-emission grids, keyed on the WR axes **(T\*, Rt)** not
  (Teff, log g) — `fetch_powr.py` (per-grid tarballs, host-only) → `bake_wr_spectra.py`
  (**flat-node** cube, NOT rectangular void-fill — the (T\*, Rt) footprint is a ragged
  parallelogram with an empty hot+dense-wind corner) → `spectra.py` `wr_spectrum_data` →
  `spectrum.js` `updateWR` (an **emission** draw: continuum-normalized so lines stand UP,
  WR species guides). **Narrow-GO, measured first (the 7a gate):** mapping real MIST WR states
  (**T\*≈Teff**, **Rt** from a Nugis–Lamers Ṁ — `star_mdot` stays OFF StellarState) shows PoWR
  covers only the cool, H-rich **WNh entry** (~10%); the stripped core is the hot, compact
  *evolutionary* surface (Teff 150–262 kK ≈ T\*, far hotter/denser-wind than any *observed* WR
  — the evolutionary-vs-spectroscopic Teff gap), so the bulk shows an honest **no-model** frame.
  Snaps to nearest node (subtype WNE/WNL/WC from surface composition, metallicity gal/lmc/smc
  from [Fe/H]). **Chunks 1–7 ALL BUILT — the WR/WD endgame arc is complete.**
  [[star-sim-wr-wd-endgame-plan]]; plan `docs/plans/smoldering-cinder-gateway.md`, spectra
  recipe `backend/docs/msg_spectra_build_recipe.md §7a/§8/§8b/§9`.

### Supernova (core-collapse — fills the dead `type="SN"` branch; a **hybrid sibling**, not on the tracks)
- The third fate. Unlike WD/WR (already on the MIST tracks), a supernova is a **computed
  semi-analytic model** — the tracks end at collapse — so it's a **sibling** (`supernova.py`,
  like `lane_emden`/`spectra`), with classification + progenitor scalars staying on the spine.
  **Chunk 1 BUILT (backend vertical, no frontend):** `EndgameResult` gained the SN-branch-only
  scalars `pre_sn_radius_rsun`/`he_core_msun`/`co_core_msun`/`h_retained` (`None` for WD/WR/none
  and for Stub/MESA); `CACHE_VERSION` **11→12** parses `he_core_mass`/`c_core_mass`/`o_core_mass`
  (the **Mcur pattern** — cached, read off the snapped track, never blended). **R₀ = max radius
  over the final-phase rows EXCLUDING the terminal EEP row** (the open calibration knob, settled:
  the low-g terminal artifact can spuriously inflate *or* shrink R; max beats the median, which
  underestimates). `supernova.py` is a **pure sibling** (imports only `state.StellarState`,
  never the provider): a frozen `Progenitor` input (the route builds it from the EndgameResult),
  `supernova_model(progenitor, m_ni, e_kin)` → a `SupernovaModel` (light curve
  **`w·L_p·rise + (1−w)·L_radio`** — the blend kills the t=0 ⁵⁶Ni deposition spike a `max()`
  would surface — + homologous photosphere `StellarState`s `R=v·t`, Teff from Stefan-Boltzmann,
  `logg` honestly negative). NS/BH from a labeled CO-core cut, `M_ej = final − remnant`;
  no-plateau radioactive-only fallback for compact R₀<300 low-Z progenitors. `/supernova`
  bypasses `PROVIDER` for the compute but calls `PROVIDER.endgame()` for the progenitor; a
  non-SN progenitor → `is_supernova:false`, real fate echoed, no curve. **3-tier honesty:** Tier-1
  ⁵⁶Co tail slope (bulletproof) · Tier-2 plateau shape from MIST M_ej/R₀ (±dex level) · Tier-3
  peak/tail ∝ M_Ni (a **free slider**). **Two advisor test corrections, measurement-validated:**
  the Tier-3 test scales the radioactive **tail** not the peak (the IIP peak IS the M_Ni-free
  plateau `L_p`); the Tier-1 Co-slope is measured on the served **`L_radio` component** (0.00976)
  — on `L_total` the plateau cutoff bleeds in and steepens it to 0.01023. Measured canonical 15 M☉:
  plateau 1.83e42/138.7 d. **Chunk 2 BUILT (frontend gateway + light-curve panel):** a reversible
  `sn-mode` mirroring WD/WR — the dead SN note becomes a `→ Continue: Supernova` gateway button
  (enabled at end-of-life, still foreshadowed from ZAMS), the HR panel CSS-swaps its title to
  **Supernova light curve** and `hr.setSupernova()` redraws it as **L vs LINEAR days** (the straight
  ⁵⁶Co tail — a log-time axis would bend it), the age slider becomes a **linear-days time scrubber**
  (`snStateIndex` → nearest homologous state), the ⁵⁶Ni-mass **`sn-control` slider** (Tier-3, 0.001–0.3,
  debounced refetch) lifts the **tail not the plateau**, and the new **cited observed-photometry
  overlays** (`sn.js` — SN 1987A ⁵⁶Co tail + SN 1999em IIP plateau, **published bolometric fits, not raw
  photometry**, cited in a visible `.hr-sn-caption`) are the deferred **Tier-1 anchor**. Consumers
  (3D/SED/comp/scale/readout/classify) get the photosphere StellarState via an explicit `{endgame:"sn"}`
  signal (NOT naive reuse — `logg≈−5` ejecta would trip the boiling-fireball gate); `star.js` shows a
  smooth glowing sphere (granulation/corona off), `comp.js`/`spectrum.js` honest
  placeholders, entry narrates the un-modeled bounce. Mass/[Fe/H] stay live → re-snap (`trySNResnap`;
  WD/WR/none revert with a note). Playwright-verified at 1440 + 390 px (zero console errors), 215 pytest
  (backend untouched). **Chunk 3 BUILT (3D expanding fireball → remnant, frontend-only):** `star.js`
  gained `FIREBALL_FRAG` (a dedicated additive `fireball` sphere mesh, reuses `star.geometry`) + `REMNANT_FRAG`
  (a small camera-facing additive dot). In SN mode the surface sphere hides (`star.visible=!sn`, set
  **unconditionally**) and the fireball shows: 3D value-noise fbm on a bounded time orbit (boils, no drift/seam),
  center-bright, color = the **honest blackbody Teff** (the one load-bearing cue — blue-white→orange→red IS the
  cooling); a single additive layer with clamped alpha keeps the hue + cell structure (no white-out). `refreshSN`
  drives `snGrow` (swells the ball over the early scrub — the evocative "expanding" beat, true AU-scale R on the
  scale bar) + `snFade` (dissipates it over the late tail), threaded `{endgame:"sn", remnant, snGrow, snFade}`.
  As `snFade`→1 the remnant emerges: **NS** → a tiny hot blue-white dot (color labeled **evocative, NOT a Teff** —
  a real NS's optical thermal emission is negligible); **BH/failed** → no dot, the frame goes dark ("**winks out**").
  Measured: a BH-on-SN progenitor IS in-grid (**30 M☉ solar** → BH vs **15 M☉ solar** NS), so winks-out isn't dead
  code — both verified on-screen. **Chunk 4 BUILT (pre-collapse onion shell, frontend-only):** `comp.js` `drawSNOnion`
  replaces the SN placeholder with the progenitor's onion cross-section, driven by the scalars `/supernova` already
  serves (`final/he/CO/remnant` masses + ⁵⁶Ni — **no backend change**). Real boundaries (remnant/CO/He/total) sized by
  **area ∝ enclosed mass** (radius ∝ √(M/M_tot)); the inner Si/O–Ne shells are **faint schematic** dividers (MIST v2.5
  runs massive stars only to ~carbon burning, so `c_core_mass` is the *last computed* boundary — the iron core is never
  built; the caption owns it, the boron-b8 discipline); **NS/BH contrast honest** (a BH's remnant = the whole CO core →
  the onion visibly LACKS the copper C/O+heavy band, only He+H eject); ⁵⁶Ni an **exaggerated** slider-tied ring (not to
  scale, kept on BH too — consistent with the light curve). Static across the time scrub (`comp.update` no-op in SN mode),
  redraws on the ⁵⁶Ni-slider / mass-re-snap (both verified live: 0.06→0.25, NS↔BH). Phone-width label-overflow bug caught
  + fixed (even-spacing fit, caveats fold into the always-shown caption). **Chunk 5 BUILT (remnant branch NS/BH/failed-SN
  + cliff softening; backend + frontend — the SN arc is COMPLETE):** the hard CO=7 NS/BH cut became a **labeled fallback
  continuum** `φ=smoothstep(CO_NS_MAX=7, CO_DIRECT=12, co_core)` that softens the old cliff in the light curve AND the
  onion in one stroke — the remnant grows `M_NS+(M_final−M_NS)·φ`, the ejecta `M_ej=M_final−M_remnant` shrink smoothly
  to ~0, and the **ejected** ⁵⁶Ni `=M_Ni·(1−φ)` dims (deepest ash falls back first); new served fields `fallback_fraction`/
  `failed_sn`/`m_ni_ejected_msun`. **Two advisor blockers, fixed:** (1) the **NS↔BH label flips where the remnant crosses
  NS_MAX~2.5 M☉, NOT at CO=7** (else a near-threshold "BH" sits in the observed mass gap and reads as a bug) — so **30 M☉
  solar (CO 7.68) is now a heavy NS ~2.16, not a BH**; new demos BH-fallback 40 M☉/[Fe/H]−0.5, failed 50 M☉/[Fe/H]−1.0;
  (2) a **failed SN does NOT reuse the homologous photosphere** (`v=√(2E/M_ej)` blows up, ejected Ni→0 → log(0)) — its
  states stay at R₀ and DIM, the "disappearing supergiant", and the served curve uses a tiny floored Ni (positive, ~3 dex
  below a real IIP). **3D reconciled** (a Chunk-3 inconsistency — Chunk 3 made *all* BH wink out): NS→fireball+dot,
  **BH-fallback→fireball→dark invisible remnant (no dot, not a wink-out)**, **failed→dim→black (winks out)**. Onion drops
  the rem≤CO clamp (remnant eats C/O→He→H, no cliff), ring uses ejected Ni, failed onion ≈ all void + winks-out caption;
  `hr.js` violet failed-SN banner; readout "% fell back" + "direct collapse"; classify/SED branch on `failed`. 220 pytest,
  zero console errors at 1440 + 390 px. [[star-sim-supernova-remnant-endgame]]; plan `docs/plans/radioactive-afterglow-requiem.md`.

### SED (broadband panel — **sibling**, Teff-driven; mostly frontend, one tiny spine touch)
- `sed.js` plots the Planck blackbody γ→radio (~14 decades), Wien peak, optical
  bracket. Non-thermal overlay: a cool-star coronal X-ray band + Güdel–Benz radio
  (Chunk 1) that **collapses to a rotation→X-ray line** when rotation is supplied
  (age-gyrochronology or a user slider; Chunk 3). **Chunks 1, 2 & 3 ALL BUILT** — the
  SED non-thermal arc is complete. **Chunk 2 = the hot-star wind thermal free–free
  excess** (the one data-grounded tier): a solid teal-green λ⁻²·⁶ line from the real
  mass-loss rate, drawn where it crests the photospheric floor (Wright–Barlow). It is
  the SED's only **spine touch** — `mdot_msun_yr: float | None` is now on `StellarState`
  (the `Mdot` `_Track` column blended LINEARLY like `Vrot`, **no `CACHE_VERSION` bump**;
  Stub/MESA emit `None`). **Measure-first correction (advisor-led):** the feature is a
  mid/far-IR → sub-mm excess for **EVOLVED hot supergiants** (peaks ~35–260 µm, dec
  −8…−12), **NOT** the ZAMS-O "mm/radio" the plan's table claimed (that was ~4 dex too
  bright + circular — fixed by anchoring the coefficient on ζ Pup + a proven BB norm,
  not on the in-house number). Slope robust; level ±dex (v∞ bistability + clumping).
  [[star-sim-nonthermal-sed-plan]]; plan `docs/plans/magnetic-ember-broadcast.md`.

### Interior structure (real MESA radial profiles — a **sibling**; the honest Lane–Emden successor)
- **BUILT (1 M☉ solar + the 2/6 M☉ convective-core↔radiative-envelope FLIP).** `/structure` bypasses
  `PROVIDER` (like `/polytrope`, `/spectrum`): interior structure is a sibling, not a
  `StellarState`. `structure.py` reads offline MESA `profile.data` snapshots under
  `data/mesa_profiles/` (gitignored) with its **own** MESA-profile parser (never imports
  a provider — a §3 boundary rule) and snaps a request to the nearest saved snapshot in
  **(mass, [Fe/H], age)**, reporting the *true* snapped values (no interpolation across
  snapshots — the panel **jumps**, honestly labeled "nearest saved snapshot"). Returns
  center-normalized ρ(r)/T(r)/P(r) + X/Y/Z vs r/R, the **real convective/radiative split**
  (MESA `mixing_type==1` ∪ Schwarzschild `gradr>grada`), central scalars (ρ_c/T_c/P_c/R/M),
  and the **two canonical polytrope overlays (n=1.5, n=3)** — NOT a best fit; the canonical
  curves bracket the real ρ and the departure IS the lesson (advisor-settled: a fitted n
  would hide the very mismatch the panel exists to show). `expected_n` is a labeled hint
  from the *core* type (radiative→3 / convective→3/2), not a fit. Frontend `structure.js`
  is a **live consumer** wired into `paintState` (own debounced latest-wins fetch); draws
  ρ bold + T/X thinner + dashed polytrope references + shaded convective bands, a snapshot
  caption, a scalar readout, and a **snapped-far note** when the star is off-grid (snaps to
  the nearest of the 1/2/6 M☉ slices — honestly stated). **Why MESA-only/offline:** MIST ships
  no radial profiles and a live solve is out of scope (§2/§9), so profiles are self-run once
  (Docker MESA, the solar recipe + profile snapshots — `backend/docs/mesa_structure_recipe.md`).
  **Measured (mid-MS, ≈ solar age):** ρ_c≈190 g/cm³, T_c≈1.66×10⁷ K, R≈1.06 R☉, radiative
  core (n=3) + convective envelope base at r/R≈0.75 (SSM ≈0.71; the run is NOT solar-
  calibrated, hence loose test tolerances). Near-ZAMS shows a **real transient convective
  core** (MESA `mixing_type==1`, the early-MS ¹²C→¹⁴N-burning core before CN equilibrium) →
  an honest `expected_n=3/2` label flip, verified against the raw column, not an OR-clause
  artifact. The **2 & 6 M☉ slice** is the mirror — a **convective core** (CNO, centrally
  peaked) under a **radiative envelope**, so `expected_n` flips to **3/2** and the envelope is
  radiative at r/R≈0.9 (measured 6 M☉ mid-MS ρ_c≈16, T_c≈2.95×10⁷ K, R≈3.89 R☉, core r/R 0→0.131;
  2 M☉ core 0→0.088). **NO runtime code change** (the index globs the tree, snaps on the header
  mass/Z/age — "drops in as a bucket"); the accompanying change is data + tests: a new
  `requires_structure_massive` marker (gated on a ≥4 M☉ slice so the flip test *skips* not fails
  on a 1 M☉-only checkout), 3 flip tests, and one stale off-grid-snap test fixed (7.3 M☉ now snaps
  to 6.0). The advisor semiconvection-OR caveat was re-checked at this slice → it doesn't bite (the
  `mixing_type∪Schwarzschild` OR adds nothing beyond `mixing_type==1` here). Snapshot-selection is
  the real risk (a massive convective core *shrinks toward TAMS* → deliberately kept a healthy
  mid-MS Xc≈0.4 anchor). The **15 M☉ slice** (the SN arc's canonical progenitor — honest structure
  where the SN feature lives, was snapping to 6 M☉) is the **deepest** convective core of the set
  (ρ_c≈5.9, T_c≈3.5×10⁷ K, R≈6.67 R☉, core r/R 0→0.178; mid-MS anchor profile11, Xc 0.41) — **NO
  runtime change** again (drops in as a bucket), +1 gated test (`requires_structure_massive` already
  covers it, no conftest change), advisor OR-clause re-checked at 15 M☉ (every OR-added cell r/R≥0.97
  → no mid-radius over-shading). **13 tests** (`test_structure.py`); 233 pytest total. Playwright-
  verified 1440 px (6 M☉ + 15 M☉, "convective core → canonical n = 3/2", zero console errors).
  **Next:** other-Z buckets drop in the same way (verify the effect is *visible in the panel*
  first). [[star-sim-interior-structure-mesa]].

### Frontend & UX
- Other panels/features: Lane–Emden interior (§8), true-size scale bar, MK
  classification, instability-strip HR overlay, tooltip singleton, age-slider
  landmark ticks, responsive draggable dashboard. **No JS test harness → the
  Playwright screenshot pass IS the regression check** (use Playwright's bundled
  Chromium — `chrome --headless` hijacks the user's running Chrome).
  [[star-sim-frontend-ux]], [[star-sim-draggable-responsive-panels]],
  [[star-sim-true-size-scale-bar]], [[star-sim-instability-strip-overlay]],
  [[star-sim-tooltip-singleton]], [[star-sim-ux-four-fixes]],
  [[star-sim-ux-age-tick-fixes]], [[star-sim-phase2-shaders]],
  [[star-sim-phase3-lane-emden]].

### Tests
- **233 pytest** (gated by data present via `conftest.py` markers; MIST tests skip
  if grids absent). The §10 anchors are the regression gate (Sun: L≈1.07,
  Teff≈5834 K at 4.6 Gyr). The rotating axis now has its own within-bucket [Fe/H]
  interpolation tests (lies-between + held-out accuracy at vvcrit=0.4), mirroring the
  non-rotating ones — gated by `requires_mist_rotation_multifeh` /
  `requires_mist_rotation_heldout_feh`. The mass-loss-rate (`Mdot`) threading for the
  SED wind tail adds 4 §10 tests (present & ≤0; grows MS→AGB and up the OB sequence;
  carried through the feh-blend, lies-between & ≤0). The SN sibling has **20** tests
  (`test_supernova.py`): Chunk 1's Tier-1 ⁵⁶Co slope on the served `L_radio` component, the
  Tier-3 M_Ni-scales-the-tail linearity, the plateau⊕tail handoff, the no-plateau
  fallback, the NS/BH split, the SN-branch-only progenitor scalars, and the `/supernova`
  route (SN payload + non-SN honest-empty + 422); plus **Chunk 5's +5**: the fallback BH
  (remnant grows past the proto-NS, still erupts), the remnant/ejecta **continuity across the
  old CO=7 cut** (no cliff), the monotone fallback gradient, the **failed/direct-collapse**
  branch (M_ej<M_EJ_FAIL, ejected Ni→0, no plateau, faint-positive curve, non-expanding R₀
  photosphere), and Tier-3 linearity surviving the fallback dimming. Light-curve physics is
  unit-tested deterministically; the endgame→sibling→route path through the real provider.
  The real interior-structure sibling adds **13** tests (`test_structure.py`, gated by
  `requires_structure_data`): convective-envelope-over-radiative-core, order-of-SSM central
  values, monotone centrally-concentrated ρ, r/R spanning [0,1], canonical-polytrope overlay
  (n=3 more concentrated than n=1.5), honest age/mass snapping, and the `/structure` route +
  422s; plus **4 flip tests** for the 2/6/15 M☉ slices (gated by `requires_structure_massive`, a
  ≥4 M☉ slice so they *skip* not fail on a 1 M☉-only checkout): the 6 M☉ convective-core +
  n=3/2 + radiative-envelope-at-r/R=0.9, the direct Sun↔6 M☉ *mirror* on the same two probe
  radii, the 2 M☉ core-convective check, and the 15 M☉ SN-progenitor deepest-convective-core
  (core r/R 0→0.178, hotter/less-dense than 6 M☉).

### Next
- **`docs/plans/ROADMAP.md`** is the canonical cross-plan index of everything
  proposed-but-unbuilt (SED Chunk 2, WR/WD endgame Chunks 4–7, the
  rotation/subpopulation atlas, spectra-density stragglers). Update it (not a second
  list) when scope changes. [[star-sim-rotation-subpop-atlas]].

## Conventions

- Keep the stub honest: it is physically *flavored*, not a model. Label
  approximations in comments (the corona/activity layer is "evocative, not
  predictive" per spec §7).
- Don't let scope creep in: no live structure solve, no nuclear network, no
  deploy/bundle concerns (spec §2). This runs locally.
- **Claude's auto-memory is tracked in the repo** at `docs/memory/` (`MEMORY.md`
  index + one file per fact). The harness still reads/writes memory from its fixed
  path `~/.claude/projects/M--claud-projects-star-sim/memory`, which is a **directory
  junction** pointing at `docs/memory/` — so every memory write lands in the repo.
  Consequence: after writing or editing memory, **`git add docs/memory` and commit
  it** like any other tracked change (the session-end ritual already covers this). If
  the junction is ever missing (fresh clone on another machine, or it got replaced by
  a real dir), re-create it: `New-Item -ItemType Junction -Path "<that .claude path>"
  -Target "<repo>\docs\memory"` (Windows; no admin needed) — the repo copy is the
  source of truth.
