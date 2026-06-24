---
name: star-sim-wr-wd-endgame-plan
description: Planned (not yet built) full Wolf–Rayet & white-dwarf endgame renderers — design, measured grounding, locked decisions, chunked plan; plus the hot-end-can't-extend spectrum finding.
metadata:
  type: project
---

The user wants **full** Wolf–Rayet (WR) and white-dwarf (WD) support — at the
slider limits a button appears ("→ Continue: White Dwarf" / "→ Continue:
Wolf–Rayet") that jumps into a dedicated endgame renderer. **Design agreed,
plan written & committed, NO code started** (user said "just write a plan").
Plan: `docs/plans/smoldering-cinder-gateway.md`.

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
