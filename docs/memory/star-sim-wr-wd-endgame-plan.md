---
name: star-sim-wr-wd-endgame-plan
description: Full Wolf–Rayet & white-dwarf endgame renderers — design, measured grounding, locked decisions, chunked plan; CHUNKS 1 (backend accessor+classifier), 2 (reversible WD gateway + WD mode shell) & 3 (WD 3D shader + structure panel) BUILT, plus the Chunk-2/3 continuous-living→WD-transition fix (degeneracy-gate corona+SED X-ray, raise GATE_SHOW→0.999); plus the Lane–Emden-in-WD hint (a WD IS a degenerate polytrope n≈1.5→3; hint+caption coherence; editing a static n-only caption ≠ breaking decoupling); plus the hot-end-can't-extend spectrum finding.
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

**CHUNK 3 DONE (WD 3D shader + structure panel; frontend-only, pytest UNCHANGED 137).** The WD-correct
renderers replace Chunk 2's first-pass ones. **3D shader (`star.js`):** `update(state,{endgame:"wd"})`
draws a **smooth, featureless cooling sphere** — granulation off, corona off, blackbody color from Teff
(blue-white central star → orange cold cinder), quadratic limb darkening. **The advisor's two corrections
shaped it:** (1) **crystallization is a CORE phenomenon, NOT photospheric** — faceting the gaseous surface
would imply a crystalline *surface* (wrong) AND is simpler-and-more-correct, so the 3D sphere stays
perfectly smooth and the crystal cue goes in the structure-panel CORE; (2) **granulation is faded by a
log g GATE** (`uGran = clamp((4−logg)/3)`), not a hard wd flag, so the sequence's opening **TPAGB giant
still boils** (real convective star, log g≈0.5→uGran 1) and only the degenerate remnant is smooth. Living
path (no opts) auto-restores granulation+corona on exit (the Chunk-2 exit-restoration discipline).
**Structure panel (`comp.js`):** new `setEndgame(states)`/`clearEndgame()` (mirrors `hr.setEndgame`) swap
the burning-abundance views for a **schematic layered cross-section** (onion disk: C/O core under thin He
buffer under thin H DA atmosphere + a label column), driven by the MARKER state, not the EEP/track
machinery. **Honest where the data is, schematic-and-labeled where it isn't — MEASURED via `/endgame`
curl before building** (the recurring "verify before you label" discipline): the loaded MIST grid gives
**ALL DA + C/O WDs** across masses 1–6.5 (surface purifies to **pure H** by gravitational settling —
X_surf 0.70 central star→1.00 cold WD; the core is **already C/O at the TPAGB**, Z_core=1, C≈0.24/O≈0.74),
so the **core C:O ratio and DA/DB atmosphere type are READ FROM THE MODEL each frame** (data-driven); the
**He buffer + ALL layer thicknesses are canonical & exaggerated to be visible** (no radial structure is
modeled — the Lane-Emden/MESA-profile territory), with the drawn **envelope thinning as log g rises**
(giant shedding→degenerate thin skin, tied to real log g). **Crystallization in the core, onset log
g-GATED** (~6.5 kK at log g 7.95 for 0.54 M☉ up to ~13 kK at log g 8.7 for 1.0 M☉ — the Gaia
crystallization sequence; a fixed Teff threshold would under-state massive WDs), grows center-out. The
non-DA/He-core paths are a **minimal data-parameterized fallback** (commented; don't author untested DB
artwork that reads as a tested feature — advisor). **The mass–radius relation is the re-snap payoff** the
floor-clamped 3D sphere CAN'T show (advisor) → it lives in the readout + scale bar: re-snap 1→6 M☉ shrinks
the WD (R 0.0129→0.0079 R☉, log g 7.95→8.63, remnant 0.544→0.973, ~82%→~90% crystallized), cold-WD scale
marker lands at the **Earth dot** (≈1.4 R⊕ — "Earth-sized" made visual). **Width-fix (advisor-caught — my
wide-only 1440/760 screenshots MISSED it; the project verifies 390 px every frontend chunk):** the first
pass drew label sublines at a fixed x with no wrap → **truncated at phone width** (confirmed at 308 px:
"…~1e-4 M (schema", "…≈99% of the m"); the caption clipped too. Fix = label sublines **wrap** to the
column width + the caption reserve is **DYNAMIC** (`wrapText` returns its line count → `capH` = lines·lh).
**General lesson: a fixed-x / fixed-reserve canvas layout is width-fragile; verify at 390 px, not just
wide.** `main.js` wires `star.update(s,{endgame:"wd"})` + `comp.setEndgame/clearEndgame` in
refreshWD/enterWD/exitWD/tryWDResnap; CSS hides the comp mode toggle + legends in `body.wd-mode`. Verified
via **Playwright bundled Chromium** (the `chrome --headless` hijack caveat) at **1440 AND 390 px**: cooling
sequence (boiling amber giant→smooth blue-white 107 kK central star→smooth orange Earth-sized cold WD),
structure "thick envelope→thin skin" + growing crystallized core, mass-radius re-snap, reversible exit
(granulation+corona+comp toggle all return; living Sun/HR unregressed). Only the pre-existing favicon 404.
**Tracked for Chunk 6:** the spectrum shows the WD placeholder for the WHOLE endgame scrub incl. the
TPAGB-giant rows where it's false (a ~3600 K giant has a real spectrum) — Chunk-2 `refreshWD` behavior,
make it phase-aware when wiring WD spectra.

