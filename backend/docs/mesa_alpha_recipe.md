# MESA α-enhanced (equivalent-Z) recipe — the `/alpha` what-if overlay data

**Phase 3 of `docs/plans/tempered-lineage-inspiral.md` (α-enhanced evolution axis).**
This is the durable record of *how the α-enhanced overlay data is made* — the exact
MESA inputs you (the user) run once in Docker MESA, and where to drop the output. It
mirrors `mesa_helium_recipe.md` / `mesa_solar_recipe.md`: self-run compute, gitignored
output, hosted on a GitHub Release once baked.

## What this is — and the honesty call that collapsed the "heaviest phase" into the lightest

[α/Fe] (O, Ne, Mg, Si, S, Ca, Ti vs. the Fe-peak) is a star-formation-history clock:
core-collapse SNe deliver α-elements promptly, Type Ia SNe deliver iron with a ~1 Gyr
delay, so fast-formed old populations (halo, thick disk, globular clusters, massive
ellipticals) lock in high [α/Fe] (~+0.3–0.4). O and Mg dominate the metal *mass* budget
more than Fe does, so **α-enhancement at fixed [Fe/H] raises the true total Z**, raising
envelope opacity and shifting the track **cooler/redder and slightly longer-lived** at
fixed mass — the **opposite sign from the He effect** (Phase 2).

The plan originally scoped this as "the heaviest of the three": a custom α-enhanced metal
mixture **plus** an α-enhanced OPAL/OP opacity table. **We settled on the equivalent-Z
approach instead** (advisor-endorsed), for a physics reason, not just convenience:

- MESA ships **only solar-scaled** opacity tables (GS98/AGSS09 via OPAL/OP/OPLIB). On the
  main sequence (H-rich) it uses the solar-scaled **Type-1** tables; the Type-2 tables
  that track individual C/O enhancement only blend in when material is nearly H-free (He
  cores), so they do **not** capture α-enhancement on the MS — exactly where Gate 3's
  effect lives. A "matching α-enhanced table" is not in the box.
- **Salaris, Chieffi & Straniero (1993)** showed an α-enhanced track is reproduced, to a
  **few percent**, by a **scaled-solar track at the equivalent total metallicity**
  `[M/H] = [Fe/H] + log₁₀(0.638·10^[α/Fe] + 0.362)`. That residual is **below what this
  sim resolves** and below the documented MESA-vs-MIST systematic — so true α-enhanced
  tables would buy nothing *visible*. The equivalent-Z run **is** the honest model.

So Phase 3's MESA setup is a **Z-only change** (an `initial_z`/`Zbase` bump), not a
custom-mixture/opacity-table build — Phase-2 difficulty.

### The one honesty rule that shapes the whole recipe (and the caption)

Like Phase 2, this is a **what-if overlay sibling** (Ap/Bp, gravity-darkening, initial-He),
**never compared against the live MIST spine** — an α-enhanced MESA track is only shown
against a MESA **baseline** run with the identical inlist, the equivalent Z the sole
difference. And the equivalent-Z model is **scaled-solar**: Fe is *not* held at solar in
its interior — everything is scaled up together. Salaris is a **track-equivalence** claim,
not "Fe stays solar." The caption must say so exactly:

> α-enhanced track approximated by its scaled-solar equivalent-Z counterpart (Salaris 1993);
> the α-boosted mixture is not modeled in the interior. At fixed [Fe/H] the track responds
> to α only through the total metallicity Z — α's distinctive signature is **spectroscopic**
> (see the Coelho α-toggle), not evolutionary.

That framing is the *lesson*, not a hedge: the payoff of this axis is showing that the
track-level and spectrum-level α responses are different things.

## 0. The batch: 3 masses × 2 compositions = 6 runs

The single physics variable is **Z** (via `initial_z` **and** `Zbase` together). Y is
**held fixed at 0.2704** in every run — α-enhancement raises Z at *fixed* Fe **and** *fixed*
He; the extra metals come out of hydrogen (X drops).

| run | initial_mass | **initial_z = Zbase** | initial_y | ZAMS X = 1−Y−Z | represents |
|---|---|---|---|---|---|
| baseline 1 M☉ | 1.0 | **0.0152** | 0.2704 | 0.7144 | [Fe/H]=0, [α/Fe]=0 |
| baseline 2 M☉ | 2.0 | **0.0152** | 0.2704 | 0.7144 | scaled-solar |
| baseline 6 M☉ | 6.0 | **0.0152** | 0.2704 | 0.7144 | scaled-solar |
| enhanced 1 M☉ | 1.0 | **0.029862** | 0.2704 | 0.6997 | [Fe/H]=0, **[α/Fe]=+0.4** |
| enhanced 2 M☉ | 2.0 | **0.029862** | 0.2704 | 0.6997 | equiv-Z (Salaris) |
| enhanced 6 M☉ | 6.0 | **0.029862** | 0.2704 | 0.6997 | equiv-Z (Salaris) |

