# MSG (pymsg) build recipe — for the build-time spectrum bake

The Phase 5 **spectrum panel** uses [MSG](https://msg.readthedocs.io) (Townsend's
"Multidimensional Spectral Grids") to interpolate synthetic stellar spectra in
`(Teff, log g, [Fe/H])`. Per the hosting decision, MSG is a **build-time tool**:
we build it once in a container, use `pymsg` offline to bake a dense spectrum
grid into compact arrays, and the runtime backend does pure-Python trilinear
lookup (no MSG/Fortran dependency at run time, Windows-clean). This file is the
durable record of **how to build MSG**, because pymsg has no pip/conda-forge
wheel — it must be compiled from source, and the build has several non-obvious
gotchas.

**Key finding:** MSG builds cleanly on a **lean conda-forge stack — no MESA SDK,
no ~1.2 GB download.** MSG's docs "strongly recommend" the MESA SDK, but it only
needs a modern Fortran compiler + LAPACK + LAPACK95 + HDF5 + fypp + pkgconf +
cython, all of which conda-forge provides *except* LAPACK95 (built from netlib
source in one step). This was proven end-to-end (see §4).

## 0. Why not the MESA SDK image directly

The project already has `evbauer/mesa_lean:r24.03.1.01`. It is **too old**: it
ships **gfortran 9.2**, but MSG 2.2's `FFLAGS` include `-ftrampoline-impl=heap`,
an **upstream GCC 14** option — gfortran 9.2 rejects it. MSG 2.2 also gates on
**MESA SDK ≥ 26.2.2**. Rather than download a current SDK, we get **gfortran 15
from conda-forge** (which has the flag) and build everything lean.

## 1. Inputs (downloaded on the host, copied into the container)

- MSG source: `https://github.com/rhdtownsend/msg/releases/download/v2.2/msg-2.2.tar.gz`
- Miniforge: `https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh`
- LAPACK95 source: `https://www.netlib.org/lapack95/lapack95.tgz` (netlib v2.0, 2000)

Any modern Linux works as the base (we reused the `mesa_lean` container only for
convenience; **the SDK toolchain is not used**).

## 2. Build LAPACK95 from source (the one piece conda-forge lacks)

netlib LAPACK95 ships a NAG-compiler `make.inc` and **no `.f90.o` rule** (modern
GNU make has no built-in one). Write a gfortran `make.inc` with legacy flags and
add the suffix rule:

```make
FC  = gfortran -ffree-form -ffree-line-length-none
FC1 = gfortran -ffixed-form -ffree-line-length-none
OPTS0 = -O1 -fPIC -std=legacy -fallow-argument-mismatch -frecursive -w
MODLIB = -I./
OPTS1 = -c $(OPTS0)
OPTS3 = $(OPTS1) $(MODLIB)
OPTL = -o
OPTLIB =
LAPACK95 = ../lapack95.a
LAPACK77 = -llapack
BLAS = -lblas
LIBS = $(LAPACK95) $(LAPACK77) $(BLAS)
SUF = f90

.SUFFIXES: .f90 .o
.f90.o:
	$(FC) $(OPTS3) $<
```

```bash
cd LAPACK95 && mkdir -p lapack95_modules
cd SRC && make -j1 single_double_complex_dcomplex
# -> ../lapack95.a (3.6 MB) and lapack95_modules/{f95_lapack,f77_lapack,la_auxmod,la_precision}.mod
cp ../lapack95.a ../liblapack95.a    # so -llapack95 resolves
```

## 3. Build MSG with conda-forge gfortran 15

```bash
bash Miniforge3-Linux-x86_64.sh -b -p /opt/conda
source /opt/conda/etc/profile.d/conda.sh && conda activate base
conda install -y -c conda-forge gfortran libblas liblapack hdf5 \
                                 pkgconf fypp numpy cython gawk

export MSG_DIR=/path/to/msg-2.2
export MESASDK_ROOT="$CONDA_PREFIX"        # fypp_deps formats this; just needs to be non-empty
export CPATH="$CONDA_PREFIX/include" LIBRARY_PATH="$CONDA_PREFIX/lib"
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$MSG_DIR/lib"
```

pkg-config files (lapack95 ours, lapack ours, **hdf5_fortran.pc ships with conda**):

```bash
PCDIR=/tmp/mypc; mkdir -p $PCDIR
printf 'Name: lapack\nVersion: 3.0\nLibs: -L%s/lib -llapack -lblas\nCflags:\n' "$CONDA_PREFIX" > $PCDIR/lapack.pc
printf 'libdir=/path/to/LAPACK95\nincdir=/path/to/LAPACK95/lapack95_modules\nName: lapack95\nVersion: 3.0\nRequires: lapack\nLibs: -L${libdir} -llapack95\nCflags: -I${incdir}\n' > $PCDIR/lapack95.pc
export PKG_CONFIG_PATH="$PCDIR:$CONDA_PREFIX/lib/pkgconfig"
```

Patches to the extracted MSG tree (re-apply on every fresh extract):

```bash
# (a) bypass the SDK ">=26.2.2" version gate (we are not using the SDK)
for f in $(find "$MSG_DIR" -name check_sdk_version); do printf '#!/bin/sh\necho passed\n' >"$f"; chmod +x "$f"; done
# (b) conda's pkgconf strips the conda-prefix -I/-L (treats it as a system path),
#     so MSG never gets -I$CONDA_PREFIX/include for hdf5.mod. Append explicitly.
for mk in "$MSG_DIR"/build/Make.inc "$MSG_DIR"/src/forum/build/Make.inc; do
  printf '\nFFLAGS += -I%s/include\nFPPFLAGS += -I%s/include\nLDFLAGS += -L%s/lib\n' \
     "$CONDA_PREFIX" "$CONDA_PREFIX" "$CONDA_PREFIX" >> "$mk"
done

make -j4 -C "$MSG_DIR"        # builds libmsg/libcmsg/libfmsg/libforum + pycmsg*.so
pip install "$MSG_DIR/python" # the pure-python pymsg wrapper
```

