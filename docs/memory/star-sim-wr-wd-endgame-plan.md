---
name: star-sim-wr-wd-endgame-plan
description: Full Wolf–Rayet & white-dwarf endgame renderers — design, measured grounding, locked decisions, chunked plan; CHUNKS 1 (backend accessor+classifier) & 2 (reversible WD gateway + WD mode shell) BUILT; plus the hot-end-can't-extend spectrum finding.
metadata:
  type: project
---

The user wants **full** Wolf–Rayet (WR) and white-dwarf (WD) support — at the
slider limits a button appears ("→ Continue: White Dwarf" / "→ Continue:
Wolf–Rayet") that jumps into a dedicated endgame renderer. **Design agreed,
plan written & committed; Chunk 1 (backend) BUILT.** Plan:
`docs/plans/smoldering-cinder-gateway.md`.

**CHUNK 1 DONE (backend endgame accessor + classifier; 137 tests, was 121 — +14
`test_endgame.py` + stub/mesa "none").** What landed:
- **`endgame()` is on the `StellarStateProvider` Protocol** (NOT a route hasattr-sniff —
  advisor: that's a §3 violation). MESA/Stub return `EndgameResult(type="none")` so the
  `/endgame` route stays provider-agnostic. `EndgameResult` dataclass lives in
  `provider.py` `{type, mass_init_msun, feh_init, final_mass_msun, wr_threshold_msun,
  states:list[StellarState]}`; its `states` are §3-clean StellarStates, the scalars are
  gateway *routing metadata*.
- **`MISTProvider.endgame` SNAPS both mass AND feh** (advisor: snapping feh is *necessary*
  — interpolating feh near the WR threshold hits the "phase present on one bracket grid,
  absent on the other" hazard the plan's own risk register flags). Reports the **true
  snapped** mass/feh (honest, §6 — verified: req(60,+0.2)→feh +0.0; req(2.7,−0.6)→feh −0.5).
- **Classification is data-derived** from the snapped track's FSPS phases: φ9→**WR**;
  φ6-present OR final-logg>7 (`_WD_LOGG`)→**WD**; ends-at-φ5-onset→**SN** (dead end,
  `states=[]` — the lone pre-collapse supergiant row is a logg≈0 artifact, dropped);
  else→**none** (low-mass still-living). **WR threshold scanned per grid, never hardcoded**
  (`_wr_threshold`): the real fine grid gives onset **+0.5→35, 0.0→48, −0.5→56** (finer than
  the coarse 40/50/60 first measured; slightly non-monotonic at low Z — m100=56<m075=58 —
  so the test asserts the metal-rich *trend* + brackets, not global monotonicity).
- **Data plumbing:** `star_mass`(current mass)+`star_mdot`(mass-loss) added to `_Track` +
  `_TRACK_COLS` + cache (**CACHE_VERSION 8→9**, one ~107 s reparse) but **deliberately NOT to
  `_grid_window`/`_blend_windows`** (advisor: the endgame snaps to one track, nothing reads a
  *blended* current mass). **StellarState UNTOUCHED** (Option B) → no `EXPECTED_KEYS` change.
  `final_mass<initial` confirmed (1 M☉→0.544 WD; 2.7@−0.5→0.672 WD; 60 M☉→23.6 stripped WR).
- **The advisor's "cooling-track monotonic" TRAP** (blocker, Locked #4): the WD endgame is
  NOT monotonic as a whole — the TPAGB pulses (φ5, 601 rows) oscillate everything (*why* we
  snap), and φ6 *contracts to a ~107 kK central star* (Teff RISES) before cooling to 2393 K.
  So **only logg is monotonic over all post-AGB rows**; Teff & L are monotonic only **past the
  CSPN Teff peak (the "knee")**. The test (`test_wd_cooling_track_is_monotonic_past_the_cspn_knee`)
  splits on the knee accordingly. Age IS strictly increasing over the whole endgame (Chunk 2's
  log-cooling-age scrub won't fold). Solar WD↔SN boundary measured between **6.5 (WD, logg 8.70)
  and 7.0 (SN)** — the super-AGB / electron-capture regime.
- **`_state_from_row` generalized with `eep_origin`** (default ZAMS row; endgame passes its
  first post-window row) so endgame states report their **continuing** EEP and **reuse the
  16-element metals-dict construction** (no drift). Endgame `win` dict = single track sliced
  `[track_end+1 .. last-real]` into the same keys `_grid_window` emits, fed straight to
  `_state_from_row`. `/endgame` returns `asdict(EndgameResult)` (states = exact StellarState shape).

**CHUNK 0 DONE (spectrum-grid scoping, research — notes appended to
`backend/docs/msg_spectra_build_recipe.md` §7):** WD-before-WR confirmed for *axis-compatibility*.
**Koester DA = GO** (SVO `koester2`, 2-col ASCII, Teff×log g, ~30–60 LOC) but a **separate WD cube**
(log g 6.5–9.5 disjoint from the main cube, [Fe/H] degenerate), not a splice. **TMAP hot WD/CSPN =
conditional GO** (bulk via SVO `tmap` SSAP only, NOT TheoSSA on-demand; 50–190 kK; **flux ×π×10⁸**;
LTE↔NLTE seam ~50–80 kK). **Koester DB = NO-GO** (restricted/non-redistributable — drop; cover hot-He
DO via TMAP). **PoWR WR = conditional GO at best** (public tarballs, but axis is wind Rt not log g →
own (T\*, Rt) cube; star must be **assumption-mapped**: v∞ + clumping D assumed, Teff↔T\* approximate;
L is *not* discarded — sets R\*→Rt). Naming trap: "Reindl 2020" pure-H grid is actually Bohlin/Hubeny/
Rauch 2020 = TLUSTY twin (95 kK cap), NOT TMAP. So Chunk 6 (Koester+TMAP) tractable, Chunk 7 (PoWR)
carries the real design cost.

**CHUNK 2 DONE (frontend reversible WD gateway + WD mode shell; frontend-only, pytest UNCHANGED 137).**
A **"→ Continue: White Dwarf"** button at the age-slider limit when the snapped star classifies WD
(honest "core collapse — not simulated" note for SN masses; nothing for none/WR — WR is Chunk 4);
click → reversible **`wd-mode`** (a "← Back to the living star" button). In the mode the age slider is a
**cooling scrubber**, **mass/[Fe/H] stay live** (re-snap → different remnant; out-of-WD-range reverts
with a note), HR swaps to **wide endgame axes** (logT→5.7, logL→−5.6) drawing the **Teff-coloured
cooling track** (cool giant → ~100–400 kK central star → cold cinder); 3D/scale/comp/readout take the
endgame StellarState; spectrum = placeholder; SED keeps the blackbody but drops the X-ray overlay.
Reusable lessons (advisor + the Playwright pass — all genuinely caught, not green-check theatre):
- **The cooling-axis crux (the forward-note #1 above, RESOLVED):** confirmed a single log-cooling-age
  axis inverts the story (601 pulse rows eat ~half the slider; the 107 kK central-star spike → a
  ~0.02-dex sliver). Fix = a **3-zone piecewise-INDEX map** — pulses 12% / rise-to-central-star 16% /
  cooling 72% — with the boundaries DERIVED from the data (last TPAGB row + hottest post-AGB "knee").
  The cooling zone is plain index-linear because **MIST's post-knee rows are ALREADY ~even in
  log(cooling age)** (measured: frac→log10(age−knee_age) monotone over 7.16 decades on 1 M☉), so each
  decade still gets visible travel — no log math needed in the mapping at all. (So the "cooling age vs
  time-since-AGB" open question dissolved: index-based scrub; the readout shows BOTH absolute age and a
  "cooling age = age − knee_age".)
- **Forward-note #2 honored:** the SN card shows the supernova mass but NO "remnant mass" line; the WD
  readout's "Remnant mass" row uses `final_mass_msun` only for WD states.
- **Separate the WD path from the live plumbing (advisor):** `refreshWD()` picks `states[i]` from the
  pre-fetched `/endgame` result — NO `/state` fetch, no window build, no phase snap. Consumers get
  **explicit mode signals**, NOT logg heuristics: `spectrum.showPlaceholder(msg)`,
  `classify.update(s,"wd")` (AGB→PN-central-star→white-dwarf by phase+logg, dodging "O2 III blue
  giant"), `sed.update(s,{endgame})` (drops the dynamo-less X-ray band). `hr.setEndgame/clearEndgame`.
- **TWO real bugs the Playwright pass caught:** (a) a live `/state` landing **after `enterWD()`
  clobbered the WD render** (reqToken only catches newer `refresh()` calls, not a mode switch) →
  `refresh()`/`refreshTrack()` now bail if `mode !== "live"` + `enterWD` bumps the tokens; (b)
  **`exitWD` returned the wrong star** — typing an SN mass in the FOCUSED number box reverts `massValue`
  but `setNum`'s focus-guard can't update the box, so the **blur `change` on the exit click re-commits
  the stale value** right before exit → `exitWD` restores `lastWDMass/Feh` (the confirmed WD progenitor
  we were viewing), deterministic regardless of the race. (General lesson: a focus-guarded number box +
  a click that blurs it = a stale re-commit; restore from a known-good var, don't trust the live value.)
- **Lazy `/endgame` fetch** (when the age nears the limit, not per mass drag — 1 MB/58 ms, only when it
  matters). Verified via **Playwright bundled Chromium** (the `chrome --headless` hijack caveat),
  **22/22**: gateway→scrub pulses/107 kK central star/2393 K cold WD (logg 7.95)→re-snap 1→3 M☉
  (remnant 0.544→0.666)→SN revert→reversible Back→SN note at 8→none at 0.3; §10 living Sun anchor
  (1.07, 5834 K, G2 V) + variable-star overlay unregressed, HR reverts to normal axes on exit, no JS
  errors. First-pass comp feeds the endgame track as-is (DA hydrogen surface correct). **WD-correct 3D
  shader + WD-semantics structure panel = Chunk 3; WR branch = Chunk 4.**

**Remaining: Chunks 3–7** (WD 3D shader + structure panel, then the WR mode shell + 3D wind shader, then
the data-gated WR/WD spectra above).

**The hot-end question that preceded it (answered, closed):** "is there a dataset
to extend the *higher* (hot) end?" → **No.** OSTAR2002 (Teff [27500, 55000] K) is
the **hottest grid on the entire MSG library** (verified the grids page: OSTAR,
BSTAR2006, C3K, CAP18, Coelho14, Göttingen, SPHINX, BT-Settl, NewEra — none hotter).
Nothing above 55000 K exists in MSG. PoWR (WR, ~200 kK) / TMAP (hot WD/CSPN) exist
*outside* MSG but are wrong physics for a massive **main-sequence** O star (WR =
wind emission lines; TMAP = WD gravities logg 7–9) AND not MSG `.h5` (pymsg can't
read them). So the existing hot-end **no-model notice above 55000 K is the correct
behavior**; don't extend it. (BSTAR2006 is the only refinement option — NLTE inside
15000–30000 K, replaces not extends.) This is what turned the conversation toward
WR/WD as their *own* renderers.

**Measured grounding (re-verify if grids change — both my first guesses were WRONG,
advisor caught them):** the MIST EEP tracks ALREADY carry both endgames — they're
just clipped by the `phase >= 5` window cutoff (NOT missing data, NOT a new
provider). Measured from `feh_*/eeps/*.track.eep`:
- **WD on disk for low/int mass:** 1 M☉ p000 → EAGB(φ4) → **TPAGB φ5 = 601
  thermal-pulse rows** → **post-AGB φ6 = 312 rows** spanning Teff 2393–106663 K,
  logg −0.2…**8.0**; final row a cold WD (2393 K, logg 7.95, logL −5.31, **27.55
  Gyr**). The WD *cooling track is clean/monotonic*; only the TPAGB *bridge* is the
  mess.
- **WR on disk for the very massive end, feh-gated:** φ9 (`9:"WR"` already in
  `_PHASE_NAMES`) appears at **≥40 M☉ at [Fe/H]=+0.5, ≥50 at 0.0, ≥60 at −0.5…−1.0**
  (more metals → stronger winds → strips at lower mass). Large segment (146 rows @
  60 M☉, 449 @ 300 M☉), Teff to **~250000 K**. ≈8–40 M☉ just end at φ5 → core-collapse
  SN (NOT rendered — honest dead-end branch).
- EEP header carries **`star_mdot`** (mass-loss → WR wind axis) and **`star_mass`**
  (final mass → WD initial-final mass relation). **GOTCHA:** EEP filename = `int(mass
  *100)` zero-padded 5 (60 M☉ = `06000M`, 300 = `30000M`; I once mis-typed `00060M`
  =0.6 M☉ and got all-zeros).

**Architecture spine (4 principles):** (1) **No new provider** — WR/WD ARE
`StellarState`; extend the window, `/endgame` goes THROUGH `PROVIDER`; spectra stay
siblings. (2) **Sim interpolates; endgame SNAPS to one real grid track** (MESA
precedent) — this dissolves the TPAGB problem: pulses can't be interpolated across
mass but ONE star's real pulses scrub fine (user's "bigger slider" was right axis-
wrong: the fix is snap-not-interpolate + fine scrub). (3) Gateway **narrates the
un-simulated gap** (PN ejection / pre-SN). (4) **Evocative-but-labeled** shaders
(corona precedent); missing spectra show an honest "no atmosphere model yet"
placeholder, never a faked clamp.

**Locked decisions (user):** (1) gateway **reversible** (slide back to the living
star); (2) **mass stays live** in the endgame (re-snap → different WD final mass /
WR type); (3) WD cooling-age axis **log** (27 Gyr span); (4) present the **full
scrubbable sequence** (pulses → ~100 kK central-star/PN → Gyr cooling), not a
snapshot.

**Chunked plan (8 chunks; 1–5 on-hand data, 6–7 data-gated spectra last, 0
parallel research):** 0=spectrum-grid scoping (PoWR/Koester/TMAP exist? format?
license? pymsg can't read → new converter), 1=backend endgame accessor+classifier
(snap-to-track, type WD/WR/SN, true+final mass, feh WR threshold), 2=reversible
gateway + WD mode shell (HR cooling track + log cooling-age + live mass), 3=WD 3D
degenerate-sphere shader + structure panel, 4=WR mode shell + HR-to-250kK +
stripped-surface composition, 5=WR 3D wind shader, 6=WD spectra (Koester/TMAP,
separate logg-7–9 cube — the tractable one, hydrostatic keys on Teff+logg), 7=WR
spectra (PoWR wind-axis — hardest; reconcile with `star_mdot`). **Key risk:** the
spectra are the ONE thing not on-hand & NOT the MSG bake pattern → scope (Chunk 0)
before promising "full spectra"; honest fallback = labeled placeholder.

See [[star-sim-phase5-spectra]] (the spectrum sibling + bake/runtime this builds on),
[[star-sim-phase4-mesa]] (snap-to-track precedent), [[star-sim-mist-provider]]
(the window/phase machinery being extended).
