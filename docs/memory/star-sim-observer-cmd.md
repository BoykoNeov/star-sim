---
name: star-sim-observer-cmd
description: "Axis A (the observer's view) — photometry.py + /photometry + /photometry_track siblings: distance + extinction + synthetic B/V/BP magnitudes → observational CMD. A1 backend+data + A2 reddening.js overlay + A3 dedicated CMD PANEL (cmd.js, its own #observer-panel with the distance/A_V/R_V sliders moved out of Controls) ALL BUILT. The marker visibly moves; observed marker/arrow tip = EXACT /photometry."
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

**A1 BUILT 2026-07-10 (backend + data, +10 tests).**

**A3 BUILT 2026-07-10 — the CMD is now its OWN dedicated panel (backend `/photometry_track`
route + frontend `cmd.js` + the distance/A_V/R_V sliders MOVED OUT of Controls into
`#observer-panel`; +3 tests, 425 pytest, Playwright 1440+390 zero console errors).**
Prompted by **user feedback**: the A2 control (opt-in toggle in Controls) only visibly
changed the READOUT TEXT — the Spectrum/SED reddening overlay is imperceptible for most
stars (**measured: A_V 0.5→4 moved only ~0.01% of SED pixels** — CCM89 is identity outside
the UV, so the reddened curve hugs the blackbody). The user also disliked that the
observer control's reveal-body changed the Controls panel's vertical size. Fix
(advisor-endorsed): ship the capstone CMD graph in its own panel where the marker
**visibly moves**, and moving the 3-slider block out fixes the Controls jump too.

- **`/photometry_track`** (api.py, bypasses PROVIDER for the compute but calls
  `PROVIDER.track` for the states — like `/photometry`): composes the whole track's
  `StellarState`s → a `spectrum_data` flux **STACK** → ONE vectorized `band_mags_stack`
  pass → per-state intrinsic absolute **(B−V)₀, M_V** + age/eep/phase/teff. **Decimated to
  ~120 points** (`n_max`, uniform stride; ~0.25 s warm at 606 EEP rows). The locus is
  **age-independent**, so an age-scrub never refetches (deduped by `(mass,feh,vvcrit)`).
- **`cmd.js`** (pushed-data consumer like roche.js): draws the observational CMD — B−V x
  (blue left/red right), **M_V inverted-y** (bright up, as astronomers plot it). Elements:
  the intrinsic **Teff-coloured locus** + a white **intrinsic marker ON it**; driven by the
  sliders, an **orange observed marker** + a **reddening/distance vector arrow** + a faint
  dashed **"as observed" locus**. DISTANCE = a uniform μ slide straight DOWN (dimming, no
  colour); DUST = the arrow tilts DOWN-and-RIGHT (fainter + redder).
- **The honesty pin (advisor's load-bearing point): the observed marker + the arrow TIP
  are the EXACT `/photometry` values** (`bv_obs`, `mv_app` — the same tested path the
  readout prints, so the plotted point can NEVER contradict the number below it). Only the
  faint dashed "as observed" LOCUS applies the marker's vector *uniformly* (the standard
  de-reddening assumption) — labelled as such, never plotted as exact truth.
- **No opt-in toggle** — the panel is simply ON when eligible (`observerHasData && mode==="live"`,
  same init probe). Default seed **d=100 / av=0** → a pure VERTICAL distance arrow on first
  view (visibly non-inert) while **Spectrum/SED stay byte-unchanged** (setReddening guards on
  `redAv>0`); dragging A_V then diagonalises the arrow AND reddens Spectrum/SED. Hidden in
  every endgame/stripped mode via `dropObserverForModeSwitch` in the shared chokepoint
  (verified hidden in stripped + WD, restored on Back). `layout.js` appends the new
  `data-panel-id="observer"` for users with a saved order.

**A2 BUILT 2026-07-10 (frontend-only)** — the ORIGINAL Observer control in the Controls
panel (`#observer-control` toggle + reddening overlay on Spectrum/SED via `reddening.js`
CCM89 + `/photometry` readout). **Superseded by A3's dedicated panel** (the reddening
overlay + readout survive; the toggle/`#observer-control` were removed, the sliders moved).
Its findings still hold:

