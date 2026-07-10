---
name: star-sim-coeval-ensemble-bpass
description: "The BPASS coeval-population overlays — the first ENSEMBLE sibling (bpass.py + /population + /population_hrd), single-vs-binary. Chunks 1 (SED spectrum), 2 (HRD number-density), 3 (SED hosting) ALL BUILT — the arc is complete on both panels."
metadata: 
  node_type: memory
  type: project
  originSessionId: 58fc9a43-acfe-4fd8-b5b2-818477be0a6a
---

The **coeval-ensemble overlay** (plan `docs/plans/coeval-ensemble-overlay.md`) — the
**first ENSEMBLE sibling**. Every prior sibling renders ONE thing (a track, one state,
one two-body system); this renders a whole *coeval stellar population* (a million stars
born together at the marker's [Fe/H], seen at the marker's age) as an INTEGRATED spectrum,
split **single-star vs. binary**. The headline: **binaries keep a population UV/ionizing-
bright far longer** (stripped hot stars, blue stragglers, hot subdwarfs) — the thing a
single-star sim structurally cannot show. Data = **BPASS v2.3** (Eldridge+2017, Stanway &
Eldridge 2018, Byrne+2022), population synthesis — NOT POSYDON (co-evolved tracks). This is
the explicitly-unscoped population-overlay tail named across the binarity plans.

