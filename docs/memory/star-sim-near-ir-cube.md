---
name: star-sim-near-ir-cube
description: "The near-IR spectrum cube (v2, 2026-09-06): λ 3000 Å → 2.5 µm. The wall was the COOL grid (Göttingen MedRes-A stops at 1 µm), never CAP18/OSTAR; MedRes-R is the drop-in. Piecewise λ bins (2.5 Å optical / 10 Å near-IR) + float32-as-baked make the wider cube CHEAPER in RAM than the optical one. BAKE_VERSION is now per cube. CCM89 gained its IR branch. Bands are gated by the served cube's own coverage; the CMD panel draws Johnson/Gaia/2MASS."
metadata:
  node_type: memory
  type: project
---

The last open **science** row of the roadmap: the spectrum cube stopped at 8999 Å, so
Gaia G/RP and 2MASS JHK were uncomputable and the observer panel was optical-only.
Shipped 2026-09-06. Full build record: `backend/docs/msg_spectra_build_recipe.md` §6a.

## The finding that made it cheap: it was never the atmospheres

`bake()` clamps λ to the **narrowest** spliced grid, so the cool splice alone decided
the cube's red edge. Measured off the `.h5` files' own `specsource` attrs — the grids
page is a claim, the file is the fact:

| grid | λ range |
|---|---|
| `sg-CAP18-coarse.h5` | 1300 Å – 6.5 µm (already there) |
| `sg-OSTAR2002-low.h5` | 880 Å – 5 µm (already there) |
| `sg-Goettingen-MedRes-A.h5` | 3000 Å – **1 µm** ← the wall |
| `sg-Goettingen-MedRes-R.h5` | 3000 Å – **2.49999 µm** ← the fix |

MedRes-R is the same PHOENIX library over the **same three axes and the same ranges**
(Teff 2300–12000, [Fe/H] −4…+1, log g 0–6), R = 10000 ×10-oversampled instead of
Δλ = 1 Å, 4.8 GB instead of 1.7. So the data half was a download and a re-bake — no new
splice logic, and the void statistics came out **bit-unchanged** from v1 (7380 voids,
6390 filled along log g, 990 same-Teff, **0 fallback**).

`lam_max` is 24999.91, not 25000, and `bake()` floors it — the cube ends at **24985 Å**
with **4299** bins, not 4300. A test that pins 4300 against the *cube* would be wrong;
`build_lam_edges` (the pure function) is what 4300 belongs to.

## Two memory decisions, both measured before anything was written

1. **The λ axis is piecewise.** 3000–25000 Å at the optical 2.5 Å step is 8800 bins =
   **629 MB resident** (measured, not estimated). The optical cannot be coarsened to pay
   for it: its 2.5 Å bins were measured at ~1 bin/px at full panel width, Na D landing on
   2.4 bins. So `build_lam_edges` keeps 2.5 Å below `NIR_FROM` (1 µm) and uses `NIR_STEP`
   (10 Å) above — R = 1000 at 1 µm rising to 2500 at 2.5 µm, comparable to the optical's
   R ≈ 2400 at 6000 Å and far finer than the bands it exists to serve.
2. **`_Spectra` stopped upcasting float32 → float64 on load.** That upcast had been
   doubling the cube for nothing. Together the *wider* cube costs **less** than the
   optical one did:

   | cube | bins | npz | resident |
   |---|---|---|---|
   | v1 optical (float64 on load) | 2400 | 98 MB | 343 MB |
   | v2 near-IR (float32 as baked) | 4299 | 180 MB | **308 MB**, cold load 0.7 s |

## The trap that CI could not have caught

`spectra.py` had **one `BAKE_VERSION` checked against all five cubes**. Bumping it for
the main cube would have rejected the alpha, WD, WR and stripped cubes on a machine whose
four were fine — and the run would have been **green**, because every one of those tests
skips on a data-free clone. Versions now ride in the `_CUBE_FILES` row, per cube. The
same shape of coupling exists wherever one constant guards several artefacts; look for it.

## The physics bug that fell out on the way

`ccm89` returned **exactly 0 past 9091 Å**, so a dust-reddened star would have kept an
**unreddened J/H/K tail beside a dimmed B and V** — a silent wrong colour in the very
bands this work exists to serve. CCM89's IR branch (eq. 2a/2b, 0.3 ≤ x ≤ 1.1, i.e.
0.909–3.33 µm) is now in `photometry.py` *and* `reddening.js`, pinned at the three 2MASS
pivots in both suites: A_J/A_V 0.288, A_H 0.182, A_Ks 0.118. The two branches meet at
x = 1.1 with a **real 3.0e-4 step (0.06 %)** — CCM89's own, not a port bug — pinned as a
bound, since a mis-transcribed coefficient opens it far wider. See [[star-sim-js-test-harness]].