**The equivalent-Z number (goes straight into the inlist — verify it, don't trust recall):**

```
[α/Fe] = +0.4  →  f_α = 10^0.4 = 2.5119
[M/H]  = [Fe/H] + log10(0.638·f_α + 0.362) = 0 + log10(1.9646) = +0.293
Z_equiv = Z_sun · (0.638·f_α + 0.362) = 0.0152 · 1.9646 = 0.029862  (≈ 0.0299)
```

Masses 1/2/6 M☉ reuse the MESAProvider solar set (a natural before/after against data
already validated) and match Phase 2, for a consistent story across both what-if axes.
[α/Fe]=+0.4 is the old-population extreme (halo/GC/thick-disk plateau), chosen for gate
margin. (The **baseline** runs are inlist-identical to Phase 2's helium baseline; run them
fresh anyway so this batch is self-contained and verifiable — the "matched everything but
one variable, in one batch" discipline. The old runs are an optional cross-check only.)

## 1. Run MESA in Docker (same image/mechanics as the other recipes)

Image `evbauer/mesa_lean:r24.03.1.01` (MESA r24.03.1). On Windows the Docker Desktop
**Linux engine must be running first** (`docker info` should respond). Drive it with
`docker cp` (robust across Windows drive-sharing quirks — no bind mount), exactly like
`mesa_helium_recipe.md §1`:

```bash
docker pull evbauer/mesa_lean:r24.03.1.01        # ~15 GB, once (cached if you ran §helium)
docker run -d --name mesa_alpha evbauer/mesa_lean:r24.03.1.01 sleep infinity

# one work template per run so LOGS don't clobber each other; copy the default
# history column list into each (we only need the surface-H/He edit, §3)
for run in base_1 base_2 base_6 enh_1 enh_2 enh_6; do
  docker exec mesa_alpha bash -lc "
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
**`M:\claud_projects\temp\mesa_alpha_inlists\inlist_{base,enh}_{1,2,6}`** — each is the
solar recipe inlist with `initial_y` made explicit (0.2704, same in all) and the batch
variable set on **both** `initial_z` and `Zbase` (baseline `0.0152` / enhanced
`0.029862`). For reference, `inlist_enh_1`:

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
    Zbase = 0.029862                          ! == initial_z (the alpha axis MOVES Z: change Zbase too!)
/

&controls
    initial_mass = 1.0                        ! (2.0 / 6.0 in the other files)
    initial_z    = 0.029862                   ! Salaris equiv-Z for [Fe/H]=0, [alpha/Fe]=+0.4 (baseline 0.0152)
    initial_y    = 0.2704                      ! HELD FIXED in every run (alpha raises Z at fixed Fe AND fixed Y)

    xa_central_lower_limit_species(1) = 'h1'
    xa_central_lower_limit(1) = 1d-4

    energy_eqn_option = 'dedt'
    use_gold_tolerances = .true.

    history_interval = 1                       ! dense track (~150 exposed rows)
/
```

> **The metallicity gotcha applies here (unlike Phase 2).** On the Y axis Z was fixed, so
> `Zbase` stayed at 0.0152. On this axis Z *is* the variable, so `Zbase = initial_z` must
> move to `0.029862` in the enhanced runs — the exact "change Zbase too, not just
> initial_z" note from `mesa_structure_recipe.md §10`. Don't leave a stale `Zbase=0.0152`
> in an enhanced inlist.

## 3. `history_columns.list` edit — automated in the run loop (§4)

The reused `MESAProvider` parser needs `surface_h1`, `surface_he4`, `center_h1`,
`center_he4`. `center h1`/`center he4` are already uncommented in the default list; the two
**surface** lines (`!surface h1` / `!surface he4`) need uncommenting (MESA uses a *space*,
e.g. `surface h1` → column `surface_h1`). §4's loop does this with a `sed` inside the
container — no manual edit. The ZAMS surface Z (`1 − surface_h1 − surface_he4`) is what the
Phase-3 sibling keys the pair on (baseline ≈ 0.0152, enhanced ≈ 0.0299 — cleanly distinct).
No profile columns needed (a track overlay, not a structure panel).

## 4. Compile, run (detached), collect

```bash
INLISTS="/m/claud_projects/temp/mesa_alpha_inlists"   # adjust to your Git-Bash mount of M:
for run in base_1 base_2 base_6 enh_1 enh_2 enh_6; do
  docker cp "$INLISTS/inlist_$run" mesa_alpha:/home/docker/$run/inlist_project
  docker exec mesa_alpha bash -lc "cd /home/docker/$run &&
    sed -i 's/!surface h1/ surface h1/; s/!surface he4/ surface he4/' history_columns.list"
  docker exec mesa_alpha bash -lc "cd /home/docker/$run && ./mk > mk.log 2>&1"
  docker exec -d mesa_alpha bash -lc \
    "cd /home/docker/$run && ./rn > rn.log 2>&1; echo exit=\$? > rn.done"
done
# each 1 M☉ run to TAMS ~4-5 min (incl. first-run rates cache); 6 M☉ shorter.
# wait for all six rn.done, then collect:
for M in 1 2 6; do
  docker cp mesa_alpha:/home/docker/base_$M/LOGS/history.data \
    "data/mesa_alpha/baseline/${M}Msun/history.data"   # mkdir -p first
  docker cp mesa_alpha:/home/docker/enh_$M/LOGS/history.data \
    "data/mesa_alpha/enhanced/${M}Msun/history.data"
done
docker rm -f mesa_alpha
```

Layout — the Phase-3 sibling globs `data/mesa_alpha/{baseline,enhanced}/<M>Msun/` and keys
the two members of each pair by their **ZAMS surface Z** (row 0). Directory names are human
clarity only.

## 5. Verify the runs + the *sharpened* measure-first gate (Gate 3) — report these back

**(a) Confirm MESA honored the metallicity** — don't assume. The enhanced ZAMS
`Z = 1 − surface_h1 − surface_he4` should be ≈ 0.0299, baseline ≈ 0.0152, and **Y ≈ 0.2704
in both** (the fixed-Y check — a leaked Y difference would contaminate the test):

```bash
for d in data/mesa_alpha/*/[126]Msun; do
  awk 'NR==6{for(i=1;i<=NF;i++){if($i=="surface_h1")a=i; if($i=="surface_he4")b=i}}
       NR==7{printf "%-40s X=%.4f Y=%.4f Z=%.4f\n", FILENAME, $a, $b, 1-$a-$b}' \
    "$d/history.data"
done
```

**(b) Gate 3 has TWO parts, not one (the advisor sharpening) — compare at MATCHED PHASE
(central Xc), NEVER matched age:**

1. **Visibility** (the easy part — it *will* pass; equiv-Z ≈ 2× solar is a large shift):
   the enhanced ZAMS is measurably **cooler (redder) and slightly fainter**, and τ_MS
   measurably **longer** than baseline — the opposite sign from the He effect.
2. **Distinctiveness** (the part that actually decides the framing): because this is a
   pure Z change, the enhanced track is, by construction, *the same thing the existing
   [Fe/H] axis already does at higher Z*. That is **not** a reason to kill the feature — it
   **is the lesson**, and it must be owned in the caption (§What this is): the track sees
   only total Z; the α-specific fingerprint is spectroscopic. If, when built, the overlay
   cannot be told apart from "just bump [Fe/H]," the honest move is to **lean into the
   Coelho pairing**, not to pretend the track independently resolves α.

**Measure ZAMS + τ_MS through the parser, NOT raw row 0.** With
`create_pre_main_sequence_model = .true.`, history.data **row 0 is the cool ~4400 K
Hayashi pre-MS model for every mass** — reading it (an `awk NR==7`) makes every ZAMS
Teff look broken (a 1 M☉ ZAMS reads 4461 K instead of the real ~5750 K). The
`MESAProvider` parser the sibling reuses **windows the pre-MS rows off**, so the parsed
track's row 0 IS the ZAMS. Use it (run from `backend/`):

```bash
python -c "
from star_sim.providers.mesa import _build_track, _state_from_track
for M in (1, 2, 6):
    for kind in ('baseline', 'enhanced'):
        t = _build_track(f'../data/mesa_alpha/{kind}/{M}Msun/history.data')
        s = _state_from_track(t, 0.0)          # parsed row 0 = ZAMS (pre-MS windowed off)
        tau = (t.age[-1] - t.age[0]) / 1e9     # windowed MS lifetime (TAMS - ZAMS age)
        print(f'{kind:8s} {M}Msun  ZAMS Teff={s.Teff_K:5.0f} L={s.L_lsun:8.3f}  tau_MS={tau:.3f} Gyr')
"
```

Expected direction (higher Z at fixed mass): enhanced **cooler**, **fainter**, **longer**
τ_MS at every mass. If visible → Gate 3 passes and the sibling (Chunk 3b) + overlay
(Chunk 3c) get built with the Coelho-paired framing. If a mass shows no shift, drop it (the
"don't ship a control nobody can see work" rule).

## 6. Then hand back

Once the six `history.data` files are under `data/mesa_alpha/` and §5(a)/(b) are reported,
Phase 3 continues on my side: a `star_sim/alpha.py` sibling (a near-clone of `helium.py` —
reusing MESAProvider's `_build_track`/`_state_from_track`, keying the pair by ZAMS Z instead
of Y) + a `/alpha` route serving the baseline+enhanced pair for a requested mass, then the
frontend overlay toggle paired in-caption with the Coelho spectrum α-toggle. **No sibling,
route, or frontend gets built before Gate 3 is measured** (per the plan and the advisor).
No further compute from you after this batch.
