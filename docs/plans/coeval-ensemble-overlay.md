# Plan: The coeval-ensemble overlay — a whole population beside the one star (BPASS)

## Status: RECON DONE (schema measured 2026-07-10, ~1 GB alpha+00 sin+bin pair landed under `data/bpass/`, gitignored). No build yet — Chunk 1 is the next decision.

Every sibling so far renders **one** thing: a single star's track (`provider`), one
representative state (`binary.py`, `structure.py`, `supernova.py`, `spectra.py`,
`lane_emden.py`), or **one** two-body system through time (`posydon.py`). This arc adds the
first **ensemble** sibling: a *coeval stellar population* — a million stars born together at
the marker's metallicity, shown as they are now at the marker's age — overlaid beside the one
star the user picked. The single star becomes one member of the cohort it was born into, and
the headline is what a single-star sim structurally **cannot** show: **binaries reshape the
population** (stripped/rejuvenated hot stars keep it UV/ionizing-bright far longer; binaries
fill the blue-straggler / stripped-He gaps single-star tracks leave empty).

This is the explicitly-unscoped **population-overlay** tail named across the binarity plans
(`entwined-consort-inspiral.md` §4c(ii), `whirling-cohort-atlas.md` Tier D). BPASS is the
data source; it is **NOT** POSYDON (co-evolved *tracks*) — it is **population synthesis**
(integrated spectra + number/HRD/SN-rate census for whole coeval populations). A genuinely
separate sibling, not a `posydon.py`/`binary.py` branch.

## The one honesty rule that gates the whole arc (Gate 0)

**The single-vs-binary difference must be visibly real through the real consumer, and be
something the single-star sim cannot already show.** A population overlay that just draws "a
cloud around the single star" with no binary story fails the gate. The first chunk must aim
squarely at the binary payoff (UV-longevity in the SED, or gap-filling on the HRD). Measure
it through the runtime before any control ships (the boron-b8 / VO-7400 / α-axis
optimistic-framing discipline).

## Recon result (measured 2026-07-10 — file sizes & products, real not recalled)

- **BPASS v2.3 SSP *spectra*** — Zenodo record **10.5281/zenodo.6383329**, CC-BY 4.0.
  Ten HDF5 files, **531.2 MB each**: `SSP_Spectra_BPASSv2.3_{sin,bin}-imf135_300-alpha{-02,+00,+02,+04,+06}.hdf5`.
  `sin` = single-star populations, `bin` = includes binaries. The **`alpha+00`** (solar-scaled)
  pair matches this sim's non-α evolution axis → ~1 GB for the single+binary pair.
  Each file holds **all 13 metallicities × the age grid × the wavelength grid** for one
  (IMF, α). **In-session fetchable** (Zenodo direct file URLs), unlike POSYDON's ~10 GB/Z.
- **REAL HDF5 schema (MEASURED 2026-07-10, `fetch_bpass.py` on the landed files — this is the
  Benson/Galacticus repackaging, a single clean cube, no per-Z demux / no HOKI reader):**
  four datasets — `spectra` **(13 Z × 51 age × 100000 λ)** float64; `ages` (51,);
  `metallicities` (13,); `wavelengths` (100000,). Root attrs carry IMF / α / citations.
  - `ages` = **linear age in Gyr**, log-spaced **0.001 → 100.0** (= 1 Myr → 100 Gyr; the
    classic 10⁶–10¹¹ yr grid stored as Gyr, NOT as log). → snap on the marker's `age_gyr`.
  - `metallicities` are **already `[Fe/H]` = log₁₀(Z/0.020)** (Z☉=0.020 BPASS convention),
    **−3.30103 → +0.30103** (verified: 0.0→Z=0.020, +0.301→0.040, −0.155→0.014, …). →
    snap on the marker's `[Fe/H]` **directly, no Z→[Fe/H] conversion**. (Note the ~0.15 dex
    offset vs MIST's Z☉≈0.0142 — a labeled systematic, honest either way.)
  - `spectra` **units = L☉ / Hz** (i.e. **f_ν, NOT f_λ**), per the **10⁶ M☉** population
    (attr `units='L☉/Hz'`, `unitsInSI=3.827e26`). The SED overlay must handle f_ν — convert
    to f_λ = f_ν·c/λ² if the panel is per-Å, or plot f_ν / annotate.
  - `wavelengths` = **1 → 100000 Å, 1 Å step**.
- **The HRD "numbers" / stellar-census product is a DIFFERENT release** (the classic
  BPASS main data release — plain-text `.dat` "numbers"/"starmass"/"supernova"/"ionizing"/
  "colours" files, tens of MB, on the Warwick/gSTAR/Google-Drive distribution, **not** the
  Zenodo spectra record above). The HR-density overlay (Chunk 2 below) needs its own recon +
  handoff for that release; do NOT assume its schema from the spectra file.

