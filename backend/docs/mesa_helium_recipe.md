# MESA initial-helium (Y) recipe — the `/helium` what-if overlay data

**Phase 2 of `docs/plans/tempered-lineage-inspiral.md` (initial-helium / Y axis).**
This is the durable record of *how the He-enhanced overlay data is made* — the
exact MESA inputs you (the user) run once in Docker MESA, and where to drop the
output. It mirrors `mesa_solar_recipe.md` / `mesa_structure_recipe.md`: self-run
compute, gitignored output, hosted on a GitHub Release once baked.

> **Fast path (casual users): skip this whole recipe.** The six `history.data`
> files this recipe produces are already hosted on the `mesa-helium-baked-v1`
> GitHub Release. Just run
>
> ```bash
> python -m star_sim.fetch_helium_baked
> ```
>
> and the `/helium` overlay lights up (no Docker, no MESA, no compute). The recipe
> below is only for **regenerating** the data from scratch or changing the batch.

## What this is (and the one honesty rule that shapes the whole recipe)

Globular-cluster CMDs (ω Cen, NGC 2808) show a **He-enhanced second generation**
(Y ≈ 0.35–0.40 vs. primordial ≈ 0.25) at the *same* [Fe/H] as the first
generation — He enrichment tracks H-burning pollution, not supernova iron, so it
is an axis genuinely **independent of Z**. At fixed mass/[Fe/H], raising Y raises
the mean molecular weight μ, so by homology the star is **more luminous, hotter
(bluer), and shorter-lived** (τ_MS = M/L falls) — the "second-parameter" effect.

The feature is a **what-if overlay sibling** (like Ap/Bp and gravity-darkening),
**never compared against the live MIST spine**. The entire honesty basis is
**"matched everything but Y."** That single rule dictates the recipe:

- **Run baseline AND enhanced together, in one batch, with `initial_y` set
  explicitly in BOTH** — baseline `0.2704`, enhanced `0.40`, everything else
  byte-identical. Do **not** reuse the old `data/mesa/solar/` runs as the shipped
  baseline: `history.data` does not record the full inlist, so you can't verify
  after the fact that they used an identical setup, and a comparison you can't
  verify is exactly the trap this axis is designed against. (The old solar runs
  used MESA's *implicit* default Y ≈ 0.2704; keep them only as an optional
  cross-check, not the shipped pair.)
- **Do NOT touch `Zbase`.** The "change Zbase too, not just initial_z" note in
  `mesa_structure_recipe.md §10` is the *metallicity*-axis gotcha. On the **Y
  axis Z is unchanged**, so `Zbase = initial_z = 0.0152` in *both* runs. Don't let
  a different `Zbase` leak in from a copied metallicity inlist.

## 0. The batch: 3 masses × 2 compositions = 6 runs

| run | initial_mass | initial_z | Zbase | **initial_y** | expected ZAMS X = 1−Y−Z |
|---|---|---|---|---|---|
| baseline 1 M☉ | 1.0 | 0.0152 | 0.0152 | **0.2704** | 0.7144 |
| baseline 2 M☉ | 2.0 | 0.0152 | 0.0152 | **0.2704** | 0.7144 |
| baseline 6 M☉ | 6.0 | 0.0152 | 0.0152 | **0.2704** | 0.7144 |
| enhanced 1 M☉ | 1.0 | 0.0152 | 0.0152 | **0.40** | 0.5848 |
| enhanced 2 M☉ | 2.0 | 0.0152 | 0.0152 | **0.40** | 0.5848 |
| enhanced 6 M☉ | 6.0 | 0.0152 | 0.0152 | **0.40** | 0.5848 |

Masses 1/2/6 M☉ reuse the MESAProvider solar set (a natural before/after against
data already validated). Y = 0.40 is the observationally-motivated NGC 2808
bluest-MS extreme (ΔY ≈ +0.13), chosen for gate margin — see the measure-first
gate in §5.

## 1. Run MESA in Docker (same image/mechanics as the other recipes)

Image `evbauer/mesa_lean:r24.03.1.01` (MESA r24.03.1). On Windows the Docker
Desktop **Linux engine must be running first** (`docker info` should respond — at
the time of writing the daemon was stopped, so start Docker Desktop before this).
Drive it with `docker cp` (robust across Windows drive-sharing quirks — no bind
mount), exactly like `mesa_structure_recipe.md §1`:

