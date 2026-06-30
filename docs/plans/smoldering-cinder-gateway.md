# Plan: Stellar endgames — Wolf–Rayet & White-Dwarf renderers

## Context

The user asked for **full** Wolf–Rayet (WR) and white-dwarf (WD) support — not a
minimal label, the real thing: at the limits of the existing sliders a button
appears ("→ Continue: White Dwarf" / "→ Continue: Wolf–Rayet"); clicking it
**jumps into a dedicated endgame renderer** for that regime. This plan is the
agreed design, chunked into relatively small, independently-shippable vertical
slices (the project's house style — every prior phase shipped as one).

**The key realization (measured, not assumed):** both WR and WD are *already in
the MIST tracks we load* — they are simply clipped off by the `phase >= 5`
window cutoff. So this is **not a new data source and not a new provider**; the
§3 boundary holds a third time. We extend the exposed window and add new
*consumer/renderer modes*. The only genuinely new external data are the WR/WD
*spectra*, which are data-gated and quarantined into the last phases.

## Locked decisions (from the user)

1. **Gateway = reversible mode.** You can slide back from the endgame to the
   living star. The endgame is a mode you enter and leave, not a one-way door.
2. **Mass slider stays live inside the endgame.** Dragging mass re-snaps the
   progenitor → a *different* WD (initial→final mass relation: 1 M☉ → ~0.5 M☉,
   8 M☉ → ~1 M☉) or a different WR (type/extent, threshold-gated). We have
   `star_mass` (final mass) on the track for this.
3. **WD cooling-age axis = log.** The 1 M☉ WD reaches **27 Gyr**; linear would
   crush the whole cooling story into the first pixel.
4. **Present the richer picture, not a snapshot.** "Jump to WD" enters a
   **scrubbable sequence**: thermal pulses → the ~100 kK central-star /
   planetary-nebula phase → cooling over Gyr to a cold cinder. (For WR: the
   short WR sub-phase of the massive star's life.)

## Measured grounding (facts on disk — re-verify if grids change)

All from the loaded MIST v2.5 EEP tracks (`feh_*/eeps/*.track.eep`):

- **WD endgame is on disk for low/intermediate mass.** The 1 M☉ p000 track:
  EAGB (φ4, 101 rows) → **TPAGB (φ5, 601 rows of thermal pulses)** → **post-AGB
  (φ6, 312 rows)** that span Teff 2393–106 663 K, logL −5.31…3.48, **logg
  −0.2…8.0** — the final real row is a cold WD (Teff 2393 K, logg 7.95, logL
  −5.31, age 27.55 Gyr). 3.0 M☉ is the same shape (final logg 8.16). **285+ rows
  per track have logg > 7** (degenerate). The WD cooling track itself is *clean
  and monotonic* (Teff↓, logg↑, L↓); the mess is the TPAGB *bridge* to it.
- **WR endgame is on disk for the very massive end, metallicity-gated:**
  WR (φ9) appears at **≥ 40 M☉ at [Fe/H]=+0.5**, **≥ 50 M☉ at 0.0**, **≥ 60 M☉
  at −0.5…−1.0** (more metals → stronger winds → strips at lower mass — exactly
  the expected physics). It is a *large* segment (146 rows at 60 M☉ solar, 449 at
  300 M☉), Teff reaching **~250 000 K**. The provider already maps the label
  (`9: "WR"` in `_PHASE_NAMES`).
- **The track carries the wind/stripping inputs:** the EEP header has
  **`star_mdot`** (mass-loss rate) and **`star_mass`** (current mass) — the wind
  strength a WR spectrum needs, and the final mass a WD needs.
- **The in-between (≈8–40 M☉) just ends** at φ5 with one row — these become
  core-collapse supernovae (neutron star / black hole), which we do **not**
  render. The gateway must have an honest third branch (a dead-end "SN — not
  simulated" card, optional flavor) rather than mis-routing them.

## Architecture spine (four principles)

1. **No new provider — extend the window.** WR/WD states *are* `StellarState`
   (Teff, L, R, logg, composition all defined). A new provider accessor exposes
   the post-window rows; the §3 boundary is untouched, `PROVIDER` in `api.py`
   stays `MISTProvider`. The spectra remain **siblings** (like `/polytrope`,
   `/spectrum`) — new routes that bypass `PROVIDER`.
2. **The sim interpolates; the endgame snaps.** The endgame **snaps to the
   nearest real grid track** (no cross-mass interpolation — the MESA provider
   already does exactly this). This dissolves the TPAGB problem: the 601
   thermal-pulse rows can't be *interpolated* across mass (incoherent pulses),
   but the real pulses of *one* snapped star scrub beautifully. The user's
   "bigger slider" was the right instinct on the wrong axis — the fix is
   snap-not-interpolate, then a fine scrub over the real pulses.
3. **The gateway narrates the gap.** The transition is the honest place to say
   what the sim does *not* simulate (PN ejection for WD; the march to
   core-collapse for WR). The seam becomes a feature, not a hidden cheat.
4. **Evocative, honestly labeled** (the existing corona precedent). The new 3D
   shaders (a WR wind glow; a cooling-color degenerate sphere) are "evocative,
   not predictive" and say so. Where a real model is missing (spectra, before
   the data-gated phases land), the panel shows an honest "no atmosphere model
   for this regime yet" state, never a faked clamp.

## Chunk breakdown

Ordered by dependency and risk: foundation → WD on-hand-data vertical → WR
on-hand-data vertical → data-gated spectra last. Chunk 0 is pure research and
runs in parallel. Every chunk leaves `main` green with tests (backend) or a
Playwright screenshot pass (frontend), per house style.

### Chunk 0 — Spectrum-grid scoping (research, parallel, no code) — ✅ DONE
**Outcome (full notes in `backend/docs/msg_spectra_build_recipe.md` §7):** **WD
before WR confirmed — for axis-compatibility.** **Koester DA = GO** (SVO `koester2`,
2-col ASCII, Teff×log g, ~30–60 LOC, cite Koester 2010) — but a **separate WD cube**
(log g 6.5–9.5 disjoint from the main cube, [Fe/H] degenerate), not a splice.
**TMAP hot WD/CSPN = conditional GO** (SVO `tmap` SSAP bulk only, NOT TheoSSA
on-demand; Teff 50–190 kK; flux ×π×10⁸; LTE↔NLTE seam with Koester ~50–80 kK).
**Koester DB = NO-GO** (restricted, non-redistributable — drop; cover hot-He DO via
TMAP instead). **PoWR WR = conditional GO at best** (public tarballs, but axis is the
wind quantity Rt not log g → its own (T\*, Rt) cube, and the star must be
**assumption-mapped**: v∞ and clumping D assumed, Teff↔T\* approximate). All
gitignore-and-cite. So Chunk 6 (Koester+TMAP) is tractable; Chunk 7 (PoWR) carries
the real design cost. Naming trap: "Reindl 2020" pure-H grid is actually Bohlin/
Hubeny/Rauch 2020 = the TLUSTY twin (95 kK cap), not TMAP.

**Goal:** de-risk "full spectra" *before* promising it (the advisor's insistence;
the same discipline that caught the WR/WD assumptions).
**Do:** verify the candidate grids — **PoWR** (WR emission grids: WNL/WNE/WC),
**Koester** DA/DB and/or **TMAP** (hot WD/CSPN) for WD — for: (a) existence &
downloadability, (b) on-disk format, (c) **license/redistribution**, (d) whether
a bake reader can ingest them or it's new converter code (they are **not** MSG
`.h5`, so `pymsg` will *not* open them — expect a custom reader). For WR, read
**PoWR's axis definitions** and check whether MIST's `star_mdot`/`star_mass`
supply what its transformed-radius/mass-loss axis needs.
**Deliverable:** a go/no-go + format notes appended to
`backend/docs/msg_spectra_build_recipe.md`; updates this plan's risk register.
**Blocks:** nothing in Chunks 1–5; gates Chunks 6–7.

### Chunk 1 — Backend: endgame accessor + classifier (foundation) — ✅ DONE
**Status:** shipped (137 tests, was 121). `endgame()` is on the `StellarStateProvider`
Protocol returning `EndgameResult` (`provider.py`); `/endgame` routes through `PROVIDER`
and stays §3-agnostic (MESA/Stub return `type="none"`). `MISTProvider.endgame` snaps
**both** mass and feh to the nearest real grid track, classifies WD/WR/SN/none from the
snapped track's phases, scans the WR threshold per grid (+0.5→35, 0.0→48, −0.5→56 M☉),
and exposes the post-`track_end` rows as StellarStates. `star_mass`/`star_mdot` added to
`_Track` + cache (v8→9), not to the mixing functions; `StellarState` untouched. See the
CLAUDE.md Done bullet + `tests/test_endgame.py` for the full record.

**Goal:** expose the post-window track, snapped, with the metadata the gateway needs.
**Do:** new `MISTProvider` method (e.g. `endgame(mass, feh)`) that **snaps to the
nearest grid mass** (no cross-mass interp) and returns the rows *past* the normal
window as ordered `list[StellarState]`: φ5+φ6+cooling for low/int (→ WD), φ9 for
massive (→ WR). Plus an **endgame classifier**: type ∈ {`WD`, `WR`, `SN`/none},
reporting the *true* snapped mass, the final `star_mass`, and the feh-dependent
WR threshold (derived from whether the snapped track carries φ9 — not hardcoded).
New `/endgame` route (**through `PROVIDER`** — it is `StellarState`).
**Tests (§10):** snap-to-true-mass; phase coverage (WD track carries 5+6 and ends
degenerate logg>7; WR track carries 9); cooling-track monotonic; TPAGB present
but single-track (never interpolated); classifier correct across mass×feh
(WD below threshold, WR above, SN in between); `final_mass < initial_mass`;
WR-threshold matches the measured 40/50/60 by feh.
**Depends:** nothing. **Foundation for 2–5.**

### Chunk 2 — Frontend: reversible gateway + WD mode shell (HR + controls) — ✅ DONE
**Status:** shipped (frontend-only; 137 tests unchanged). A "→ Continue: White Dwarf"
button appears at the age-slider limit when the snapped star classifies WD (an honest
"core collapse — not simulated" note for the SN masses; nothing for `none`; WR is
Chunk 4). Clicking enters a **reversible** `wd-mode` (a "← Back to the living star"
button restores the living star at its track end). Inside the mode the **age slider
becomes a log-spaced cooling scrubber** and **mass/[Fe/H] stay live** (re-snap the
progenitor → a different remnant; out-of-WD-range masses revert with a note). The HR
diagram swaps to wide endgame axes and draws the **Teff-coloured cooling track**
(cool-giant → ~100–400 kK central star → cold cinder); the 3D star, scale bar,
composition and readout take the endgame `StellarState`; spectrum shows an honest
placeholder; the SED keeps its blackbody but drops the (dynamo-less) X-ray overlay.
**Key design (advisor-guided):** the cooling scrub is a **3-zone piecewise-index map**
(pulses 12% → rise-to-central-star 16% → cooling 72%) — a naive single log-cooling-age
axis lets the 601 chaotic pulse rows eat half the slider and crushes the dramatic
central-star spike to a sliver; within the cooling zone MIST's rows are already ~even in
log(cooling age), so plain index there gives each decade visible travel. The WD path is
**separate from the live plumbing** (picks `states[i]` from the pre-fetched /endgame
result — no /state fetch); consumers get **explicit mode signals** (not logg
heuristics): `spectrum.showPlaceholder()`, `classify.update(s,"wd")`,
`sed.update(s,{endgame})`. `/endgame` is fetched **lazily** (when the age nears the
limit), and `refresh()`/`refreshTrack()` bail if the mode left "live" (a live fetch
landing after `enterWD()` would otherwise clobber the WD render — the bug the
verification caught). `exitWD` returns to `lastWDMass/Feh` (robust to the focus/blur
race where a still-focused mass box re-commits a reverted value on the exit click).
Verified via Playwright (22/22 checks: gateway → scrub pulses/107 kK central star/2393 K
cold WD → re-snap to a different remnant → SN revert → reversible Back; living Sun
anchor + variable-star overlay unregressed). The first-pass composition feeds the
endgame track as-is (DA hydrogen surface shows correctly); WD-correct comp/3D come in
Chunk 3.

**Goal:** a crossable, reversible WD gateway with a correct cooling track.
**Do:** the context button at the slider limit (driven by Chunk 1's classifier);
enter/leave the WD endgame **reversibly** (slide back to the living star); the
transition interstitial that narrates the un-simulated PN-ejection gap; rebind
controls inside the mode — **age → log cooling-age**, **mass stays live**
(re-snaps progenitor → different final mass); draw the **WD cooling track on the
HR diagram** (extend axes down to logL ≈ −5). First pass feeds the *existing*
3D/composition with endgame state; **spectrum = honest placeholder**.
**Verify:** Playwright — cross the gateway, scrub the log cooling-age across
pulses→PN→cold WD, drag mass to get a different final mass, slide back out; no JS
errors. **Depends:** Chunk 1.

### Chunk 3 — WD 3D shader + structure panel — ✅ DONE
**Status:** shipped (frontend-only; 137 tests unchanged). The first-pass renderers are
replaced with WD-correct ones. **3D shader (`star.js`):** `update(state, {endgame:"wd"})`
renders a **smooth, featureless cooling sphere** — granulation off, corona off, just the
blackbody color at Teff (which sweeps blue-white central star → orange cold cinder) under
quadratic limb darkening. Granulation is faded out by a **log g gate** (`uGran =
clamp((4−logg)/3)`), NOT a hard wd flag, so the sequence's opening **TPAGB giant still
boils** (a real convective star, log g ≈ 0.5 → uGran 1) and only the degenerate remnant
goes smooth — a gentle scrub transition, and it doesn't regress Chunk 2's giant. The
living path (no opts) restores granulation + corona automatically on exit. **Structure
panel (`comp.js`):** a new `setEndgame(states)`/`clearEndgame()` (mirrors `hr.setEndgame`)
swaps the burning-abundance views for a **schematic layered cross-section** — a C/O core
under a thin He buffer under a thin H (DA) atmosphere, an onion disk + a label column.
What's **honest** (the advisor's discipline): the **C/O core composition (C:O) and the
DA/DB atmosphere type are READ FROM THE MODEL each frame** (data-driven — the loaded MIST
grid measured ALL DA + C/O: surface purifies to pure H by gravitational settling, core is
already C/O at the TPAGB); the **He buffer + all layer thicknesses are canonical and
exaggerated to be visible** (no radial structure is modeled), with the drawn envelope
**thinning as log g rises** (giant shedding its envelope → degenerate thin skin — an
evocative cue tied to the real log g). **Crystallization is shown in the CORE, never on
the gaseous surface** (the advisor's key correction — the C/O lattice forms in the dense
interior, not the atmosphere), with the **onset Teff rising with log g** (~6.5 kK at log g
7.95 for a 0.54 M☉ WD up to ~13 kK at log g 8.7 for a 1.0 M☉ WD — the Gaia crystallization
sequence), so a re-snapped massive WD crystallizes hotter. The non-DA/He-core paths are a
**minimal data-parameterized fallback** (commented; the current grid only produces DA C/O
WDs), not authored artwork. The wide HR cooling axes + readout (Chunk 2) carry the
mass–radius relation the floor-clamped 3D sphere can't (R 0.013→0.0079 R☉, log g 7.95→8.63
as the progenitor mass rises 1→6.5 M☉; the cold-WD scale-bar marker lands at the **Earth
dot**, ≈1.4 R⊕ — "Earth-sized" made visual). `main.js` wires `star.update(s,{endgame:"wd"})`
+ `comp.setEndgame/clearEndgame` in `refreshWD`/`enterWD`/`exitWD`/`tryWDResnap`; CSS hides
the comp mode toggle + legends in `body.wd-mode` (the structure view draws its own labels).
**Width-robust** (advisor-caught — the first pass truncated labels at phone width): the
label sublines **wrap** to the column width (never clip at the canvas edge) and the honesty
caption's reserve is **dynamic** (its wrapped line count, so the last line never clips on a
narrow panel). Verified via Playwright (bundled Chromium — the `chrome --headless` hijack
caveat) on the real served UI at **1440 AND 390 px**: the cooling sequence (boiling amber
giant → smooth blue-white 107 kK central star → smooth orange Earth-sized cold WD), the
structure cross-section reading "thick envelope → thin skin" with a growing crystallized
core, the mass–radius re-snap (1→6 M☉: smaller WD, thinner envelope, ~90% crystallized),
and reversible exit (granulation + corona + the comp toggle all return). Only the
pre-existing favicon 404; no JS errors. No JS test harness → the screenshot pass is the
regression check (as in Phases 2–5).

