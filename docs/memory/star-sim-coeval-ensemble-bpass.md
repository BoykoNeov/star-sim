---
name: star-sim-coeval-ensemble-bpass
description: The BPASS coeval-population SED overlay — the first ENSEMBLE sibling (bpass.py + /population), single-vs-binary integrated spectra. Chunks 1 (overlay) + 3 (hosting) BUILT; Chunk 2 (HRD number-density) deferred.
metadata:
  type: project
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

**Next**: Chunk 2 (HRD number-density overlay — needs the SEPARATE BPASS "numbers" plain-text
release, its own recon). See [[star-sim-binary-stripped]]
(the single-star stripped endpoint), [[star-sim-co-hms-rlo]] (POSYDON co-evolved binary tracks),
[[star-sim-phase5-spectra]] (the spectra-bake precedent), [[star-sim-nonthermal-sed-plan]] (the
SED panel this overlays).
