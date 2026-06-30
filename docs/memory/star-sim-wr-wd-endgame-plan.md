---
name: star-sim-wr-wd-endgame-plan
description: "Full Wolf–Rayet & white-dwarf endgame renderers — design, measured grounding, locked decisions, chunked plan; CHUNKS 1 (backend accessor+classifier), 2 (reversible WD gateway + WD mode shell), 3 (WD 3D shader + structure panel) & 4 (WR mode shell + HR-to-316kK + stripped-surface WN→WC→WO composition via the NORMAL comp views + WN/WC/WO subtype + mass-stays-live re-snap; SED coronal band suppressed; un-modeled gap narrated at the END = core-collapse; living→WR seam verified continuous before coding) & 5 (WR 3D optically-thick-wind shader: WIND_FRAG additive halo over the opaque sphere — limb-brightened electron-scattering haze + outward-advected value-noise filaments, Z_surf density cue WN→WC/WO, honest Teff color NOT a chemistry hue, intensity ramps by X_surf strippedness (≈off at WNh entry → blazes up as H strips: no entry pop, the continuation-not-cut discipline) × a clamped-L tie NOT a measured Ṁ; FIT-TO-FRAME extent recomputed each frame because the WR scrub opens on a huge R≈33 star that would clip; uTime wiring trap) BUILT, plus CHUNK 6a (Koester DA WD spectra: a SECOND spectrum sibling /wd_spectrum, a separate rectangular host-baked Teff×logg cube — 82×13, pure-H so no [Fe/H], NO Docker/pymsg via fetch_koester.py+bake_wd_spectra.py; DC Planck-continuum below the ~5000 K floor + 80 kK no-model honesty edges; phase-aware logg≥6.0 cube switch fixing the Chunk-3 TPAGB-giant-placeholder polish; BAKE_VERSION now coupled across THREE files; 137→153 tests) & CHUNK 6b (TMAP NLTE hot-WD/CSPN spectra: SVO `tmap` H-rich Hemass=0 slab spliced as the >80 kK hot slab of the SAME WD cube → 93×13, grid koester2-DA+TMAP-CSPN, host-baked fetch_tmap.py — no Docker; the ~100–400 kK post-AGB central star now shows a real spectrum where the no-model frame was, regime "CSPN" logg-aware; MEASURED corrections to the §7 scoping: NO ×π×10⁸ — SVO ascii is physical, seam ratio 1.005–1.021 → no rescale; vacuum→air; log-linear blue-gap fill for TMAP's 3200 Å start; logg-clamp 5.4→6.5 honest because the optical is logg-insensitive at CSPN temps (Δ0.03 vs 0.41 for a cooling DA); NO BAKE_VERSION bump (OSTAR precedent — re-bake before tests); advisor-caught the contracting-RISE no-model flash → route on the MAIN cube's REAL 55 kK ceiling not 80 kK; Query teff bound→500000; residual no-model re-pointed at TMAP's 190 kK ceiling; 153→157 tests) BUILT, plus the Chunk-2/3 continuous-living→WD-transition fix (degeneracy-gate corona+SED X-ray, raise GATE_SHOW→0.999); plus the Lane–Emden-in-WD hint (a WD IS a degenerate polytrope n≈1.5→3; hint+caption coherence; editing a static n-only caption ≠ breaking decoupling); plus the hot-end-can't-extend spectrum finding; plus the living-HR endgame preview (eager /endgame fetch + a fetchEndgamePreview/maybeFetchEndgame token race), wd-mode hides the variable-star overlay, and total age in the cooling caption."
metadata: 
  node_type: memory
  type: project
  originSessionId: 21a0b8fa-fa38-49c1-9e10-eaa9aea3a27a
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