## The gotchas (each cost a build iteration)

1. **gawk is mandatory.** MSG's `makedepf08.awk` uses POSIX classes
   (`[[:blank:]]`). The container's `awk` was **mawk**, which silently doesn't
   match them → generated `*.dep` files miss all cross-module rules → Fortran
   module build race (`Cannot open module file 'kinds_m.mod'`). Install gawk and
   `ln -sf $(command -v gawk) /opt/conda/bin/awk`.
2. **Build from a FRESH extract.** A failed parallel build leaves a corrupt
   `libforum.dep` + partial `.anc/.mod`; `make` won't recover. `rm -rf` and
   re-extract, then `make -j` is fine on a clean tree.
3. **gfortran needs an explicit `-I` for `.mod` search — `CPATH` does NOT work**
   for Fortran modules (verified). Hence patch (b) above.
4. **`fypp_deps` crashes if `MESASDK_ROOT` is unset** (`'{}/lib/python'.format(None)`).
   conda's python already has `fypp` importable, so just set `MESASDK_ROOT` to any
   valid path (we use `$CONDA_PREFIX`); the bogus `/lib/python` entry is ignored.
5. **lapack95 `.mod` must be built by the SAME gfortran** that builds MSG (gfortran 15).
   The MESA SDK's prebuilt `liblapack95.a` is gfortran-9.2 — its `.mod` are
   unreadable by gfortran 15 (so you must build lapack95 from source).

## 4. Runtime usage (the bake step will use this)

```python
import os, numpy as np, pymsg
# MSG_DIR set; LD_LIBRARY_PATH includes $CONDA_PREFIX/lib and $MSG_DIR/lib
sg = pymsg.SpecGrid("sg-demo.h5")
sg.axis_labels          # ['Teff', 'log(g)']   (CAP18 also has '[Fe/H]')
sg.axis_x_min/x_max     # {'Teff': 3500.0, 'log(g)': 0.0} .. {'Teff': 49000.0, ...}
sg.lam_min, sg.lam_max  # 3000 .. 9003 Angstrom (demo grid)
F = sg.flux(x={'Teff':5772.0,'log(g)':4.44}, z=0.0, lam=lam)  # erg/cm^2/s/A, len(lam)-1 bins
```

`flux(x, z, lam, deriv=None, order=3)`: `x` = dict of axis params, `z` = redshift
(use 0.0), `lam` = wavelength bin boundaries (Å). Returns flux per bin.

**Measured proof** (bundled `sg-demo.h5`, a Kurucz `ap00` grid, solar, 3500–49000 K):
Balmer Hα/Hβ absorption depth peaks at A stars (Hα 42%, Hβ 62% at 9500 K), Ca K
(3933 Å) is strong in cool stars (73% in M, 70% in the Sun) and vanishes when hot
(0.1% at A) — textbook spectral-sequence behaviour. Flux scales ~3000× from M to O.

## 5. For the real bake: the grid (CAP18 — now baked)

`sg-demo.h5` proves the pipeline but is **solar-only** (no `[Fe/H]` axis). For the
`(Teff, log g, [Fe/H])` bake, fetch a `[Fe/H]`-varying grid from the
[MSG grid-files page](http://user.astro.wisc.edu/~townsend/static.php?ref=msg-grids)
— **CAP18** (Allende Prieto 2018), the metallicity-varying grid. The page lists four
CAP18 variants; the right one is **`sg-CAP18-coarse.h5`** — it is the smallest with
**exactly the three axes we want** (`Teff, log(g), [Fe/H]`; the `large` 73 GB variant
adds `[α/Fe]` + `log(ξ)`, and `high`/`ultra` are the same 3 axes at 2.9/5.2 GB just
higher spectral resolution we resample away anyway). Current download (~339 MB, v2):

```bash
curl -fL -o data/spectra/grids/sg-CAP18-coarse.h5 \
  http://user.astro.wisc.edu/~townsend/resource/download/msg/grids/CAP18/coarse/sg-CAP18-coarse.h5
```

Grids are large HDF5 downloads, gitignored like `data/mist` and `data/mesa` (keep the
`.h5` so a future re-bake doesn't re-download).

**Heads-up — CAP18's Teff ceiling is 30000 K, not ~50000.** (The earlier note here
claiming ~50000 K was wrong — verified against the grid: `Teff∈[3500, 30000]`,
`log(g)∈[0, 5]`, `[Fe/H]∈[−5, 0.5]`.) On its own CAP18 **traded hot-end coverage for
the metallicity axis** vs the solar `sg-demo` (which reached 49000 K). That hot-end gap
is now closed by the **OSTAR2002 splice** (§5a below): the baked grid reaches **55000 K**.
The clamp is symmetric with the cool floor and handled honestly in `spectrum_data` — a
star hotter than 55000 K shows the 55000 K spectrum, never a 422/freeze.

## 5a. The hot-end splice (OSTAR2002, >30000 K)

CAP18 stops at 30000 K, but the hottest draggable star (a massive metal-poor O star)
reaches ~80000 K. To give those O stars *real* spectra — whose defining feature is
**He II 4686** absorption, not the Balmer/Ca/Na lines of cooler stars — we splice in
**OSTAR2002** (Lanz & Hubeny 2003, a TLUSTY O-star grid, 27500–55000 K) onto the hot end
of the Teff axis. The `low` variant is the right tier (smallest, like CAP18 `coarse`):

```bash
curl -fL -o data/spectra/grids/sg-OSTAR2002-low.h5 \
  http://user.astro.wisc.edu/~townsend/resource/download/msg/grids/OSTAR2002/low/sg-OSTAR2002-low.h5
```

(~50 MB; gitignored like the other grids — kept so a re-bake doesn't re-download.) Its
axes are `Teff / Z/Zo / log(g)` — note the **linear** metallicity ratio `Z/Zo` (0…2), not
CAP18's logarithmic `[Fe/H]`. The bake reconciles them by sampling OSTAR at
`Z/Zo = 10**[Fe/H]` (floored at OSTAR's smallest *positive* node 0.001 = [Fe/H]=−3 — see
the gotcha below) and clamping log g to OSTAR's 3.0–4.75 (hot models live at high gravity;
the flat clamp below 3.0 is the honest edge). **BSTAR2006 was deliberately NOT used**: it
spans 15000–30000 K, entirely inside CAP18's range, so it adds nothing above 30000 K (its
only role would be replacing CAP18's hot LTE end with NLTE, a bigger change for a worse
seam — measured BSTAR/CAP18≈0.94 vs OSTAR/CAP18≈0.97–0.99 at the overlap).