**Follow-up (continuous living→WD transition) — ✅ DONE** (frontend-only; 137 unchanged).
User report: switching into the endgame "feels some steps are missing" — the corona, the
SED coronal X-ray/radio band, and (slightly) the radius all popped. Root cause (curl
`/state`+`/endgame`, advisor-reviewed): the endgame's first state is the **very next track
row** after the living EAGB endpoint (mass 1: R 82.8→86.6, Teff 3624→3601, activity
0.82→0.83 — continuous *data*), but the corona (`star.js`) and the SED X-ray overlay
(`sed.js`) **hard-switched on the wd mode flag** while granulation already faded via a log g
gate. Fix = drive **corona AND the SED X-ray overlay by the SAME degeneracy gate
`clamp((4−logg)/3)`** granulation uses → all three fade together: the opening AGB giant keeps
the boil + glow + dimmed coronal band it had as a living star (a *continuation*), dying only
as the bared core degenerates (gDeg→0 at log g≳4 → smooth glowless cold WD, no band). Living
stars pass gDeg=1 → byte-identical. **Mid-scrub refinement (2nd advisor pass + state scan):**
routing the endgame through the living Teff-regime machinery, its hard coolgiant→cool boundary at
5000 K would flash the band UP to the brighter dynamo level as the post-AGB contraction races through
5000–6500 K — a **1-row pop for ~2 M☉** (none for 1/3 M☉; their rows skip the zone). Closed by drawing
**only the dimmed "dying-giant" band gated by gDeg** in the endgame (no regime switches — a contracting
post-AGB core is not a cool MS dynamo / A-F gap / O-wind star), so the band stays at one level and fades
monotonically (verified the 2 M☉ danger row now flat: ymean 82→83, count fading not jumping). The
**radius pop was a latent bigger bug** (advisor + curl): the gateway showed at `GATE_SHOW=0.98`, but the linear-age axis crams RGB-tip→CHeB→
EAGB into the last ~2%, so at 0.98 the living star is still a **mid-RGB star** (R=8.4) →
entering jumped RGB→AGB-giant (10×). Fix = raise `GATE_SHOW`→**0.999** (gateway only at the
true end, where the step to states[0] is imperceptible — displayRadius 2.42→2.43); the age
snap (drags within 1.5% → exactly 1.0) keeps it a natural "slam right", `/endgame` still
prefetches at 0.9. **Blocker verified first:** corona continuity needs endgame
`states[0].activity` ≈ the living end-row's (the old hard-off never read it) — curl confirmed
(0.82↔0.83). **Spectrum held out of scope** (advisor): the WD placeholder is honest (no
atmosphere grid at log g 7–9); a giant-phase "show the real spectrum" reintroduces the
wrong-clamp Chunk 2 avoided — same symptom, separate Chunk-6 decision. Verified via Playwright
(bundled Chromium): gateway hidden at 0.95/0.98, shown at 1.0; WD entry indistinguishable from
the living EAGB end (corona ring + boil) + 324 coral X-ray px; cold WD smooth glowless + 0
coral px; reversible exit; only the favicon 404.

