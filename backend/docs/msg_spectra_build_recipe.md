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

## 5. For the real bake: the grid

`sg-demo.h5` proves the pipeline but is **solar-only** (no `[Fe/H]` axis). For the
`(Teff, log g, [Fe/H])` bake, fetch a `[Fe/H]`-varying grid from the
[MSG grid-files page](http://user.astro.wisc.edu/~townsend/static.php?ref=msg-grids)
— **CAP18** (Allende Prieto 2018) reaches ~50000 K and varies metallicity. Grids
are large HDF5 downloads, gitignored like `data/mist` and `data/mesa`.
