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

### Chunk 2 — Frontend: reversible gateway + WD mode shell (HR + controls)
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

### Chunk 3 — WD 3D shader + structure panel
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

### Chunk 4 — WR mode shell + HR + composition (reuses the gateway)
**Goal:** the WR side of the gateway, on-hand data.
**Do:** the WR gateway branch (threshold-gated by feh, from Chunk 1); WR mode
rebinds **age → scrub the WR sub-track**, **mass stays live** (re-snap, but only
above the WR threshold — below it the button is the WD or SN branch); extend the
**HR axis to ~250 kK**; the composition panel shows the **stripped surface**
(H gone → He → C/O → N: the WN→WC→WO story — already in the track). Spectrum =
honest placeholder. **Verify:** Playwright — a 60 M☉ star, cross into WR, see the
stripped-surface composition and the hot HR position; reversibility holds.
**Depends:** Chunks 1–2 (gateway scaffolding).

### Chunk 5 — WR 3D wind shader
**Goal:** the optically-thick-wind look (closes the on-hand-data work).
**Do:** a wind shader — radial outflow / electron-scattering haze, a bright hot
core, an emission-line glow halo; no granulation; evocative/labeled. **Verify:**
Playwright (WN vs WC/WO flavor if feasible). **Depends:** Chunk 4.

> **End of on-hand-data work.** After Chunk 5 the full architecture + pedagogy
> ships for both endgames on data already on disk — all four panels except the
> *real* spectra (which show the honest placeholder).

### Chunk 6 — WD spectra (data-gated; depends on Chunk 0)
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
