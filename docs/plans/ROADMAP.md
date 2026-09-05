# Roadmap — the open-items index

**This is the canonical, single-page view of everything proposed-but-not-yet-built.**
It is a *thin index*: the linked plan doc is the source of truth for design detail. When
something ships, move its row (with the measured payoff) to `SHIPPED.md` — this page never
narrates builds. When scope changes, edit the plan and the one-line hook here, not a second
list. CLAUDE.md's "what's next" points at this file.

## Status legend

- **planned** — designed and chunked in a plan doc; ready to implement.
- **sketched** — a concrete approach exists but is not chunked.
- **idea** — named with a rationale; no design yet.
- **blocked** — waiting on data or a licence; recorded so it is not re-proposed.

## The two standing plans (read these first)

| Plan | What it holds |
|---|---|
| [`science-hurdles.md`](science-hurdles.md) | The tiered ledger of every measured scientific limit (T1 residual / T2 data-limited / T3 parametrized / T4 evocative / out-of-scope) with a verdict per row and a prioritised **NEXT** list (§6). |
| [`structure-refactor.md`](structure-refactor.md) | The project-structure debts with measured sizes (api routers, shared grid helpers, `main.js` chokepoint/registry, a `node --test` harness) and the order to pay them. |
| [`visual-performance.md`](visual-performance.md) | The measured visuals/performance ledger: the 2026-09-05 numbers, what shipped, and the remaining rows (each with a recipe + acceptance check) — plus the reusable measurement harness in `temp/star-sim-perf`. |

## Open science (from `science-hurdles.md` §6, in priority order)

| Item | Status | Hook | Where |
|---|---|---|---|
| Near-IR spectrum bake (→ 2.5 µm) | planned, data-gated | Extends the main absorption cube past 8999 Å so Gaia G/RP and 2MASS JHK become computable on the observer CMD. Host-side bake + one `BAKE_VERSION` bump. | `science-hurdles.md` §3; `outward-quartet-atlas.md` §Axis A |
| Grid density at 0.3–0.45 M☉ | idea | The fully-convective transition is the one place log-mass weighting is slightly worse; MIST has no finer nodes, so this would mean MESA slices. Only if a visible drag artefact is measured. | `science-hurdles.md` §1.1 |

## Open engines and follow-ons

| Item | Status | Hook | Where |
|---|---|---|---|
| Binarity follow-ons: `CO-HeMS` / `CO-HeMS_RLO` double-compact-object channel; a POSYDON population overlay | sketched / unscoped | Both are separate extractions from the 84 GB already on disk; the DCO channel is the GW-progenitor payoff. Merger *time* stays out (needs natal kicks — two prescriptions deep). | `tempered-lineage-inspiral.md`; memory `star-sim-co-hms-rlo.md` |
| Live solver / reduced nuclear network | idea | The ultimate "any star" capability; large, only worth it if the grid approach hits a real wall (spec §9). | `whirling-cohort-atlas.md` (Tier D); spec §9 |
| Type Ia supernova | blocked (needs a binary channel) | Off the WD branch, never the core-collapse arc. Recorded so it is not started in the wrong place. | memory `star-sim-supernova-remnant-endgame.md` |

## Minor / probably-skip — recorded so we don't re-propose them

| Item | Status | Hook | Where |
|---|---|---|---|
| Microturbulence (ξ) | idea | Spectral line-saturation knob (CAP18-large carries it); real but thin pedagogy — likely not worth a control. | `whirling-cohort-atlas.md` (Tier B) |
| Spectra density re-bake | skip (measured) | 2.5 Å bins ≈ 1 bin/px at full width; reconsider only per zoom band where the sample dots show under-sampling. | `graceful-toasting-thimble.md`; `SHIPPED.md` |
| Koester DB (He-atmosphere WD) spectra | blocked (licence) | Restricted / non-redistributable. | memory `star-sim-wr-wd-endgame-plan.md` |
| [α/Fe] spectra beyond [Fe/H] +0.2 | blocked (data) | Coelho has α = 0 only at {−1.0, −0.5, 0, +0.2}. | `SHIPPED.md` |

## Structure (from `structure-refactor.md` §4, in order)

*Steps 1–4 shipped 2026-09-03 — `api.py` → routers, `main.js` guards + the living-only
registry, the `node --test` harness, and `init` → per-panel `wire*()` (+ `controls.js`).
See `SHIPPED.md` §6.*

1. Shared grid helpers (`snap`, `load_npz`, missing-data hints); `spectra/` package.
2. `providers/mist.py` split along its existing seams (`_parse` / `_grid` / the class);
   the fetch/bake table form; the `conftest.py` `requires(dataset)` factory.

## Visuals & performance (from `visual-performance.md` §§3–4, in payoff order)

| Item | Status | Hook | Where |
|---|---|---|---|
| Adaptive pixel ratio for the 3D star | sketched | The surface shader is 108 hash evaluations per fragment; at DPR 2 that is ~76 M per frame. Drop the star canvas's pixel ratio by 0.5 when a 60-frame mean exceeds 25 ms; never on a capable GPU. | `visual-performance.md` P1 |
| Vendor `three.module.js` | sketched | The only external asset (1.2 MB from unpkg); no network → a black 3D panel with no actionable error. | `visual-performance.md` P2 |
| `/track` payload (811 KB per mass change) | measure first | Time the fetch + `JSON.parse`; only then `GZipMiddleware`. Never round the floats. | `visual-performance.md` P3 |
| Static layers for `sed.js` / the comp cno view | optional | The scrub is ~1.5 ms now; only if a slower target is measured. | `visual-performance.md` P4 |
| Cold-disk first load (155 s) | only if still a complaint | Hidden behind the pre-warm; shortening it means a cache-format change and a re-bake of the hosted assets. | `visual-performance.md` P5 |
| The Controls panel's ~200 px reserved blank on the default Sun | sketched, needs a 1440 + 390 jump check | Replace the fixed reservation with the one-line "Appears for…" note the other gated controls use. | `visual-performance.md` V1 |
| Row-height pairing in the two-column layout | idea | Short beside tall (Readout ↔ Controls, Spectrum ↔ SED); three options, screenshot each. | `visual-performance.md` V2 |

## Cross-cutting cautions (unchanged)

Every new axis multiplies the grid and the UI; prefer **toggles for discrete real axes**
and **views/overlays** over another slider, and keep spectrum-only axes visibly distinct
from evolution axes. Every entry is tiered by **what data backs it** (see
`science-hurdles.md`); the "don't label a non-feature" check comes first — measure that
the effect is visible and real through the runtime path before shipping a control for it.
