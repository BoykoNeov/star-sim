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
  saved snapshot, never imports a provider), `binary.py` (the **binary-stripped-star**
  sibling behind `/binary` — the hot He-star a companion strips, Götberg 2018; its own
  CSV parser over the *committed* `star_sim/data/gotberg_z014.csv`, snaps (Z,Minit),
  never imports a provider — the ~70% WR channel; also carries path (b): `/binary_pair`
  composes the donor + a PROVIDER companion, and `roche_geometry()` computes the pure
  RLOF-moment Roche-lobe geometry from the CSV's `P_init` column), `api.py` (FastAPI, the
  swap point; also hosts `/polytrope`, `/structure`, `/spectrum`, `/binary` and
  `/binary_pair`, the routes that do NOT go through `PROVIDER`).
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
  `src/{main,star,hr,comp,lane,structure,roche,spectrum,sed,scale,classify,color,canvas,layout,tooltip,sn}.js`.
  `roche.js` is the binary path-(b) Chunk-3 **mass-transfer / Roche-lobe** panel (a pushed-data consumer
  drawing the RLOF-moment orbital-plane figure-of-eight from `/binary_pair`'s `roche` block; shown only in
  `body.stripped-mode.companion-on`).
  `sn.js` is the SN endgame's cited observed-photometry dataset (SN 1987A ⁵⁶Co tail +
  SN 1999em IIP plateau, published bolometric fits — the Tier-1 overlay anchor); `hr.js`
  gains a `setSupernova()` light-curve view (L vs **linear** days → the straight ⁵⁶Co tail),
  a **Teff-colored living track** + glowing marker (one shared `drawMarker`), a
  **past/future split at the marker** (traversed solid, ahead dim — living AND endgame
  tracks, `splitIndex` = marker array identity + age fallback), faint
  **O·B·A·F·G·K·M spectral-class bands** (letters above the top frame line, living view
  only), and dotted **iso-radius diagonals** (constant-R graph paper from L=4πR²σT⁴,
  living AND endgame views — the WD cooling track slides down one; never the SN light
  curve — see [[star-sim-frontend-ux]]).
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
  shader (Teff→color × H_p granulation × **chromatic** limb darkening (blue darkens
  most — the limb warms) × Teff-keyed **exposure** (cool = deep/saturated, hot =
  clipped blue-white, Sun anchored at 1.0) × streak-proof rotation + activity corona
  quad (monotone outside-the-limb profile — never a rim ring) + a Teff×L-keyed
  **glare** quad (hot luminous objects blaze; SN re-keys it to the light curve) +
  an opt-in **Ap/Bp chemical-peculiarity** what-if (`uPeculiar` + `peculiarSpots()`: co-
  rotating oblique-dipole abundance spots, a brightness-only dip, EVOCATIVE like the corona;
  a `#peculiar-toggle` track-stable on the A/B mass regime, faded per-state outside the
  A/B-MS Teff window; composes with gravity darkening — see [[star-sim-apbp-peculiarity]]) —
  see [[star-sim-phase2-shaders]] for the rework) + a **deterministic static starfield
  backdrop** (seeded, a flat far sheet NOT a shell; pure backdrop, encodes no state —
  see [[star-sim-frontend-ux]]). `color.js` is the reference
  Planck→CIE→sRGB color pipeline
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
  mass grid **0.1–300 M☉** per metallicity, window **ZAMS → end of early-AGB** (the
  LIVING track hard-stops at φ5 per §6 "messy, defer" — but the TPAGB thermal-pulse rows
  are NOT lost: `endgame()` snaps to one real track and exposes them, and they ship two ways
  — the WD gateway's cooling scrub (loops compressed to 12%, `WD_FP`) AND an opt-in
  **thermal-pulse showcase** that decompresses the He-shell-flash sawtooth to the full HR
  panel, gated on a data-derived amplitude floor). Non-rectangular valid
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