**CHUNK 2/3 FOLLOW-UP DONE (continuous living→WD transition; frontend-only, pytest UNCHANGED 137).**
User: switching into the endgame "feels some steps are missing" — corona vanished, SED coronal X-ray/
radio band vanished, radius popped. Root cause (curl `/state`+`/endgame`, advisor-reviewed): endgame
`states[0]` (first thermal pulse) is the **very next track row** after the living EAGB endpoint —
near-identical (mass 1: R 82.8→86.6, Teff 3624→3601, **activity 0.82→0.83**) — so the *data* is
continuous, but the corona (`star.js`) + the SED X-ray overlay (`sed.js`) **hard-switched on the wd
mode flag** while granulation already faded via the log g gate. FIX = drive **corona AND the SED X-ray
overlay by the SAME degeneracy gate `clamp((4−logg)/3)`** granulation uses → all three fade together:
the opening AGB giant keeps the boil+glow+dimmed coronal band it had as a living star (a *continuation*),
dying only as the bared core degenerates (gDeg→0 at log g≳4 → smooth glowless cold WD, no band). Living
stars pass gDeg=1 → byte-identical. **2ND ADVISOR PASS caught a mid-scrub artifact endpoint-only checks
missed:** routing the endgame through the living Teff-regime machinery, its **hard coolgiant→cool branch
boundary at 5000 K** would flash the band UP to the brighter dynamo level as the post-AGB contraction
races through 5000–6500 K — scanning the real `/endgame` states found a **1-row pop for ~2 M☉** (none
for 1/3 M☉, whose rows skip the zone). FIX = in the endgame draw **ONLY the dimmed "dying-giant" band
gated by gDeg** (a contracting post-AGB core is not a cool MS dynamo / A-F gap / O-wind star → skip the
whole living regime machinery), so the band stays pinned at one level and fades monotonically (2 M☉
danger row now flat: band ymean 82→83, count fading not jumping). REUSABLE: **verify the MIDDLE of a
scrub, not just the endpoints** — a fix that newly draws through a regime the living path never traversed
can pop at a hard branch boundary. **The radius pop was a latent bigger bug** (advisor + curl): the
gateway showed at `GATE_SHOW=0.98`, but the linear-age axis crams RGB-tip→CHeB→EAGB into the last ~2% →
at 0.98 the living star is still a **mid-RGB star** (R=8.4) → entering jumped RGB→AGB-giant (10×). FIX =
raise `GATE_SHOW`→**0.999** (gateway only at the true end, where the step to states[0] is imperceptible —
displayRadius 2.42→2.43); the age snap (drags within 1.5% → exactly 1.0) keeps it a natural "slam right",
`/endgame` still prefetches at 0.9. **Blocker verified FIRST** (advisor): corona continuity needs endgame
`states[0].activity` ≈ the living end-row's (the old hard-off never read it) — curl confirmed (0.82↔0.83),
so the gate alone suffices. **Spectrum held OUT of scope** (advisor): the WD placeholder is honest (no
atmosphere grid at log g 7–9); a giant-phase "show the real spectrum" reintroduces the wrong-clamp Chunk 2
avoided — same symptom, separate Chunk-6 decision (the Tracked note above). REUSABLE LESSON: render the
endgame by the **star's state (a degeneracy gate), not a mode flag** — so the gateway is a *continuation*,
not a cut; and a too-loose end-of-life threshold + a linear-age axis = the visible "missing steps". Verified
Playwright (bundled Chromium): gateway hidden 0.95/0.98 / shown 1.0; WD entry indistinguishable from the
living EAGB end (corona ring+boil)+324 coral X-ray px; cold WD smooth glowless+0 coral px; reversible exit.

