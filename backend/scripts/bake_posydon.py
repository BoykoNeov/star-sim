"""Build-time bake of a POSYDON co-evolved-binary grid — path (b) Chunk 4a.

Reads an extracted POSYDON HMS-HMS grid HDF5 (`fetch_posydon.py`'s validator found it
already organized **per run** — `grid/run<i>/{binary_history,history1,history2}` — NOT
POSYDON's packed `PSyGrid` format the plan worried about. So no host-side POSYDON-loader
demux is needed: this bake reads the raw grid file directly with plain h5py.

Still a bake, not a live read (advisor-settled): the raw file is ~4.8 GB and carries ~500
history columns this app never needs, so we follow the `bake_*.py` precedent (spectra/WD/
WR/stripped) — trim to the ~15 columns per star a `StellarState` needs, filter to usable
runs, decimate very long tracks, and write one compact `.npz` the runtime (`posydon.py`)
reads with zero h5py / POSYDON dependency (the same host-vs-runtime split as
`bake_wr_spectra.py`).

Filtering (measured on the solar HMS-HMS grid, 39712 runs):
  * drop `interpolation_class == "not_converged"` (762 runs, ~2% — numerically unreliable)
  * drop runs with no `binary_history` group (a run that failed before any output)
  * drop runs where `binary_history`/`history1`/`history2` row counts disagree (row
    alignment is POSITIONAL — history1/2 carry no age/model_number of their own, so a
    length mismatch would silently misalign the two stars against the orbit)

Two honest gaps in this grid vs the plan's schema guess (verified against the real
columns, not assumed — the boron-b8 discipline):
  * **No eccentricity column** — HMS-HMS binaries are tidally circularized, so
    `binary_history` simply has none. The runtime reports ecc=0.0, not a fabricated field.
  * **Composition is C/N/O only** (`surface_c12/n14/o16`, `center_c12/n14/o16`) — a
    partial `metals_surf`/`metals_core` dict, never the MIST 16-metal breakdown.

Run once per metallicity, after `fetch_posydon.py`'s recipe has landed + extracted the
grid (see that module's docstring):

    python -m star_sim.fetch_posydon                 # confirms the schema
    python scripts/bake_posydon.py --z-label 1Zsun    # -> data/posydon/baked/1Zsun.npz

--- CO-HMS_RLO (path (b) Phase 1 Chunk 1a, docs/plans/tempered-lineage-inspiral.md) ---

A second grid type, `CO-HMS_RLO`, ships in the same per-metallicity tarball: a compact
object (NS/BH/WD, left by an earlier primary's collapse) orbiting a still hydrogen-rich
secondary. Schema recon (2026-07-08, measured against the real extracted solar HDF5, not
assumed) found this is NOT a drop-in for the HMS-HMS bake above:

  * `history2` (the compact-object side's stellar-structure history) is **absent in all
    9069 sampled runs, unconditionally** — not a stub, not NaN-filled, the HDF5 key
    genuinely doesn't exist. `S1` is always the normal star (real `history1`), `S2` is
    always the compact object (`final_values.S2_state` in {"BH","NS","WD","None"}).
  * No `eccentricity` column here either (same circularization-at-RLO-onset story as
    HMS-HMS) — `ecc=0.0` stays a documented sentinel, not a fabricated field.
  * The CO's mass is a real per-row column (`binary_history.star_2_mass`) that GROWS via
    accretion (measured: 4.19->4.99 Msun over one stable_MT run) — a genuine accretion
    phase, not a placeholder. `binary_history.lg_mstar_dot_2` is the CO's own accretion
    rate (more direct than `lg_mtransfer_rate`, which is the donor's transfer rate before
    any `xfer_fraction` loss), feeding the accretion-luminosity cue.
  * `rl_relative_overflow_2` is always <=0 across sampled runs (the point-mass CO cannot
    itself overflow a Roche lobe) — `mt_state` on this grid is effectively only
    "detached"/"RLOF1", never "RLOF2"/"contact".

Extraction (same tarball, a different internal path — do NOT extract into the HMS-HMS
grid's own directory, `bake()`'s `main()` picks `glob("*.h5")[0]` and would silently grab
whichever sorts first):

    mkdir -p data/posydon/CO-HMS_RLO_<Zlabel>
    tar -C data/posydon/CO-HMS_RLO_<Zlabel> --wildcards --strip-components=2 \\
        -xzvf data/posydon/POSYDON_data_v2_grids_<Zlabel>.tar.gz '*/CO-HMS_RLO/*.h5'
    python scripts/bake_posydon.py --grid-type co-hms-rlo --z-label 1Zsun --feh 0.0
        # -> data/posydon/baked_co/1Zsun_co_hms_rlo.npz
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# Bump alongside any change to the column set / filter / decimation logic below, so a
# stale npz baked by an older version of this script is rejected by the runtime (the
# MIST _parsed_tracks.npz CACHE_VERSION precedent).
# v2: _decimate force-keeps RLOF/contact rows (a uniform stride could otherwise straddle
# a short RLOF episode entirely on a >300-row track — measured 1/251 capped tracks).
BAKE_VERSION = 2

# Bump alongside any change to the CO bake's column set / filter / decimation logic —
# the sibling of BAKE_VERSION above, kept separate since the two bakes' output shapes
# are genuinely different (one star + a compact-object scalar block, not two stars).
BAKE_VERSION_CO = 1

_REPO_ROOT = Path(__file__).resolve().parents[2]
POSYDON_DATA_DIR = _REPO_ROOT / "data" / "posydon"
OUT_DIR = POSYDON_DATA_DIR / "baked"
OUT_DIR_CO = POSYDON_DATA_DIR / "baked_co"

# POSYDON's own solar reference metallicity (Zbase in the grid file paths, e.g.
# "Zbase_0.0142_m1_..."), matching the sim's [Fe/H] = log10(Z / Z_sun) convention.
POSYDON_SOLAR_Z = 0.0142

# The per-star history columns a StellarState (+ a little extra for future compact-object
# work) needs. Kept lean on purpose — trimming ~54 raw columns to these is the whole point
# of baking rather than reading the 4.8 GB file live.
_HISTORY_COLS = [
    "log_L", "log_Teff", "log_R",
    "surface_h1", "surface_he4", "surface_c12", "surface_n14", "surface_o16",
    "center_h1", "center_he4", "center_c12", "center_n14", "center_o16",
    "he_core_mass", "co_core_mass",
]

_BINARY_COLS = [
    "age", "star_1_mass", "star_2_mass", "period_days", "binary_separation",
    "lg_mtransfer_rate", "rl_relative_overflow_1", "rl_relative_overflow_2",
]

# A track longer than this is decimated to a uniform stride down to roughly this many
# rows (keeping the first and last row always) — most tracks are far shorter (median ~31
# rows on the solar grid; only a handful reach several hundred), so this mainly guards
# against a pathological long run bloating the bake, not the common case.
_MAX_ROWS_PER_TRACK = 300

# CO-HMS_RLO: only ONE stellar history (the normal star, always history1 per the recon
# above) + the compact object's own accretion rate (lg_mstar_dot_2, more direct than the
# donor-side lg_mtransfer_rate for the accretion-luminosity cue).
_CO_BINARY_COLS = [
    "age", "star_1_mass", "star_2_mass", "period_days", "binary_separation",
    "lg_mtransfer_rate", "lg_mstar_dot_2",
    "rl_relative_overflow_1", "rl_relative_overflow_2",
]


def _decimate(n: int, cap: int, must_keep: np.ndarray | None = None) -> np.ndarray:
    """Row indices to keep for a track of `n` rows, capped at ~`cap` (always keeps row 0
    and row n-1) via a uniform stride. Identity (all rows) when n <= cap.

    `must_keep` (row indices where RLOF/contact is firing) is unioned in on top of the
    stride — a uniform decimation of a >300-row track can otherwise straddle a short
    RLOF episode entirely (measured: 1/251 capped tracks on the solar grid), leaving
    `outcome="stripped + companion"` with no surviving row where the transfer actually
    shows. This can push the kept count slightly over `cap`; that's fine — the cap is a
    size guard, not a hard contract."""
    if n <= cap:
        return np.arange(n)
    idx = np.linspace(0, n - 1, cap).round().astype(np.int64)
    if must_keep is not None and must_keep.size:
        idx = np.concatenate([idx, must_keep])
    return np.unique(idx)


def bake(h5_path: Path, out_path: Path, *, feh: float) -> None:
    import h5py

    t0 = time.time()
    f = h5py.File(h5_path, "r")
    grid = f["grid"]
    iv = grid["initial_values"]
    fv = grid["final_values"]
    n_runs = iv.shape[0]

    ic_all = fv["interpolation_class"][:].astype(str)
    s1_all = fv["S1_state"][:].astype(str)
    s2_all = fv["S2_state"][:].astype(str)
    mth_all = fv["mt_history"][:].astype(str)
    # Bulk-read the initial-value axes once (not per-run field indexing, which would be
    # ~120k individual small HDF5 reads across the full grid).
    iv_m1 = iv["star_1_mass"][:]
    iv_m2 = iv["star_2_mass"][:]
    iv_p = iv["period_days"][:]

    track_m1: list[float] = []
    track_q: list[float] = []
    track_p: list[float] = []
    track_row_start: list[int] = []
    track_row_count: list[int] = []
    track_ic: list[str] = []
    track_s1: list[str] = []
    track_s2: list[str] = []
    track_mth: list[str] = []

    row_cols: dict[str, list[float]] = {c: [] for c in _BINARY_COLS}
    for c in _HISTORY_COLS:
        row_cols[f"s1_{c}"] = []
        row_cols[f"s2_{c}"] = []

    n_dropped_not_converged = 0
    n_dropped_missing = 0
    n_dropped_mismatch = 0
    n_kept = 0
    row_offset = 0

    for i in range(n_runs):
        if ic_all[i] == "not_converged":
            n_dropped_not_converged += 1
            continue
        run = grid[f"run{i}"]
        if not ({"binary_history", "history1", "history2"} <= set(run.keys())):
            n_dropped_missing += 1
            continue
        # One bulk read per group (a structured record array), not one read per column —
        # 39712 runs x 38 columns of individual HDF5 reads would dominate the bake time.
        bh_rec = run["binary_history"][:]
        h1_rec = run["history1"][:]
        h2_rec = run["history2"][:]
        n = bh_rec.shape[0]
        if not (h1_rec.shape[0] == n and h2_rec.shape[0] == n) or n == 0:
            n_dropped_mismatch += 1
            continue

        # Index-identity check (advisor-flagged): run{i}'s FIRST row should match
        # initial_values[i]'s masses/period — confirms run<->initial_values correspondence
        # rather than assuming it. A mismatch drops the run rather than silently mis-tagging
        # its grid axes.
        if (abs(bh_rec["star_1_mass"][0] - iv_m1[i]) > 1e-3 * max(1.0, iv_m1[i])
                or abs(bh_rec["star_2_mass"][0] - iv_m2[i]) > 1e-3 * max(1.0, iv_m2[i])
                or abs(bh_rec["period_days"][0] - iv_p[i]) > 1e-3 * max(1.0, iv_p[i])):
            n_dropped_mismatch += 1
            continue

        rlof_rows = np.where((bh_rec["rl_relative_overflow_1"] > 0)
                              | (bh_rec["rl_relative_overflow_2"] > 0))[0]
        keep = _decimate(n, _MAX_ROWS_PER_TRACK, must_keep=rlof_rows)

        for c in _BINARY_COLS:
            row_cols[c].append(bh_rec[c][keep])
        for c in _HISTORY_COLS:
            row_cols[f"s1_{c}"].append(h1_rec[c][keep])
            row_cols[f"s2_{c}"].append(h2_rec[c][keep])

        m = keep.size
        track_m1.append(float(iv_m1[i]))
        track_q.append(float(iv_m2[i]) / float(iv_m1[i]))
        track_p.append(float(iv_p[i]))
        track_row_start.append(row_offset)
        track_row_count.append(m)
        track_ic.append(ic_all[i])
        track_s1.append(s1_all[i])
        track_s2.append(s2_all[i])
        track_mth.append(mth_all[i])
        row_offset += m
        n_kept += 1

        if n_kept % 5000 == 0:
            print(f"  ...{n_kept} tracks kept ({i + 1}/{n_runs} scanned, "
                  f"{time.time() - t0:.0f}s)")

    f.close()

    print(f"scanned {n_runs} runs: kept {n_kept}, dropped "
          f"{n_dropped_not_converged} not_converged, {n_dropped_missing} missing-history, "
          f"{n_dropped_mismatch} row-mismatch/index-mismatch  ({time.time() - t0:.0f}s)")
    if n_kept == 0:
        raise SystemExit(f"no usable tracks found in {h5_path}")

    data: dict[str, np.ndarray] = {
        "bake_version": np.array(BAKE_VERSION),
        "feh": np.array(feh),
        "z_base": np.array(POSYDON_SOLAR_Z * 10.0 ** feh),
        "track_m1_init": np.asarray(track_m1, dtype=np.float64),
        "track_q_init": np.asarray(track_q, dtype=np.float64),
        "track_p_init_d": np.asarray(track_p, dtype=np.float64),
        "track_row_start": np.asarray(track_row_start, dtype=np.int64),
        "track_row_count": np.asarray(track_row_count, dtype=np.int64),
        "track_interpolation_class": np.asarray(track_ic),
        "track_s1_state": np.asarray(track_s1),
        "track_s2_state": np.asarray(track_s2),
        "track_mt_history": np.asarray(track_mth),
    }
    for c, vals in row_cols.items():
        data[f"row_{c}"] = np.concatenate(vals).astype(np.float32)

    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    total_rows = row_offset
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  {n_kept} tracks, {total_rows} rows total "
          f"({time.time() - t0:.0f}s)")


def bake_co(h5_path: Path, out_path: Path, *, feh: float) -> None:
    """CO-HMS_RLO variant of `bake()` above — one real stellar history (always
    `history1`, per the schema recon) + the compact-object's mass/accretion time series
    from `binary_history`, never a second `StellarState`. Reuses the same `_decimate`/
    RLOF-keep/index-identity-check logic; the only structural difference is dropping every
    `history2` read (it never exists on this grid) and swapping the track axes from
    (M1, q, P) to (M_star, M_co_init, P) — a compact-object mass is a real physical value,
    not a mass ratio."""
    import h5py

    t0 = time.time()
    f = h5py.File(h5_path, "r")
    grid = f["grid"]
    iv = grid["initial_values"]
    fv = grid["final_values"]
    n_runs = iv.shape[0]

    ic_all = fv["interpolation_class"][:].astype(str)
    s1_all = fv["S1_state"][:].astype(str)
    s2_all = fv["S2_state"][:].astype(str)          # the compact-object TYPE (BH/NS/WD/None)
    mth_all = fv["mt_history"][:].astype(str)
    iv_m1 = iv["star_1_mass"][:]
    iv_m2 = iv["star_2_mass"][:]
    iv_p = iv["period_days"][:]

    track_m1: list[float] = []
    track_m2: list[float] = []
    track_p: list[float] = []
    track_row_start: list[int] = []
    track_row_count: list[int] = []
    track_ic: list[str] = []
    track_s1: list[str] = []
    track_co_type: list[str] = []
    track_mth: list[str] = []

    row_cols: dict[str, list[float]] = {c: [] for c in _CO_BINARY_COLS}
    for c in _HISTORY_COLS:
        row_cols[f"s1_{c}"] = []

    n_dropped_not_converged = 0
    n_dropped_missing = 0
    n_dropped_mismatch = 0
    n_kept = 0
    row_offset = 0

    for i in range(n_runs):
        if ic_all[i] == "not_converged":
            n_dropped_not_converged += 1
            continue
        run = grid[f"run{i}"]
        if not ({"binary_history", "history1"} <= set(run.keys())):
            n_dropped_missing += 1
            continue
        bh_rec = run["binary_history"][:]
        h1_rec = run["history1"][:]
        n = bh_rec.shape[0]
        if h1_rec.shape[0] != n or n == 0:
            n_dropped_mismatch += 1
            continue

        if (abs(bh_rec["star_1_mass"][0] - iv_m1[i]) > 1e-3 * max(1.0, iv_m1[i])
                or abs(bh_rec["star_2_mass"][0] - iv_m2[i]) > 1e-3 * max(1.0, iv_m2[i])
                or abs(bh_rec["period_days"][0] - iv_p[i]) > 1e-3 * max(1.0, iv_p[i])):
            n_dropped_mismatch += 1
            continue

        # Only rl_relative_overflow_1 ever fires on this grid (the CO can't overflow its
        # own lobe — measured, rl_relative_overflow_2 <= 0 throughout).
        rlof_rows = np.where(bh_rec["rl_relative_overflow_1"] > 0)[0]
        keep = _decimate(n, _MAX_ROWS_PER_TRACK, must_keep=rlof_rows)

        for c in _CO_BINARY_COLS:
            row_cols[c].append(bh_rec[c][keep])
        for c in _HISTORY_COLS:
            row_cols[f"s1_{c}"].append(h1_rec[c][keep])

        m = keep.size
        track_m1.append(float(iv_m1[i]))
        track_m2.append(float(iv_m2[i]))
        track_p.append(float(iv_p[i]))
        track_row_start.append(row_offset)
        track_row_count.append(m)
        track_ic.append(ic_all[i])
        track_s1.append(s1_all[i])
        track_co_type.append(s2_all[i])
        track_mth.append(mth_all[i])
        row_offset += m
        n_kept += 1

        if n_kept % 5000 == 0:
            print(f"  ...{n_kept} tracks kept ({i + 1}/{n_runs} scanned, "
                  f"{time.time() - t0:.0f}s)")

    f.close()

    print(f"scanned {n_runs} runs: kept {n_kept}, dropped "
          f"{n_dropped_not_converged} not_converged, {n_dropped_missing} missing-history, "
          f"{n_dropped_mismatch} row-mismatch/index-mismatch  ({time.time() - t0:.0f}s)")
    if n_kept == 0:
        raise SystemExit(f"no usable tracks found in {h5_path}")

    data: dict[str, np.ndarray] = {
        "bake_version_co": np.array(BAKE_VERSION_CO),
        "feh": np.array(feh),
        "z_base": np.array(POSYDON_SOLAR_Z * 10.0 ** feh),
        "track_m1_init": np.asarray(track_m1, dtype=np.float64),
        "track_m2_init": np.asarray(track_m2, dtype=np.float64),
        "track_p_init_d": np.asarray(track_p, dtype=np.float64),
        "track_row_start": np.asarray(track_row_start, dtype=np.int64),
        "track_row_count": np.asarray(track_row_count, dtype=np.int64),
        "track_interpolation_class": np.asarray(track_ic),
        "track_s1_state": np.asarray(track_s1),
        "track_co_type": np.asarray(track_co_type),
        "track_mt_history": np.asarray(track_mth),
    }
    for c, vals in row_cols.items():
        data[f"row_{c}"] = np.concatenate(vals).astype(np.float32)

    out_path = Path(os.path.abspath(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".npz.tmp")
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, **data)
    os.replace(tmp, out_path)
    size_mb = os.path.getsize(out_path) / 1e6
    total_rows = row_offset
    print(f"wrote {out_path}  ({size_mb:.1f} MB)  {n_kept} tracks, {total_rows} rows total "
          f"({time.time() - t0:.0f}s)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grid-type", choices=("hms-hms", "co-hms-rlo"), default="hms-hms",
                    help="which POSYDON grid to bake (default hms-hms, the two-normal-"
                         "star grid; co-hms-rlo is the compact-object + normal-star grid, "
                         "Phase 1 Chunk 1a)")
    p.add_argument("--z-label", required=True,
                    help="the extracted grid subdir (e.g. 1Zsun) — hms-hms expects "
                         "data/posydon/<z-label>/*.h5 (fetch_posydon.py's layout); "
                         "co-hms-rlo expects data/posydon/CO-HMS_RLO_<z-label>/*.h5 "
                         "(this module's docstring recipe)")
    p.add_argument("--feh", type=float, required=True,
                    help="[Fe/H] of this grid (e.g. 0.0 for the 1Zsun solar bucket)")
    p.add_argument("--out", default=None,
                    help="output .npz path (default data/posydon/baked/<z-label>.npz, or "
                         "data/posydon/baked_co/<z-label>_co_hms_rlo.npz for co-hms-rlo)")
    a = p.parse_args(argv)

    is_co = a.grid_type == "co-hms-rlo"
    src_dir = (POSYDON_DATA_DIR / f"CO-HMS_RLO_{a.z_label}") if is_co else (POSYDON_DATA_DIR / a.z_label)
    h5_files = sorted(src_dir.glob("*.h5")) if src_dir.is_dir() else []
    if not h5_files:
        raise SystemExit(
            f"no .h5 grid found under {src_dir} — extract the {a.grid_type} grid there "
            f"first (see this module's docstring recipe)"
        )
    if is_co:
        out_path = Path(a.out) if a.out else (OUT_DIR_CO / f"{a.z_label}_co_hms_rlo.npz")
        bake_co(h5_files[0], out_path, feh=a.feh)
    else:
        out_path = Path(a.out) if a.out else (OUT_DIR / f"{a.z_label}.npz")
        bake(h5_files[0], out_path, feh=a.feh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