### Binary-stripped stars (the ~70% WR channel — a **sibling**, not a provider; `/binary` bypasses PROVIDER)
- **CE/COMPACT-OBJECT TAIL — CHUNKS 1a (backend) & 1b (frontend render) & 1c (full 8-bucket
  [Fe/H] axis + free M_star/M_co/P custom sliders) ALL BUILT** (Phase 1 of
  `docs/plans/tempered-lineage-inspiral.md`; a compact object NS/BH/WD orbiting a still-H-rich
  star — the stage AFTER the HMS-HMS episode, the ~X-ray-binary/GW-progenitor channel). A
  genuinely new sibling `posydon_co.py` + `/co_binary_track` (schema recon: `history2` is absent
  grid-wide, so there's only ever ONE real star — not a `posydon.py` branch). **Chunk 1b** is a
  **standalone curated demo** inside stripped-mode (its own `.co-binary-view` body class, mutually
  exclusive with the HMS-HMS `.binary-view` — each hides the other's demo row + an unconditional
  cross-token bump kills a slow-in-flight-fetch race): HR shows ONLY the living star (a point-mass
  CO gets NO luminosity point — `hr.setBinaryTrack(states, null, {s1:"star"})`), `star.js`
  `CO_MARKER_FRAG`/`coMarker` draws a schematic 3D glyph beside it (BH = a persistent dark disc +
  ring, deliberately NOT the SN "winks out"; NS = a hot point), `roche.js drawLiveCo` draws the
  same point-mass marker (never a Teff disc) with the lobe as the accretion target, and the
  η·Ṁ·c² accretion cue is surfaced in the age-slider caption **relative to the star's own L**
  (~2.5× during RLOF1). The one backend touch: `co_binary_track_payload` folds in per-step Roche
  geometry by reusing `binary.track_roche_geometry` via a `SimpleNamespace` adapter (star→donor,
  CO→accretor, q=m_co/m_star). An advisor-flagged false-data leak fixed: the readout/scale/MK-class
  single-star consumers froze on the unrelated stripped snapshot → CSS-hidden in `.co-binary-view`.
  **Chunk 1c** (data + frontend + one backend correctness fix, mirrors HMS-HMS 4c/4d, **no
  runtime-logic change for the axis** — `co_binary_track` was already snap-always over the whole
  grid): extracted + baked the 7 non-solar buckets → the **full 8-bucket [Fe/H] axis** (−4.0…+0.30,
  coextensive with the HMS-HMS axis); a `#co-binary-feh` picker (populated from the real
  `available_feh`) + a "Custom system…" picker revealing three **log** sliders — the CO custom axis
  is **(M_star, M_co, P), NOT (M1, q, P)** (a CO's mass is a physical value ~1.2–307 M☉, not a
  ratio). **The full-grid pytest caught a real artifact:** the accretion-cue Eddington bound was
  SOLAR-ONLY characterized (2–3.5×); the metal-poor grids reach **505,221× Eddington** on a few rows
  — ALL on POSYDON `unstable_MT` (CE/merger) tracks (the served caption would've shown ~10^13× the
  star's own L, newly reachable via the picker/sliders). Gated the η·Ṁ·c² cue OFF `unstable_MT` (the
  `active` mask now needs `not is_unstable_mt`) → bounded **≤3.46× Eddington grid-wide**, the stable
  X-ray-binary payoff preserved. **Not built:** `CO-HeMS`/`CO-HeMS_RLO` (double-compact-object
  channel — a separate extraction). [[star-sim-co-hms-rlo]].
- **PATH (b) CHUNK 4d BUILT (frontend-only, NO backend change, Playwright-verified 1440+390 zero
  console errors):** the [Fe/H] metallicity-bucket picker — the frontend catch-up once
  [[star-sim-hosted-data-assets]] finished baking+hosting the FULL 8-bucket POSYDON axis
  ([Fe/H] ≈ −4.0…+0.30); `/binary_track`/`/binary_track_meta` already took a `feh` param
  (`binary_track_meta`'s `available_feh` field was already served) but `main.js` had it
  hardcoded to `feh=0` in both fetch call sites. A `<select id="binary-feh">` in
  `binary-demo-row`, populated from the real `available_feh` list (never hardcoded), applies
  to WHICHEVER system is showing — curated demo or "Custom orbit" — unlike M1/q/P which only
  ever drive "custom" (mirrors the MIST mass/[Fe/H] split: orthogonal axes). Deliberately kept
  visible during an active co-evolving movie (`.binary-feh-label` excluded from the
  `body.binary-view .binary-demo-btn` hide rule) so a user can compare metallicities without
  leaving it. A new `customFeh` state var + `refetchBinaryTrack` (renamed/generalized from
  `refetchBinaryCustom` — resolves (m1,q,p) for ANY active `binaryDemoKey`, not just
  "custom") + a `binary-feh-note` (always-visible snap-honesty line, the M1/q/P
  `binary-custom-note`'s counterpart but NOT hidden inside the custom-only controls). Switching
  buckets re-fetches `binary_track_meta` first (clamping customM1/Q/P + repositioning the
  custom sliders to the new bucket's bounds — each POSYDON metallicity is its OWN grid, so
  bounds differ) before re-fetching the track, avoiding a stale slider-vs-fetched mismatch.
  **Verified through the real app (Playwright):** the select lists all 8 real buckets; entering
  the Case-B demo at solar then switching to [Fe/H]=−1.0 re-fetches both routes and the note
  updates; on "Custom orbit" with M1 dragged to 280 (snaps to the grid ceiling 286 M☉,
  "stripped + companion" at solar) switching to the most metal-poor bucket ([Fe/H]=−4.0) at the
  SAME (M1,q,P) genuinely changes the outcome to "stable mass transfer" — real physics, not a
  cosmetic label swap. Zero console errors at 1440/390 px. Plan
  `docs/plans/entwined-consort-inspiral.md`; memory `star-sim-binary-stripped.md`.
- **PATH (b) CHUNK 4c BUILT (frontend-only, NO backend change, 310 pytest unchanged, Playwright
  1440+390 zero errors):** free M1/q/P sliders — `/binary_track` was already fully general
  (snap-always over the WHOLE POSYDON grid, §6); Chunk 4b's three curated demos were a UI
  de-risking choice, not a backend limit, so this needed no `posydon.py`/`api.py` touch. A
  fourth **"Custom orbit…"** demo button reveals three sliders (M1, q, P) driving the exact
  same `enterBinaryView` fetch path. Log-scale 0..1 position sliders for M1/P (measured span
  via `/binary_track_meta`: 3.92–286.4 M☉ ≈1.9 dex, 0.1–5179.5 d ≈4.7 dex — the ⁵⁶Ni-slider
  idiom), a direct linear binding for q (0.05–0.99, <1 dex). A note line always states the
  TRUE snapped node + outcome + any `*_snapped_far` flags, never the raw dragged numbers.
  **One real bug the first Playwright pass caught:** the sliders panel was revealed before
  the initial `/binary_track` fetch resolved, so a drag during that window landed while
  `binaryView` was still `false` and got silently dropped by `refetchBinaryCustom`'s own
  guard; fixed by moving the reveal to after `binaryView = true` (the same point the demo/
  Back buttons already gate their own interactivity on). Verified via a poll-based
  Playwright script: entering shows the Case-B default, dragging P to the log floor re-snaps
  to the real merger node, dragging M1 to the ceiling re-snaps far off-grid with an honest
  note, the scrubber/Back/re-entry all work. **Path (b) is now built end-to-end (Chunks
  1–4c, +4d above for the metallicity axis)** — what remains is the explicitly unscoped tail:
  richer CE/compact-object outcomes, a population overlay (BPASS). Plan
  `docs/plans/entwined-consort-inspiral.md`; memory `star-sim-binary-stripped.md`.
- **PATH (b) CHUNKS 4a & 4b BUILT — the two-star TIME render is live (310 pytest [+4]):**
  the on-ramp to a real binary grid — POSYDON HMS-HMS, the first TIME-SERIES, TWO-BODY
  sibling. **Chunk 4a** (backend, solar-first): the user landed all 8 metallicity tarballs
  (~84 GB, `data/Posydon/`); only solar is extracted + baked so far. Recon correction: the
  raw grid HDF5 is already per-run (`grid/run<i>/{binary_history,history1,history2}`), not
  POSYDON's packed `PSyGrid` — so `scripts/bake_posydon.py` reads it directly with plain
  h5py (host-side, filters `not_converged`/misaligned runs, verifies the
  run↔`initial_values` index identity, decimates >300-row tracks) into a flat CSR `.npz`
  (33,121 tracks/1.48M rows/142 MB); the runtime `star_sim/posydon.py` sibling is
  h5py/POSYDON-free, snaps (M1,q,P,[Fe/H]) in normalized log-M1/log-P/linear-q space to the
  nearest track (never interpolates, §6). **Gate 0 CLOSED** through the real runtime (demo
  system M1=8.83/q=0.6/P=3.73 d): the mass ordering crosses live (donor 8.83→1.07 M☉,
  companion 5.30→5.94 M☉), the period widens 3.73→6.94 d, `mt_state` fires a real
  detached→RLOF1→detached sequence. Two honest gaps vs the original plan guess: no
  eccentricity column (HMS-HMS circularizes; `ecc` is a labeled 0.0) and C/N/O-only
  composition (not MIST's 16-metal breakdown). `/binary_track` + `/binary_track_meta`
  bypass `PROVIDER`, snap-always. **Chunk 4b** (frontend, a deeper reveal INSIDE
  stripped-mode — mode stays `"stripped"` throughout, the WD-thermal-pulse sub-view
  pattern): three curated demo systems (same donor M1=8.83/q=0.6, only P differs — merger /
  the Gate-0 stripped+companion / detached), a "Co-evolve the system" button row that
  fetches `/binary_track` once and repurposes the age slider as a free index-linear
  system-time scrubber (mass/[Fe/H] disabled meanwhile — POSYDON's grid is independent of
  the MIST axes). `hr.js` gained a genuinely new drawing mode (`setBinaryTrack`/
  `updateBinaryIndex` — BOTH stars' full tracks, Teff-colored, independent past/future
  splits, markers fixed-labeled "donor"/"companion" by IDENTITY so the reversal is the
  crossing, never a relabel). The Roche panel (Chunk 3) goes LIVE (`roche.js drawLive`,
  the untouched static `drawPanel` stays for the snapshot): a **backend addition** was
  needed here — `binary.py`'s Roche engine was factored into a pure
  `_roche_geometry_from_params(q, m1, m2, a, n_samples)` + a new `track_roche_geometry`
  that `posydon.py` imports (sibling-calls-sibling, mirroring `structure.py` →
  `lane_emden.solve_lane_emden`; no `BAKE_VERSION` bump, computed at request time) at a
  decimated 40-sample resolution (~2ms/step vs the CSV path's 160-sample ~14ms, keeping a
  271-step track fetch under ~1s). Two real upgrades over the static snapshot: both stars
  get a REAL Teff/R every step (drawn as real discs always), and whichever star `mt_state`
  flags as overflowing gets its lobe filled + the stream (measured/labeled: the real
  photospheric radius does NOT itself cross the lobe outline during RLOF — a local L1
  excess, not whole-photosphere inflation). 3D is free (`star.update(s1,{companion:s2})`,
  the exact Chunk-2 call, now driven every scrub frame). Playwright-verified 1440+390,
  zero console errors, the Case-B markers visibly cross and the Roche lobes visibly
  reshape/fill through a real detached→RLOF1→detached sequence. **Chunk 4c (free q/P
  sliders) is now built too — see the bullet above.** Plan
  `docs/plans/entwined-consort-inspiral.md`.
- **PATH (b) CHUNK 3 BUILT (backend + frontend, 287 pytest [+8], Playwright 1440+390 zero errors):**
  "the mass-transfer geometry / Roche lobes" — a genuinely new TWO-STAR render: the orbital-plane
  figure-of-eight at the moment of Case-B RLOF (the causal story behind the stripped star). Advisor-settled
  Option B (the RLOF *moment*, a 2D plane view, separation from a new `P_init` CSV column via Kepler; NOT
  3D Roche surfaces). Honest geometry (lobe shape from q=0.8 alone; L1/L2/L3 by bisecting dΦ/dx; lobe
  outlines by radial march to the critical Kopal equipotential — the **L1-tangent bug** fixed by stopping
  at the first crit-crossing OR Φ-turnover so the lobes kiss). The RLOF donor is a bloated cool giant of
  un-modelled Teff → **schematic warm tint, never the stripped Teff**; the companion is drawn at its real
  modelled radius, compact inside its lobe. **The blocker (advisor): the cross-panel mass-ordering
  REVERSAL** (donor is the HEAVIER M1 here vs the LIGHTER post-strip object everywhere else — same class as
  the Chunk-1 q-bug) is owned by the panel intro + caption. Pure `roche_geometry()` (no PROVIDER) folded
  into `binary_pair_payload`; new `roche.js` panel CSS-gated to `body.stripped-mode.companion-on`.
  **Next (b) Chunk 4: the on-ramp to a real binary grid (POSYDON/BPASS) — a separate recon+handoff.**
- **PATH (b) CHUNK 2 BUILT (frontend-only, 279 pytest UNCHANGED, Playwright 1440+390 zero errors):**
  "the companion drawn in 3D" — the accretor as a REAL second sphere beside the stripped donor. **No
  backend touch** (the companion state is already served by `/binary_pair`). **Honesty split (advisor):**
  the *sphere* is Tier 1/2 honest (a real modeled single-star state → the full surface shader: Teff
  color, relative size, granulation, limb darkening), unlike the evocative corona/wind/fireball; what's
  NOT modeled is the geometry BETWEEN the stars (no separation/orbit) → the side-by-side placement is
  SCHEMATIC, caption-owned (un-drawn-orbit precedent). `star.js` = a 2nd `companion` sphere (own
  `ShaderMaterial`, per-star uniforms differ) + a `companionGlare` (7–27 kK would blaze), no 2nd corona;
  `update(state,{companion})` lays donor LEFT / companion RIGHT via direct `mesh.position.x`
  (camera-facing quads stay parallel under x-shift — no billboard math), relative log-size preserved
  (companion bigger than the compact donor IS the reversal in 3D), a shared `applyCompanionScale`
  fit-to-frame factor (`FRAME_HALF_H` precedent, re-run each frame → live-resize refit), both glares
  TEMPERED ×0.6 (glare-merge trap), `companionMat.uTime` in `animate()` (else boil freezes); all
  offsets+`.visible` UNCONDITIONAL → toggle-off byte-identical. `main.js` threads the companion state +
  the schematic caption sentence. Measured: donor stays compact (R 0.16→0.88 R☉) vs the MS companion
  (1.83→7.76 R☉) at every node → "companion bigger" reads everywhere. NO 3D text labels (scope; left=donor
  matches the HR blue-left). Next (b) Chunk 3: Roche-lobe geometry, then a real binary grid. [[star-sim-binary-stripped]].
- **Chunks 1 (backend) & 2 (frontend what-if mode) & 3 (stripped-star spectra) BUILT — path (a) COMPLETE.**
  **Chunk 3** (backend + frontend, 273 pytest, Playwright 1440+390 zero console errors): a FOURTH
  spectrum sibling **`/stripped_spectrum`** over the Götberg CMFGEN cube — `scripts/bake_stripped_spectra.py`
  bakes a **flat-node** host-baked cube (like WR, not rectangular Teff×logg) keyed on the SAME `(Z, M_init)`
  node `/binary` snaps (state↔spectrum consistency), **solar-only**, from `normalised_spectrum.txt`
  (CMFGEN **continuum-normalized** Fnorm → no continuum estimation), **vac→air** + **sort-by-λ** (measured
  gotchas). `spectra.py stripped_spectrum_data` + `spectrum.js updateStripped` = a **bidirectional** draw
  (absorption dips at the subdwarf end, emission peaks at the He-star end; `display_max` cap, continuum line
  at 1.0, regime-branched caption). Reads the resolved node off `state.mass_init_msun`/`feh_init` (no drift).
  **Measure-first gate CLOSED through the runtime:** the absorption→emission sequence is real & monotone
  (2 M☉ pure absorption Hα 0.50 → 18 M☉ He II 4686 **7.2×** emission), distinct from the false O-star Balmer
  spectrum the Chunk-2 placeholder protected against. Bonus: fixed a pre-existing `.spectrum-zoom[hidden]`
  CSS leak (zoom presets leaked into every endgame + stripped mode — dead in WR/SN/stripped, working-but-
  meant-hidden in WD). Recipe §10. Path (b) (two-star co-evolution) stays deferred.
  **Chunk 2** (frontend-only, 266 pytest
  UNCHANGED, Playwright 1440+390 zero console errors): the reversible `mode="stripped"`. Entry-point
  (i) settled — a **mass-gated TOGGLE** (`#stripped-toggle`, mirrors the Ap/Bp control) for eligible
  progenitors (2–18.2 M☉), a MID-LIFE FORK (not an end-of-life gateway) that still snaps the whole
  display, fetched from `/binary`. **One exit** — the shared endgame-bar "Back" (`exitEndgame`, which
  captures `prevMode` to return the fork to the age it forked FROM, not the track end); unchecking
  calls the same. **The three false-data leaks blocked (advisor):** HR keeps the progenitor's living
  track faint + drops the marker **blue-left** (reuses `hr.setEndgame([s],"stripped")` auto-fit, no
  hr.js change); **comp = a NEW single-state SURFACE view** (`comp.setStripped`/`drawStripped` — the
  measured He-rich H/He/Z bar; the core is by-construction so NOT drawn); **spectrum → placeholder**
  (the main cube is H-atmosphere → a He-star would paint a FALSE O-star Balmer spectrum); **structure
  → not called** (keeps its last profile). `classify.strippedLabel` (sdO/B < 1.5 M☉ → He-star above,
  via `opts.mStrip`); age slider DISABLED (one representative state). SED wind tail off + honest for
  free (`mdot=None` → `computeWindTail` null). Re-snap (`tryStrippedResnap`): snap-always, no revert —
  a drag past the grid edges shows an in-band snapped-far caption note. [[star-sim-binary-stripped]];
  plan `docs/plans/stripped-consort-unveiling.md`. **Next = Chunk 3** (stripped-star spectra, deferred).
- **Chunk 1 BUILT (backend vertical, solar-first).** The hot He-rich core a close companion
  exposes by Case-B Roche-lobe overflow (Götberg+2018) — the dominant observed stripped/WR
  channel, retiring the single-star-WR "minority channel" caveat. It's the first build from
  the atlas Tier-D **binarity** item, **path (a)** (the stripped endpoint; path (b) two-star
  co-evolution deferred). A **sibling** (a binary product can't pass the single-star §3
  interface): `binary.py` imports only `state.StellarState`, `/binary` bypasses `PROVIDER`,
  exactly like `supernova.py`/`structure.py`. `backend/star_sim/data/gotberg_z014.csv` is the
  **committed** Z=0.014 table (23 rows, SED-verified ≤0.07 dex; only the spectra stay
  gitignored under `data/gotberg_stripped/`). `stripped_star(mass, feh)` **snaps** (Z, Minit)
  → nearest node (never interpolates, §6) → a `StrippedStar` = the §3-clean `StellarState` +
  routing scalars (`m_strip_msun` [CURRENT mass — no home on the state], snapped m_init/Z,
  `*_snapped_far` flags, `mass_grid_min/max`). Route is **snap-always** (out-of-grid flagged
  in-band, 422 only for mass≤0). **Gotchas baked in:** Teff/Reff not T★; `Z_surf`=grid Z with
  (X_H,X_He) renormalized to 1−Z; `mdot=None` + no lifetime (not in the 8-col table). The
  **visibility gate keys Teff+Y_surf only, NEVER L** (advisor catch: L flips sign across the
  grid — M_strip≪M_init). 266 pytest (12 new in `test_binary.py`; `requires_gotberg_data`
  guards the SED regression). Adding the 3 non-solar Z tables = drop a CSV + one `_GRID_TABLES`
  tuple. **Next = Chunk 2** (frontend what-if `stripped-mode`). [[star-sim-binary-stripped]];
  plan `docs/plans/stripped-consort-unveiling.md`.

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
- **BUILT — the three interior regimes: 0.25 M☉ fully-convective M dwarf + 1 M☉ solar radiative-core↔
  convective-envelope + the 2/6/15/25 M☉ convective-core↔radiative-envelope FLIP; PLUS the metallicity
  axis (1 M☉ at [Fe/H]=−1/+0.5, the convective envelope shallows as Z drops).** `/structure` bypasses
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
  the nearest of the 0.25/1/2/6/15/25 M☉ slices — honestly stated). **Why MESA-only/offline:** MIST ships
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
  → no mid-radius over-shading). The **25 M☉ slice** brackets the upper SN-progenitor range — the
  **deepest** convective core of the ladder (ρ_c≈3.79, T_c≈3.78×10⁷ K, R≈8.47 R☉, core 0→0.228;
  0.131→0.178→0.228), same drop-in (no runtime change), +1 gated test, OR-clause re-checked (zero
  mid-radius over-shade). The **0.25 M☉ slice** is the **third regime — a fully-convective M dwarf**
  (advisor chose it over the literal "Next: other-Z": a new *regime* is visible-by-construction so
  the honesty gate is met automatically): a single convective zone spanning **0→1** (the whole star),
  `expected_n`→3/2, ρ_c≈135–138, T_c≈7.4×10⁶ K (below the Sun's — weak pp), R≈0.247 R☉. Two
  advisor-flagged **run** changes (unlike the pure drop-ins): **`max_age=2d9` replaces the TAMS stop**
  (a 0.25 M☉ MS lifetime is ~10¹²⁻¹³ yr — the central-H stop never fires, Xc barely moves) and **ship a
  settled-MS profile, not a pre-MS-contracting one** (profiles 20/21/22 of 22, L settled ~0.0105 L☉).
  **The polytrope-honesty INVERSION** (measured before writing it into the caption): a fully-convective
  star *is* the textbook n=3/2 polytrope, so the real ρ **hugs the n=1.5 overlay** (~1–5%) and sits far
  above n=3 — **the one bucket where the idealization works**, inverting the panel's usual "the departure
  is the lesson." NOT a pure drop-in: +`requires_structure_lowmass` marker (≤0.5 M☉ gate) + 2 tests +
  the off-grid snap probe re-pointed 0.3→0.15 (0.25 is now the grid floor) + a small `structure.js`
  caption refinement ("fully convective …the rare case the real profile follows it"; blank conv.base).
  **18 tests** (`test_structure.py`); 238 pytest total. Playwright-verified 1440 px (6/15 M☉ "convective
  core → canonical n = 3/2"; 0.25 M☉ "fully convective", ρ overlapping the n=1.5 dash, whole-panel
  convective shading; zero console errors). The **metallicity axis** added — the first non-mass slice
  (1 M☉ at [Fe/H]=−1.0 and +0.5): the solar-abundance-problem effect, lower Z → more transparent
  envelope → **shallower convective envelope** (base at higher r/R). **Gating measurement first, at
  matched Xc not age** (a metal-poor 1 M☉ is hotter/shorter-lived): mid-MS envelope base **0.70/0.75/
  0.95** at [Fe/H] **+0.5/0/−1** — visibly, monotonically distinct → clears the honesty gate. **NOT a
  core-type flip** (advisor-predicted): core stays radiative, `expected_n=3` at every Z; the whole
  payoff is the envelope-depth band. −2.0 run too but **not shipped** (base 0.99, fragments). **MESA
  gotcha: change `Zbase` too, not just `initial_z`** (round Z → clean [Fe/H] label auto). **Runtime NO
  code change** (the index already snapped mass→feh→age; frontend already passed the marker's [Fe/H]);
  data (`1Msun_fehm1p0`/`1Msun_fehp0p5`) + `requires_structure_multifeh` marker + 1 trend test + a
  **[Fe/H]-snapped-far note** (`structure.js`, the Z grid is 1 M☉-only) + the conv.base tooltip Z-link.
  Recipe §10. The **[Fe/H] axis now lives at a SECOND mass — the 0.8 M☉ K dwarf** (§11), so the
  interior grid is a genuine **partial 2D (mass × [Fe/H]) grid** for the first time. Same regime as
  the Sun (radiative core + conv. envelope) but a deeper envelope → the Z-shallowing is stronger AND
  **stays a single unfragmented zone at every Z** (base **0.66/0.69/0.81** at [Fe/H] +0.5/0/−1,
  matched-Xc-measured, monotone, core stays radiative n=3 — not a flip). **Chosen by measurement over
  two rejects:** 6 M☉ convective-*core* edge (the novel Z-on-a-core lesson) **failed the gate** (~0.02
  shift, non-monotonic below Xc 0.5 — massive stars respond to Z in R/Teff, not core fraction); 1.3 M☉
  envelope gave a clean 2-point but **fragments into ~0.99 slivers by [Fe/H]=−0.5** (real mixing_type,
  not OR-artifact — checked), so not shipped. **Runtime NO code change** again (mass→feh→age snap; a
  Z-less mass falls back to solar — both verified through the real `interior_structure()` path); +3
  data dirs (`solar_0p8Msun`/`0p8Msun_fehp0p5`/`0p8Msun_fehm1p0`) + 1 trend test (mass-parametrized
  `_midms_envelope_base`, existing `requires_structure_multifeh` marker) + a `structure.js` comment
  refresh (note reads the snapped result → correct as the axis grows). **238 pytest**, Playwright-
  verified 1440 (conv. band shallows 0.659→0.694→0.807 across +0.5→−1, zero console errors). **Next:**
  extend the [Fe/H] axis to more masses (clean on the lower MS, fails in the convective-core regime —
  verify visible first), or ship the 1.3 M☉ double-convective structure on its own merits.
  [[star-sim-interior-structure-mesa]].

### Frontend & UX
- Other panels/features: Lane–Emden interior (§8), true-size scale bar (with
  **swallowed-orbit rings** — an engulfed orbit fills with the star's tint), MK
  classification, instability-strip HR overlay, tooltip singleton, age-slider
  landmark ticks, responsive draggable dashboard, **first-load skeleton sheen**
  (`<body class="loading">`, removed on first paint/error; per-ID CSS selectors —
  the canvas `#id` background shorthand outranks a class rule), the **polish batch**
  (comp bulk-view boundary dots at the cursor + brighter phase labels; tick-label
  10.5px / SED band-name 11px legibility bumps; header tag → "ZAMS → remnant"
  — the stale "Phase 5 · spectra" retired). **No JS test harness → the
  Playwright screenshot pass IS the regression check** (use Playwright's bundled
  Chromium — `chrome --headless` hijacks the user's running Chrome).
  [[star-sim-frontend-ux]], [[star-sim-draggable-responsive-panels]],
  [[star-sim-true-size-scale-bar]], [[star-sim-instability-strip-overlay]],
  [[star-sim-tooltip-singleton]], [[star-sim-ux-four-fixes]],
  [[star-sim-ux-age-tick-fixes]], [[star-sim-phase2-shaders]],
  [[star-sim-phase3-lane-emden]].

### Tests
- **333 pytest** (gated by data present via `conftest.py` markers; MIST tests skip
  if grids absent). The POSYDON CO-HMS_RLO compact-object sibling (`test_posydon_co.py`,
  gated `requires_posydon_co_data`) adds **23** — Chunk 1a's 18 (snap/parse honesty, whole-grid
  no-NaN/no-dupe, per-step StellarState validity, the accretion-cue Eddington-bound regression,
  the Gate-1 CO-mass-growth/RLOF-then-detach regression, route shape + 422/503) plus Chunk 1b's
  **2** (the `/co_binary_track` payload carries a non-null per-step `roche` block; the Gate-1
  Roche reshape/lobe-swap: q sweeps 0.53→1.18 as the star strips and the BH accretes, the star
  fills its lobe on every RLOF1 step) plus Chunk 1c's **3** (gated `requires_posydon_co_multifeh`:
  `available_feh` reflects the real baked bucket set; the metallicity axis is real — the same
  (M_star, M_co, P) request snaps to a different real track / outcome across [Fe/H] buckets; and
  the served-level regression that the η·Ṁ·c² accretion cue is `None` on POSYDON `unstable_MT`
  tracks — the gate that keeps the metal-poor 505,221×-Eddington artifact off the caption). The
  Chunk-1a Eddington-bound test was updated to mirror the now two-part gate (not-detached AND
  not-unstable_MT, ceiling tightened 10→5×). The POSYDON co-evolved-binary sibling (path (b) Chunk 4a) adds
  **19** tests (`test_posydon.py`, gated `requires_posydon_data`): snap honesty (a
  request lands on a true (M1,q,P) grid node, never interpolated, verified via an
  exact-node round-trip over a 300-track sample), no duplicate grid nodes and no
  non-finite values across the WHOLE baked grid (an advisor-flagged check — the multi-
  rerun grid could in principle serve a superseded track, or a CE/disruption row could
  emit NaN into the JSON payload; both measured clean), decimation preserving the RLOF
  episode on capped tracks (`BAKE_VERSION` 2 force-keeps RLOF/contact rows on top of the
  uniform stride), both stars' valid `StellarState`s at every step, `mass_init_msun`
  constant vs the current-mass routing scalar, the Gate-0 regression (mass-ordering
  crossing, orbit widening, a real detached→RLOF1→detached sequence, the "stripped +
  companion" outcome) through the real runtime, merger-track graceful degradation, and
  the `/binary_track` + `/binary_track_meta` routes (snap-always + 422 on structurally
  invalid input). The binary path-(b) Chunk-3 Roche geometry adds **8** tests in
  `test_binary.py` (P_init parse, snap↔geometry consistency, donor-heavier-at-RLOF,
  Kepler separation ≈43.7 R☉, L-point ordering, lobes-kiss-at-L1 + donor-bigger + no-leak,
  Eggleton fill, and the route carrying `roche` + the companion fitting its lobe); Chunk 4b's
  `track_roche_geometry` adds **4 more** there (duck-typed synthetic steps: matches the
  single-node engine at the same params, donor/companion lobe sizes swap across a synthetic
  reversal, `None` on a degenerate step) plus **2** in `test_posydon.py` (the Gate-0 track's
  real lobes reshape + swap dominance; the `/binary_track` route carries a non-null `roche`
  block on every step).
  The binary-stripped-star spectrum sibling (Chunk 3) adds **7**
  tests (`test_stripped_spectra.py`, gated `requires_stripped_spectra_data`): the flat-node
  snap honesty + state↔spectrum consistency, the absorption→emission sequence as a
  regression (He II 4686 flat at the subdwarf end → strong emission at the He-star end),
  the continuum-normalized shape, and the `/stripped_spectrum` route (snap-always + 422).
  The §10 anchors are the regression gate (Sun: L≈1.07,
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
  The real interior-structure sibling adds **17** tests (`test_structure.py`, gated by
  `requires_structure_data`): convective-envelope-over-radiative-core, order-of-SSM central
  values, monotone centrally-concentrated ρ, r/R spanning [0,1], canonical-polytrope overlay
  (n=3 more concentrated than n=1.5), honest age/mass snapping, and the `/structure` route +
  422s; plus **4 flip tests** for the 2/6/15 M☉ slices (gated by `requires_structure_massive`, a
  ≥4 M☉ slice so they *skip* not fail on a 1 M☉-only checkout): the 6 M☉ convective-core +
  n=3/2 + radiative-envelope-at-r/R=0.9, the direct Sun↔6 M☉ *mirror* on the same two probe
  radii, the 2 M☉ core-convective check, and the 15 M☉ SN-progenitor deepest-convective-core
  (core r/R 0→0.178, hotter/less-dense than 6 M☉); plus the **25 M☉ upper-SN-range** test and
  the **2 low-mass M-dwarf** tests (`requires_structure_lowmass`); plus **two metallicity-axis
  trend tests** (`requires_structure_multifeh`, gated on |[Fe/H]|>0.3), one at **1 M☉** and one
  at **0.8 M☉** (the second mass on the Z axis — the partial 2D grid): the matched-Xc monotone
  envelope-shallowing base(+0.5)<base(0)<base(−1), all `expected_n`=3 (not a core flip). The 0.8 M☉
  one reuses a mass-parametrized `_midms_envelope_base`.

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
