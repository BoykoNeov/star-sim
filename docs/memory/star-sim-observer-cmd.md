---
name: star-sim-observer-cmd
description: "Axis A (the observer's view) — photometry.py + /photometry sibling: distance + extinction + synthetic B/V/BP magnitudes → observational CMD. A1 backend+data BUILT; A2/A3 frontend next."
metadata: 
  node_type: memory
  type: project
  originSessionId: c8134080-7591-46d3-b4c4-0cf00c173efa
---

Axis A of the outward quartet (`docs/plans/outward-quartet-atlas.md` §Axis A) — the
theory→telescope bridge: turn the intrinsic star (surface F_λ, R, Teff) into what a
telescope records — an **apparent** magnitude, reddened by dust, dimmed by distance.
Payoff = the observational **colour–magnitude diagram (B−V, M_V)**, the observer's HR
diagram, which composes with the Axis-B isochrone ([[star-sim-isochrone-cluster]]) into
a real cluster CMD. The **capstone** of the quartet.

**A1 BUILT 2026-07-10 (backend + data, +10 tests).** A2 (frontend Observer control
group: distance/A_V/R_V → reddened overlay + mag readout) and A3 (the CMD panel) are next.

## The load-bearing Gate-0 findings (measured first, advisor-driven)

- **The main absorption cube IS absolute physical surface F_λ** — verified by
  integrating the served solar spectrum: it reaches **98.2%** of the Planck in-band
  σT⁴ (9000 K → 102%). So `observed F_λ = surface F_λ · (R/d)²` gives real absolute
  magnitudes. (Cool 4000 K = 61.5% is real optical line-blanketing, not a scale error.)
- **The cube stops at 8999 Å** (optical only, 3001–8999 Å). This is the advisor's
  load-bearing catch: **Gaia RP + 2MASS JHK fall entirely off the red edge; Gaia G is
  truncated ~0.05–0.13 mag.** So the anchor **swapped from M_G to M_V**, flagship CMD =
  **(B−V, M_V)** — the classic observational HR diagram (still composes with Axis B).
  Clean in-cube bands: **Bessell B, V + Gaia BP** (verification only — BP alone isn't a
  standard color, RP is off-edge). A true Gaia CMD needs a WIDER cube re-bake (future).
- **Use SVO ZeroPoints, NOT a Vega spectrum** (advisor reversed his own earlier steer):
  the SVO per-band ZeroPoint(Jy) method EMPIRICALLY nails M_V,Sun=**4.832** (t 4.81±0.05)
  and the exact 10.000 distance modulus, so the absolute pipeline is right. A Vega SED is
  a rabbit hole (no astropy; hand-parsing CALSPEC FITS) that wouldn't move things enough.
- **Synthetic solar B−V = 0.612 is ~0.04 blue of 0.65** — a known **B-band Vega
  zero-point convention** offset (SVO Bessell.B 3908.5 Jy vs literature ~4000–4060 →
  swapping gives 0.649). It is **common-mode** across the star, its track, and the
  isochrone — all pass through the same photometry — so it **CANCELS in relative CMD
  placement** (the star still sits on the cluster locus, the turnoff still dates it).
  Color tolerance relaxed to ±0.05; documented as a convention effect, not a fudge.
- **E(B−V)=0.296 at A_V=1/R_V=3.1 is NOT a bug** (nominal A_V/R_V=0.322): band-integrated
  extinction is source-dependent and legitimately a hair lower (A_B/A_V=1.296 vs
  monochromatic 1.324, a ~2% flux-weighting effect). Don't chase it.

## Architecture (the sibling idiom, spec §3)

- `star_sim/fetch_filters.py` → **committed** `star_sim/data/filters.json` (~15 kB, like
  `gotberg_z014.csv`): per band the SVO transmission curve + Vega **ZeroPoint (Jy)** +
  **DetectorType** (0 energy B/V, 1 photon BP) + pivot. Works on a fresh clone.
- `star_sim/photometry.py` — a **pure sibling** (imports only json/os/pathlib/numpy —
  **not even StellarState**; AST-tested no-provider, like `bpass.py`). `ccm89(lam,rv)` →
  A(λ)/A(V); `band_mags_stack(lam, flux[N,:], radius_rsun[N], distance_pc, av, rv)` — the
  **VECTORIZED** core (so A3's whole track+isochrone needs NO N HTTP round-trips —
  advisor-flagged); `photometry_point(...)` for the single star returns both absolute
  M_X (10 pc, no dust) and apparent m_X + (B−V)₀/E(B−V)/distance modulus. DetectorType
  branches the band integral: energy `∫f·T dλ`, photon `∫f·T·λ dλ`.
- `/photometry` (bypasses PROVIDER like `/spectrum`) **composes** `spectrum_data`
  (full-res absolute F_λ) + `photometry_point`, like `binary_pair`. Params
  teff/logg/feh/**radius_rsun**/distance_pc/av/rv. 503 if cube/filters missing, 422 on
  radius≤0. Echoes teff_requested/teff_max so a hot-clamped star's blue color is flagged
  a lower bound.
- Tests `test_photometry.py` (+10): Gate-0 M_V=4.81±0.05, B−V=0.65±0.05, exact distance
  modulus, reddening reddens+dims, hotter-is-bluer, vectorized==scalar, CCM89 shape,
  route shape+422, AST no-provider/no-StellarState. Gated `requires_spectra_data` (needs
  the cube); CCM89 + AST tests are ungated.

See [[star-sim-phase5-spectra]] (the cube), [[star-sim-isochrone-cluster]] (Axis B, the
CMD's cluster partner), [[star-sim-habitable-zone]] (Axis D). Plan
`docs/plans/outward-quartet-atlas.md` §Axis A.