- **The formula-vs-data split (advisor).** Reddening is CCM89, a fixed closed-form, so
  it's a **verbatim JS port** in a pure `frontend/src/reddening.js` (the hz.js helper
  idiom — `ccm89(lamAng,rv)` + `extinctionFactor`). Client-side is *unavoidable* anyway:
  the SED synthesizes its own Planck curve with no served flux to redden. But magnitudes
  need filters.json + Vega ZeroPoints + the tested band integration — all server-side —
  so the READOUT fetches `/photometry` (debounced, latest-wins), never reimplemented.
- **A2's Gate 0 (done BEFORE any drawing): the JS ccm89 port matches `photometry.py`
  to 10 decimals** at 5000 Å (optical), 2175 Å (bump), 1500 Å (deep UV) — both branches.
  Ported the 4a/4b UV formula VERBATIM (no deep-UV F_a/F_b correction) so the drawn
  overlay can't drift from the served readout. (Don't reconstruct E(B−V) in JS — it's
  band-integrated; trust A1's tests. The direct function-match is the consistency check.)
- **Spectrum overlay:** a second **reddened curve drawn UNDER the intrinsic** on the SAME
  normalization — `fmax` stays pinned to the intrinsic peak (reddened flux never enters
  its scan), so the intrinsic curve is byte-unchanged when Observer is on (advisor
  constraint). The blue-end suppression IS the visible reddening signature.
- **SED overlay:** a reddened blackbody; CCM89 is identity outside ~1250–9091 Å so it hugs
  the BB across most of the 14 decades and only dips in the UV — carving the **2175 Å
  extinction bump**. **The bump LABEL is self-gated** (advisor "never label a non-feature"):
  the bump is a dip-THEN-recovery, visually distinct only when the Wien peak is in the UV
  (`lamPeak < 300 nm`, Teff ≳ 10⁴ K) so the near-UV continuum is flat; for a cool star the
  steep Wien decline masks the recovery → label softens to just "reddened (A_V …)".
  Measured through the runtime: Sun → no bump; a 35,560 K O star → the bump with a visible
  V-notch.
- **Readout placement = the Observer group, NOT the State readout** (advisor): apparent
  mag / reddened colour are observer-dependent, which would breach the State readout's
  "everything from one StellarState" §3 contract. Readout: M_V · apparent V (μ) · (B−V)₀ →
  reddened, E(B−V); honesty note carries the hot-clamp lower-bound + the standing B-band
  ZP-offset caveat.
- **Living-only** (mags need the absolute-flux main cube): hidden in every endgame/stripped
  mode via `dropObserverForModeSwitch()` in the shared chokepoint. **One teardown-ordering
  bug caught + fixed:** `observerOff()` ends with `updateObserverControl()` which RE-SHOWS
  the control if mode hasn't flipped off "live" yet → force-hide the control div AFTER
  `observerOff()`. **Seed demonstrative A_V=0.5 / d=100 pc on enable** so "toggle on"
  visibly changes something (a d=10/A_V=0 default looks identical to intrinsic).
- **Gate for the toggle (frontend-only, no `/photometry_status` route):** probe
  `/photometry` once at init with the Sun's params — 200 → offer it, 503 → hide it (A3 reuses
  the same `observerHasData` probe to gate the whole panel).

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
- `/photometry_track` (A3, api.py) — `PROVIDER.track(mass,feh,vvcrit)` → flux stack →
  `band_mags_stack` → intrinsic (B−V)₀/M_V per state, decimated to `n_max` (~120). 503
  cube-missing, 422 out-of-grid mass. The vectorized-stack loop lives in api.py (which
  already composes PROVIDER + spectrum_data), so `photometry.py` stays a pure sibling.
- Tests `test_photometry.py` (**+13** total, +3 for A3): Gate-0 M_V=4.81±0.05, B−V=0.65±0.05,
  exact distance modulus, reddening reddens+dims, hotter-is-bluer, vectorized==scalar,
  **the `/photometry_track` locus shape+decimation** (solar ZAMS bluer+fainter than the
  giant tip), **locus↔`photometry_point` consistency at ZAMS**, **422-on-bad-mass**, CCM89
  shape, route shape+422, AST no-provider/no-StellarState. Gated `requires_spectra_data`;
  CCM89 + AST tests ungated.

See [[star-sim-phase5-spectra]] (the cube), [[star-sim-isochrone-cluster]] (Axis B, the
CMD's cluster partner), [[star-sim-habitable-zone]] (Axis D). Plan
`docs/plans/outward-quartet-atlas.md` §Axis A.