**Two splice gotchas (each cost a bake iteration):**

1. **Floor `Z/Zo` at the smallest *positive* node, not 0.0.** A query at `Z/Zo` between
   0.0 (OSTAR's metal-free model) and 0.001 needs the metal-free bracket, which is masked
   at hot/high-gravity points — MSG then raises `ValueError('invalid argument')` (a
   partial-cell void) rather than the clean `LookupError` the bake fills. Flooring at
   0.001 stays among the metal nodes; [Fe/H]<−3 is below any real star anyway.
2. **Void-fill must preserve Teff.** OSTAR masks low gravity at hot Teff, and at the
   metal-poor + intermediate-hot corner an *entire* log g line can be void. The old fill
   fell back to nearest-neighbour over the full param space, which (in index distance)
   pulls the 30000 K *cool-grid* neighbour — a wrong-Teff fill. The bake now has a
   **same-Teff fill pass** before the global fallback (clamps metallicity, keeps the
   temperature exact). On the CAP18+OSTAR bake: 6390 along log g, **990 same-Teff, 0
   fallback** — no Teff-crossing fill anywhere.

## 5b. The cool-end splice (Göttingen/PHOENIX, <3500 K)

CAP18 stops at 3500 K, but the coolest draggable stars reach **~2800 K** — measured
through the live provider: a 0.1 M☉ M-dwarf bottoms at **2809 K**, and the RGB/AGB
tips of low-mass stars (incl. the **Sun's own giant tip, ~3278 K**) sit below 3500 K
too. Clamping all of them to the 3500 K floor was a poor stand-in: below ~3000 K the
optical spectrum is dominated by **TiO molecular bands** that deepen fast as the star
cools (a frozen 3500 K spectrum understates them badly). So we splice in the
**Göttingen grid** (Husser et al. 2013 PHOENIX, the canonical cool-star library)
onto the *cool* end of the Teff axis. The **Solar-alpha MedRes-A** variant is the
right tier:

```bash
curl -fL -o data/spectra/grids/sg-Goettingen-MedRes-A.h5 \
  http://user.astro.wisc.edu/~townsend/resource/download/msg/grids/Goettingen/MedRes-A/v3/sg-Goettingen-MedRes-A.h5
```

(~1.7 GB; gitignored like the other grids — kept so a re-bake doesn't re-download.) Why
this grid (verified against the live grids page, not assumed):

- Axes are **exactly `Teff, [Fe/H], log(g)`** — the SAME three as CAP18, and metallicity
  is **logarithmic `[Fe/H]`** (NOT the TLUSTY hot grids' linear `Z/Zo`), so the cool
  splice needs **no metallicity conversion at all** — even simpler than the hot one.
- **Teff [2300, 12000] K** — covers the whole gap below 2809 K, with a generous
  3500–12000 K overlap with CAP18 for a clean seam.
- **log g [0, 6]** — spans cool **dwarfs *and* giants**, so the RGB/AGB tips (log g ~0–1.5)
  are covered, not just M-dwarfs. (This ruled out **SPHINX** — a cool grid 2000–4000 K
  but **dwarf-gravity-only** log g 4.0–5.5, which would clamp every cool giant; and
  **Coelho14** which only reaches 3000 K, and **C3K** which has a documented voids
  warning. NewEra LowRes is the exact-3-axis alternative but 4.9 GB for no benefit.)

Implementation (`bake_spectra.py --cool-grid`): `_prepend_cool_teff` adds log-spaced Teff
nodes below CAP18's floor at the cool axis' own log-step (the 96 CAP18 nodes are NOT
re-spread — the mirror of `_append_hot_teff`), and nodes below 3500 K sample Göttingen
with `[Fe/H]`/log g clamped to its range. Both splices compose: the Teff axis becomes
`[cool < 3500][CAP18 3500–30000][hot > 30000]`.

**Findings / honesty notes (measured through the runtime path):**

1. **The seam is graceful.** TiO 6159 Å is essentially continuous across 3500 K
   (Göttingen 0.361 → CAP18 0.356); the larger PHOENIX-vs-ATLAS difference at TiO 7053 Å
   is a *smooth interpolated ramp* between the last Göttingen node and the first CAP18
   node, not a discontinuity (RGI blends them). Per-spectrum normalization hides any
   continuum-level offset anyway.
2. **Only TiO bandheads are marked in the UI — VO was dropped.** All three TiO heads
   (5167/6159/7053 Å) verify as real, deep edges (slope-minimal step **0.55–0.75 at
   2809 K** vs ~0.03 in the Sun). But **VO 7400 Å reads ~0 (flat/negative, like a control
   wavelength)** — at the reachable Teff it forms no clean isolated bandhead, so labeling
   a guide there would mislabel near-continuum (the boron-b8 / invisible-Na lesson). VO is
   described in the panel prose but gets no guide line.
3. **The cool floor no longer clamps any real star** (2300 K is below the 2809 K coolest),
   so the hot end is now the *only* model gap → the no-model notice stays hot-end-only.

The Phase 5 panel now ships the **3-D CAP18 cube** (`sg-CAP18-coarse.h5` → a real
`[Fe/H]` axis). It originally shipped a **solar-only `sg-demo.h5` MVP** (the CAP18
grids-page host was unreachable at build time, and the MVP de-risked the whole
vertical slice); the swap to CAP18 was a **pure data re-bake, zero code change** —
the bake is **axis-generic**, so it just produced a 4-D cube (`teff × feh × logg ×
λ`) that the runtime reads back out of the `.npz` and the panel's `feh_varies`
caption lights up automatically. The baked `.npz` is **gitignored** (like all of
`data/`), so this is the only reproducibility path — re-run it after any
`BAKE_VERSION` bump or grid change.

Inside the `msg_spike` container (env per §3), with `scripts/bake_spectra.py` and
the grid copied in:

```bash
# (host) copy the script + ALL THREE grids into the reusable build container
docker cp backend/scripts/bake_spectra.py msg_spike:/tmp/bake_spectra.py
docker cp data/spectra/grids/sg-CAP18-coarse.h5 msg_spike:/tmp/sg-CAP18-coarse.h5
docker cp data/spectra/grids/sg-OSTAR2002-low.h5 msg_spike:/tmp/sg-OSTAR2002-low.h5
docker cp data/spectra/grids/sg-Goettingen-MedRes-A.h5 msg_spike:/tmp/sg-Goettingen-MedRes-A.h5

# (container) bake CAP18 + the OSTAR2002 hot splice + the Göttingen cool splice
docker exec msg_spike bash -c '
  source /opt/conda/etc/profile.d/conda.sh && conda activate base
  export MSG_DIR=/tmp/msg-2.2 MESASDK_ROOT="$CONDA_PREFIX"
  export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$MSG_DIR/lib"
  python /tmp/bake_spectra.py \
    --grid      /tmp/sg-CAP18-coarse.h5 \
    --hot-grid  /tmp/sg-OSTAR2002-low.h5 \
    --cool-grid /tmp/sg-Goettingen-MedRes-A.h5 \
    --out       /tmp/spectra_grid.npz'
# (drop --cool-grid and/or --hot-grid for a narrower cube; --grid /tmp/msg-2.2/data/
#  grids/sg-demo.h5 for the original solar MVP)

# (host) copy the cube out to where the runtime looks for it
docker cp msg_spike:/tmp/spectra_grid.npz data/spectra/spectra_grid.npz
```

The CAP18+OSTAR2002+Göttingen bake is a `(142 Teff × 12 [Fe/H] × 11 log g × 2400 λ)`
cube, **~98 MB** (CAP18+OSTAR was `123 × …`, ~76 MB; CAP18-only `96 × …`, ~69 MB; the
solar `sg-demo` bake a 2-D `96 × 11 × 2400`, ~4.7 MB):

- **Teff** **2300**–**55000 K**, **log-spaced**: 96 nodes over CAP18's 3500–30000 (cool-end
  resolution where lines change fast), then 27 *appended* at the same log-step up to
  OSTAR2002's 55000 **and 19 *prepended* at the same log-step down to Göttingen's 2300**
  (the CAP18 nodes are NOT re-spread either way). The runtime interpolates in
  `log10(Teff)` via the `axis_log` flag. Nodes >30000 K sample OSTAR2002, <3500 K sample
  Göttingen. The ≥3500 K block (CAP18+OSTAR) is **bit-identical** to the pre-cool-splice
  cube — the splice purely *added* sub-3500 coverage.
- **[Fe/H]** −5…+0.5 in 0.5 steps (12 nodes; grid-driven — real stars only reach
  ~−0.85…+0.5, the rest just clamp).
- **log g** 0–5 in 0.5 steps.
- **λ** 3000–9000 Å in 2.5 Å bins (bin *centres* stored; Göttingen's 3000–9999.9 Å
  coverage doesn't tighten the window).
- **Voids** (hot + low-gravity *and* cool + low-gravity corners with no model →
  `LookupError`, **39%** of nodes for the three-grid cube) are filled in three passes,
  each preserving Teff as far as possible: **(1) along log g** at fixed Teff *and*
  [Fe/H] (the voids are contiguous log g blocks, so this preserves the dominant
  Teff/[Fe/H] variation exactly); **(2) same-Teff** nearest valid, for a whole log g
  line that was *entirely* void (the metal-poor + intermediate-hot OSTAR corner) —
  clamps metallicity but keeps the temperature exact; **(3) global fallback** (can
  cross Teff — a last resort, logged). On the three-grid bake: **6390 along log g, 990
  same-Teff, 0 fallback** — i.e. no void anywhere got a wrong-Teff spectrum. The stored
  cube is fully regular for `RegularGridInterpolator`. (The bake also clamps **14120**
  negative-flux bins — cubic spline undershoot in deep line cores — to 0; min was
  −2.19e4. The rise from the CAP18+OSTAR bake's 8840 is the Göttingen cool block: PHOENIX
  M-star spectra have deep molecular-line cores that undershoot more. Still only ~0.03%
  of bins, and the reachable cool corner gives sane TiO depths — band step ~0.6 at
  2900 K, NOT cores pinned to black.)
- Knobs: `--grid`, `--hot-grid` (the OSTAR splice), `--cool-grid` (the Göttingen
  splice), `--n-teff`, `--lam-min/--lam-max/--lam-step`, `--out`.
- `BAKE_VERSION` must match `star_sim/spectra.py`'s; the runtime rejects a stale
  cube (re-bake to fix). Neither the CAP18 swap nor the OSTAR splice bumped it — the
  on-disk schema is axis-generic and unchanged; only the Teff axis length +
  `grid_name` differ.

Then the pure-Python runtime (`star_sim/spectra.py`, `scipy` only — no pymsg)
serves `/spectrum`; `pytest backend/tests/test_spectra.py` gates the line physics
(measured through the runtime path), and the `requires_spectra_data` marker skips
those if the cube is absent.

## 7. Endgame spectral grids (Chunk 0 scoping — WR/WD, go/no-go + format notes)

For the stellar-endgame gateway (`docs/plans/smoldering-cinder-gateway.md`, Chunks
6–7) the endgame *spectra* are the one piece NOT already on disk and NOT MSG `.h5`
— pymsg will **not** open any of these, so each needs a **custom reader** (not a
splice onto the existing cube). Scoped before promising "full spectra." **Headline:
WD before WR is confirmed — for axis-compatibility, not just "log g is cleaner."**
All three keep the gitignore-and-cite precedent (download locally, never commit).

**Koester DA white dwarfs — GO (do first).** Public on the **SVO Theoretical
Spectra Server** as `koester2` (LTE, hydrostatic, plane-parallel; Tremblay &
Bergeron 2009 H Stark profiles). No one-click tarball, but the **SSAP service**
(`ssap.php?model=koester2`) returns a VOTable index — loop `fid` to bulk-fetch
~1000–1300 models, ~tens of MB. Format: plain **2-col ASCII** (λ Å [air — verify],
F_λ erg/cm²/s/Å), ~900–30000 Å non-uniform → resample onto the 2400-λ grid. License:
SVO "author's permission" (cite **Koester 2010, Mem.S.A.It. 81, 921**). Axes: **Teff
5000–80000 K, log g 6.5–9.5/0.25** — and **WDs have NO [Fe/H] axis** (pure-H → that
cube axis is degenerate). ~30–60 LOC reader. **Does NOT splice onto the main cube:**
log g 6.5–9.5 is essentially disjoint from the current ~0–6 cube (thin 6.5–7 overlap),
so build a **separate WD cube keyed (Teff, log g)** with [Fe/H] collapsed to a dummy
node — a *sibling* like `/spectrum` itself.
[koester2](https://svo2.cab.inta-csic.es/theory/newov2/index.php?models=koester2) ·
[koester2 SSAP](https://svo2.cab.inta-csic.es/theory/newov2/ssap.php?model=koester2)

**Koester DB (He-atmosphere WD) — NO-GO.** Not on SVO, not on Koester's homepage;
holders are told it is "restricted access, private communication," **non-redistributable**.
Drop it from planning (revisit only by direct request, local-only). Mitigation: cover
hot *He* atmospheres (DO) via TMAP's He composition instead; accept no cool-DB branch.

**TMAP hot WD / CSPN — ✅ BUILT (Chunk 6b, was "conditional GO").** The CSPN /
hottest-WD regime (~100–200 kK) lives **only** in TMAP. We bulk-fetch the **SVO
`tmap` collection** (pre-baked H+He NLTE grids, **Teff 50000–190000 K / 10 kK steps,
log g 5–9 / 0.5, Hemass 0–1 / 0.1**, SSAP `fid` enumeration scriptable) — **NOT** the
native **TheoSSA/GAVO** service, which is per-model / compute-on-demand (an off-grid
request *queues a TMAP run*, minutes→days; do not hammer it). For a DA we take the
**H-rich Hemass=0 slab** (rectangular at log g ≥ 6.0). Format: plain **2-col ASCII**
(`&format=ascii`), **vacuum** λ over 3200–25000 Å, EUV-heavy (we resample only the
optical window + convert vac→air to match the cube). License: GAVO/SVO
acknowledge-and-cite (Werner+ 2003; Rauch+ 2013). Splices as the **hot slab** of the
*same separate WD cube* as Koester, above Koester's 80000 K ceiling. Build details +
two **measured corrections to this scoping** in **§8b**; the headlines:
- **No ×π×10⁸ unit conversion** (the scoping guess was wrong for *this* path). The
  ×4×10⁸ "astrophysical flux" gotcha is for the **native TheoSSA** files; the **SVO
  ascii path already serves physical erg/cm²/s/Å** — measured: the TMAP/Koester
  optical ratio at the 80000 K / log g 7 overlap is **0.98–1.08**. So the **LTE↔NLTE
  seam is already graceful** (better than OSTAR/CAP18's 0.97–0.99) → splice with **no
  rescale**, just report the agreement (the OSTAR precedent). Confirm from one real
  header before trusting a unit factor.
- **Naming trap:** the brief's "Reindl 2020 pure-H grid" is actually **Bohlin, Hubeny
  & Rauch 2020** and its clean MAST tarball is the **TLUSTY** twin (caps at 95 kK),
  **not** TMAP — don't plan the TMAP ingest around it.
[tmap](https://svo2.cab.inta-csic.es/theory/newov2/index.php?models=tmap)

**PoWR Wolf-Rayet (WN/WC) — ✅ BUILT (Chunk 7, narrow-GO; §9). Was "CONDITIONAL GO at best".**
Spectra download cleanly: **public, no registration**, bulk per-grid tarballs at
[~htodt/powr-sed/](https://www.astro.physik.uni-potsdam.de/~htodt/powr-sed/) (12 grids
WNE/WNL/WNL-H50/WC × Galactic/LMC/SMC/sub-SMC, 61–129 MB each; each model a
`flux_calib.dat` = 2-col ASCII, 200–80000 Å, R≈10⁴). License: cite the paper (Hamann &
Gräfener 2004; Sander+ 2012 WC; Todt+ 2015 WN). **But the axis is the crux:** grids are
**2-D in (T\*, transformed radius Rt)** at *fixed* L (log L=5.3), v∞, clumping D, and
composition (one grid per subtype×metallicity), where
`Rt = R*·[(v∞/2500) / (Ṁ√D/1e-4)]^(2/3)`. **Placing a track star needs THREE things the
track does not supply:** (a) v∞ must be *assumed* (∝ v_esc, constant is a choice), (b)
clumping D *assumed* (adopt the grid's), (c) Teff↔T\* is approximate (grid T\* at τ=20 vs
track Teff at τ=2/3, diverge in thick winds). The track **L is NOT discarded** — it sets
R\* (L=4πR\*²σT\*⁴) → Rt, and scales the absolute flux. So PoWR cannot share the (Teff,
[Fe/H], log g) cube; it needs its **own (T\*, Rt) cube + subtype×metallicity selector**,
with the star **snapped/assumption-mapped** on — exactly the separate-WR-panel the plan
already sketches. ~50–100 LOC + a ragged-grid void-fill + an opacity-edge band to mask.
([Todt+ 2015, A&A 579 A75](https://www.aanda.org/articles/aa/pdf/2015/07/aa26253-15.pdf) ·
[PoWR tarballs](https://www.astro.physik.uni-potsdam.de/~htodt/powr-sed/) — SVO has **no**
WR collection. *Aside:* PoWR's **OB** grids ARE Teff×log g and would slot onto the main
cube — but they're MS hot stars, not the WR endgame.)

### Chunk 7a — PoWR locus check (MEASURED, the go/no-go gate) — narrow-GO at best

Before baking, we did the discriminating measurement (advisor-gated, the same "measure
first" discipline as the TMAP units / WD radius pop): fetch **one** grid (Galactic WNE,
`wnegrid.200-80000_2016.tgz`, 129 MB) and overlay the **real MIST WR locus** on its
footprint. Findings, all measured:

- **Grid format confirmed.** Tarball = one dir per model `wnegrid.200-80000/<T*idx>-<Rtidx>/`
  with `flux_calib.dat` (2-col ASCII: λ Å [air], F_λ erg/cm²/s/Å **at 10 pc**, 200–80000 Å,
  ~59.8k pts, all normalized to **log L=5.3**) + `flux.pdf`. **No per-model parameter table**
  (not in the tarball, not in the flux.pdf text, and the PoWR website is JS-gated — unscrapeable).
  Footprint = the classic PoWR parallelogram: T* idx 03–18 (+sparse 19/20, +one 00-80), Rt idx
  04–21. **Fixed grid params (from Hamann+ 2006, astro-ph/0608078):** WNE v∞ **1600 km/s**
  (WNL 1000), **D=4**, v_D=100 km/s. **Convention (anchored, not scraped):** `log(Rt/R☉)=Rtidx/10`
  (idx 04 = 0.4 = the paper's **degeneracy floor** `log Rt<0.4` where the spectrum depends only
  on Rt·T*²), `log(T*/K)≈4.30+0.05·T*idx` (idx 03–18 ⇒ 28–158 kK, the known WNE grid range).
  An empirical T*-from-IR-RJ calibration **fails** — the IR is wind-free-free-dominated, not a
  stellar BB tail (the WR inverse problem PoWR exists to solve; don't try to invert the SED).
- **Mapping decided (advisor reversed to agree): MIST Teff → grid T\* DIRECTLY**, NOT Teff→T_2/3.
  MIST's stripped-WR Teff (150–262 kK) is the hot, compact **evolutionary/hydrostatic** surface
  ≈ PoWR's deep **T\*** (MIST has no optically-thick wind) — the well-known evolutionary-vs-
  spectroscopic Teff split (Groh/Meynet). So both grid coordinates come free, no T_2/3 round-trip:
  **T\*≈MIST Teff**, **Rt from Nugis & Lamers (2000)** Ṁ(L,Y,Z) `log Ṁ=−11.00+1.29logL+1.73logY+0.47logZ`
  with the grid's own v∞/D — PoWR returns the cooler emergent spectrum for free. (Option (b);
  star_mdot stays OFF StellarState — N&L drove the locus cleanly.)
- **THE GATE RESULT (6 stars × 21 samples = 126 points, 60/100/300 M☉ × [Fe/H] 0/−1):**
  **only 9% land IN-grid** (the cool **WNh hydrogen-rich entry**, Teff 30–60 kK, log Rt 1.0–1.3);
  **39% fall below the dense-wind Rt floor** (the grid has NO hot+dense-wind models — they sit in
  the degeneracy region and were never computed); **52% exceed the T\* ceiling** (~158–200 kK;
  MIST's bare cores reach 250+ kK). The iconic **stripped WN→WC→WO bulk is off the map of every
  PoWR atmosphere** — because MIST's evolutionary T* is far hotter/more compact than the *observed*
  WR (T* 50–140 kK) PoWR was tuned to. This is **real physics surfaced, not a bug to engineer
  around.** Verdict: **narrow-GO** — a real PoWR emission spectrum is honest ONLY for the WNh/early
  entry; the stripped tail must show the honest "no model" frame (hotter/more compact than any WR
  atmosphere grid). Scripts: scratchpad `wr_locus.py` / `wr_overlay.py` (re-run vs the provider if
  grids change).

**Top risks:** (1) **PoWR wind-axis mapping (HIGH)** — no track-only placement; v∞/D
assumed, Teff↔T\* approximate; the star is *snapped with assumptions*, accept honestly
or WR is a no-go. (2) **TMAP bulk = SVO-only (MED)** — validate the SVO node coverage at
log g 7–9 before committing (TheoSSA on-demand is no polite bulk fallback). (3) **The WD
cube is disjoint** from the existing cube (separate cube + endgame branch, not a Teff
splice — a design choice, not a blocker). (4) **unit/λ gotchas (LOW)** — TMAP ×π×10⁸,
air-vs-vacuum per grid, PoWR opacity-edge mask — confirm from one real header each.

## 8. Building the WD cube (Chunk 6a Koester DA + 6b TMAP CSPN — BOTH BUILT)

Chunk 6's **Koester DA half (6a)** and **TMAP hot-WD/CSPN half (6b)** are both done.
Unlike the main cube, neither needs **Docker / pymsg / Fortran** — both grids are
plain 2-col ASCII, so the whole vertical runs on the **host** with numpy/scipy only.
Three commands (drop the TMAP two for the 6a-only cube):

```bash
# (host, from backend/) one-time fetch of ~1066 Koester DA models into
# data/spectra/grids/koester/ (skip-existing, retrying, 6-way parallel; ~tens of MB)
python -m star_sim.fetch_koester
# 6b: ~72 TMAP H-rich hot-slab models (Teff 80–190 kK x log g 6.5–9.0) -> grids/tmap/
python -m star_sim.fetch_tmap
# bake them into ONE separate (Teff, log g) cube -> data/spectra/wd_spectra_grid.npz
python scripts/bake_wd_spectra.py --tmap-dir data/spectra/grids/tmap
```

Then the runtime (`star_sim/spectra.py` `wd_spectrum_data`) serves `/wd_spectrum`, a
**second** spectrum sibling beside `/spectrum`; `pytest backend/tests/test_wd_spectra.py`
gates it (`requires_wd_spectra_data` marker skips the data-gated half if the cube is
absent). The frontend switches the panel to the WD cube by surface gravity —
`refreshWD` calls `spectrum.updateWD` when **log g ≥ 6.0**, else the normal
`spectrum.update` (so the TPAGB-giant rows at the start of the WD scrub show their
*real* giant spectrum from the main cube, closing the Chunk-2 "known polish" gap).

**Verified facts (confirm from a real header / measured through the runtime — do not
re-derive from assumptions):**

- **Koester grid is rectangular, no voids:** **82 Teff nodes (5000–80000 K) × 13 log g
  nodes (6.5–9.5 in 0.25 steps) = 1066 models.** The bake **asserts** rectangularity and
  does **no void-fill** (unlike the MSG cubes — every cube entry is a real Koester model).
- **Pure hydrogen → no [Fe/H] axis.** `feh_varies` is always `false`; the panel says
  "Pure hydrogen, so [Fe/H] doesn't apply" rather than "solar."
- **Air wavelengths** (like the main cube), confirmed: the DA Balmer minima land within
  0.05 Å of the air line positions, so the panel's x-axis and line guides line up exactly
  when it switches cubes. Baked onto the **same 3000–9000 Å @ 2.5 Å** bin grid.
- **DC honesty edge (below the ~5000 K Koester floor):** a real cooling DA loses its
  Balmer lines (measured Hα depth ~9% at 5000 K vs ~61% at 13 kK), so below the floor the
  runtime returns an **honest Planck blackbody continuum** at the *requested* Teff (tagged
  `regime="DC"`, `teff` NOT clamped), never the 5000 K line-bearing spectrum painted onto
  a cold cinder. Same "don't label a non-feature" discipline as VO-7400 / invisible-Na.
- **80000 K = the Koester ceiling, now the Koester↔TMAP splice seam (no longer the
  no-model edge).** Above it, the TMAP NLTE slab (6b, §8b) carries the ~100–190 kK
  central star; the residual `teffAboveGrid()` no-model frame is re-pointed at TMAP's
  **190000 K** ceiling (only the most massive progenitors' ~300–400 kK central stars).
- **`BAKE_VERSION` is coupled across THREE files**, all must match or the runtime
  rejects the cube: `star_sim/spectra.py`, `scripts/bake_spectra.py`, **and**
  `scripts/bake_wd_spectra.py` (the WD cube uses the same axis-generic `.npz` schema and is
  read by the same `_Spectra` class, so it shares the version). Bump all three together.
  **6b did NOT bump it** — the splice only lengthens the Teff axis + changes `grid_name`
  (the OSTAR/Göttingen precedent); bumping would needlessly invalidate the MAIN cube and
  force a Docker re-bake.

The cube is gitignored (`data/spectra/wd_spectra_grid.npz`, like every other baked grid),
so these commands are the only reproducibility path — re-run after a `BAKE_VERSION` bump.

## 8b. Adding the TMAP hot-WD/CSPN splice (Chunk 6b — BUILT)

The WD cooling scrub passes through a ~100–400 kK **post-AGB central star** (the hot star
of a planetary nebula). 6a clipped that to the honest "no model" frame above 80000 K; 6b
fills it by splicing **TMAP** (NLTE H+He) onto the hot end of the *same* WD cube — the
mirror of the main cube's OSTAR hot-splice. `star_sim/fetch_tmap.py` fetches the H-rich
slab; `scripts/bake_wd_spectra.py --tmap-dir …` splices it on. The result is a **93 Teff
(5000–190000 K) × 13 log g (6.5–9.5) × 2400 λ** cube (~10 MB; Koester-only was 82×13).

**Verified facts (measured this build — confirm from a real header / through the runtime,
do not re-derive from the §7 scoping, which two of these correct):**

- **Grid:** SVO `tmap` H-rich (Hemass=0) slab is **rectangular at log g ≥ 6.0** — 15 Teff
  (50–190 kK) × 9 log g (5–9). We fetch the **hot, WD-gravity** subset (Teff ≥ 80000, log g
  6.5–9.0 = 72 models, ~125 MB ascii) and splice the nodes **above** 80000 K.
- **No ×π×10⁸.** The SVO ascii path serves physical erg/cm²/s/Å directly (the gotcha is for
  native TheoSSA). **Measured seam @ 80000 K: TMAP/Koester optical-mean ratio 1.005–1.021
  (mean 1.012)** across the 6 shared log g nodes → spliced **as-is, no rescale**; the bake
  prints this (`_report_seam`) as the OSTAR-style validation.
- **Vacuum→air** (Morton 2000) is applied to TMAP (it serves vacuum; the cube is air), so
  the Balmer guides line up across the cube switch. The ~1.4 Å optical shift is sub-bin —
  hot CSPN optical spectra are nearly featureless continuum — but converted for correctness.
- **The 3000–3200 Å blue gap** (TMAP starts at 3200; the window at 3000) is filled by a
  **log-linear (power-law) extrapolation** of the model's bluest 300 Å, NOT a flat fill —
  the gap sits on the steep blue Rayleigh-Jeans rise (flux ∝ λ^p, p ≈ −4), so a flat fill
  would shelf the blue edge. Measured: flux(3000)/flux(3200) ≈ 1.24 (RJ would give 1.29).
- **The log g axis stays Koester's 6.5–9.5; low-gravity central stars clamp up to 6.5.**
  Honest because the **optical is log g-insensitive at CSPN temperatures** — measured:
  100 kK at log g 6.5 vs 9.5 differs by **max 0.03** (normalized), vs **0.41** for a 13 kK
  cooling DA (Balmer-profile broadening). So the clamp on the lowest-gravity rows (log g
  ~5.4 for massive progenitors) is invisible. (The alternative — extending the axis to 5.0
  — would reintroduce the void-fill the 6a cube deliberately avoids.)
- **regime = "CSPN"** (hot central star, not a cooling DA), **log g-aware**: above 80000 K, OR
  on the contracting rise (`used_teff > 55000` — the MAIN cube's ceiling — AND the *raw* log g
  < 6.5, i.e. not yet degenerate). A hot but high-gravity remnant (a young cooling DA at 70 kK,
  log g 8) stays "DA". The panel draws Balmer guides (weak — H mostly ionized) on a steep blue
  continuum. Below ~5000 K, "DC" (unchanged). `feh_varies` stays false (pure H throughout).
- **Frontend routing (`refreshWD`): `log g ≥ 6.0 OR Teff > 55000`** — **55000 K is the MAIN
  cube's real ceiling (OSTAR)**, NOT 80000. Above it ONLY the WD cube can serve a spectrum, so
  the contracting rise (55–80 kK at log g ~5–6, Koester) through the central star (TMAP) routes
  here *continuously*. (At the nominal 80000 a ~74 kK / log g 5.6 rise row flashed "no model" —
  one row per mass, sandwiched between the giant and CSPN spectra. Route on a cube's MEASURED
  give-up point, not its sibling boundary.) 55–80 kK is also log g-insensitive (Δ 0.024–0.030),
  so the clamp is honest there too.
- **`/wd_spectrum` Query `teff` bound widened to 500000** — massive progenitors' central
  stars peak ~400 kK; without this they'd 422 instead of showing the residual no-model frame.

## 9. Building the WR cube (Chunk 7 — PoWR, narrow-GO — BUILT)

The WR-endgame wind-emission spectrum. Like the WD cube it needs **no pymsg/Docker** (PoWR
is plain 2-col ASCII), but it is structurally different from every other cube — see §7a for
WHY (the measured narrow-GO gate) and the headlines below. Two commands:

```bash
# (host, from backend/) download + extract the PoWR grid tarballs into
# data/spectra/grids/powr/<tag>/  (Galactic WNE/WNL/WC by default; add LMC/SMC:)
python -m star_sim.fetch_powr                 # MVP: Galactic only
python -m star_sim.fetch_powr --grids all      # + LMC/SMC metallicity grids
# bake them into ONE flat-node WR cube -> data/spectra/wr_spectra_grid.npz
python scripts/bake_wr_spectra.py
```

Then the runtime (`star_sim/spectra.py` `wr_spectrum_data`) serves `/wr_spectrum`, the THIRD
spectrum sibling; `pytest backend/tests/test_wr_spectra.py` gates it (`requires_wr_spectra_data`
skips the data-gated half if the cube is absent). The frontend (`spectrum.js` `updateWR`,
wired in `main.js` `refreshWR`) draws the emission spectrum or the off-grid no-model frame.

**Verified facts (confirm from a real file / measured through the runtime — do not re-derive):**

- **Tarball = one dir per model `<T*idx>-<Rtidx>/flux_calib.dat`** (2-col ASCII: λ Å,
  F_λ erg/cm²/s/Å at 10 pc, 200–80000 Å, all log L=5.3). **No parameter file ships** — the bake
  derives node coords from the convention `log T* = 4.30 + 0.05·T*idx`, `log Rt = Rt_idx/10`
  (recipe §7a). Fixed per grid: WNE v∞=1600, WNL v∞=1000, WC v∞=2000 (km/s), D=4.
- **Flat-node cube, NOT a rectangular RGI cube + void-fill.** PoWR's footprint is a ragged
  (T*, Rt) parallelogram with an empty hot+dense-wind corner; void-filling it would invent
  spectra PoWR never computed. So `wr_spectra_grid.npz` stores, per grid, the flat node
  `(log T*, log Rt)` arrays + spectra, and the runtime **snaps to the nearest node** (the
  endgame snap-to-track discipline) — `regime="none"` when the nearest node is too far / the
  star is hotter than any node (the stripped bulk, §7a).
- **Mapping (no T_2/3 round-trip):** T\* ≈ MIST Teff (the evolutionary surface ≈ PoWR's deep
  T*, §7a), Rt from the star's L + a **Nugis & Lamers (2000)** Ṁ(L,Y,Z) with the grid's fixed
  v∞/D. Subtype (WNE/WNL/WC) from surface composition; metallicity grid snapped from [Fe/H].
- **Emission, continuum-normalized.** `wr_spectrum_data` divides by a per-chunk low-percentile
  continuum (≈1) so lines stand UP, and returns a `display_max` y-cap so one He II 4686 line
  can't squash the panel under per-max normalization (the advisor's gate). Vacuum→air applied
  (PoWR is vacuum; WR lines are 1000s km/s broad so the ~1.4 Å shift is sub-resolution, but
  converted for guide alignment).
- **`BAKE_VERSION` coupled across FOUR files now** (`spectra.py`, `bake_spectra.py`,
  `bake_wd_spectra.py`, **`bake_wr_spectra.py`**) — though the WR cube has its OWN flat-node
  schema (read by `_WRSpectra`, not the axis-generic `_Spectra`), it shares the version
  discipline; bump in lockstep.
- **Galactic is the MVP slice; LMC/SMC widen the [Fe/H] axis as a pure data re-bake** (the
  CAP18 precedent — `fetch_powr --grids all` then re-bake, no code change). One filename trap:
  the LMC WC tarball is `lmc-wcgrid.200-80000.tgz` (no `_2016`); the fetcher is resilient (a
  404 on one grid skips it, the batch continues).