**CHUNK 2/3 FOLLOW-UP #2 (user-reported, frontend-only, pytest UNCHANGED 137).** Three endgame UX fixes:
**(1) living-HR endgame PREVIEW** — `hr.setEndgamePreview(states)` draws the WD cooling track
faint+dashed+CLIPPED to the living-axes frame ("where this star is headed"; the in-bounds stretch is the
post-AGB climb toward the hot upper-left + the start of the cooling sweep), the mirror of the endgame
view's faint living track. Fed by a new `fetchEndgamePreview()` that fetches `/endgame` **eagerly on
every track load** (user accepted the ~1 MB cost — it rides the track debounce, once per settled
mass/[Fe/H], and also warms the gateway), gated to `type==="WD"` (SN/WR show nothing — never promise a
remnant the star won't form). **TOKEN-RACE TRAP (advisor-caught, the screenshot MISSED it — happy-path
Sun at 4.6 Gyr never hit it):** `fetchEndgamePreview` and `maybeFetchEndgame` share `endgameToken`; when
`refreshTrack` runs at `ageFraction≥GATE_FETCH` (most clearly **exit-WD**, which pins to age=1) BOTH
fire, the latter wins the token, and the former returns early on the stale token → preview silently never
sets at the EAGB endpoint. FIX = `maybeFetchEndgame` ALSO calls `hr.setEndgamePreview` in its success
branch, so whichever fetch wins the race sets it. **(2) variable-star overlay toggle hidden in wd-mode** —
`hr.js draw()` skips `drawOverlay` in endgameMode, so the toggle was a dead click + an orphaned legend;
CSS `body.wd-mode .hr-modes,.legend-vars{display:none}` mirrors `#sed-rot`. The classical instability
strip is a LIVING-star feature (WD pulsators like ZZ Ceti are a different mechanism) → hide > draw; state
is preserved + re-shown on exit. **(3) total age in the cooling caption** — already in the WD readout's
Age row (`s.age_yr`, cumulative from ZAMS incl. cooling), but the user didn't see it there; surfaced in
the prominent `endgame-age-caption` ("· total age N Gyr since ZAMS") where the eye is. Verified Playwright
bundled Chromium incl. **enter→exit-WD → preview reappears** on the living HR; 20 M☉ (SN) shows no preview;
saturated/slow checks; Sun anchor 1.07/5834 unregressed.