**Chunk 1 BUILT 2026-07-10** (403 pytest [+6], Playwright 1440+390 zero console errors):
- **Data**: Zenodo record `10.5281/zenodo.6383329` (CC-BY 4.0). `fetch_bpass.py --download`
  pulls the `alpha+00` sin+bin pair (~1 GB, in-session Zenodo direct URLs — unlike POSYDON's
  handoff). The Benson/Galacticus repackaging is ONE clean cube per file (no HDF5-demux / no
  HOKI): `spectra (13 Z × 51 age × 100000 λ)` **f_ν [L☉/Hz] per 10⁶ M☉**, `ages` = **linear
  Gyr** log-spaced 0.001–100, `metallicities` = **already [Fe/H]=log10(Z/0.020)** (Z☉=0.020,
  ~0.15 dex off MIST's 0.0142 — a labeled systematic), `wavelengths` 1–100000 Å 1-Å step.
- **Bake** `scripts/bake_bpass_spectra.py` (host, h5py) → `data/bpass/bpass_ssp.npz` (4.1 MB,
  gitignored): λ decimated 100000→1200 by **log-rebin-AVERAGE** (faithful Lyman/Balmer breaks,
  NOT nearest-sample), float32, f_ν kept.
- **Runtime** `bpass.py` — a **pure numpy/stdlib sibling** (imports NOT even `StellarState`;
  AST-tested), never touches PROVIDER. `population_sed(feh, age_gyr, population="both")` snaps
  ([Fe/H] linear, age **nearest-in-log10** — the grid is geometric over 5 decades), converts
  **f_ν→f_λ (×c/λ²)** at serve time (preserves the sin/bin ratio, matches the panel's F_λ axis),
  returns both curves + snapped node + `*_snapped_far`. `[Fe/H]` snapped **direct + labeled**
  (not converted to the MIST Z☉ basis — the "labeled, not silently converted" stance).
- **Routes** `/population` (bypasses PROVIDER, snap-always, 422 age≤0, 503 unbaked) +
  `/population_status` (the `/helium_status` honesty gate).
- **Frontend**: `sed.js` gains `setPopulation`/`clearPopulation` (a pushed-data consumer — sed.js
  owns no fetch, like roche.js). Draws BOTH curves **co-scaled to ONE shared reference** (the
  vertical gap IS `log(F_bin/F_sin)`, Tier-1 not schematic — advisor Q2, NOT own-peak-each) and
  **fills the magenta WEDGE where bin>sin** (the payoff — huge UV/ionizing area at 40 Myr, clear
  FUV at 1 Gyr). Living-star only; coronal/wind overlays decluttered + rainbow dimmed while on;
  a population-aware SED caption. `main.js` `#population-toggle` (opt-in, gated on
  `/population_status`, **NOT mass-gated** — reads only feh+age, unlike the He/α HR overlays),
  fetches on (feh,age)-node change (bucketed finer than the grid so a same-node age scrub doesn't
  refetch), latest-wins, torn down on any mode switch via `dropHeliumForModeSwitch`.

**Gate 0 MEASURED-AND-PASSED** (`temp/bpass_recon/gate0_uv.py`, raw HDF5, solar Z, all 51 ages):
ionizing (<912 Å) bin/sin up to **~256× at 40 Myr** (7×@10 → 32×@100 → 13×@250 Myr); FUV (1500 Å)
up to **~26× at ~1 Gyr**; optical (5500 Å) **~1× at all ages** (cool-giant bulk unchanged). The
lone 8033× at 25 Gyr is a divide-by-underflow artifact (both fluxes ≈0). The gap ratio is
**representation-independent** (F_λ vs νF_ν identical), so the payoff position is set by AGE, not
normalization — caption steers to ~0.1–1 Gyr.

**The build gotcha (Playwright caught it, tests didn't):** the overlay first drew NOTHING — a
wrong dict key (`population.lam_ang` vs the served **`wavelength`**) made `drawPopulation` return
early, leaving only a dimmed rainbow stripe. It LOOKED like a fatal 14-decade-axis compression
problem (I nearly escalated to the user for a dedicated panel); it was a one-line key fix. **Lesson:
before concluding "the panel can't show this," confirm the data actually reached the canvas** (a
non-empty array on-screen) — don't blame the representation for an empty draw. The advisor's
wedge-fill + un-occlude + declutter fixes were the right call regardless (they make the real curve
legible), but the "vertical stripe" symptom was the key bug, not the representation.

**Advisor arc**: (1) pre-build — measure Gate 0 from the raw cube first; co-scale not own-peak;
draw-both not toggle; f_ν→f_λ in bpass.py; snap age in log10; status-gate. (2) mid-build — when I
reported the "compression" symptom with evidence contradicting his f_ν→f_λ call, he correctly said
re-anchoring wouldn't help (age sets the position) and the real fix was wedge-fill + un-occlude +
declutter → then the key bug surfaced.

**Chunk 3 BUILT 2026-07-10 (hosting)**: `fetch_bpass_baked.py` pulls the 4.1 MB `bpass_ssp.npz`
from the `bpass-baked-v1` GitHub Release (the **9th** tag — see [[star-sim-hosted-data-assets]]).
Mirrors `fetch_coelho_baked.py` exactly (the single self-contained cube — a flat
`{GRID_FILENAME: sha256}` over `_baked_release.fetch_one`, NOT the helium/alpha 2-tuple
asset-name mapping, which only exists because every `history.data` collides). **No loader/test
change**: `_Bpass.__init__` is `np.load` + a `bake_version` check with no MIST-style raw-source
fingerprint, so a freshly-downloaded npz loads directly (the spectra-cube path). The ONLY runtime
touch is `bpass.py`'s `_MISSING_HINT` (now leads with the baked fast path). BPASS v2.3 is
**CC-BY 4.0** — an explicit redistribution grant, the cleanest footing (like POSYDON), no license
judgment call. **Verified end-to-end** (not just skip-on-present): a real `gh release create` +
upload, then a fetch into a FRESH empty `STAR_SIM_BPASS_DIR` under `M:\claud_projects\temp` via a
**fresh subprocess** (the dir constant is read at import time — a same-process env poke wouldn't
take), reporting `"ok"` (downloaded, hash-verified), then `population_sed(0.0, 0.04)` served the
Gate-0 ionizing wedge (bin/sin ≈ 906× summed over all <912 Å bins) from nothing but downloaded
bytes.

**Chunk 2 BUILT 2026-07-10 (the HR-diagram NUMBER-DENSITY overlay — the HR-panel twin of the SED
wedge; 405 pytest [+2], Playwright 1440+390 zero console errors):**
- **Data — a DIFFERENT release from Chunk 1's v2.3 spectra** (the v2.3 Zenodo record is spectra-ONLY,
  confirmed). The HR-diagram "hrs" number-density files are the BPASS **v2.2.1** fiducial-output
  release, the `imf135_300` zip on the STARTER-KIT Zenodo record **10.5281/zenodo.7340797** (1.5 GB).
  Fetch odyssey: DataCentral (v2.1, direct HTTP) 500'd on large files (small files OK — a server
  large-file bug); Google-Drive (v2.2.1) hard headless. **Win: Zenodo honours HTTP RANGE requests** →
  a range-backed file object handed to `zipfile` reads the central directory from the tail and pulls
  ONLY the 26 `hrs-{sin,bin}.z*.dat` members (~0.3–0.8 MB compressed each), never the 1.5 GB whole.
  The v2.2.1-HRD-vs-v2.3-spectra version gap is caption-owned (different panel).
- **hrs schema (from hoki.load._hrTL — MEASURED):** each file (45900,100) ASCII = 51 ages × 9 blocks
  × 100 rows; 9 = 3 HR types {TL,Tg,TTG} × 3 surface-H bins {high,med,LOW}. Type **TL** (rows 0:15300),
  all_H=hi+med+lo; grid[age,ti,li] logTeff=0.1+0.1·ti (real stars ti~33..55), logL=−2.9+0.1·li; values
  = stars/1e6Msun per cell per age (RAW per-age count; hoki's dt weighting is only for age-RANGE
  stacking). **Metallicity keyed by z-code in the FILENAME** (zem5..z040 → [Fe/H]=log10(Z/0.020) — the
  gotcha the plan flagged; the low-H block = the stripped/He stars).
- **Bake** `scripts/bake_bpass_hrd.py` (ranged extraction built in) → `data/bpass/bpass_hrd.npz` (~1.6
  MB — sparse density compresses hugely; crops the mostly-empty 100×100 grid to the occupied logt(28)/
  logl(100) window). **Runtime** `bpass.py` `population_hrd()`+`hrd_available()` over a 2nd cube
  (`_BpassHRD`, `BAKE_VERSION_HRD`, same snap idiom). **Route** `/population_hrd` (bypasses PROVIDER,
  snap-always); `/population_status` gains `has_hrd`.
- **Frontend rides the EXISTING `#population-toggle`** (one concept, both panels): `refreshPopulation`
  fetches `/population`+`/population_hrd` in parallel (HRD `.catch(null)` degrades gracefully) →
  `hr.setPopulationHRD`. `hr.js` draws a translucent cell heatmap in the LIVING view only (behind
  track/marker): MAGENTA where the single pop is ≤20% of the binary count (binary-only — blue
  stragglers/stripped-He), faint CYAN where in both, + a bottom-left legend. Shared note gains the HRD
  lesson + the stripped-star excess.
- **Gate 0 (measured, solar 40 Myr):** single hot-region (logTeff>4.4) count = **0**, binary ~**283**
  (139 binary-only cells); stripped-He total ~**33×** more with binaries.
- **THE BUILD GOTCHA (Playwright caught it, tests didn't — AGAIN, exactly like Chunk 1's dict-key):**
  the entire magenta payoff was INVISIBLE at first — a too-narrow 4-decade alpha range clamped the
  sparse hot cells (~1–10 stars, ~5 dex below the ~10⁵ cool-MS peak) to zero alpha. The Gate-0 tests
  passed the whole time (they assert counts, not pixels). Fixed with an 8-decade range + a per-category
  alpha FLOOR (the binary-only cells are categorical — "singles can't make these" — not a density
  claim). **Lesson restated: a passing data-gate test doesn't prove the payoff reached the canvas.**
- **Advisor arc (Chunk 2):** pre-build — fetchability is the pivot, test it (CKAN API + gdown +
  range-extract), scope tiny, measure Gate 0 through the parser BEFORE any UI, z-code→[Fe/H] yourself,
  crop the mostly-empty grid, version gap is caption-owned, defer overlay aesthetics until you've seen
  the data. All followed; Gate 0 lit up decisively so the chunk was real.

**HRD hosting** (the SED's Chunk-3 analogue) is a clean FOLLOW-UP, deliberately not done this session:
the cube is host-baked/gitignored and the `has_hrd` gate hides the HR cloud on a data-less clone (how
Chunk 1 shipped before Chunk 3). It also needs the v2.2.1 starter-kit license confirmed CC-BY + a
`gh release` asset upload (outward-facing). See [[star-sim-hosted-data-assets]], [[star-sim-binary-stripped]]
(the single-star stripped endpoint), [[star-sim-co-hms-rlo]] (POSYDON co-evolved binary tracks),
[[star-sim-phase5-spectra]] (the spectra-bake precedent), [[star-sim-nonthermal-sed-plan]] (the
SED panel Chunk 1 overlays).