```bash
docker pull evbauer/mesa_lean:r24.03.1.01        # ~15 GB, once (already cached if you ran §structure)
docker run -d --name mesa_he evbauer/mesa_lean:r24.03.1.01 sleep infinity

# one work template per run so LOGS don't clobber each other; copy the default
# history column list into each (we only need the surface-H/He edit, §3)
for run in base_1 base_2 base_6 enh_1 enh_2 enh_6; do
  docker exec mesa_he bash -lc "
    cp -r \"\$MESA_DIR/star/work\" /home/docker/$run &&
    cp \"\$MESA_DIR/star/defaults/history_columns.list\" /home/docker/$run/"
done
```

Gotchas (from the earlier recipes, unchanged):
- **`pgstar_flag = .false.`** → headless, no Xming/VcXsrv.
- Kill a stray run with **`pkill -x star`**, never `pkill -f .../star`.
- Run detached (`docker exec -d`) so a run survives the client.
- `./mk` builds `star` *into that work dir*; run each in its own dir/LOGS.

## 2. `inlist_project` — the six files are pre-generated for you

The six inlists are already written to
**`M:\claud_projects\temp\mesa_helium_inlists\inlist_{base,enh}_{1,2,6}`** — each
is the solar recipe inlist (`mesa_solar_recipe.md §2`) with `initial_y` made
**explicit**, differing only in `initial_mass` (1.0/2.0/6.0) and `initial_y`
(baseline `0.2704` / enhanced `0.40`). For reference, `inlist_enh_1`:

```fortran
&star_job
    create_pre_main_sequence_model = .true.   ! clean ZAMS; the parser skips pre-MS rows
    pgstar_flag = .false.                     ! headless
    history_columns_file = 'history_columns.list'
/

&eos
/

&kap
    use_Type2_opacities = .true.
    Zbase = 0.0152                            ! == initial_z; SAME in every run (Y axis, Z fixed)
/

&controls
    initial_mass = 1.0                        ! (2.0 / 6.0 in the other files)
    initial_z    = 0.0152                     ! -> [Fe/H] ~ 0.00 (project Z_sun = 0.0152); SAME in every run
    initial_y    = 0.40                       ! the ONLY physics knob that varies (baseline 0.2704 / enhanced 0.40)

    ! stop at end of the main sequence (central H exhausted) -- the He effect
    ! (bluer/brighter ZAMS + shorter tau_MS) lives entirely inside this window
    xa_central_lower_limit_species(1) = 'h1'
    xa_central_lower_limit(1) = 1d-4

    energy_eqn_option = 'dedt'
    use_gold_tolerances = .true.

    history_interval = 1                       ! dense track (~150 exposed rows)
/
```

## 3. `history_columns.list` edit — automated in the run loop (§4)

`MESAProvider`'s parser (which the Phase-2 sibling reuses) needs `surface_h1`,
`surface_he4`, `center_h1`, `center_he4`. `center h1`/`center he4` are already
uncommented in the default list; the two **surface** lines (`!surface h1` /
`!surface he4`) need uncommenting (MESA uses a *space*, e.g. `surface h1` → column
`surface_h1`). §4's loop does this with a `sed` inside the container — no manual
edit. No profile columns are needed (a track overlay, not a structure panel).

## 4. Compile, run (detached), collect

```bash
INLISTS="/m/claud_projects/temp/mesa_helium_inlists"   # adjust to your Git-Bash mount of M:
for run in base_1 base_2 base_6 enh_1 enh_2 enh_6; do
  docker cp "$INLISTS/inlist_$run" mesa_he:/home/docker/$run/inlist_project
  # uncomment the two surface abundance columns in this run's history_columns.list
  docker exec mesa_he bash -lc "cd /home/docker/$run &&
    sed -i 's/!surface h1/ surface h1/; s/!surface he4/ surface he4/' history_columns.list"
  docker exec mesa_he bash -lc "cd /home/docker/$run && ./mk > mk.log 2>&1"
  docker exec -d mesa_he bash -lc \
    "cd /home/docker/$run && ./rn > rn.log 2>&1; echo exit=\$? > rn.done"
done
# each 1 M☉ run to TAMS ~4-5 min (incl. first-run rates cache); 6 M☉ shorter.
# wait for all six rn.done, then collect:
for M in 1 2 6; do
  docker cp mesa_he:/home/docker/base_$M/LOGS/history.data \
    "data/mesa_helium/baseline/${M}Msun/history.data"   # mkdir -p first
  docker cp mesa_he:/home/docker/enh_$M/LOGS/history.data \
    "data/mesa_helium/enhanced/${M}Msun/history.data"
done
docker rm -f mesa_he
```

