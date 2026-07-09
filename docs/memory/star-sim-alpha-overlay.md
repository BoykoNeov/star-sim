---
name: star-sim-alpha-overlay
description: Phase 3 α-enhanced (equivalent-Z) what-if overlay — alpha.py sibling + /alpha + HR overlay (old-population [α/Fe], Salaris equiv-Z, self-run MESA). BUILT.
metadata:
  type: project
---

**Phase 3 of `docs/plans/tempered-lineage-inspiral.md` — the α-enhanced evolution axis.
BUILT end-to-end 2026-07-09 (Chunks 3a/3b/3c); Playwright-verified, 397 pytest. This
COMPLETES the whole tempered-lineage plan (Phases 1–3).**

The old-population what-if: at fixed [Fe/H], boosting [α/Fe] (O, Ne, Mg, Si, S, Ca, Ti vs.
the Fe-peak) raises the true total metallicity Z (α-elements dominate the metal *mass*), so
at fixed mass the track is **cooler (redder), slightly fainter, and longer-lived** — the
**opposite sign** from the Phase-2 He effect. A **what-if overlay sibling** like `helium.py`;
bypasses `PROVIDER`, NEVER compared vs. the live MIST spine (MESA-vs-MESA only).

**The load-bearing decision — the "heaviest phase" collapsed to Phase-2 difficulty
(advisor-endorsed).** The plan billed Phase 3 as a custom α mixture + an α-enhanced OPAL/OP
opacity table. Two facts killed that: (1) **MESA ships only solar-scaled opacity tables** —
on the MS (H-rich) it uses solar-scaled **Type-1** tables; the Type-2 tables that track
individual C/O enhancement only blend in when H-poor (He cores), so they do NOT capture α on
the MS where the effect lives — a matching α table isn't in the box, and generating/downloading
one contradicts "zero downloads." (2) **Salaris, Chieffi & Straniero (1993)** showed an
α-enhanced track ≈ a **scaled-solar track at the equivalent total Z** to a few percent — below
what this sim resolves and below the MESA-vs-MIST systematic. So true α tables buy nothing
*visible*. Phase 3's MESA setup became a **Z-only change** (the metallicity "change Zbase too,
not just initial_z" gotcha **applies here**, unlike the Y axis where Z was fixed).

**The equivalent-Z number (verified from primary sources, goes into the inlist):**
`[M/H] = [Fe/H] + log10(0.638·10^[α/Fe] + 0.362)` (SCS93). For [Fe/H]=0, [α/Fe]=+0.4 →
factor 1.9646 → **Z_equiv = 0.0152·1.9646 = 0.029862** (≈0.0299), **Y held at 0.2704** in both
runs (α raises Z at fixed Fe AND fixed He; X drops). Recipe `backend/docs/mesa_alpha_recipe.md`.

**Chunk 3a (data, Claude ran the MESA batch in Docker himself — user turned Docker on, "you
bake").** Six runs (3 masses × 2 comps), image `evbauer/mesa_lean:r24.03.1.01`, `docker cp`
driven, inlists differ ONLY in `initial_mass` (1/2/6) and `initial_z=Zbase` (0.0152 / 0.029862).
Converged exit 0, ~300 rows each. **Composition honored exactly** (base Z=0.0152 / enh Z=0.0299,
Y=0.2704 both). **Gate 3 PASSED at every mass** — measured **via the real parser that skips
pre-MS**, NOT raw row 0 (with `create_pre_main_sequence_model=.true.` row 0 is the cool ~4400 K
Hayashi pre-MS model — a gotcha that made my first raw-awk ZAMS read nonsense): 1 M☉ ΔTeff −488 K
/ τ_MS 1.49×; 2 M☉ −1247 K / 1.34×; 6 M☉ −1606 K / 1.12× (cooler+fainter+longer). Data gitignored/
MESA-local (`requires_alpha_data`); no npz bake (raw read, like helium).

**Chunk 3b (backend).** `star_sim/alpha.py` — a near-clone of `helium.py`, keying the pair by
**ZAMS surface Z** (`1 − Xs[0] − Ys[0]`) not Y, asserting two-per-mass. `alpha_overlay(mass)`
snaps 1/2/6 M☉ (solar [Fe/H]), returns both tracks as §3 `StellarState` lists + ZAMS Teff/L,
equivalent [M/H] (=log10(Z/Z_sun)), windowed τ_MS. **`alpha_fe` is DERIVED from the measured
baseline/enhanced Z ratio via the inverted Salaris relation** (data-derived, not hardcoded →
recovers +0.40). `/alpha` (snap-always, 422 mass≤0, 503 missing) + `/alpha_status` (visibility
gate). **+9 tests** (`test_alpha.py`; 1 UNGATED status test): cooler/fainter/longer Gate-3 asserts,
derived-[α/Fe]≈+0.4, §3-state validity, snap honesty, route/422, AST sibling-no-PROVIDER. 397 pytest.

**Chunk 3c (frontend, Playwright 1440+390 zero errors).** A LIGHT HR overlay like He, **mutually
exclusive** with it (they SHARE the `hr.js` overlay slot — only one MESA what-if owns the HR panel;
each toggle unchecks the other via inline state-clear). `hr.setHeliumOverlay` was generalized to
accept custom ZAMS `labels:{enh,base}` — the α labels show the equivalent **[M/H]** (+0.29 / +0.00),
reinforcing "the track sees only total Z." MIST spine hidden while on. Caption carries the whole
story + the Coelho-paired honesty framing: "…Cooler + fainter, and longer-lived: τ_MS 1.16 vs 0.86
Gyr (1.3× longer). The track sees only the total Z — α's own signature is spectroscopic (see the
spectrum α-toggle)." τ_MS (LONGER here, no HR axis) surfaced explicitly. `/alpha_status`→`alphaHasGrid`
visibility gate + fetch-failure teardown (the He data-absent fixes).

**The real bug Playwright caught: a duplicate-ID collision.** I first named the toggle
`#alpha-toggle` — but that ID was ALREADY the Coelho **spectrum** α-enhancement toggle (from the
rotation-atlas thread). Playwright strict-mode flagged "resolved to 2 elements." Renamed mine to
**`#alpha-track-toggle`/`-control`/`-note`** (track-level vs. spectrum-level — collision-free AND
clearer, reinforces the Coelho pairing). Lesson: before adding a new frontend id, grep for it.

**Gate 3 part 2 (distinctiveness) is the LESSON, not a defect (advisor):** because this is a pure
Z change, the enhanced run IS what the [Fe/H] axis does at higher Z — the track responds to α only
through total Z; α's distinctive fingerprint is spectroscopic (Coelho). The overlay is framed
around this (caption pairs it with the spectrum α-toggle), never as "the track independently
resolves α." **Do-not-build-UI-before-gate discipline honored** (recipe + inlists prepared first
while Docker was off; sibling/route/frontend only after Gate 3 measured).

**Next = Phase 3 (α axis) is the plan's end.** Future α work would be the real α-enhanced opacity
tables (a labeled fidelity upgrade, currently not worth it) — or move to a ROADMAP thread.
[[star-sim-helium-overlay]] [[star-sim-phase4-mesa]] [[star-sim-rotation-subpop-atlas]]
[[star-sim-interior-structure-mesa]] [[star-sim-hosted-data-assets]]