## Which bands are honest is a property of the DATA

`photometry.bands_within(lam)` keeps only filters whose **full** tabulated transmission
lies inside the served λ grid. The committed asset carries eight bands (B, V, BP, G, RP,
J, H, Ks); an optical cube answers for three, this one for eight, and **no code reads a
version flag**. That is what let the band table, the CMD planes and the tests all land
before the bake existed. Integrating Ks over a cube that stops at 8999 Å would have been
the invisible-Na trap in its purest form.

## Verification (v1 kept aside and compared — do this before overwriting)

- **The optical did not move.** Every CAP18 and OSTAR node is **bit-identical** to v1 over
  the first 2400 bins (median and max |ΔF|/F exactly 0). The 19 sub-3500 K nodes changed
  as they must (a different resampling of the same models): median 0.25 %, p90 2.6 %,
  p99 12 %; the lone >100× outlier is one bin whose v1 flux was 3.2e-6 against a cool-block
  median of 4.7e4 — a dead molecular line core, not a physical change.
- **Solar anchors** (literature in brackets): M_V 4.832 (4.81, *unchanged from v1 to the
  last digit* — as it had to be, the optical bins being identical) · M_G 4.683 (4.67) ·
  M_Ks 3.317 (3.27) · (BP−RP) 0.819 (0.82) · (J−Ks) 0.368 (0.362) · (V−Ks) 1.516 (1.560) ·
  (B−V) 0.612 (0.65 — the known B-band zero-point *convention*, unchanged; V−Ks carries the
  same ~0.04 mag scale, and it is common-mode, see [[star-sim-observer-cmd]]).
- **A cool star, where the point is.** 3300 K / log g 4.9: V−Ks 4.67 (observed M dwarfs
  ~4–5), J−Ks 0.86, and **67.7 %** of the served 3000 Å–2.5 µm flux beyond 1 µm, against
  **28.1 %** for the Sun. The panel's near-IR band shows the H₂O bands and the J/H/K windows.

## Frontend consequences

- **The spectrum panel keeps an optical default frame** (`OPTICAL_VIEW_HI` = 10000 Å).
  Framing all 22000 Å by default would squeeze the whole visible spectrum — the colour
  shading, every marked line — into the left third. The near-IR is a **band you pick**,
  beside the line presets. Every other cube (WD/WR/stripped/α) stops at 8999 Å, so the cap
  is a no-op there and their framing is byte-identical.
- **Sample dots are gated on density, not on "is a band selected"** — 1500 of them across
  the near-IR paint a rope, not a sampling — and the caption **measures its own bin spacing
  off the served λ array**, because a hard-coded 2.5 Å is now true in only half the range.
- **No near-IR line markers.** Pa β, He I 10830 and the CO bandhead each need their own
  measured Gate 0 (slope-minimal step against a control wavelength) first. A band with no
  guide lines is honest and complete; unmeasured guides are the TiO/VO lesson.
- **The CMD is three planes** — Johnson (B−V, M_V), Gaia (BP−RP, M_G), 2MASS (J−Ks, M_Ks).
  `/photometry_track` carries a `mag` dict per row (not a hand-picked mv/bv0/bp trio, which
  would put V in the payload twice with no authoritative copy) and `cmd.js` holds no band
  arithmetic: a diagram is which two bands to subtract and which to plot down the side. The
  readout speaks the selected plane's bands, so numbers and axes cannot disagree, and the
  B-band caveat shows only in Johnson. A plane whose filters run off the grid's red edge
  **greys with a reason** — the third hide-reason, see [[star-sim-frontend-ux]].
- **The observer panel floor was re-measured and raised** (700 → 707, phone 721 → 728):
  the band row adds 23 px *and* the 2MASS/Gaia labels are longer than the Johnson ones, so
  both had to be re-swept. See [[star-sim-visual-performance]].

## Operational notes

- The main cube has **no hosted `-baked` asset** (unlike Koester/PoWR/Coelho): it is the one
  cube that needs the MSG container, so a fresh clone has no `/spectrum` until someone bakes
  it. See [[star-sim-hosted-data-assets]].
- The `msg_spike` container survives stop/start with its MSG toolchain and the three older
  grids in `/tmp` — check `docker ps -a` before assuming a multi-hour rebuild.
- `docker cp` of a 5 GB grid into the container took ~25 minutes and **blocks `docker exec`
  meanwhile**; that is saturation, not a hang.
