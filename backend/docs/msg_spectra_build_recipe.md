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

## 6. Running the bake (`scripts/bake_spectra.py` → `data/spectra/spectra_grid.npz`)

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
# (host) copy the script + BOTH grids into the reusable build container
docker cp backend/scripts/bake_spectra.py msg_spike:/tmp/bake_spectra.py
docker cp data/spectra/grids/sg-CAP18-coarse.h5 msg_spike:/tmp/sg-CAP18-coarse.h5
docker cp data/spectra/grids/sg-OSTAR2002-low.h5 msg_spike:/tmp/sg-OSTAR2002-low.h5

# (container) bake CAP18 + the OSTAR2002 hot-end splice — set the MSG runtime env first
docker exec msg_spike bash -c '
  source /opt/conda/etc/profile.d/conda.sh && conda activate base
  export MSG_DIR=/tmp/msg-2.2 MESASDK_ROOT="$CONDA_PREFIX"
  export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$MSG_DIR/lib"
  python /tmp/bake_spectra.py \
    --grid     /tmp/sg-CAP18-coarse.h5 \
    --hot-grid /tmp/sg-OSTAR2002-low.h5 \
    --out      /tmp/spectra_grid.npz'
# (drop --hot-grid for a CAP18-only cube; --grid /tmp/msg-2.2/data/grids/sg-demo.h5
#  for the original solar MVP)

# (host) copy the cube out to where the runtime looks for it
docker cp msg_spike:/tmp/spectra_grid.npz data/spectra/spectra_grid.npz
```

The CAP18+OSTAR2002 bake is a `(123 Teff × 12 [Fe/H] × 11 log g × 2400 λ)` cube,
**~76 MB** (CAP18-only was `96 × 12 × 11 × 2400`, ~69 MB; the solar `sg-demo` bake was
a 2-D `96 × 11 × 2400`, ~4.7 MB):

- **Teff** 3500–**55000 K**, **log-spaced**: 96 nodes over CAP18's 3500–30000 (cool-end
  resolution where lines change fast), then 27 more *appended* at the same log-step up to
  OSTAR2002's 55000 (the cool nodes are NOT re-spread). The runtime interpolates in
  `log10(Teff)` via the `axis_log` flag. Nodes >30000 K are sampled from OSTAR2002.
- **[Fe/H]** −5…+0.5 in 0.5 steps (12 nodes; grid-driven — real stars only reach
  ~−0.85…+0.5, the rest just clamp).
- **log g** 0–5 in 0.5 steps.
- **λ** 3000–9000 Å in 2.5 Å bins (bin *centres* stored).
- **Voids** (hot + low-gravity corners with no model → `LookupError`, **45%** of
  nodes for the spliced cube — CAP18's high-log g block plus OSTAR's low-gravity
  block) are filled in three passes, each preserving Teff as far as possible:
  **(1) along log g** at fixed Teff *and* [Fe/H] (the voids are contiguous log g
  blocks, so this preserves the dominant Teff/[Fe/H] variation exactly); **(2)
  same-Teff** nearest valid, for a whole log g line that was *entirely* void (the
  metal-poor + intermediate-hot OSTAR corner) — clamps metallicity but keeps the
  temperature exact; **(3) global fallback** (can cross Teff — a last resort,
  logged). On the CAP18+OSTAR bake: **6390 along log g, 990 same-Teff, 0 fallback**
  — i.e. no void anywhere got a wrong-Teff spectrum. The stored cube is fully
  regular for `RegularGridInterpolator`. (The bake also clamps **8840** negative-flux
  bins — cubic spline undershoot in deep CAP18 line cores — to 0; min was −2.19e4;
  unchanged by the splice, as OSTAR added 0 negative bins. Still only ~0.02% of bins,
  and the reachable cool/metal-rich corner gives sane depths, NOT cores pinned to
  black: Na D 0.48, Ca K 0.85 at [Fe/H]=+0.5 — a resolution artefact, not a broken cube.)
- Knobs: `--grid`, `--hot-grid` (the OSTAR splice), `--n-teff`,
  `--lam-min/--lam-max/--lam-step`, `--out`.
- `BAKE_VERSION` must match `star_sim/spectra.py`'s; the runtime rejects a stale
  cube (re-bake to fix). Neither the CAP18 swap nor the OSTAR splice bumped it — the
  on-disk schema is axis-generic and unchanged; only the Teff axis length +
  `grid_name` differ.

Then the pure-Python runtime (`star_sim/spectra.py`, `scipy` only — no pymsg)
serves `/spectrum`; `pytest backend/tests/test_spectra.py` gates the line physics
(measured through the runtime path), and the `requires_spectra_data` marker skips
those if the cube is absent.