Layout — the Phase-2 sibling globs `data/mesa_helium/{baseline,enhanced}/<M>Msun/`
and keys the two members of each pair by their **ZAMS surface_he4** (row 0, the
initial Y before burning — robust, version-independent; the history *header* does
not carry `initial_y`). Directory names are human clarity only.

## 5. Verify the runs + the measure-first gate (Gate 2) — report these back

**(a) Confirm MESA honored `initial_y`** — don't assume. The enhanced ZAMS
`surface_he4` should be ≈ 0.40, the baseline ≈ 0.2704:

```bash
# row 0 (first data row = line 7) surface_h1 / surface_he4 per run
for d in data/mesa_helium/*/[126]Msun; do
  awk 'NR==6{for(i=1;i<=NF;i++){if($i=="surface_h1")a=i; if($i=="surface_he4")b=i}}
       NR==7{printf "%-40s X=%.4f Y=%.4f Z=%.4f\n", FILENAME, $a, $b, 1-$a-$b}' \
    "$d/history.data"
done
```

**(b) Gate 2 — compare at MATCHED PHASE (central Xc), NEVER matched age.** The
enhanced track is *shorter-lived*, so equal age ≠ equal evolutionary point (the
same "matched-Xc, not age" discipline as `mesa_structure_recipe.md §10`). Per
mass, for **both** Y, report:

- **ZAMS Teff and L** (row 0) — the *bluer + brighter* check (enhanced should be
  hotter and more luminous at the same mass/Z).
- **τ_MS** = the age of the last row (central H exhausted, the TAMS stop) — the
  *shorter main-sequence lifetime* check (enhanced should be smaller).

**Measure ZAMS + τ_MS through the parser, NOT raw row 0.** With
`create_pre_main_sequence_model = .true.`, history.data **row 0 is the cool ~4400 K
Hayashi pre-MS model for every mass** — an `awk NR==7` reads it and makes every ZAMS
Teff look broken (a 1 M☉ ZAMS reads 4461 K instead of the real ~5750 K, so the
bluer/brighter check can't be read off it). The `MESAProvider` parser the sibling
reuses **windows the pre-MS rows off**, so the parsed track's row 0 IS the ZAMS. Use it
(run from `backend/`):

```bash
python -c "
from star_sim.providers.mesa import _build_track, _state_from_track
for M in (1, 2, 6):
    for kind in ('baseline', 'enhanced'):
        t = _build_track(f'../data/mesa_helium/{kind}/{M}Msun/history.data')
        s = _state_from_track(t, 0.0)          # parsed row 0 = ZAMS (pre-MS windowed off)
        tau = (t.age[-1] - t.age[0]) / 1e9     # windowed MS lifetime (TAMS - ZAMS age)
        print(f'{kind:8s} {M}Msun  ZAMS Teff={s.Teff_K:5.0f} L={s.L_lsun:8.3f}  tau_MS={tau:.3f} Gyr')
"
```

If enhanced-Y is measurably bluer/brighter at ZAMS **and** shorter-lived than
baseline at every mass tried → Gate 2 passes and the sibling + route (Chunk 2b) +
overlay (Chunk 2c) get built. If the shift isn't visible at some mass, that mass
is dropped (the honesty-tiering rule — don't ship a control nobody can see work).

## 6. Then hand back

Once the six `history.data` files are under `data/mesa_helium/` and §5(a)/(b) are
reported, Phase 2 continues on my side: the `helium.py` sibling (reusing
MESAProvider's `_read_mesa_history` / `_build_track` parser) + a `/helium` route
serving the baseline+enhanced pair for a requested mass, then the frontend
overlay toggle. No further compute from you after this batch.
```