**Follow-up (Lane–Emden panel in the WD endgame) — ✅ DONE** (frontend-only; 137 unchanged).
The user asked whether the Lane–Emden interior panel is *irrelevant* in wd-mode (every other
panel transforms; this decoupled sibling just sits there showing the user's chosen n). The answer
flips it: a white dwarf **IS** a degenerate polytrope (n≈1.5 non-relativistic → **n=3** as the mass
nears the **Chandrasekhar limit**; the n=3/γ=4/3 limit is *why* there's a maximum mass — the same
physics behind this gateway's mass–radius relation + the WD→SN boundary), so it's the *most* relevant
the panel ever gets. User chose **"hint, keep n user-set"** (over auto-deriving n — the one honest
carve-out, but it departs from the decoupled-toy design). Built: a `body.wd-mode` gold callout that
**swaps in for** the general "not the real interior" intro, pointing at n≈1.5–3. **Advisor caught**
that hiding the intro made a latent caption clash worse (the intro reconciled lane.js's general n=3
"Sun-like radiative star" caption; gone, the WD hint sat above a Sun-star label) — and the key unlock:
**editing a static n-only caption does NOT break decoupling** (decoupling = not feeding *star state*
into the panel; n stays the sole driver). Fix: the **n=3 landmark caption now carries both framings**
(Sun-like radiative star *and* a relativistic degenerate gas near Chandrasekhar); n=1.5 already named
white-dwarf cores. All HTML + CSS + one caption string; lane.js stays decoupled. Verified Playwright
at 1440 + **390px** (the n slider/readout stay live; hint wraps clean, no clip; 0 JS errors).
**Caveat (not gated):** the hint shows for the whole scrub incl. opening TPAGB-giant rows where
"degenerate core" is premature — same character as the Chunk-6 spectrum-placeholder note, milder.

**Goal:** replace the wrong-looking first-pass renderers with WD-correct ones.
**Do:** a **degenerate-sphere shader** — Earth-scale relative size, smooth (no
granulation), quadratic limb darkening, **cooling-color shift** blue-white →
white → yellow → red over Gyr, optional crystallization flavor at the cool end;
evocative/labeled. Adapt the composition panel to **WD semantics** — a layered
core (C/O or He) under a thin H/He envelope, and/or a cooling-curve readout
(L, Teff, age) — *not* the burning-abundance CNO view. **(Open: exactly what
replaces the comp panel — decide at build time.)**
**Verify:** Playwright across the cooling sequence (hot blue central star → cold
red cinder). **Depends:** Chunk 2.

### Chunk 4 — WR mode shell + HR + composition (reuses the gateway) — ✅ DONE
**Status:** shipped (frontend-only; 137 pytest unchanged; 31/31 Playwright on the real
served UI at 1440 + 390 px). A `→ Continue: Wolf–Rayet` button appears at the age-slider
limit when the snapped star classifies WR (threshold-gated by the Chunk-1 classifier);
click → reversible **`wr-mode`** (shares the gateway scaffolding with WD: `exitEndgame`,
shared `lastEgMass/Feh`, `tryResnap` dispatcher, 3-way event handlers). In the mode the
age slider becomes an **index-linear scrub** over the φ9 sub-track (simpler than WD's
3-zone pulse map — the WR sub-track is one clean monotonic run) with a **WN→WC transition
landmark** (first row with surface Z ≥ 0.4; absent for WN-only stars like 35 M☉ @ +0.5);
mass/[Fe/H] **stay live** (re-snap → a different WR; SN/WD/none revert with a note). The
**key reuse**: the composition panel uses its **NORMAL burning-abundance views** (not a
WD-style custom cross-section) — the WR sub-track has a real EEP axis with an evolving
surface, so the WN→WC→WO stripping story falls out of the existing bulk/cno views from
real data (`comp.setTrack(states)` + `comp.update`, no `setEndgame`; the comp toggle stays
visible). HR gets **WR-specific bounds** (logT 3.6–5.5 ≈ 4 kK–316 kK, logL 4.3–7.0 — WR
is far more luminous than the WD endgame, 300 M☉ peaks at logL 6.80) via `setEndgame(states,
"wr")`. Classification (`classify.js`) reads the **WN/WC/WO subtype from the surface
composition** (data-driven: He-dominant+N → WN, H-present → WNh, C/O-dominant → WC, hottest
+ O-strong → WO). 3D star = a smooth blazing-hot sphere (gDeg=0 — granulation/corona off;
a **deliberate Chunk-5 placeholder** for the wind shader; verified it doesn't read as
broken). Spectrum = honest placeholder (WR wind-emission spectra are Chunk 7). SED keeps
the blackbody but **suppresses the coronal X-ray band entirely** (`{endgame:"wr"}` — a WR
is wind-driven, not a convective dynamo; the band legend entries are hidden too — don't
label a non-feature). **Per the advisor, the un-modeled gap is narrated at the END**
(the end-of-scrub caption says "next is core-collapse… not modeled") — the mirror of the
WD's PN-ejection-at-entry, because the WR stripping itself IS modeled. The living→WR seam
was verified continuous before coding (60 M☉: living CHeB R=36.5/Teff=31kK → WR
R=33.4/Teff=32kK; the GATE_SHOW=0.999 + age-snap-to-1.0 guarantees the gateway only shows
at the true endpoint, so no radius pop — same safety as WD).

**Goal:** the WR side of the gateway, on-hand data.
**Do:** the WR gateway branch (threshold-gated by feh, from Chunk 1); WR mode
rebinds **age → scrub the WR sub-track**, **mass stays live** (re-snap, but only
above the WR threshold — below it the button is the WD or SN branch); extend the
**HR axis to ~250 kK**; the composition panel shows the **stripped surface**
(H gone → He → C/O → N: the WN→WC→WO story — already in the track). Spectrum =
honest placeholder. **Verify:** Playwright — a 60 M☉ star, cross into WR, see the
stripped-surface composition and the hot HR position; reversibility holds.
**Depends:** Chunks 1–2 (gateway scaffolding).

### Chunk 5 — WR 3D wind shader — ✅ DONE
**Status:** shipped (frontend-only; pytest UNCHANGED 137; Playwright bundled-Chromium pass on
the real served UI at 1440 + 390 px). Replaces Chunk 4's smooth blazing-hot-sphere placeholder.
A new **WR wind layer in `star.js`** (`WIND_FRAG` + a `wind` mesh) renders the optically-thick-
wind look: the (still-opaque) hot sphere is wrapped in a camera-facing additive **wind halo** —
an electron-scattering **haze brightest in a thin annulus AT the limb** (softening the hard edge
into the wind, the "pseudo-photosphere"; the limb-brightening is genuinely apt for an extended
scattering atmosphere), decaying outward, broken up by **radial outflow filaments** (2D value
noise advected outward over `uTime`, two decorrelated octaves so they scatter organically, NOT
into spokes). No granulation/corona (gDeg=0 still). **Evocative/labeled** (the WR narrate paragraph
now says so): color is the honest blackbody at Teff; the halo's reach + density read from
**`Z_surf`** (a smooth, extended helium WN wind sharpens into a denser, clumpier carbon/oxygen
WC/WO wind), intensity from a gentle clamped `L` tie — explicitly **not a measured Ṁ** (`star_mdot`
isn't on StellarState, §3/Option B). **No chemistry-driven hue** (advisor: it would contradict the
spectrum panel's honest "no WR model yet" placeholder — the WN/WC/WO flavor falls out of state via
Teff + radius + the `Z_surf` density cue instead).

**The headline (advisor-caught BEFORE coding):** the WR scrub **opens large** — 60 M☉ → `states[0]`
R≈33 R☉ → `displayRadius`≈2.23, near the 2.65 clamp; the camera (z=8, 40° FOV) sees ±2.91 world
units, tighter horizontally at 390 px (aspect<1). A **constant** halo extent would straight-edge-clip
the viewport (the framing-pop family that bit Chunks 2/3). Fix = **fit-to-frame extent** (`applyWindScale`:
cap the quad half-size at `0.95·FRAME_HALF_H·min(1,aspect)`), recomputed **every frame** in `animate()`
so a live resize can't reintroduce the clip. Happy side effect: the halo is **thin at the big entry →
fuller as the core strips and shrinks** (R 33→0.57, Teff 32→249 kK) — physically apt AND a gentle
entry. `uTime` is driven from the same clock in `animate()` (the corona has none — easy to
forget). The `wind` mesh is `visible=false` in **every non-WR path**, so living + WD are untouched.

**Entry-pop fix (2nd advisor pass — don't ship a rationalized flag):** capping *extent* alone wasn't
enough — intensity was `L`-driven and `logL`≈6 is ~flat across the sub-track, so the wind blazed at
~full even at the WNh entry, popping from the near-glowless living CHeB star into a bright limb ring
(also the "eye/ring" look). FIX = **ramp the wind intensity by strippedness, not L** — `wStrip =
1 − clamp(X_surf/0.25)` is ≈0 while H-rich (WNh entry, X≈0.28) and →1 as hydrogen vanishes (full by
frac≈0.28, exactly as Z_surf flips to WC). So the gateway is a **continuation** (entry = the bare
continuing sphere, wind blazes UP as the core stripping bares it — a real WN→WC growth in the wind
itself, not just the Z_surf clumpiness), the same discipline every prior endgame chunk used. Verified:
entry now a bare sphere matching the living star, no pop; outward streaming confirmed across frames;
WN-only (35 @ +0.5, Z≈0.045) keeps a smooth halo while WC/WO (60, 300 M☉) go clumpy/streaky.
**Verified:** WNh entry (smooth thin halo) → WC mid (clumpy ring) → WO end (compact blazing core +
dense clumpy halo), no clip at 1440 OR 390 px, reversible exit restores granulation+corona, living
Sun (granulation+corona) + cold WD (smooth glowless) unregressed, 0 real JS errors (only Playwright's
own WebGL `ReadPixels` perf warnings from screenshotting).

**Goal:** the optically-thick-wind look (closes the on-hand-data work). Replaces Chunk 4's
smooth blazing-hot-sphere placeholder (`star.update(s,{endgame:"wr"})`, currently gDeg=0).
**Do:** a wind shader — radial outflow / electron-scattering haze, a bright hot
core, an emission-line glow halo; no granulation; evocative/labeled. **Verify:**
Playwright (WN vs WC/WO flavor if feasible). **Depends:** Chunk 4.

> **End of on-hand-data work.** After Chunk 5 the full architecture + pedagogy
> ships for both endgames on data already on disk — all four panels except the
> *real* spectra (which show the honest placeholder).

### Chunk 6 — WD spectra (data-gated; depends on Chunk 0)
**Split into 6a (Koester DA — BUILT) + 6b (TMAP hot WD/CSPN — BUILT).**
**Goal:** real WD spectra (the tractable spectrum — hydrostatic, plane-parallel).
**Do:** fetch Koester/TMAP; write the **bake reader/converter** (new code — not
pymsg) → bake a **WD cube at logg 7–9** (a *separate* cube; you can't splice
high-logg nodes onto the normal grid); new sibling route (e.g. `/wd_spectrum`);
wire the WD spectrum panel (DA = pressure-broadened Balmer; DB = He I), with
temperature/logg-gated line guides. Replace the placeholder.
**Tests:** measured through the runtime path (the project rule — not raw grid
numbers): Balmer depth vs Teff, DA vs DB, logg dependence. **Fallback:** if
Chunk 0 is a no-go, keep the labeled placeholder and document it.
**Depends:** Chunks 0, 3.

**✅ 6a — Koester DA: BUILT.** Host-only vertical (no Docker/pymsg — Koester models are
plain ASCII): `star_sim/fetch_koester.py` (SSAP bulk-fetch of ~1066 models) →
`scripts/bake_wd_spectra.py` (rectangular 82 Teff × 13 log g cube → `wd_spectra_grid.npz`,
**asserts rectangular, no void-fill**) → `spectra.py` `wd_spectrum_data` → `/wd_spectrum`
route → `frontend/src/spectrum.js` `updateWD`. **DA = pressure-broadened Balmer**, the
Balmer guides tagged `balmer:true` (drawn for DA, hidden for DC). Two honest edges grounded
in the data: **DC** below the ~5000 K Koester floor (an honest Planck continuum at the real
Teff — no H lines painted on a cold cinder), and the **80000 K ceiling = no-model frame**
for the ~107 kK central star (reuses the existing `teffAboveGrid()` path). Pure-H → no
[Fe/H] axis (`feh_varies:false`). 15 tests in `test_wd_spectra.py` (measured through the
runtime). Build recipe: `backend/docs/msg_spectra_build_recipe.md §8`.

**✅ 6b — TMAP hot WD / CSPN: BUILT.** The ~100–190 kK CSPN/hottest-WD regime that fills
the >80000 K no-model gap. Host-only (TMAP is plain ascii, like Koester — no Docker):
`star_sim/fetch_tmap.py` (SVO `tmap` H-rich Hemass=0 slab, Teff 80–190 kK × log g 6.5–9.0
= 72 models) → `scripts/bake_wd_spectra.py --tmap-dir` splices the >80000 K nodes onto the
hot end of the SAME WD cube → **93 Teff (5000–190000 K) × 13 log g × 2400 λ**, grid
`koester2-DA+TMAP-CSPN` (the §7-precedent OSTAR hot-splice, on the WD cube). Runtime adds a
`regime="CSPN"` above 80000 K (logg-aware: the low-gravity contracting **rise** 55–80 kK
also reads CSPN, a hot high-gravity remnant stays DA); frontend routes the central star to
the WD cube (`refreshWD`: log g ≥ 6.0 **OR Teff > 55000** = the main cube's OSTAR ceiling, so
the contracting rise routes here too — advisor-caught: at >80000 a 55–80 kK/low-logg rise row
flashed "no model"). It narrates it ("Hot central star (CSPN) …
hydrogen mostly ionized, weak Balmer on a steep blue continuum"). **Three measured findings
(two correct the §7 scoping):** (1) **no ×π×10⁸** — the SVO ascii path already serves
physical erg/cm²/s/Å (gotcha was for native TheoSSA); the **LTE↔NLTE seam @ 80000 K is
already graceful, TMAP/Koester ratio 1.005–1.021**, so splice with no rescale (OSTAR
precedent). (2) **3000–3200 Å blue gap** (TMAP starts at 3200) filled with a **log-linear
extrapolation** of the RJ tail, not a flat shelf. (3) **log g clamp 5.4→6.5 on the lowest
central stars is honest** — the optical is log g-insensitive at CSPN temps (measured Δ 0.03
vs 0.41 for a cooling DA), so no axis extension / void-fill needed. **No `BAKE_VERSION`
bump** (Teff-axis length + `grid_name` only, like OSTAR). Residual no-model frame re-pointed
at TMAP's **190000 K** ceiling (only ~300–400 kK massive-progenitor central stars). 157
pytest (+4), Playwright-verified (CSPN across the rise + the spike with no no-model flash,
DA/DC unregressed, 0 JS errors, 390 px clean). Recipe
`backend/docs/msg_spectra_build_recipe.md §8b`.

**Known polish — RESOLVED in 6a.** The Chunk-2 placeholder (`refreshWD` called
`showPlaceholder` unconditionally, so the TPAGB-giant rows at the start of the WD scrub
*wrongly* showed "no WD spectrum" when a ~3600 K giant **does** have a real spectrum) is
fixed: `refreshWD` is now **phase-aware by surface gravity** — log g ≥ 6.0 → `updateWD`
(the Koester cube), else `update` (the main cube), so the giant rows show their real
spectrum and the WD cube engages only once degenerate. The 6.0 threshold sits in the
empty main(≤5)/Koester(≥6.5) gravity gap, so the cube switch is invisible.

### Chunk 7 — WR spectra (data-gated, hardest; depends on Chunk 0)
**Goal:** real WR emission spectra.
**Do:** fetch PoWR; reconcile its **wind axis** (Teff + transformed-radius /
mass-loss) with MIST's `star_mdot`; write the reader/converter; bake a WR cube;
new sibling route (e.g. `/wr_spectrum`); the emission-line panel (broad He II,
C IV, N III/V…) — a different draw from the absorption panel. Measured tests.
**Fallback:** labeled placeholder. **Depends:** Chunks 0, 5. **Highest risk.**

## Risk register

- **Spectrum data is the one thing that can sink "full"** (Chunk 0). PoWR /
  Koester / TMAP are not MSG `.h5` → pymsg won't read them → new converter, *if*
  they fetch & license-permit at all. Honest fallback = labeled placeholder.
- **WR/WD spectra are asymmetric.** WD keys cleanly on (Teff, logg) like normal
  stars (just logg 7–9). WR forms in the *wind* — MIST's 250 kK hydrostatic Teff
  may not be the spectrum-defining number; PoWR needs a wind axis. → do WD
  spectra before WR.
- **The SN dead-end branch** (≈8–40 M☉): must be classified and shown honestly
  (no WR/WD renderer; a "core-collapse — not simulated" card), not mis-routed.
- **logg leaves the atmosphere grid** for WD (7–9): a separate cube, and the
  *normal* spectrum route must keep its honest "no model" notice if a WD logg is
  ever sent to it.
- **Radius rescale** for WD (Earth-sized, ~100× smaller): the 3D scale/shader
  assumptions break — handle in Chunk 3, label the relative size.
- **Crossing the TPAGB honestly:** snap-to-track only (Principle 2). Never
  interpolate the pulses across mass.
- **WR-threshold non-monotonicity** at low Z (the 150 M☉ gap in the sweep):
  derive the gateway branch from the *snapped track's* phases, not a hardcoded
  mass cut.

## Open questions (resolve at build time, not now)

- WD composition panel: layered-core view vs cooling-curve readout vs both
  (Chunk 3).
- WR 3D: how far to push WN/WC/WO visual differentiation (Chunk 5).
- Whether the SN dead-end gets a real card or is just an absent button (Chunk 2).
- Endgame scrub axis labeling: "cooling age" vs "time since AGB" for WD; the WR
  sub-track scrub units.

## Pointers / resume

- This plan: `docs/plans/smoldering-cinder-gateway.md`.
- Measurement scripts used to ground it lived in the scratchpad (`measure_*.py`);
  re-run against `feh_*/eeps/*.track.eep` if the grids change.
- Spectrum build/bake recipe (extend for Chunks 6–7):
  `backend/docs/msg_spectra_build_recipe.md`.
- Precedents to lean on: MESA provider (snap-to-track), Lane–Emden & spectrum
  panels (sibling routes that bypass `PROVIDER`), the corona layer (evocative +
  labeled), the axis-generic bake/runtime (cube schema).