**Consequence:** the cleanest, best-documented, CC-BY, in-session-fetchable BPASS product is
the **integrated SSP spectrum** (single vs binary). That points the first slice at the
**SED/spectrum-panel overlay**. But the concrete overlay type stays **gated on Gate 0** — see
Chunk 0.

## The architectural shift — the first ENSEMBLE sibling

The data model is genuinely new — not a `StellarState`, not a pair of them, not a track of
pairs. A BPASS SSP is a **flux array** f_λ(λ) for a chosen (Z, age, single|binary), or (for
the census product) a **number density over an HRD grid**. Neither fits any existing shape.
So:

- `bpass.py` runtime sibling — imports only `numpy`/stdlib (NOT even `StellarState`: a
  population is not a star; it returns arrays/dicts). **Never imports `StellarStateProvider`**
  (§3). Its own simple parser over host-extracted flat files (the `structure.py` precedent).
- `/population` route — **bypasses `PROVIDER`** (like `/spectrum`, `/structure`, `/binary`).
  Takes `?feh=&age_gyr=&population=sin|bin` (+ maybe `alpha=` later), snaps (Z, age) to the
  nearest BPASS grid node (never interpolate — §6; report the true snapped node + snapped-far
  flags, the `binary.py` discipline).
- Frontend consumer as an **OVERLAY on an existing panel**, not a new panel (the roadmap's
  "prefer views/overlays over yet another panel" caution). The overlay's **age = the marker's
  current age** and **Z = the marker's [Fe/H]** — a coeval population "born with your star,
  now this old," a clean honest tie to the existing age scrubber + [Fe/H] slider. A
  **single ↔ binary toggle** is the one new control; the payoff lives in that toggle.

**Extraction-vs-runtime split (the MESA-structure / POSYDON precedent):** the raw BPASS
files are HDF5. Extraction (host-side or a one-time bake) may use `h5py` / BPASS's own HOKI
reader to export flat per-(Z, age) arrays; the runtime `bpass.py` reads those flats with its
own parser and imports no HDF5-demux heroics / no BPASS tooling. Since the spectra file is
only ~531 MB, a **build-time bake** to a compact void-free `.npz` (the `spectra.py` precedent)
is the natural shape: bake once → ship/cache a small `data/bpass/bpass_ssp.npz` → pure-Python
runtime. This also gives a `fetch_bpass_baked.py` hosting path later (BPASS is public
third-party like MIST, which IS hosted — the CC-BY carve-out likely allows it; confirm).

## Column / schema mapping — RECON DONE (measured against the real HDF5, 2026-07-10)

`fetch_bpass.py` opened the landed files and printed the layout above. The unknowns this
section flagged are now **answered by measurement** (recorded so the bake is coded against the
real schema, not a recalled guess — the boron-b8 / α-axis discipline):

- **Metallicity keying:** a single 3-D cube `spectra[Z, age, λ]` — NOT per-Z datasets. Bake
  = read the cube, decimate λ, stack `[sin, bin]`, save a compact `.npz`. Trivial.
- **Age axis:** 51 log-spaced **linear-Gyr** values 0.001–100 (not log-age bins). Snap on
  `age_gyr`.
- **Wavelength:** 1 Å sampling, 1–100000 Å (the classic full grid). Decimate for the SED
  panel (the panel shows ~decades on a log-λ axis; the full 100k-point 1-Å grid is overkill).
- **Metallicity mapping:** the `metallicities` dataset **is `[Fe/H]`** already
  (log₁₀(Z/0.020)) — snap directly, no conversion; note the Z☉=0.020-vs-0.0142 systematic.
- **Flux units:** **f_ν [L☉/Hz] per 10⁶ M☉** — the one real handling wrinkle for the SED
  overlay (see the Chunk-1 note).

## Chunked build (each chunk measured + Playwright-verified — the project cadence)

### Chunk 0 — recon (BLOCKS everything; the data-gate)
- `fetch_bpass.py` (BUILT with this plan): a fetch **recipe + validator**. Because the file
  is ~531 MB and CC-BY on Zenodo with direct URLs, it can **optionally auto-download** the
  `alpha+00` sin+bin pair (guarded, opt-in) OR document the handoff; then it opens the HDF5
  and **prints the real schema** (datasets, shapes, wavelength/age/Z axes).
- **Decision after recon (the advisor-flagged blocking choice, NOT made now):** which overlay
  is Chunk 1 — the **SED integrated-spectrum overlay** (favored by the recon: cleanest,
  in-session-fetchable, UV-longevity = Gate 0) vs the **HRD number-density overlay** (needs
  the separate numbers release). Pick the one that is *visibly single-vs-binary distinct*
  through the runtime. Likely SED first, HRD as Chunk 2.

