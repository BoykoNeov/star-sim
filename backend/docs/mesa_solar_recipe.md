# Solar MESA grid recipe (the `[Fe/H]≈0.00` MESAProvider bucket)

`MESAProvider` is multi-metallicity by snapping: it groups the `history.data`
runs under `data/mesa/` into `[Fe/H]` buckets. The fetched **bearums** grid
(`python -m star_sim.fetch_mesa`) is metal-poor only (`[Fe/H]≈-0.84`). This
recipe produces a **near-solar** run (`Z=0.0152` → `[Fe/H]≈0.00`) and drops it
in alongside bearums with **zero provider code** — the provider just finds the
new file and forms a second bucket.

Why bother: it gives a near-solar Sun anchor and a second, much-closer-to-solar
point for the MESA-vs-MIST cross-validation (the bearums-only grid was 0.84 dex
sub-solar). The output is gitignored (like all of `data/`), so this file is the
durable record of *how it was made*.

It is **not** a calibrated standard solar model (no α_MLT/Y tuning to force
`L=1, R=1` at 4.6 Gyr) — that's deliberate scope control. See the measured
anchor below; the offset from the literal Sun is real and honest.

## 1. Run MESA in Docker (no local MESA install needed)

Image: `evbauer/mesa_lean:r24.03.1.01` (MESA r24.03.1). Driven directly with
`docker exec` — the project's interactive SSH helper script is not needed.

```bash
# pull once (~15 GB)
docker pull evbauer/mesa_lean:r24.03.1.01

# start a container with a host work dir mounted (any gitignored scratch dir)
docker run -d --rm --name mesa_dock \
  -v "<host_work_dir>:/home/docker/docker_work" \
  evbauer/mesa_lean:r24.03.1.01 sleep infinity

# copy the work template + default column list, then drop in the files below
docker exec mesa_dock bash -lc '
  cp -r "$MESA_DIR/star/work" /home/docker/docker_work/solar &&
  cp "$MESA_DIR/star/defaults/history_columns.list" /home/docker/docker_work/solar/'

# ... edit inlist_project + history_columns.list (sections 2 & 3) ...

# compile + run (detached so it survives the client; sentinel on completion)
docker exec mesa_dock bash -lc 'cd /home/docker/docker_work/solar && ./mk'
docker exec -d mesa_dock bash -lc \
  'cd /home/docker/docker_work/solar && ./rn > rn.log 2>&1; echo "exit=$?" > rn.done'
```

Gotchas learned the hard way:
- **`pgstar_flag = .false.`** (in the inlist) → headless, no Xming/VcXsrv needed.
- Kill a stray run with **`pkill -x star`**, never `pkill -f .../star` — the `-f`
  pattern matches its *own* command line and the kill suicides mid-script.
- Run detached (`docker exec -d`) so the run isn't tied to the client's lifetime.

## 2. `inlist_project` (the whole recipe)

```fortran
&star_job
    create_pre_main_sequence_model = .true.   ! clean ZAMS; provider skips pre-MS rows
    pgstar_flag = .false.                     ! headless
    history_columns_file = 'history_columns.list'   ! use the edited local copy
/

&eos
/

&kap
    use_Type2_opacities = .true.
    Zbase = 0.0152                            ! must match initial_z
/

&controls
    initial_mass = 1.0                        ! Msun
    initial_z = 0.0152                        ! -> [Fe/H] ~ 0.00 (project Z_sun = 0.0152)

    ! stop at end of the main sequence (central H exhausted) -- covers the
    ! cross-validation's Xc = 0.6/0.4/0.2 and the 4.6 Gyr Sun anchor
    xa_central_lower_limit_species(1) = 'h1'
    xa_central_lower_limit(1) = 1d-4

    energy_eqn_option = 'dedt'
    use_gold_tolerances = .true.

    history_interval = 1                       ! dense track (~150 exposed rows)
/
```

## 3. `history_columns.list` edit

`MESAProvider._build_track` requires `surface_h1`, `surface_he4`, `center_h1`,
`center_he4` (the rest — `log_L/log_Teff/log_R/log_g/star_age/star_mass/
model_number` — are on by default). In the copied `history_columns.list`,
**`center h1`/`center he4` are already uncommented; uncomment the two surface
lines** (note: MESA uses a *space* in the directive, e.g. `surface h1`, which
produces the column `surface_h1`):

```
   ! individual surface mass fractions (as many as desired)
      surface h1     ! <- uncommented (was !surface h1)
      surface he4    ! <- uncommented (was !surface he4)
      surface c12
      surface o16
```

## 4. Place the output

Copy `LOGS/history.data` to its own subtree — **not** the bearums
`data/mesa/<M>Msun/` path (the provider reads mass from the file, not the dir
name, but keep them separate for clarity):

```bash
mkdir -p data/mesa/solar/1Msun
cp <host_work_dir>/solar/LOGS/history.data data/mesa/solar/1Msun/history.data
```

Verify it loads as a new bucket:

```python
from star_sim.providers import MESAProvider
p = MESAProvider()
print(p.parameter_ranges())          # feh now spans -0.84 .. 0.00
print(p.state_at(1.0, 0.0, 4.6e9))   # Sun anchor
```

> The 2 & 6 M☉ solar runs were made **identically** — same inlist, only
> `initial_mass = 2.0` / `6.0` (same `Z=0.0152`, same TAMS stop). They land in
> the same `[Fe/H]≈0.00` bucket, giving a solar grid of **1/2/6 M☉** that matches
> the metal-poor cross-val's masses.

## 5. Measured result

- Buckets: `[-0.84, 0.00]` — bearums (1–20 M☉) + solar (**1/2/6 M☉**).
- `feh_init = +0.00`, ZAMS `Z_surf = 0.01523` (all three masses).
- **Sun anchor (1 M☉, 4.6 Gyr): L = 1.18 L☉, Teff = 5894 K, R = 1.04 R☉,
  logg = 4.40, mid-MS** — *not* solar-calibrated (no α_MLT/Y tuning to force L=1).
- **Solar MESA-vs-MIST cross-val (matched Z+Y+Xc, masses 1/2/6):** the 1 M☉ Sun
  is dramatically tight (|ΔlogL|≤0.014, |ΔTeff|≤0.04%, |ΔR|≤1.5% — ~10× under the
  metal-poor bracket); the intermediate masses grow off ZAMS (worst at Xc=0.2:
  |ΔlogL|≤0.069, |ΔR|≤9.9%, the convective-core hook), staying inside the
  metal-poor envelope. ΔlogL sign is not uniform (MESA brighter at 1 M☉, MIST at
  2/6). See `backend/tests/test_mesa_vs_mist_solar.py`.

## 6. Cross-validation bracket note

The MESA-vs-MIST test matches on **Z**, not the `[Fe/H]` label. This run's ZAMS
`Z_surf = 0.01523` is **below** MIST p000's ZAMS `Z = 0.01635`, so p000 alone
does **not** bracket it. The straddling MIST grids are **m050** (`Z ≈ 0.00517`)
and **p000** (`Z = 0.01635`) → the matched MIST `[Fe/H]` solves to ≈ -0.04.
A solar cross-validation test should gate on both grids being present.