**LANE–EMDEN-IN-WD FOLLOW-UP DONE (frontend-only, pytest UNCHANGED 137).** User asked: is the
Lane–Emden interior panel *irrelevant* to the WD endgame (it's the one panel that doesn't transform —
a decoupled sibling showing the user's chosen n)? **The answer FLIPS it:** a white dwarf **IS** a
degenerate polytrope (n≈1.5 non-relativistic → **n=3** as the mass nears the **Chandrasekhar limit**;
the n=3/γ=4/3 limit is *why* there's a max mass — same physics as this gateway's mass–radius relation +
the WD→SN boundary), so it's the *most* relevant the panel ever gets. **n.b. auto-deriving n is the ONE
honest carve-out here** (a WD genuinely is a polytrope) vs the rejected MS-star auto-derive (MIST gives
no convective/radiative split → faked fit) — but the user chose **"hint, keep n user-set"** (preserve
the decoupled-toy design). Built: a `body.wd-mode` gold callout that **swaps in for** the general "not
the real interior" intro (`.lane-wd-hint` shown, `.lane-intro` hidden via CSS), pointing at n≈1.5–3.
**ADVISOR caught two things:** (1) hiding the intro made a latent caption clash WORSE — the intro was
the disclaimer that *reconciled* lane.js's general n=3 caption ("a Sun-like radiative star"); gone, the
WD hint sat directly above a Sun-star label with nothing bridging. (2) **THE KEY UNLOCK / a premise I had
WRONG: editing a static n-only caption does NOT break decoupling.** Decoupling = not feeding *star state*
(`refresh`/`refreshTrack`) into the panel; a richer n-only string keeps n the sole driver. I'd conflated
"don't touch lane.js" with "keep it decoupled" — they're different. FIX = enrich the **n=3 landmark
caption to carry BOTH framings** ("…a Sun-like radiative star — and, by the same maths, a relativistic
degenerate gas: a white dwarf near the Chandrasekhar mass…"), both true; **n=1.5 already carried both**
(always named white-dwarf cores), so hint + the two captions now tell one coherent story. All HTML + CSS
+ one caption string; lane.js stays decoupled (never wired to refresh). Verified Playwright bundled
Chromium at **1440 AND 390px** (the documented per-chunk phone check — the overflow flag was the
hover-tooltip element, hint text wraps clean): live→intro / wd→hint swap + reverse on exit, n
slider/readout stay live in wd-mode (drag n=3 → ξ₁ 6.90, ρc/ρ̄ 54.18), 0 JS errors. **CAVEAT (advisor,
not gated):** the static hint shows for the whole wd-mode scrub incl. the opening TPAGB-giant rows where
"degenerate core" is premature — same character as the Chunk-6 spectrum-placeholder note, milder.

**Remaining: Chunks 4–7** (WR mode shell + HR-to-250kK + stripped-surface composition, then the WR 3D
wind shader, then the data-gated WR/WD spectra above).

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