### Chunk 1 (likely) — SED integrated-population-spectrum overlay
- `scripts/bake_bpass_spectra.py` (host-side, `h5py`): read the sin+bin `alpha+00` HDF5 →
  a compact `data/bpass/bpass_ssp.npz` (Z × age × λ, single & binary), the `spectra.py`
  bake precedent. Decimate λ to the SED panel's needs if the full 1-Å grid is overkill.
- `bpass.py` `population_sed(feh, age_gyr, population)` — snaps (Z, age) → nearest node,
  returns f_λ(λ) + the true snapped (Z, age) + snapped-far flags.
- `/population?feh=&age_gyr=&population=sin|bin` (bypasses PROVIDER; snap-always; 422 only on
  structurally invalid input; 503 if unbaked — the `/spectrum` precedents).
- Frontend: an opt-in overlay on the **SED panel** (`sed.js`) — the integrated population
  spectrum at the marker's (Z, age), a **single ↔ binary toggle**, the single star's own SED
  kept for scale. Caption owns the normalization (per 10⁶ M☉, not the one star's flux) and
  the lesson (binaries → sustained UV/ionizing flux). Living-star only (hidden in
  WD/WR/SN/stripped, like the other spectrum overlays).
- `test_bpass.py` (gated `requires_bpass_data`): snap honesty (true grid node); the sin-vs-bin
  UV-flux difference as a **Gate-0 regression** (binary population brighter in the UV at
  intermediate age — the measured payoff); route shape + 422; the AST sibling-imports-no-
  PROVIDER check.

### Chunk 2 (deferred) — HRD number-density overlay on the HR panel
- Recon the separate BPASS **numbers** release (plain-text census, its own `fetch`/handoff).
- Overlay a per-cell number-density contour on the existing HR panel at the marker's (Z, age);
  the user's star sits as one point in the cloud; the single↔binary toggle shows binaries
  populating the blue-straggler / stripped-He / hot-subdwarf regions single-star tracks leave
  empty. Gate 0 = those regions light up only in `bin`.

### Chunk 3 (optional) — hosting + derived census
- `fetch_bpass_baked.py` (the MIST/POSYDON hosting precedent) for the small baked `.npz`.
- Possibly surface derived scalars (ionizing photon rate, SN rate vs age) as a caption/readout.

## Open questions
1. ~~HDF5 internal schema~~ — **ANSWERED** (single cube, see the recon section).
2. ~~[Fe/H] mapping~~ — **ANSWERED**: the axis is already `[Fe/H]`=log₁₀(Z/0.020); note the
   ~0.15 dex Z☉ systematic vs MIST in the caption.
3. ~~In-session vs handoff fetch~~ — **ANSWERED**: the Zenodo direct-URL pull worked headless
   (`--download` landed both 531 MB files, exit 0). In-session is fine.
4. **Normalization framing (still open — the Chunk-1 UX call):** the overlay is per-10⁶-M☉
   f_ν, the single star is one star's f_λ; the caption must own that they are not on the same
   absolute scale (normalize the population curve to its own panel, or a schematic dual-axis).
   Advisor consult at Chunk 1 if it reads as a bug.
5. **f_ν → panel representation (still open — measure at Chunk 1):** the cube is f_ν [L☉/Hz];
   the SED panel's axis convention decides whether to convert to f_λ (×c/λ²) or plot f_ν. A
   build detail, settled by looking at `sed.js`.
6. **α composition (deferred):** BPASS ships α-enhanced population spectra (alpha±0.2…+0.6).
   Out of scope for Chunk 1 (`alpha+00` only), a natural tie-in with the Coelho α spectrum
   axis later.

## Honesty tiering (the project rule, applied)
- **Tier 1/2 (real, measured):** the integrated population spectrum vs (Z, age), single vs
  binary, straight from the BPASS SSP — the UV-longevity difference is *measured*, not
  narrated. (Chunk 2: the HRD census counts, likewise real.)
- **Schematic (caption-owned):** the per-10⁶-M☉ vs one-star flux-scale relationship; any
  visual pairing of the population cloud with the single marker.
- **Gate 0 first:** the single-vs-binary difference must be visible-and-real through the
  runtime before any control ships.

## References
BPASS: Eldridge et al. 2017 (PASA 34, e058); Stanway & Eldridge 2018 (MNRAS 479, 75);
BPASS v2.3 α-enhanced: Byrne et al. 2022 / the v2.3 release paper (Warwick). Data: Zenodo
10.5281/zenodo.6383329 (v2.3 SSP spectra, CC-BY 4.0); the main BPASS data release (numbers/
HRD census) via the Warwick/gSTAR portal. HOKI reader: Stevance et al. 2020 (JOSS). See also
`entwined-consort-inspiral.md` (the POSYDON co-evolved-track sibling — the *other* binary
data source, deliberately kept distinct) and `whirling-cohort-atlas.md` Tier D (where this
population sibling was first named).
