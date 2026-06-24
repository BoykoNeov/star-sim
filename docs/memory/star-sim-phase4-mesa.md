---
name: star-sim-phase4-mesa
description: "MESAProvider — second real provider (offline MESA history.data): proves §3 boundary again, measured MESA-vs-MIST cross-validation, multi-metallicity by snapping NOW REALIZED with a local-Docker solar grid ([Fe/H]≈0.00) whose solar cross-val is ~10x tighter than the metal-poor one."
metadata: 
  node_type: memory
  type: project
  originSessionId: d0d55144-3bfa-4561-8a8f-384c6d5f8c05
---

`providers/mesa.py` is the **second real provider**: reads offline MESA
`history.data` (a different on-disk format) behind the same §3 boundary as
[[star-sim-mist-provider]], proving the abstraction a second time. Deliberately
**discrete-grid, multi-metallicity by snapping** (was single-Z; the hard guard that
raised on >0.02-dex [Fe/H] spread is gone): runs group into `[Fe/H]` buckets (key =
derived feh rounded 2 dp), and `state_at`/`track` **snap feh-then-mass** — nearest grid
[Fe/H] bucket, then nearest mass within it — reporting that run's *true*
`mass_init_msun`/`feh_init` (no silent extrapolation, §6). `_snap(mass)` →
`_snap(mass, feh)` is the single choke point; `parameter_ranges`/`mass_range` report a
real feh span + **non-rectangular** per-Z mass domain; off-grid feh snaps in-range /
raises out-of-range (mirrors true-mass honesty). Single-Z is the degenerate one-bucket
case (no `CACHE_VERSION`; MESA has no parse cache). Only the along-track age→row
inversion interpolates. **No cross-mass/cross-[Fe/H] interp on purpose** — raw history
has no EEP column, and computing EEPs to row-align tracks *is* MIST's `iso` machinery
(spec rules out "a MESA reimplementation"); so the §10 lies-between test is MIST-specific
and N/A. **Multi-Z now REALIZED** (was latent): a near-solar `[Fe/H]≈0.00` bucket (a local
Docker MESA run, see below) sits alongside bearums `−0.84`, so two Z buckets load — the
drop-in needed **zero provider code** (data + tests only). Always-on multi-Z tests
use a programmatic two-bucket synthetic fixture (non-rectangular: solar 1+2 M☉ /
metal-poor −0.5 1 M☉). 90 tests (was 85). Self-contained ~40-line parser (no
`mesa_reader` dep). Honest proxies, all commented: dedup retry rows by
`model_number` (keep last write → strictly-increasing `star_age`); ZAMS = first
row Xc dropped ~0.0015 below initial; eep = monotonic row index (NOT MIST-comparable);
[Fe/H] from ZAMS surface Z; coarse MS→RGB→CHeB phase from central H/He.
Per-element `metals_*` come back **empty** (tutorial runs log no isotopes —
StellarState defaults handle it; relevant for [[star-sim-phase4-cno]]). MESA is
**opt-in**: `PROVIDER` in api.py stays MISTProvider.

Data via `fetch_mesa.py`: `bearums/InteractivePlots` (pinned SHA, **no upstream
license → NOT committed**; downloaded into gitignored `data/mesa/` for local use,
like the MIST grids). Grid: 1/2/4/6/10/14/20 M☉, single Z≈0.0022 → [Fe/H]≈−0.84.

**Measured MESA-vs-MIST cross-validation** (`test_mesa_vs_mist.py`, the deliverable):
diffs the two through the public `track()` API, controlling both confounds —
matched on **Z** (solve MIST [Fe/H] whose ZAMS Z = the MESA run's; sample Z=0.00218
sits between MIST m100 Zinit=0.00171 / m075 Zinit=0.00303 → needs
`fetch_mist --feh m075,m100`) NOT on derived [Fe/H] (different Z_sun/Y(Z) → equal
"[Fe/H]" ≠ equal Z), and compared at **shared central Xc** (0.6/0.4/0.2) not each
code's ZAMS label. Yinit agrees (~0.2518 both → Y not a confound). Gaps (M=1/2/6):
near ZAMS |ΔlogL|≤0.036, |ΔTeff|≤2.3%, |ΔR|≤8.2%; late MS |ΔlogL|≤0.126,
|ΔTeff|≤4.4%, |ΔR|≤20.3% — MESA systematically more luminous/larger, gap **grows
off ZAMS** (late-MS overshoot/mixing/opacity; tutorial inlist ≠ MIST v2.5).
Consistency within physics scatter, not bit-for-bit.

