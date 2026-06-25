---
name: star-sim-rotation-subpop-atlas
description: Star Sim — captured discussion (not built) of a rotation axis + other subpopulation controls; user said "nothing is out of scope."
metadata:
  type: project
---

**DISCUSSION CAPTURED, nothing built.** Plan doc:
`docs/plans/whirling-cohort-atlas.md`. Prompted by the user noticing that for
Wolf–Rayet stars rotation+age affects far more than the X-ray emission
(`magnetic-ember-broadcast.md` SED Chunk 3 rotation slider), and asking what
other sliders would reveal different subpopulations. **User directive: "nothing
is out of scope"** — so the old spec §2/§9 walls (no binary engine, no live
solver) are now recorded as candidate directions *with a cost*, not forbidden.
Honesty tiering stays (tier by what data backs it, not by what we wish it showed).

**Verified this session (re-check if grids change):**
- MIST v2.5 rotating grid EXISTS: `discover_tarball_url(vvcrit="0.4")` resolves
  `MIST_v2.5_..._vvcrit0.4_EEPS.txz` on the live server. So rotation = real data.
- On disk: only `vvcrit0.0` (5 metallicities). Provider keys grids by `[Fe/H]`
  only (`_feh_from_path`) → two vvcrit dirs at same feh would COLLIDE; rotation is
  NOT carried as an axis. Adding it = a third backend axis (provider work mirroring
  the `[Fe/H]` add).
- Surface N (`Ns`) already plumbed → rotating tracks would show **MS** surface-N/He
  enrichment (Hunter diagram), which we don't show today (only post-MS dredge-up).
- Bake resolution ≈ R 2400 → v sin i line broadening visible only above ~125 km/s
  (fast rotators yes, Sun no).
- **NOT verified (the build gate):** does v2.5 ramp rotation in by mass? (v1.2
  imposed vvcrit=0.4 only above ~1.2–1.8 M☉ — low-mass stars brake.) If so the
  rotation axis does NOTHING at 1 M☉, bites only in the WR regime. Cheap settle:
  fetch the 0.4 grid, diff a 1 M☉ track vs 0.0; identical ⇒ ramped.

**The atlas (tiers):** A (real, changes track) = **rotation vvcrit 0.0↔0.4** (the
headline; 2-point so toggle/snap not continuous; payoff = MS N-enrichment, lifetime
shift, lowered WR threshold, CHE at low Z). B (real, spectrum-only) = **[α/Fe]**
(CAP18-large re-bake; thick-disk/halo; MIST evol is solar-scaled so track won't
follow), **v sin i broadening** (frontend convolution, fast rotators only),
microturbulence ξ. C (evocative) = gravity darkening/oblateness (von Zeipel),
the SED activity band→line slider, magnetic Ap/Bp. D (needs a new engine, was "out
of scope") = **binarity/mass transfer** (the biggest — ~70% of WR are binary-
stripped; also blue stragglers/Algols/stripped-He/GW pop; needs a binary engine or
BPASS/POSYDON grid), initial-He/GC multiple populations, α-enhanced *evolution*,
live solver. Bonus zero-data = **instability-strip overlay** on the HR diagram
(Cepheid/RR Lyrae regions — a view, not a slider; cheapest honest win).

**Key physics points:** rotation reshapes the whole track (mixing→MS N/He up,
longer life, HR shift), not just X-rays; for WR it's the headline (lowers WR
threshold, sets subtype/final mass/remnant spin, CHE). **Rotation+age splits by
type:** cool stars spin DOWN via magnetic braking (gyrochronology → age predicts
rotation, basis of SED Chunk 3); hot/WR stars have NO braking (radiative envelope)
→ rotation set by winds+binaries, so age does NOT predict their rotation. So
"rotation" wears two hats: selects a different track (vvcrit, real for all masses)
vs pins activity/X-ray (age-derivable only for cool MS stars). See
[[star-sim-nonthermal-sed-plan]] and [[star-sim-wr-wd-endgame-plan]].

Suggested order if picked: instability-strip overlay → rotation toggle (after the
mass-ramp diff) → v sin i broadening → [α/Fe] re-bake → binarity/live-solver.
