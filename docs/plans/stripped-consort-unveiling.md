# Plan: Binary-stripped stars — the ~70% WR channel, as a sibling

## Status: PATH (a) CHUNKS 1–3 BUILT (complete). PATH (b) CHUNKS 1–2 BUILT (companion on the HR + drawn in 3D).

**Path (b) Chunk 2 done 2026-07-06 (frontend-only, 279 pytest UNCHANGED, Playwright
1440 + 390 zero console errors).** "The companion drawn in 3D" — the accretor rendered as a
real second sphere beside the stripped donor. **No backend touch** (the companion state is
already served by `/binary_pair` from Chunk 1).
- **The honesty split (the load-bearing call, advisor-settled):** the companion *sphere* is
  Tier 1/2 honest — a real modeled single-star `StellarState` (from `PROVIDER`), so it's drawn
  with the FULL surface shader (real Teff color, real relative size, granulation, limb
  darkening, exposure), unlike the evocative corona/wind/fireball. What is NOT modeled is the
  geometry BETWEEN the stars (no separation/orbit/system-inclination in the data), so the
  side-by-side placement is SCHEMATIC (the un-drawn-orbit precedent); the caption owns it
  ("Each star is a real modeled star, but their side-by-side placement is schematic — the
  separation and orbit are not modeled").
- **`star.js`:** a second `companion` sphere (own `ShaderMaterial` reusing `SURFACE_VERT/FRAG`
  — per-star uniforms differ, so it can't share `surfaceMat`) + a `companionGlare` quad (the
  accretor runs 7–27 kK and would blaze; an un-glaring companion beside a blazing donor would
  misread as "less real"). No second corona (a hot star is near-glowless). `update(state, opts)`
  gains `opts.companion`: donor LEFT / companion RIGHT, offset via direct `mesh.position.x`
  (camera-facing quads stay parallel under an x-shift → no billboard math), relative log-size
  preserved (the companion reading BIGGER than the compact donor IS the Algol reversal in 3D),
  then a single shared `applyCompanionScale` fit factor shrinks both to the tighter frame axis
  (horizontal binds on phone, `FRAME_HALF_H` precedent), re-run each frame in `animate()` so a
  live resize refits. Both glares TEMPERED ×0.6 to keep the lane between the stars from washing
  into one blob (the glare-merge trap). `companionMat.uTime` driven in `animate()` (else the
  boil freezes — the fireball precedent). All offsets + `.visible` set UNCONDITIONALLY, so
  toggle-off resets the primary to the origin and hides the companion = byte-identical.
- **`main.js`:** `refreshStripped` threads `{ companion: strippedData.companion.state }` to
  `star.update` when `companionOn`; the caption gains the schematic-layout honesty sentence.
- **Measured across the grid (the advisor's high-mass concern, answered by the data):** the
  stripped donor stays COMPACT at every node (R 0.16 → 0.88 R☉, mass 2 → 18) while the MS
  companion is large (1.83 → 7.76 R☉), so the "companion bigger" cue reads everywhere. Low-mass
  end is a clean color contrast too (2 M☉: donor blue-white 20 kK, companion warm-yellow 7 kK).
- **Scope call on record (advisor-accepted):** NO 3D text labels this chunk — the caption + HR
  labels + size/color carry identity; left=donor is a convention matching the HR's blue-left.
- **Files:** `frontend/src/star.js` (companion sphere + glare + `applyCompanionScale` + the
  two-body block in `update` + `animate` uTime/refit), `frontend/src/main.js` (`refreshStripped`
  thread + caption). No backend, no tests changed (frontend-only; the Playwright pass is the gate).
- **Next (path (b) Chunk 3+):** the mass-transfer geometry / Roche lobes (a genuinely new
  two-star render), then the on-ramp to a real binary grid (POSYDON/BPASS).

**Path (b) Chunk 1 done 2026-07-02 (backend + frontend HR two-marker reversal, 279 pytest,
Playwright 1440+390 zero console errors).** "The companion drawn" — the second star of the Algol
system on the HR diagram, the mass-ratio reversal made visible. **No new dataset:** it reuses the
Götberg stripped DONOR (path (a)) + the single-star `PROVIDER` for the COMPANION (accretor).
- **The measure-first gate (mirroring path (a)'s Gate 0) PASSED through the real consumers** across
  the whole eligible grid: the Algol reversal is real at every node (`M_strip < M2_init`, 0.35<1.60
  … 6.72<14.54), the companion is a sane MS star at every node (Teff 7.3–27.4 kK, phase MS, at the
  donor's MS lifetime), and the donor is always hotter (blue-left). Bonus payoff: the L-ordering
  *flips* — at low mass the companion OUTSHINES the sub-luminous stripped donor ("the optically
  bright companion", Götberg 2018), at high mass the donor wins — but the donor is always hotter.
- **The two advisor correctness catches, both baked in:** (1) the companion baseline is
  `M2_init = 0.8·M_init` (the grid's fixed **q=0.8**, confirmed in the ReadMe — non-conservative,
  so no accretion-efficiency guess enters; `ΔM = M_init−M_strip` is NOT attributed to the companion,
  it's wind + non-conservative RLOF loss). (2) the companion's age/phase is defused by that baseline
  — being *less massive* it lives longer, so at the donor's MS lifetime (= elapsed system age, `TAMS`
  on the donor track) it's still mid-MS, never a degenerate off-track companion.
- **Architecture:** `binary.py` stays a PURE §3 sibling — it never fetches the companion (that needs
  `PROVIDER`, which a sibling must not import). The composition happens in the ROUTE: new
  `/binary_pair` calls `stripped_star` (donor) + `PROVIDER.state_at(0.8·M_init, feh, τ)` (companion),
  and `binary.binary_pair_payload` assembles the two-star payload + transfer scalars (`mass_msun`,
  `mass_ratio_init`=0.8, `mass_ratio_final`=M2/M_strip >1 [both companion÷donor, one convention →
  the reversal crosses 1.0; advisor caught a first cut mixing conventions], `elapsed_age_yr`). Both stars share the
  snapped system Z (`feh_snapped`). `/binary` (path (a)) is byte-unchanged.
- **Frontend:** an opt-in **"Show companion"** toggle in the endgame bar (stripped-mode only, CSS-
  gated) — the literal path (a)→(b) transition ("companion named" → "companion drawn"). Path (a) is
  the default (byte-unchanged when off). On: the stripped fetch routes to `/binary_pair`, `hr.js`
  gains `setCompanion(state)` (a second Teff-colored marker with a dashed ring + a dotted link to the
  donor + labels "stripped star"/"companion", re-fitting the axes to enclose it so the low-mass
  brighter companion never clips), the caption narrates the reversal off the served scalars, and the
  readout gains Companion + Mass-ratio(now) rows. Reversible; resets on mode enter/exit.
- **Files:** `binary.py` (+`COMPANION_MASS_RATIO`/`companion_init_mass`/`binary_pair_payload`),
  `api.py` (+`_donor_ms_lifetime`/`/binary_pair`), `test_binary.py` (+6: the reversal-across-grid
  regression, the pair assembler, the route gate + snap-far + 422), `hr.js` (+`setCompanion`/
  `drawCompanion`/`markerLabel`, companion in fitBounds + clearEndgame), `main.js` (companion toggle
  + `companionOn` state + fetch route + caption/readout), `index.html` (toggle + narration), `styles.css`.
- **Next (path (b) Chunk 2): DONE** (see the top of this doc) — the 3D companion sphere is built.
  Then further: the mass-transfer geometry / Roche lobes (needs a genuinely new two-star render),
  the on-ramp to a real binary grid (POSYDON/BPASS).

## Status (historical): CHUNKS 1, 2 & 3 BUILT. The stripped-star arc is complete (path (b) deferred).

**Chunk 3 done 2026-07-02 (backend + frontend, 273 pytest, Playwright 1440+390 zero console
errors).** The stripped-star spectrum panel — the real CMFGEN spectrum replacing the Chunk-2
placeholder:
- **`scripts/bake_stripped_spectra.py`** → a **flat-node** cube (like the WR cube, NOT
  rectangular Teff×logg) keyed on the grid node `(Z, M_init)` — the SAME snap identity
  `binary.py` uses — so the runtime snaps to the node `/binary` already resolved and the panel
  spectrum is guaranteed to be the SAME star as the marker (advisor's tightest constraint).
  **Solar-only** (grid_014, 23 nodes) matching the committed solar param table; grid-generic
  (`--grids`) so the 3 non-solar Z append when their param tables land. Reads
  `normalised_spectrum.txt` (CMFGEN **continuum-normalized** Fnorm, so NO continuum estimation),
  **vac→air** (measured: Balmer minima land at vacuum <0.1 Å, off air 1.1–1.7 Å — Morton 2000,
  TMAP/PoWR precedent), **sort-by-λ before binning** (CMFGEN band-concat can be non-monotone;
  the solar files measured monotone but the empty-bin interp fallback needs it — cheap
  insurance), bin to the shared 3000–9000 Å @ 2.5 Å grid. Cube 0.2 MB, gitignored.
- **`spectra.py` `_StrippedSpectra` + `stripped_spectrum_data(minit, feh)`** — the flat-node
  runtime (snap nearest Z-in-feh-space then nearest M_init). Serves Fnorm as-is + a `regime` ∈
  {"absorption","hybrid","emission"} from the peak optical Fnorm (measured thresholds) + a WR-style
  `display_max` y-cap (floored 1.2 so an absorption node fills the panel, capped 8 so a monster
  He II 4686 can't squash it) + `continuum: 1.0`. `feh_varies` false (solar-only).
- **`/stripped_spectrum` route** (snap-always like `/binary`; 422 only mass≤0; 503 if not baked).
- **The measure-first gate CLOSED through the runtime (advisor BLOCKER):** the absorption→emission
  sequence is real and monotone — 2 M☉ (20 kK) pure absorption (He II 4686 flat 1.0, Hα 0.50) → 3.65
  absorption → 6.66 (54 kK) hybrid (He II 4686 emits 1.15) → 9 emission (2.48) → 18.17 (101 kK)
  strong emission (He II 4686 **7.19×**, Hα 3.21). Distinct from the false O-star Balmer spectrum the
  placeholder protected against (and the hot nodes are >55 kK where the main cube is a clamped "no
  model" anyway) — the justification for a fourth cube, measured.
- **Frontend `spectrum.js` `updateStripped`** — reads the RESOLVED node off the state itself
  (`mass_init_msun`/`feh_init`, which binary.py sets to the snapped node → exact, no drift), a
  **bidirectional** `drawStripped` (mirrors `drawWR`: rainbow shade + dashed continuum line at 1.0
  + `display_max` y-scale, but absorption dips below AND emission peaks above), `STRIPPED_LINES`
  guides (He II 4686 the diagnostic + Balmer/He I, no up/down gate), a regime-branched caption.
  `main.js` `applyStrippedModel` swaps `showPlaceholder` → `spectrum.updateStripped(s)`.
- **Bonus bug fix caught by the screenshot pass:** the `.spectrum-zoom` zoom-preset row leaked into
  every endgame + stripped mode (`hidden=true` silently failed — missing the `[hidden]` re-assertion
  vs `display:flex`, unlike the `.alpha-toggle-row[hidden]` idiom); fixed with one CSS line. (Advisor
  nuance: the leaked buttons were dead only in WR/SN/stripped — those draw paths ignore the band
  window; WD's zoom actually worked but `updateWD` intends to hide it, so the fix restores that intent.)
- **Files:** `scripts/bake_stripped_spectra.py` (new), `spectra.py` (+`_StrippedSpectra`/
  `stripped_spectrum_data`/`STRIPPED_GRID_FILENAME`), `api.py` (`/stripped_spectrum`),
  `tests/test_stripped_spectra.py` (7, `requires_stripped_spectra_data` in `conftest.py`),
  `frontend/src/spectrum.js` (+`updateStripped`/`drawStripped`/guides/caption/export), `main.js`
  (2 swaps), `styles.css` (the zoom-leak fix). `backend/docs/msg_spectra_build_recipe.md §10`.

## Status (historical): CHUNKS 1 & 2 BUILT. Next = Chunk 3 (stripped-star spectra, optional/deferred).

**Chunk 2 done 2026-07-02 (frontend-only, 266 pytest UNCHANGED, Playwright 1440+390 zero
console errors).** The reversible what-if `stripped-mode` + payoff render:
- **Entry point (i), settled:** a mass-gated TOGGLE (`#stripped-toggle`, mirroring the Ap/Bp
  control), shown only for eligible progenitors (2–18.2 M☉) in live mode + while active. It's a
  MID-LIFE FORK, not an end-of-life gateway — so a toggle, not a gateway button — but still a
  reversible MODE (`mode="stripped"`) that snaps the whole display, fetched from `/binary`
  (snap-always, no vvcrit). **One exit path:** the SHARED endgame-bar "Back" (= `exitEndgame`);
  unchecking the toggle calls the same path. `exitEndgame` captures `prevMode` and pins-to-end
  ONLY for the true endgames — the stripped fork returns to the age it forked FROM (ageValue
  untouched inside the mode).
- **Consumers rendered directly, with the THREE false-data leaks blocked (advisor):** HR keeps
  the progenitor's living track as faint context and drops the marker BLUE-LEFT of it (reuses
  `hr.setEndgame([s],"stripped")` auto-fit — no hr.js change); comp shows a NEW single-state
  SURFACE view (`comp.setStripped`/`drawStripped` — the measured He-rich bar H/He/Z; the core is
  by-construction so it is NOT drawn); classify a `strippedLabel` (sdO/B hot subdwarf < 1.5 M☉ →
  He-star above; keyed on the CURRENT mass threaded via `opts.mStrip`); scale radius-based (no
  mass_init read — the audit worry was moot); readout `renderStrippedReadout` (current m_strip +
  progenitor + He surface). **spectrum → honest placeholder** (the main cube is H-atmosphere
  models → a He-star's Teff/logg would paint a FALSE O-star Balmer spectrum); **structure → NOT
  called** (keeps its last profile, like wd/wr/sn — else it'd fetch a normal ZAMS profile); the
  age slider is DISABLED (one representative state — no lifetime in the table).
- **SED wind free-free tail: naturally off + honest** — `mdot=None` so `sed.js`'s `computeWindTail`
  returns null (no line drawn), AND a stripped star's fast wind wouldn't crest the floor anyway.
  No gating code needed (the measure-first concern resolved itself in the data).
- **Re-snap (`tryStrippedResnap`, in the `tryResnap` dispatch):** UNLIKE wd/wr/sn there's no fate
  to revert on (`/binary` is snap-always), so a drag past the grid edges snaps to nearest + shows
  an in-band snapped-far note in the caption, rather than reverting.
- **Composition-honesty catch (advisor blocker, post-first-verify):** the surface is NOT always
  He-rich — the LOW-mass end is H-rich (2–3 M☉ → X≈0.99, an sdB-like subdwarf keeping a thin H
  envelope; crossover ~3.5–4 M☉). Hardcoding "helium-rich" would be a false measured label AND
  contradict `classify`. Every per-state label now derives from `heRich = Y_surf > X_surf`
  (`drawStripped` tag/line + `strippedCaption(heRich)`, `strippedLabel`, readout, caption); static
  prose says the surface "flips H→He with mass." Verified at BOTH mass=2 and mass=8.
- **Files:** `main.js` (the orchestration — els, state, `updateStrippedControl`/`fetchStripped`/
  `applyStrippedModel`/`refreshStripped`/`renderStrippedReadout`/`enterStripped`/
  `tryStrippedResnap`, `exitEndgame`+`tryResnap` extended, toggle handler), `comp.js`
  (`setStripped`/`drawStripped`), `classify.js` (`strippedLabel`), `index.html` (toggle + bar
  title/narration + age span), `styles.css` (stripped-mode rules). No backend touch.

## Status (historical): CHUNK 1 BUILT (backend vertical, solar-first, 266 pytest).

**Chunk 1 done 2026-07-02 (backend only, solar-first).** The data + runtime vertical:
- **`backend/star_sim/data/gotberg_z014.csv`** — the verified Z=0.014 table committed to
  the repo (23 rows, 8 StellarState columns + a provenance header carrying the ≤0.07-dex
  SED-verification note). Committed *inside* the package (tiny, versioned with the code);
  only the spectra stay gitignored under `data/gotberg_stripped/`.
- **`backend/star_sim/binary.py`** — the pure sibling (imports only `state.StellarState`,
  never a provider). Own CSV parser; `stripped_star(mass, feh)` snaps (Z, Minit) →
  nearest node (never interpolates, §6) → a `StrippedStar` (the §3-clean `StellarState`
  + routing scalars: `m_strip_msun` [current mass, no home on the state], the snapped
  `m_init`/Z, `feh_snapped`, `mass_snapped_far`/`feh_snapped_far`, `mass_grid_min/max`).
  The two gotchas baked in: Teff/Reff not T★; Z_surf = grid Z with (X_H, X_He)
  renormalized to 1−Z. `mdot=None` (not in the 8-col table — the SED tail is a Chunk-2
  measure-first call); no stripped-phase lifetime (also not in the table). `age_yr`/`eep`
  are a documented sentinel (`REPRESENTATIVE_AGE_YR`), not age zero.
- **`/binary` route** — bypasses `PROVIDER` (like `/structure`/`/supernova`). **Snap-always,
  advisor-settled:** out-of-grid snaps to nearest + flags `*_snapped_far` in-band; 422 only
  for structurally invalid input (mass ≤ 0). The hide-below-2 / note-above-18.2 is a Chunk-2
  UX read of the flags, NOT a backend 422.
- **`test_binary.py` (12 tests) + `requires_gotberg_data` marker.** Parse/snap/validity/
  route-smoke run always (committed table). Two gated tests: the **visibility gate** vs
  `PROVIDER.state_at` (`requires_mist_data`) keys on **Teff + Y_surf only, never L** — the
  advisor's correctness catch: the L comparison flips sign across the grid (sub-luminous
  at 2 M☉ → over-luminous at 18 M☉) because M_strip ≪ M_init, so a naive `stripped.L <
  single.L` assert would fail at high mass. The **SED-consistency regression** (the
  verifier ported into the suite, `requires_gotberg_data`) is now durable, not a temp
  script.

Advisor sign-offs baked into the build: the L-sign-flip (correctness), the marker's real
home (the SED regression), drop the lifetime, snap-always-not-422, the named sentinel.

---
### Original build plan (below) — retained for the Chunk 2+ roadmap.

## Status (historical): DATA ON DISK + SOLAR GRID VERIFIED. Gate 0a RESOLVED.

**Update 2026-07-02 — data landed and was verified.** The user host-fetched the
VizieR tarball (browser, past Anubis) → `data/gotberg_stripped/`. Recon results
(see "Data recon — RESULTS" below) changed two plan assumptions:
- **Gate 0a RESOLVED: the grid is 1D-in-`Minit` per Z** (23 masses × 4 Z = 92 models;
  period `P` is a fixed function of mass, not a free axis). Snap key = **(Z, Minit)**.
- **Provenance is two-source.** The CDS deposit holds only **spectra + broadband
  magnitudes** — NOT the structural parameters. `Teff/L/R/logg/Mstrip/X_surf` come from
  the **paper's** Table 1 (Z=0.014) + Appendix B (the other 3 Z), transcribed from ar5iv.
  The **solar (Z=0.014) table is fully verified** against the on-disk SEDs (all 23 rows,
  ≤0.07 dex — see below); it is small enough to **commit to the repo**. The other 3 Z
  tables are a scoped follow-up (ar5iv truncates before Appendix B; needs another route).
  → **build solar-first, add the [Fe/H] axis when the 3 tables land** (advisor-endorsed).

The first build from the atlas's Tier-D **binarity** item (`whirling-cohort-atlas.md`).
Scope chosen by the user (2026-07-02): **path (a) — the stripped-star endpoint**, the
single hot He-star a close companion produces by Roche-lobe overflow. Not the full
two-star co-evolution (path (b) — Roche geometry, Algol reversal, both stars on the HR;
deferred, would take (a) as its first chunk).

Path (a) is **not a bait-and-switch** for the roadmap item: the *dominant observed
channel* for stripped/WR stars is binary stripping (~70%, Sana+2012, Shenar+2020), so
the stripped-star endpoint **is** the binarity headline. It also directly retires the
caveat the project keeps writing — "a single-star WR demo shows the *minority* channel."

## The architectural decision — SIBLING, not a new provider (settled)

The roadmap said "behind a new provider." That is **wrong for this spine** and we are
not doing it. The `StellarStateProvider` Protocol returns exactly one single-star state
(`track()`/`state_at()` → one `StellarState`), and `StellarState` is single-star by
contract (§3). A binary product cannot go through that interface without discarding the
companion or mutating the dataclass — both §3 violations.

The honest fit is the pattern the project already uses for everything that doesn't
reduce to one single-star track: **a sibling.** Exactly like `supernova.py` + `/supernova`
(computed, bypasses `PROVIDER`, emits `StellarState`s + routing scalars), `structure.py`
+ `/structure` (offline data, own parser, never imports a provider), `spectra.py`,
`lane_emden.py`. So:

- `binary.py` — a pure sibling: imports only `state.StellarState`, **never** the provider.
  Reads the Götberg stripped-star parameter table (its own parser), snaps a request to
  the nearest model in (initial mass, Z), and returns a `StellarState` for the stripped
  star (plus a few §3-clean routing scalars: `M_strip`, `M_init`, stripped-phase
  lifetime, the companion caveat). The stripped star is a hot He object — a perfectly
  ordinary single-star `StellarState` that the existing 3D/HR/comp/spectrum consumers
  render with **zero consumer changes**.
- `/binary` — a FastAPI route that bypasses `PROVIDER` for the compute (like `/structure`,
  `/supernova`, `/spectrum`). No Protocol change, no `StellarState` change, no
  `CACHE_VERSION` bump (the MIST cache is untouched).

## The phenomenon (what the stripped star IS, and why it's visible)

A star of initial mass ~2–18 M☉ in a close binary fills its Roche lobe near the end of
its main sequence (case B mass transfer). The companion strips the H envelope, exposing
a hot, compact, **He-rich core** that then burns helium. This object is the missing link
that **unifies subdwarfs (low mass) and Wolf–Rayet stars (high mass)** as one sequence of
stripped-envelope stars (Götberg+2018, the paper's thesis).

Why the measure-first gate is near-certain to pass — a stripped star is **off the
single-star mass–luminosity relation by construction**:
- **Hot** — Teff tens of kK (the envelope that made it look cool is gone).
- **He-surfaced** — X_H,surf ≈ 0.0–0.3, Y_surf ≈ 0.7–1.0 (vs ~0.7 X for a normal MS star).
- **Sub-luminous for its Teff** — it sits far to the blue-left of the single-star track, in
  the subdwarf/WR region of the HR diagram.

So a stripped 3 M☉ looks nothing like a single 3 M☉. **The real measurement still runs
once a slice is on disk** (Gate 0 below) — the project's boron-b8 / VO-7400 discipline —
but the physics makes a null result implausible.

## Measured grounding (the data recon — the gate that had to close first)

- **The grid exists, is published, CC-BY, ASCII on VizieR** — Götberg et al. 2018,
  A&A 615 A78, VizieR catalog **J/A+A/615/A78**. (The Zenodo record 2595656 is only the
  MESA *inlists* — the *data* is on VizieR.) Same host-baked SVO/CDS-ASCII precedent as
  the Koester (6a) / TMAP (6b) / Coelho (α) cubes — **no Docker, no MESA run.**
- **Coverage:** stripped mass **0.35–7.9 M☉** from progenitor **2.0–18.2 M☉**, >20
  log-spaced mass points, at **4 metallicities** Z = 0.014 (≈[Fe/H] 0), 0.006 (≈−0.4),
  0.002 (≈−0.85), 0.0002 (≈−1.85).
- **The per-model parameter table is exactly a `StellarState`:** columns `Minit, Pinit,
  Mstrip, M_H,tot, L, LH, T★, Teff, log10 g_eff, Reff, X_H,surf, X_He,surf` + wind Ṁ,
  Eddington factor, terminal wind speed, ionizing fluxes Q0/Q1/Q2. **The mapping, with
  the advisor's two corrections baked in:**
  - `Teff`→`Teff_K` and `Reff`→`R_rsun` — **use these, NEVER `T★`.** `T★` is the inner
    hydrostatic (evolutionary) temperature; for a star with a wind it differs from the
    spectroscopic `Teff`. `Teff`/`Reff` are the self-consistent Stefan-Boltzmann pair
    that place the star correctly on the HR (the same evolutionary-vs-spectroscopic gap
    that bit WR spectra Chunk 7a). Feeding `T★` would misplace the marker.
  - `L`→`L_lsun`, `log g_eff`→`logg`, `X_H,surf`→`X_surf`, `X_He,surf`→`Y_surf`,
    (1−X−Y)→`Z_surf`, `Z`→`feh_init`.
  - **`Minit`→`mass_init_msun`** (the progenitor — the slider's meaning). **The current
    mass is `Mstrip`, which has NO home on `StellarState`** (there is only `mass_init`).
    Mirror WD/WR exactly: current mass rides as a **routing scalar** on the `/binary`
    result (like `final_mass_msun` on `EndgameResult`), NOT on the state. **Audit the
    consumers that read `mass_init` as "mass now"** — `scale.js` (true-size scale bar)
    and `classify.js` are the likely misreads; they must use the served current mass in
    stripped-mode, not `mass_init`.
  - wind `Ṁ`→`mdot_msun_yr` — but see caveat: the SED free-free tail is a **false
    freebie until verified** (Chunk 2 note below).
  - Core composition unknown from this table → leave `metals_core` empty / He-core
    inferred (honest, like other siblings).
- **Spectra bonus:** per model, a 50 Å–50 000 Å SED + normalized spectrum (CMFGEN NLTE).
  A spectrum-panel follow-on (Chunk 3), host-bakeable exactly like the WR/WD cubes.
- **Fetch access:** CDS bot-blocks the *HTML* viz-bin pages (Anubis), but the raw FTP
  files under `cdsarc.cds.unistra.fr/ftp/J/A+A/615/A78/` are typically direct-GET-able —
  `fetch_gotberg.py` runs **host-side** like the other `fetch_*` scripts. If the FTP is
  also gated, the host wgets the VizieR tar manually (recipe will document it).

## Data recon — RESULTS (2026-07-02, measured on disk)

What the VizieR deposit `data/gotberg_stripped/` actually contains:
- **4 grid dirs** `grid_0002 / grid_002 / grid_006 / grid_014` (Z=0.0002/0.002/0.006/
  0.014), **23 model subdirs each**, named `M1_<Minit>q0.8P<P>Z<Z>_vinf1.5`. Each subdir
  holds `SED.txt` (λ[Å], F_λ[erg/s/cm²/Å **at 1 kpc**]) + `normalised_spectrum.txt`.
- **4 `.dat` tables** `m0002.dat…m014.dat` — per the ReadMe byte-spec these are **only
  broadband absolute magnitudes** (NUV,FUV,UVW1/2,UVM2,U,B,V,R,I,J,H,Ks). **No Teff/L/R/
  logg/Mstrip/abundances.** So the `.dat` files are not the parameter source.
- **Structural parameters live in the paper**, Table 1 (Z=0.014) + Appendix B Tables 2–4.
  Columns exactly match a `StellarState`: `M_init, M_strip, Teff[kK], logL, logg, R_eff,
  X_H,s, X_He,s` (values quoted "halfway through core-He burning", X_He,c=0.5).

**The verification (the transcription is LLM-summarized → must not be trusted blind).**
The SEDs are ground truth (flux at 1 kpc), so `L = 4π(1 kpc)²·∫F_λ dλ` (trapezoid, **λ
sorted** — CMFGEN concatenates frequency bands so the file order isn't monotone; **clipped
at 5 µm** — all real luminosity of these hot compact stars is blueward of 5 µm). Three
per-row checks (advisor's plan): (1) table logL≈SED logL; (2) Stefan-Boltzmann
`R²(Teff/5772)⁴`≈SED logL [verifies Teff & R]; (3) `logg=4.438+log Mstrip−2 log R`≈table
logg [verifies Mstrip & R]. **Result: all 23 solar rows PASS** — max |Δ| = 0.070 (tblL vs
sedL), 0.063 (SB vs sedL), 0.017 (logg). Verifier: `M:/claud_projects/temp/gotberg_verify/
verify_z014.py`.
- **Real data-quality artifact found + handled:** the **3.65 M☉ solar** `SED.txt` has a
  spurious >5 µm free-free tail carrying **85%** of its integrated flux (neighbors: 0%);
  its UV/optical peak is normal and its *table* row is internally self-consistent (checks
  2+3 pass). The 5 µm integral clip neutralizes it. **Relevant to Chunk 3** (that spectrum
  file needs the same clip before baking).

**Build gotchas locked in (advisor):**
- **`Z_surf` = the grid Z**, NOT `1−X_H−X_He` (the table rounds X to 2 dp → 0.46+0.54=1.00
  → would give Z=0). Take `X_surf=X_H`, `Y_surf=X_He` from the table; renormalize the pair
  to `1−Z` for closure. The He-rich surface is the headline — get X/Y right.
- The 674 MB `J_A+A_615_A78.tar.gz` was deleted post-extract (spectra tree kept).

## Two honest caveats to bank up front

1. **The grid is one representative state per stripped star** (the long-lived He-burning
   stage), not a full time-track. This is *perfect* for path (a) as a snap-to-model
   endpoint (like the WR/WD/endgame snaps), but means (a) is a "here is the product"
   view, not an animated in-spiral. The caption owns it.
2. **The companion is not modeled** in (a) — we show the stripped star alone. The caption
   names the companion as the *cause* (a close binary did the stripping) without drawing
   it. Drawing the companion + the mass-transfer geometry is path (b).

## The UX entry point — a real fork (decide in Chunk 2, advisor consult)

Unlike WD/WR/SN (genuine *endgames* of the same single star, reached at the slider's end),
the stripped star is a **counterfactual at end-of-MS**: "instead of expanding to a red
giant, a close companion strips the envelope *now* → this hot stripped star." So it is a
**mid-life fork**, not an end-state. Two candidate UX framings:

- **(i) A standalone "what-if" mode toggle** gated on the eligible progenitor-mass range
  (like the Ap/Bp toggle's mass gating), available across the star's life, that snaps the
  whole display to the stripped product with a caption on the timing. *Lean.* It matches
  the physics (a fork, not a fate) and avoids inventing mid-track gateway placement.
- **(ii) An end-of-life-style gateway button** ("→ What if: stripped in a binary")
  mirroring the WD/WR/SN gateways, reusing that exact placement/mode machinery.

Either way it is a **reversible mode** (`stripped-mode`) mirroring `wd/wr/sn`-mode, with
mass/[Fe/H] resnap and a hard revert. The advisor flagged (a) "maps almost exactly onto
the endgame-gateway UX"; the open sub-question is *where the button lives*. Settle it in
Chunk 2 with a consult; ship whichever is more honest without new UX invention.

## Chunked build

Honesty spine throughout: measure visible-and-real through the runtime path **before**
shipping any control; label the counterfactual; the companion is named, not modeled.

### Gate 0 — measure-first (BLOCKS Chunk 1 shipping; host-fetch a minimal slice)

**Prerequisite — the fetch is a USER HANDOFF (I cannot run it).** My environment is
blocked from CDS both ways: Anubis anti-bot on the `cdsarc` HTML viz-bin pages, and an
expired TLS cert on the legacy `u-strasbg` host. So the data cannot land without the host
running the fetch. The concrete next action is a fetch command handed to the user, then
**wait** — nothing past `fetch_gotberg.py` can be built or measured until data is on disk.

**Gate 0a — the data-shape gate — RESOLVED 2026-07-02: 1D-in-`Minit`.** Each `(Minit, Z)`
has exactly one model (23 masses × 4 Z); period `P` scales with mass (fixed Case-B value),
not a free axis. **Snap key = (Z, Minit).** No 2D `Minit×Pinit` rework needed.

**Gate 0b — visibility.** Parse the solar-Z (Z=0.014) table, build a `StellarState` for a
mid-grid stripped star, and confirm through the **real consumers** it is visibly distinct
from the MIST single-star of the same initial mass:
- HR position blue-left of the single-star track (hot `Teff`, sub-luminous);
- He-dominant surface in the comp panel (Y_surf ≳ 0.7 vs ~0.28);
- a sane 3D render (small hot blue star).
If a stripped 10 M☉ reads like a single 10 M☉ through the runtime, stop — no feature.
(Physics says it won't; this is the discipline gate, not an expected-fail.)

### Chunk 1 — the data + runtime vertical (backend only) — SOLAR-FIRST
- **The parameter table is a committed repo file, NOT a fetch output** (provenance is
  two-source — see Data recon). Ship `star_sim/data/gotberg_params.csv` (or a `.py`
  literal) holding the verified **Z=0.014** rows (23 rows, the 8 StellarState columns);
  the 3 non-solar Z tables are appended when acquired. This file is checked in (tiny);
  only the **spectra** stay gitignored under `data/gotberg_stripped/`.
- `star_sim/fetch_gotberg.py` (host-side) — documents/wraps the **spectra** fetch (the
  browser-past-Anubis VizieR tarball → `data/gotberg_stripped/`). It does NOT provide the
  parameters (those are the committed table). Mostly a recipe + a sanity parser over the
  extracted tree. Real work is Chunk 3.
- `star_sim/binary.py` — the pure sibling: its own parser over the committed table,
  `stripped_star(mass, feh)` → `StellarState` (snap Minit→nearest grid mass, Z→nearest
  available; report the TRUE snapped values, never interpolate — §6 snap). `Z_surf`=grid
  Z, `X_surf/Y_surf` from the table renormalized to `1−Z` (the rounding gotcha). Plus a
  small result object carrying `M_strip`, `M_init`, `Z`, stripped-phase lifetime, and the
  eligible mass range (for the UI gate). **Snap key = initial mass** (the slider's meaning;
  the stripped star is "what a M-progenitor becomes"). With solar-only on disk, every
  [Fe/H] snaps to Z=0.014 with an honest snapped-far note until the axis grows.
- `/binary` route (bypasses `PROVIDER`; 422 out-of-grid, honest snapped-far note in-band).
- `backend/tests/test_binary.py` — Gate 0 turned into regression (gated by a
  `requires_gotberg_data` marker in `conftest.py`): parse; snap honesty (returned
  Minit/Z are real grid nodes); `StellarState` validity (0<X+Y+Z≈1, logg/Teff/L sane);
  **the visibility gate** (stripped Teff hotter + Y_surf higher + off the single-star
  L–Teff relation vs `PROVIDER.state_at()` at the same Minit); route smoke (payload +
  out-of-grid).

### Chunk 2 — the frontend what-if mode + payoff render
- The reversible `stripped-mode` (settle entry-point (i)/(ii) with an advisor consult),
  gated on the eligible progenitor-mass range (hidden/greyed outside [2, 18.2]; honest
  snapped-far note at the Z edges). Fetch `/binary` for the marker's (mass, [Fe/H]).
- Consumers render the stripped `StellarState` directly: **3D** = the existing hot-star
  shader (small hot blue star, granulation faint at that Teff; corona per its activity)
  — no new shader; **HR** = the marker jumps blue-left (optionally a leader from the
  single-star end, like the WD-preview leader); **comp** = the He-dominant surface via
  the *normal* comp views (the stripped surface IS the story, exactly like WR);
  **readout/classify** = hot subdwarf/He-star line (reads the served **current** mass
  `Mstrip`, not `mass_init`).
- **CORE composition is INFERRED, not measured (advisor forward-note from Chunk 1).**
  The Chunk-1 state sets `Y_core=1−Z` (≈0.99 He), `X_core=0` — a He-burning core "by
  construction." But the grid state is "halfway through core-He burning," which
  *physically* has a **C/O-enriched** core, and the committed table carries no core data.
  So the comp panel's CORE view must NOT render a pristine-He core as if it were measured
  — either suppress the core view in stripped-mode (surface-only, matching "the surface
  IS the story"), or label the core explicitly as an inference. The **surface** X/Y/Z is
  the real, measured payoff; the core is a placeholder.
- **The age slider in stripped-mode** — one representative state means nothing to scrub.
  Either **disable** the slider or **relabel** it to the static stripped-phase lifetime
  (mirroring how WD/WR/SN repurpose it as an endgame scrubber). Decide here; entering a
  mode without deciding this leaves a dead control.
- **SED wind free-free tail — VERIFY, do not assume it's free.** The Chunk-2 free-free
  excess was anchored on *evolved hot supergiants* (ζ Pup: dense, slower wind). A
  stripped/WR-like star has a **fast** wind (high v∞), so `Ṁ/v∞` — what sets the
  free-free level — is small and may **not crest the photospheric floor**, or may need
  the WR caption branch instead of the supergiant one. Measure whether the tail is
  physically appropriate through the runtime before showing it; **gate it off if
  wrong-regime** (same discipline that caught the mm/radio over-brightness).
- Caption narrates the counterfactual: a close companion stripped the H envelope at
  end-of-MS; this is the ~70% binary WR/subdwarf channel; the companion is not drawn.
- Playwright-verify 1440 + 390 px, zero console errors; toggle-off round-trip asserted;
  hidden in WD/WR/SN endgames.

### Chunk 3 — stripped-star spectra (spectrum-panel follow-on, optional/deferred)
- `fetch_gotberg.py --spectra` + `scripts/bake_stripped_spectra.py` → a stripped-spectrum
  cube keyed (Teff, log g) [pure-ish He, so no [Fe/H] axis within a Z — mirror the WD
  cube's shape] → a **fourth** spectrum sibling `/stripped_spectrum` + `spectrum.js`
  `updateStripped`. CMFGEN NLTE — likely an *emission*-flavored draw at the hot/WR end,
  absorption at the subdwarf end (measure which per Teff, like the WR 7a gate). Host-baked,
  no Docker. Gated + no-model honesty edges like every other spectrum cube.

### Chunk 4 — the on-ramp to path (b) (NOT this build; recorded so it's not re-proposed)
The mass-transfer causal story with the companion drawn, the Algol mass-ratio reversal,
both stars on the HR. Needs POSYDON (HDF5, un-reconned) or MESA-binary self-run (converges
far worse than single-star — last resort) + a genuinely new two-star rendering model. This
is where path (b) begins; (a) is its honest first chunk.

## Honesty tiering (the project rule, applied)

- **Tier 1/2 (real data, changes the rendered state):** the stripped `StellarState` and
  (Chunk 3) the baked stripped spectrum — straight from the Götberg CMFGEN grid. The HR
  jump, the He surface, the hot Teff, the wind Ṁ tail are all *measured*.
- **Counterfactual labeling (like the corona / α what-if, spec §7):** the stripping event,
  the timing ("at end-of-MS"), and the un-drawn companion are narrated, not modeled. The
  what-if is visibly a hypothesis about a companion, never a claim this specific star is
  in a binary.
- The **"don't label a non-feature" check comes first** (Gate 0): visible-and-real through
  the runtime before any control ships.

## Open questions (settle as they come up)

1. **Snap key — initial mass vs stripped mass?** Lean initial mass (matches the slider's
   meaning: "what a star of this mass becomes if stripped"). **Depends on Gate 0a** — the
   1D-in-Minit vs 2D-in-(Minit×Pinit) data-shape check that blocks Chunk 1. If 2D, the
   snap key needs rework (a period axis, or snap-to-representative-period per Minit).
2. **UX entry point (i) vs (ii)** — the mid-life what-if toggle vs the end-of-life gateway.
   Chunk 2 + advisor.
3. **Below 2 M☉ / above 18.2 M☉** — hide the toggle, or snap-with-a-note. Lean: hide below
   2 (no product in grid), snap-far note above 18.2.
4. **Z→[Fe/H] snapping at the edges** — the sim axis is −1.0…+0.5; Z=0.0002 (≈−1.85) is
   below it, so effectively 3 reachable Z nodes. Honest snapped-far note.

## References

Stripped-star models & spectra: Götberg, Justham, de Mink et al. 2018 (A&A 615 A78, the
grid); Götberg et al. 2019 (A&A 629 A134, integrated-spectrum impact); Götberg et al. 2023
(stripped stars in different metallicity environments). Binary WR/stripped channel & binary
fraction: Sana et al. 2012; Shenar et al. 2020; Paczyński 1967 (the classic stripping
picture). Subdwarf–WR unification: Götberg+2018 thesis. Path-(b) binary grids: POSYDON
(Fragos et al. 2023); BPASS (Eldridge et al. 2017). See also `whirling-cohort-atlas.md`
(Tier D) and `smoldering-cinder-gateway.md` (the WR endgame this plugs into).