**CHUNK 4 DONE (WR mode shell + HR + composition; frontend-only, pytest UNCHANGED 137; 31/31 Playwright
on the real served UI at 1440 + 390 px).** A **`→ Continue: Wolf–Rayet`** button at the age-slider limit
when the snapped star classifies WR (threshold-gated by Chunk 1's classifier) → reversible **`wr-mode`**.
The WR side SHARES the WD gateway scaffolding: `exitWD`→**`exitEndgame`** (handles both), `lastWDMass/Feh`→
shared **`lastEgMass/Feh`**, a **`tryResnap()` dispatcher**, and **3-way** event handlers (`mode !== "live"
? egResnap : track`). What's WR-specific:
- **Scrub = plain index-linear** over the φ9 sub-track (`wrIndexFromFraction = round(frac·last)`), NOT the
  WD 3-zone pulse map — the WR sub-track is ONE clean monotonic stripping run (no chaotic pulses to dodge).
  One landmark: the **WN→WC transition** (`wrZones`: first row with surface **Z_surf ≥ 0.4**), with a snap
  target there. **wc = -1 for WN-only stars** (measured: 35 M☉ @ +0.5 ends Y_surf 0.955 — never reaches WC);
  the tick logic drops the WC tick then (verified).
- **THE KEY REUSE (advisor-endorsed): the composition panel uses its NORMAL burning-abundance views, NOT a
  WD-style custom cross-section.** The WR sub-track has a real EEP axis with an evolving surface, so the
  WN→WC→WO stripping story falls out of the existing bulk/cno views from REAL DATA — `comp.setTrack(states)`
  + `comp.update(s)`, never `comp.setEndgame`; the comp mode toggle STAYS visible (no `body.wd-mode`-style
  hide). Both less code and more honest than authoring artwork. (Core: He→C/O burning; surface: H vanishes,
  He then C/O metals take over — both visible at once.)
- **HR WR-specific bounds** via generalized **`hr.setEndgame(states, kind)`**: logT 3.6–5.5 (≈4 kK–316 kK),
  **logL 4.3–7.0** — WR is FAR more luminous than the WD endgame (the WD's logL ceiling 4.5 would clip the
  whole WR track; measured **300 M☉ peaks at logL 6.80**, the onset). `endgameKind` picks bounds+gridlines.
- **WN/WC/WO subtype from the surface composition** (`classify.js` `wrLabel`, mode `"wr"`): Z_surf<0.4 → WN
  (X_surf>0.1 → **WNh**, H still present); C/O-dominant → WC; hottest (Teff≥200 kK) + O>0.2 → WO. Data-driven,
  schematic-labeled.
- **3D = smooth blazing-hot sphere** (`star.update(s,{endgame:"wr"})` → gDeg=0, granulation+corona off) — a
  **deliberate Chunk-5 placeholder** for the wind shader (verified at 390 px it reads as a hot luminous star,
  not broken). **SED suppresses the coronal band ENTIRELY** (`{endgame:"wr"}` → `endgameWR` skips
  `drawActivity` — a WR is wind-driven, not a convective dynamo; UNLIKE WD which keeps a gDeg-faded band) AND
  hides the two `.sed-nonthermal-legend` entries (don't label a non-feature). Spectrum = honest placeholder.
- **ADVISOR-CRITICAL framings, both honored:** (1) **verify the living→WR seam BEFORE coding** (the WD chunk's
  worst bug was a gateway radius pop the happy-path screenshot missed): dumped `track(m,feh)[-1]` vs
  `endgame.states[0]` for 60/50/40/300/35 M☉ — all CONTINUOUS (60 M☉: living CHeB R=36.5/Teff=31kK → WR
  R=33.4/Teff=32kK), and GATE_SHOW=0.999 + the age-snap (any frac ≥0.985 → exactly 1.0) means the gateway
  shows ONLY at the true endpoint → no pop, same safety as WD. (2) **the un-modeled gap is at the END for WR,
  not entry** (the WR stripping IS modeled — it's the track's mass loss) → narrate it in the **end-of-scrub
  caption** ("Hottest stripped core ~249 kK — next is core-collapse… not modeled"), the mirror of the WD's
  PN-ejection-at-entry. Don't clone the WD bar text (separate WD/WR title+narrate spans toggled by body class).
- Verified incl. the **successful WR→WR re-snap** (Locked #2 — the advisor caught my first test only covered
  the revert): 60→100 swaps the sub-track (final mass 23.6→33.2, progenitor 100, ticks rebuild, scrub still
  maps, NO revert note), then 100→20 (SN) reverts to 100 with a note. Plus WN-only (35 @ +0.5: no WC tick,
  stays WN at the hot end, core-collapse caption), Sun anchor unregressed, 0 JS errors.

**CHUNK 5 DONE (WR 3D wind shader; frontend-only, pytest UNCHANGED 137; Playwright bundled-Chromium
pass on the real served UI at 1440 + 390 px).** Replaces Chunk 4's smooth blazing-hot-sphere
placeholder with the **optically-thick-wind look**. A new `star.js` **`WIND_FRAG` + `wind` mesh** (a
second camera-facing additive quad, `visible=false` in EVERY non-WR path → living + WD byte-identical)
wraps the still-opaque hot sphere in a luminous **wind halo**: an electron-scattering **haze brightest
in a thin annulus AT the limb** (softens the hard edge into the wind — the "pseudo-photosphere"; the
limb-brightening is genuinely apt for an extended scattering atmosphere) decaying outward, broken up by
**radial outflow filaments** (2D value noise sampled in cartesian space — no atan/seam — advected
OUTWARD over `uTime`, two decorrelated octaves so they scatter organically NOT into spokes; smooth haze
is the base). No granulation/corona (gDeg=0 unchanged). **Evocative/labeled** (the WR narrate paragraph
in index.html now says so): the COLOR is the honest Teff blackbody; the halo's reach (`desiredExtent`)
and density (`uFalloff`/`uDensity`) read from **`Z_surf`** (smooth extended helium WN → denser clumpier
carbon/oxygen WC/WO), intensity from a gentle **clamped `L`** tie — explicitly **NOT a measured Ṁ**
(`star_mdot` isn't on StellarState, §3/Option B).
- **ADVISOR-CRITICAL (caught BEFORE coding, the headline):** the WR scrub **opens LARGE** — confirmed
  via curl `/endgame?mass=60&feh=0`: `states[0]` R≈33.4 R☉ → `displayRadius`≈2.23 (near the 2.65 clamp);
  the camera (z=8, 40° vfov) sees ±8·tan20°≈2.91 world units, **tighter horizontally at 390 px** (aspect<1).
  A **constant** halo extent would straight-edge-clip the viewport (the framing-pop family that bit
  Chunks 2/3). FIX = **fit-to-frame extent** (`applyWindScale`: half-size = `min(rad·desiredExtent,
  0.95·FRAME_HALF_H·min(1,aspect))`, `uInnerFrac = rad/half = 1/extent`), recomputed **every frame** in
  `animate()` so a live resize can't reintroduce the clip. Happy side effect: the halo is **thin at the
  big entry → fuller as the core strips and shrinks** (measured 60 M☉: R 33→0.57, Teff 32→249 kK, Z_surf
  0.016→0.866) — physically apt AND a gentle entry (no pop). **REUSABLE: a fixed-extent additive halo is
  frame-fragile exactly like the fixed-x canvas layout (Chunk 3) — fit it to the frame, verify 390 px.**
- **ADVISOR 2ND-PASS, the entry-pop fix (don't ship a rationalized flag I'd talked myself out of):** the
  fit-to-frame capped *extent* but NOT *intensity*, and intensity was `L`-driven with `logL`≈6 ~flat across
  the sub-track → the wind blazed at ~full even at the WNh entry, popping from the near-glowless living
  CHeB star into a bright limb RING (also the "eye/ring" look I'd rationalized as "limb-brightening").
  FIX = **ramp wind intensity by STRIPPEDNESS, not L**: `wStrip = 1 − clamp(X_surf/0.25)` (X_surf is on
  StellarState; ≈0 while H-rich at the WNh entry X≈0.28, →1 by frac≈0.28 as H vanishes, exactly as Z_surf
  flips to WC). Now the gateway is a **continuation** — entry = the bare continuing sphere (matches the
  living star, only granulation/corona fade, the accepted Chunk-4 seam), the wind blazes UP as the core
  strips (a real WN→WC growth in the wind, not just Z_surf clumpiness). **REUSABLE: render the endgame by
  the star's state (here X_surf), not a mode flag — the "continuation not a cut" discipline every endgame
  chunk used; and don't accept your own rationalization of a flag you AND the advisor both raised.**
- **ADVISOR rejected a chemistry-driven emission HUE** (my Q): it would actively contradict the spectrum
  panel's honest "no WR emission model yet" placeholder (an emission-line-coloured halo claims what that
  disclaims). So color stays the Teff continuum; the WN/WC/WO flavor falls out of state for free (hotter→
  bluer, more-stripped→smaller R→fuller fit-to-frame halo) + the **structural** `Z_surf` density cue
  (denser/clumpier WC/WO). Don't make chemistry-colour the mechanism.
- **`uTime` wiring trap (advisor):** the corona has NO `uTime` updated in `animate()`; the wind needs its
  own driven by the same clock or the outflow freezes. Easy to forget — wired.
- **Verified** (Playwright bundled Chromium — the `chrome --headless` hijack caveat): WNh entry (smooth
  thin halo, big star) → WC mid (clumpy ring) → WO end (compact blazing core + dense clumpy halo), filaments
  ORGANIC not spokes, **no frame clip at 1440 OR 390 px**, reversible exit restores granulation+corona on
  the living star (wind gone), living Sun (granulation+corona, no wind) + cold WD (smooth glowless, no wind)
  unregressed, **0 real JS errors** (only Playwright's own WebGL `ReadPixels` GPU-stall perf warnings from
  screenshotting a WebGL canvas — benign, not from the page).

**CHUNK 6a DONE (Koester DA WD spectra; backend + frontend, pytest 137→153, +15 `test_wd_spectra.py`;
Playwright bundled-Chromium pass at 1440 + 390 px, 0 JS errors).** The first real endgame spectrum — the
tractable, hydrostatic one. **Host-only vertical, NO Docker/pymsg/Fortran** (Koester models are plain
2-col ASCII, unlike the MSG `.h5` grids the main cube needs). Two commands rebuild it:
`python -m star_sim.fetch_koester` (SSAP bulk-fetch ~1066 models) + `python scripts/bake_wd_spectra.py`.
- **A SECOND spectrum sibling** `/wd_spectrum` (beside `/spectrum`), bypassing `PROVIDER` like every
  spectrum route. New files: `star_sim/fetch_koester.py`, `scripts/bake_wd_spectra.py`,
  `tests/test_wd_spectra.py`; edits in `spectra.py` (`wd_spectrum_data`, `_load_wd`, `_planck_lambda`,
  `WD_GRID_FILENAME`, separate `_WD_CACHE`), `api.py` (the route, 503 on missing cube), `conftest.py`
  (`requires_wd_spectra_data`), `frontend/src/spectrum.js` (`fetchWD`/`updateWD`, `balmer:true` guides),
  `frontend/src/main.js` (`refreshWD` switch).
- **A SEPARATE rectangular cube, no void-fill** — the Koester DA grid is complete: **82 Teff (5000–80000 K)
  × 13 log g (6.5–9.5 / 0.25) = 1066 models**, pure hydrogen so **no [Fe/H] axis** (`feh_varies:false` →
  "Pure hydrogen, so [Fe/H] doesn't apply"). The bake **asserts** rectangularity (unlike the MSG cubes'
  39%-void three-pass fill); same axis-generic `.npz` schema so the runtime reuses `_Spectra` verbatim (a
  2-axis Teff×log g cube, like the original solar `sg-demo`). Baked onto the **same 3000–9000 Å @ 2.5 Å**
  grid as the main cube; **air wavelengths** confirmed (Balmer minima within 0.05 Å of air positions), so
  the x-axis/guides don't jump when the panel switches cubes.
- **TWO honest edges, both measured through the runtime, both the "don't label a non-feature" discipline:**
  (1) **DC below the ~5000 K Koester floor** — a real cooling DA loses its Balmer lines (measured Hα ~9% at
  5000 K vs ~61% at 13 kK), so below the floor `wd_spectrum_data` returns an **honest Planck blackbody
  continuum at the REQUESTED Teff (NOT clamped)**, tagged `regime="DC"` — never the 5000 K line-bearing
  spectrum painted onto a 2393 K cinder (that would add H lines it lacks AND give a too-blue slope).
  (2) **80000 K ceiling = intentional no-model** — the ~107 kK post-AGB central star is past Koester;
  reports `teff_requested > teff_max` and the panel's existing `teffAboveGrid()` path draws the honest
  "no model" frame. **That gap is exactly what TMAP fills in 6b** — tracked, not patched.
- **Phase-aware cube switch by surface gravity, fixing the Chunk-3 "Tracked for Chunk 6" polish:** the
  Chunk-2 `refreshWD` showed the WD placeholder for the WHOLE scrub incl. the TPAGB-giant rows where it's
  FALSE (a ~3600 K giant HAS a real spectrum). Now `refreshWD` switches on **log g ≥ 6.0 → `updateWD`** (the
  Koester cube), **else `spectrum.update`** (the main cube) — so giant rows show their real spectrum and the
  WD cube engages only once degenerate. The 6.0 threshold sits in the EMPTY main(≤5)/Koester(≥6.5) gravity
  gap (= the no-model central-star spike), so the switch is invisible.
- **`BAKE_VERSION` is now coupled across THREE files** (was two): `spectra.py`, `scripts/bake_spectra.py`,
  **and** `scripts/bake_wd_spectra.py` — the WD cube shares the schema + `_Spectra` reader, so it shares the
  version; bump all three together or the runtime rejects the cube.
- **Tests measured through the runtime path** (not raw grid numbers): Balmer-peaks-at-intermediate-Teff
  (Hβ ~0.52 at 11 kK, fades ≥0.08 both ways), higher-log g → shallower core (Stark broadening, the WD
  spectroscopic-gravity basis), cold-cinder-is-DC (regime DC, Hα<0.02, red>blue), hot-central-star reports
  teff_max=80000. Plus always-on route-contract tests (422 bounds, hot-star-no-422, 503-not-baked) a fresh
  checkout keeps. Build recipe: `backend/docs/msg_spectra_build_recipe.md §8`.
- **Scope:** did Koester DA (6a). **TMAP hot-WD/CSPN (6b) followed** (below).

**CHUNK 6b DONE (TMAP hot-WD/CSPN spectra; backend + frontend, pytest 153→157, +4 net in
`test_wd_spectra.py`; Playwright bundled-Chromium pass at 1440 + 390 px, 0 JS errors).** Fills the
>80000 K no-model gap — the ~100–400 kK post-AGB **central star** (CSPN). Host-only like 6a (TMAP is plain
2-col ASCII, NO Docker/pymsg). New `star_sim/fetch_tmap.py` (SVO `tmap` SSAP, the **H-rich Hemass=0 slab**,
Teff 80–190 kK × log g 6.5–9.0 = 72 models, ~125 MB ascii) → `scripts/bake_wd_spectra.py --tmap-dir` splices
the **>80000 K** nodes onto the hot end of the **SAME** WD cube (the §7-precedent OSTAR hot-splice, now on the
WD cube): **93 Teff (5000–190000 K) × 13 log g × 2400 λ**, grid `koester2-DA+TMAP-CSPN`. Runtime
(`wd_spectrum_data`) adds **`regime="CSPN"`** (logg-aware — see the rise-band bullet); frontend `refreshWD`
routes the central star to the WD cube (**log g ≥ 6.0 OR Teff > 55000**) and `spectrum.js` narrates it ("Hot
central star (CSPN) … hydrogen mostly ionized, weak Balmer on a steep blue continuum, NLTE TMAP models").
- **ADVISOR-CAUGHT (the one gap my first Playwright scrub left unsampled — it jumped 27 kK→105 kK, skipping the
  rise): the contracting post-AGB RISE flashed "no model".** The MAIN cube's REAL ceiling is **55000 K (OSTAR,
  the hottest MSG grid), not 80000** — so a wd-mode row with Teff ∈ (55, 80] kK AND log g < 6 (measured: ~1 row
  per mass, e.g. 1 M☉ 74870 K/log g 5.63, 3 M☉ 76235 K/4.89) routed to the main cube → a blank frame sandwiched
  between the giant spectrum and the new CSPN spectrum (invisible pre-6b: everything >55 kK was no-model anyway).
  FIX = route on the main cube's TRUE give-up point: **`log g ≥ 6.0 || Teff > 55000`** (above 55 kK only the WD
  cube — Koester covers 55–80 kK — can serve a spectrum; a log g-clamped Koester DA beats a blank, and 55–80 kK
  is log g-insensitive too, measured Δ 0.024–0.030). And the **regime is logg-aware** so the narration is
  coherent: CSPN if `used_teff>80000` OR (`used_teff>55000 AND raw logg<6.5`) — the low-gravity rise reads "Hot
  central star (CSPN)" (not a 74 kK "white dwarf"), while a hot HIGH-gravity remnant (a young cooling DA at 70 kK,
  log g 8) stays DA. Same Teff, opposite gravity, opposite label — physically the rise (low g) vs the cooling
  remnant (high g). **REUSABLE: my own "verify the MIDDLE of a scrub, not just the endpoints" lesson — a
  too-coarse sample (27→105 kK) hid a one-row hole; and route on a cube's MEASURED ceiling (55 kK), not its
  nominal/sibling boundary (80 kK).** Verified Playwright: dense rise sample (frac 0.18–0.27) shows giant→CSPN
  continuous, no no-model flash, 0 JS errors.
- **THE LOAD-BEARING MEASUREMENT (de-risked the whole chunk up front, advisor-confirmed):** the **×π×10⁸
  TMAP unit gotcha from the §7 scoping does NOT apply to the SVO ascii path** — it serves physical
  erg/cm²/s/Å directly (the gotcha is for native TheoSSA files). Measured: **TMAP/Koester optical-mean ratio
  at the 80000 K / log g 7 overlap = 0.98–1.08** (binned: 1.005–1.021, mean 1.012). So the **LTE↔NLTE seam is
  already graceful** (better than OSTAR/CAP18's 0.97–0.99) → splice **as-is, NO rescale**, just REPORT the
  agreement (`_report_seam`, the OSTAR precedent). **LESSON: confirm a unit factor from one real header +
  one overlap measurement before trusting the scoping note — two of the §7 TMAP guesses were wrong (this +
  vacuum-λ-matters).**
- **The first-bake blocker the advisor flagged: the 3000–3200 Å blue gap.** TMAP starts at 3200 Å; the bake
  asserts each model spans the 3000 Å window → throws on every TMAP model. It's ~80 bins (~3%) on the steep
  blue **Rayleigh-Jeans rise** toward the UV Wien peak, so a flat extrapolation shelves the blue edge. FIX =
  **log-linear (power-law) extrapolation** of the model's bluest 300 Å (`_extend_blue`, flux ∝ λ^p, p ≈ −4).
  Measured: flux(3000)/flux(3200) ≈ 1.24 (RJ would give 1.29) — a genuine rise, not a shelf.
- **The log g axis stays Koester's 6.5–9.5; the lowest-gravity central stars (log g ~5.4 for massive
  progenitors) CLAMP up to 6.5** (not extend the axis to 5.0, which would reintroduce the void-fill 6a avoids).
  **Honest because — MEASURED, not asserted (the advisor's gate: I'd justified it by an unverified
  assumption):** the optical is **log g-insensitive at CSPN temps** — 100 kK at log g 6.5 vs 9.5 differs by
  **max 0.03** (normalized), vs **0.41** for a 13 kK cooling DA (Balmer-profile broadening), so the clamp is
  invisible. **GATE the advisor insisted on: inspect the baked ARTIFACT (not just the inputs) before wiring
  the panel** — plotted 100 kK log g 6.5/9.0 (overlap), the 80→90 kK Koester→TMAP seam (no step, slope
  0.119→0.119), the blue edge (rises), negatives (none). All clean.
- **Vacuum→air** (Morton 2000) applied to TMAP (vacuum) so Balmer guides align across the cube switch (the
  ~1.4 Å optical shift is sub-bin — hot CSPN optical is nearly featureless — but converted for correctness).
- **NO `BAKE_VERSION` bump** (still 1) — the splice only lengthens the Teff axis + changes `grid_name` (the
  OSTAR/Göttingen precedent); bumping would needlessly invalidate the MAIN cube on disk → a Docker re-bake.
  **Consequence (advisor): re-bake the WD cube BEFORE the data-gated tests** (a stale Koester-only cube is
  silently accepted at the same version).
- **`/wd_spectrum` Query `teff` bound widened 200000→500000** (a latent 422 bug 6b's `||Teff>55000` routing
  exposes: massive progenitors' central stars peak ~405 kK → would 422 instead of the no-model frame).
- **Residual no-model frame re-pointed at TMAP's 190000 K ceiling** (only ~300–400 kK massive-progenitor
  central stars; `teffAboveGrid` path unchanged, just keyed off the new `teff_max`). Tests:
  `test_hot_central_star_reports_no_model` → split into `_has_real_cspn_spectrum` (107 kK now in-grid, regime
  CSPN, blue continuum) + `_above_tmap_ceiling_reports_no_model` (330 kK residual) + seam-continuity +
  logg-clamp tests. Playwright-verified the full scrub: cool giant (main cube) → contracting post-AGB (26 kK,
  main cube) → **CSPN 105–107 kK (TMAP, where the old no-model frame was)** → cooling DA (Koester Balmer) →
  cold DC cinder; reversible exit, 390 px caption wraps clean. Recipe `backend/docs/msg_spectra_build_recipe.md
  §7 (status→BUILT) + §8b`.

**Remaining: Chunk 7 (WR spectra, PoWR).** Chunks 6a (Koester DA) + 6b (TMAP CSPN) are the WD spectra,
both shipped; WR spectra (the hardest, wind-axis) is the only endgame chunk left.

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
