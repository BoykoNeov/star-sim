---
name: star-sim-apbp-peculiarity
description: Ap/Bp magnetic chemical-peculiarity — an evocative co-rotating-spots what-if on the 3D star (atlas Tier C), frontend-only.
metadata:
  type: project
---

The Ap/Bp magnetic-peculiarity feature — the atlas Tier-C evocative "minor" item, a
sibling to [[star-sim-gravity-darkening]] (both are labeled-evocative 3D surface layers,
spec §7, the corona precedent). **Frontend-only; backend byte-unchanged (238 pytest
untouched).** Built 2026-07-02.

**What it is:** ~10% of A/B main-sequence stars are magnetic chemically-peculiar (Ap/Bp):
a ~kG global dipole field, oblique to the spin axis, suppresses surface convection so
radiative diffusion sorts elements into abundance PATCHES near the magnetic poles
(Si/Cr/Sr/Eu), darker in the optical, sweeping in/out of view as the star rotates — the
α² CVn variables. NONE of this is in MIST (no magnetism/surface chemistry), so it is a
**labeled "what-if" look, never a claim about this star** (the tooltip says so).

**Implementation (three files):**
- `star.js` `SURFACE_FRAG`: a `uPeculiar` uniform + `peculiarSpots(p0, time)` — an oblique
  dipole (`mag = normalize(sin55°, cos55°, 0)`) giving `abs(dot)` polar caps, broken into
  big irregular cells by a low-freq `worleyF1` sample, and **co-rotated by `uOmega·uTime`**
  (the same rigid spin the granulation uses) so patches are surface-locked and sweep across
  the disk. Applied as a **brightness-only** dip `spots = 1 - uPeculiar·peculiarSpots·0.4`
  multiplied onto the final `surface` (uniform per-channel scale ⇒ keeps chromaticity, no
  hue shift — a hue shift would imply a false temperature map, which is gravity darkening's
  job). `uPeculiar=0` ⇒ `spots=1.0` ⇒ **byte-identical** (off / cool / hot-O / giant /
  endgame). GLSL gotcha: `patch` is a **reserved word** — the break variable is `mott`.
- `star.js` `update()`: `uPeculiar = (opts.peculiar && !eg) ? abWindow·dwarfGate : 0`, where
  `abWindow = sstep(6800,7400,Teff)·(1−sstep(15000,17000,Teff))` (A/B-MS Teff bracket) and
  `dwarfGate = sstep(3.2,3.8,logg)` (MS/dwarf gravity, so an A/F giant crossing the same Teff
  on a blue loop stays clean). Threaded from `paintState` via `star.update(s, {peculiar:
  peculiarOn})` — living path ONLY (endgame refreshers paint the star directly with their own
  `{endgame:…}` opts, untouched).
- `main.js`: `let peculiarOn` (persisted like `rotationOn`), `updatePeculiarControl()`
  (visibility TRACK-STABLE on `massValue ∈ [1.6,5.0]` & `mode==="live"`, co-located after
  every `updateRotControl()` call), and a `#peculiar-toggle` change handler that just calls
  `refresh()` (repaints the current EEP row — no fetch, off the spine).
- `index.html` `#peculiar-control` (reuses `.rot-toggle-row`/`.rot-note`) + a physics tooltip;
  `styles.css` `.peculiar-control`.

**Advisor decisions that shaped it:**
- Gate on the **A/B-MS regime, NOT the rotation toggle** — Ap/Bp is a magnetic peculiarity,
  and classic Ap stars are often *slow* rotators; reusing `rotationOn` would be wrong.
- **Track-stable toggle + per-state effect fade** (the gravity-darkening precedent: `showToggle`
  mass-derived, `gd.active` per-state) — the toggle stays put across the A/B track (no flicker
  on an age scrub) while `uPeculiar` fades as the star leaves the A/B-MS window.
- **Read distinct from gravity darkening**: brightness-dominated coherent LARGE patches that
  MOVE (not a smooth static color gradient, not fine granulation).
- **The composition-with-gravity-darkening render is the reachable untested case** (advisor's
  commit gate): at 3–5 M☉ rotation ON mid-MS you get oblate + gd gradient + spots + a live
  inclination slider all at once. Playwright-verified it composes cleanly (spots co-rotate over
  the static gd gradient about the same axis, no oblate-limb clip, distinguishable) at i=10/60/90°
  → shipped as-is (the advisor's "suppress the combo on near-critical rotators" was an explicit
  nice-to-have, not a blocker; both layers are labeled evocative what-ifs so there's no false claim).

**Verify = the Playwright screenshot pass** (bundled Chromium, not `chrome --headless`): a 3 M☉
B8 V shows coherent co-rotating patches, the EAGB giant is clean (faded), the Sun has no control,
phone width lays out fine, zero console errors.
