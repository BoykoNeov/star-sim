---
name: star-sim-binary-stripped
description: Binary-stripped-star sibling (binary.py + /binary) — Götberg 2018 hot He-star, the ~70% WR channel; Chunk 1 backend built.
metadata:
  type: project
---

The **binary-stripped-star** feature — the hot, He-rich core a close companion exposes
by Case-B Roche-lobe overflow (Götberg+2018). This is the *dominant* observed channel
for stripped/WR stars (~70%, Sana+2012), so it retires the caveat the single-star WR
demo keeps writing ("shows the minority channel"). It is the first build from the atlas's
Tier-D **binarity** item — path (a), the stripped-star endpoint (not the full two-star
co-evolution, path (b), deferred). Plan `docs/plans/stripped-consort-unveiling.md`.

**Architecture — a SIBLING, not a provider** (settled): a binary product can't go through
the single-star `StellarStateProvider`/`StellarState` interface without discarding the
companion or mutating the dataclass (both §3 violations). So it mirrors `supernova.py`/
`structure.py`: `binary.py` imports only `state.StellarState`, `/binary` bypasses `PROVIDER`.

**Chunk 1 BUILT 2026-07-02 (backend vertical, solar-first, 266 pytest):**
- `backend/star_sim/data/gotberg_z014.csv` — the verified **Z=0.014** table COMMITTED
  inside the package (23 rows: M_init, M_strip, Teff_kK, logL, logg, R_eff, X_H, X_He +
  provenance header). Two-source provenance: spectra on VizieR (gitignored under
  `data/gotberg_stripped/`), these *structural params* = the paper's Table 1, transcribed
  then VERIFIED against the on-disk SEDs (≤0.07 dex, all 23 rows). The 3 non-solar Z
  tables (0.006/0.002/0.0002) append later — grid data-shape is **1D-in-Minit** per Z
  (Gate 0a resolved; period P is a fixed function of mass, snap key = (Z, Minit)).
- `binary.py` — own CSV parser; `stripped_star(mass, feh)` snaps (Z, Minit)→nearest,
  never interpolates (§6); returns `StrippedStar` = the §3-clean `StellarState` + routing
  scalars (`m_strip_msun` [CURRENT mass — no home on the state, which has only mass_init],
  snapped m_init/Z, feh_snapped, mass/feh `_snapped_far`, mass_grid_min/max). Adding a Z =
  drop a CSV + one tuple in `_GRID_TABLES`; [Fe/H]=log10(Z/`GOTBERG_SOLAR_Z`=0.014).
- `/binary` route — **snap-always** (advisor): out-of-grid snaps + flags `*_snapped_far`
  in-band; 422 only for mass≤0. hide-below-2/note-above-18.2 is a Chunk-2 UX read.
- `test_binary.py` (12) + `requires_gotberg_data` marker (guards the gitignored SEDs).

**Gotchas baked in (build them into Chunk 2+ too):**
- **Teff/Reff, NEVER T★** — T★ is the inner hydrostatic (evolutionary) temp; for a star
  with a wind it differs from the spectroscopic Teff. Teff/Reff are the self-consistent
  Stefan-Boltzmann pair that place the marker (same evolutionary-vs-spectroscopic gap that
  bit WR spectra 7a). Feeding T★ misplaces it.
- **Z_surf = grid Z**, NOT 1−X−Y (table X rounded to 2 dp → would zero Z). Renormalize the
  (X_H, X_He) pair to close at 1−Z. He-rich surface is the headline (Y_surf ≳ 0.7 high-mass;
  low-mass end ~2 M☉ is still H-rich sdB-like — honest subdwarf↔WR sequence).
- **mdot=None, no lifetime** in Chunk 1 — neither is in the verified 8-col table (measure-
  first discipline; the SED free-free tail is a Chunk-2 call for this FAST-wind regime).
- `age_yr`/`eep` are a documented sentinel (`REPRESENTATIVE_AGE_YR`) — ONE representative
  state ("halfway through core-He burning"), not a time-track, not age zero.

**The advisor's correctness catch (the one that would've bitten):** the visibility gate
keys on **Teff + Y_surf ONLY, never L**. A stripped star is sub-luminous *for its Teff*,
but M_strip ≪ M_init makes it a He-star of a different mass, so the L comparison FLIPS SIGN
across the grid (logL 0.6 vs single ~1.05 at 2 M☉ → sub-luminous; 4.9 vs ~4.4 at 18 M☉ →
over-luminous). `stripped.L < single.L` would FAIL at high mass. Always-hotter +
always-He-enriched are the robust discriminators.

**Next = Chunk 2** (frontend what-if `stripped-mode`): entry-point (i) mid-life toggle vs
(ii) end-of-life gateway (advisor consult); consumers render the stripped state directly
(no new shader); **audit `scale.js`/`classify.js` to read the served CURRENT mass, not
mass_init**; decide the age-slider (disable vs relabel to lifetime); **VERIFY the SED wind
free-free tail** before showing it (fast wind → small Ṁ/v∞, may not crest the floor).
Related: [[star-sim-rotation-subpop-atlas]] (Tier D binarity), [[star-sim-wr-wd-endgame-plan]]
(the single-star WR this complements), [[star-sim-supernova-remnant-endgame]] (sibling pattern).