**Why:** records the second-provider deliverable and the *measured* discrepancy
(not just "a green test"), plus the gotchas a future MESA extension will hit.

**How to apply:** Tolerances pin the **measured** gaps with margin (the
`test_mist_provider.py` pattern — measure first, then pin; a priori "loose"
tolerances prove nothing — 0.1 dex = 26% in L). Tests gated by `requires_mesa_data`
+ `requires_mist_lowz`; parser/provider-API tests run always (committed synthetic
fixture + tmp copy).

**SOLAR GRID NOW DONE (was deferred) — made locally in Docker.** The MESA-Web *web form*
never delivered its result email, so instead of a public grid we **ran MESA r24.03.1
ourselves in Docker** (`evbauer/mesa_lean:r24.03.1.01`, driven by `docker exec` — no SSH
helper, no local build): **1/2/6 M☉** at `initial_z=0.0152` (=project Z_sun → derived `[Fe/H]`
rounds to +0.00 for all three), pre-MS→TAMS, `pgstar` off, `history_interval=1` (dense),
dropped at `data/mesa/solar/{1,2,6}Msun/history.data` (2/6 made identically, only
`initial_mass` changed → same bucket, masses now match the metal-poor cross-val). Output is gitignored → the
**reproducibility recipe is committed at `backend/docs/mesa_solar_recipe.md`** (image, exact
inlist, the `history_columns.list` surface-h1/he4 uncomment, placement, anchor). Sun anchor
(4.6 Gyr): L=1.18, Teff=5894 K, R=1.04 — *not* solar-calibrated (honest offset, MESA-brighter
trend). **Payoff: solar MESA-vs-MIST cross-val** (`test_mesa_vs_mist_solar.py` + gates
`requires_mesa_solar`/`requires_mist_solar_bracket`) matched on Z (solar ZAMS Z=0.01523 is
**below** MIST p000's 0.01635 → bracket is **m050+p000**, matched MIST [Fe/H]≈−0.05; Y agrees)
at Xc=0.6/0.4/0.2, **masses 1/2/6**: the **1 M☉ Sun is dramatically tight** (|ΔlogL|≤0.014,
|ΔTeff|≤0.04%, |ΔR|≤1.5% — ~10x under the metal-poor bracket), but the **intermediate masses
grow off ZAMS** (worst Xc=0.2: |ΔlogL|≤0.069, |ΔR|≤9.9% — the convective-core hook), staying
inside the metal-poor envelope (late-MS |ΔlogL|≤0.13, |ΔR|≤20%). **ΔlogL sign NOT uniform**
(MESA brighter at 1 M☉, MIST at 2/6) → no "MESA systematically brighter" assertion here
(unlike the metal-poor grid). 102 tests (was 90; the solar file mirrors the metal-poor
EARLY/LATE-Xc split + a Sun-specific tight test). One test broke as predicted:
`test_real_grid_loads_with_expected_masses` pinned single-Z (`feh min==max`) → relaxed to
verify the bearums bucket present+metal-poor+7 masses without assuming it's the only Z.
**Gotchas:** `pkill -x star` not `pkill -f .../star` (`-f` matches its own argv → kill
suicides); `docker exec -d` to detach the run; `pgstar_flag=.false.` removes the Xming/X11
prereq; **the MESA-Web web form silently never delivered → local Docker is the reliable path**.

**Finding still valid (why we ran our own):** no clean fetchable *native* multi-mass solar
MESA grid with surface composition exists publicly — `konkolyseismolab/mesalab` is **MIST
repackaged** (circular validation, rejected); `sai-veeresh/computational-astrophysics` is
genuine native solar but has **no bulk surface composition** (X/Y/Z_surf required §3 fields).
So a self-run grid (MESA-Web or local Docker) was always the real path; Docker is what
actually delivered.
