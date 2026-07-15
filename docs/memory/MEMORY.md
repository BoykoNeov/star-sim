# Memory index

One line per memory — enough to decide relevance. **Detail belongs in the topic
file, never here.** Architecture lives in `CLAUDE.md`; unbuilt work in the ROADMAP.

## The spine (§3) & providers
- [MISTProvider](star-sim-mist-provider.md) — the live provider: MIST v2.5, 2D (mass×[Fe/H]) EEP interpolation, blend-then-invert, non-rectangular domain, `.npz` parse cache.
- [Phase 4 MESAProvider](star-sim-phase4-mesa.md) — the second real provider (MESA `history.data`), snap-to-nearest, opt-in; the measured MESA-vs-MIST cross-validation.
- [Init scope](star-sim-init-scope.md) — what init delivered: the §3 provider spine, stub limits (historical).
- [Composition panel](star-sim-composition-panel.md) — §5.4 panel + `/track`: EEP-axis stacked areas, `_state_from_row`.
- [Phase 4 CNO](star-sim-phase4-cno.md) — per-element composition via `metals_surf`/`metals_core` dicts; element gotchas (Fe diffusion, boron, Cr/Mn/Ni absent).
- [Rotation & subpopulation atlas](star-sim-rotation-subpop-atlas.md) — the `vvcrit` axis: provider keys by `(feh,vvcrit)` + snaps buckets, `rotation_status` gate, real `v_rot_kms`, v sin i broadening, the Coelho [α/Fe] spectral axis.

## Fates (endgame)
- [WR/WD endgame](star-sim-wr-wd-endgame-plan.md) — the reversible gateway: `endgame()` + classifier, WD cooling scrub/shader, WR mode + wind shader, Koester/TMAP/PoWR spectra. No new provider — an endgame IS a StellarState.
- [SN + NS/BH endgame](star-sim-supernova-remnant-endgame.md) — core-collapse: a hybrid (classify on the spine, compute in `supernova.py`). ⁵⁶Ni light curve, fireball→remnant, onion, fallback continuum. Type II only.

## Siblings
- [Real interior structure (MESA)](star-sim-interior-structure-mesa.md) — `structure.py` + `/structure`: real MESA radial profiles, canonical (not fitted) polytrope overlays, the interior regimes + the partial 2D (mass×[Fe/H]) grid.
- [Phase 3 Lane–Emden](star-sim-phase3-lane-emden.md) — the §8 polytrope panel: sibling not provider, `/polytrope`, DOP853+θ=0 event.
- [Phase 5 spectra](star-sim-phase5-spectra.md) — the synthetic-spectrum panel: MSG/pymsg bake → `spectra.py` runtime + `/spectrum`; the SED panel. Recipe `backend/docs/msg_spectra_build_recipe.md`.
- [Binary-stripped stars](star-sim-binary-stripped.md) — `binary.py` + `/binary` (Götberg He-star, the ~70% WR channel), Roche geometry, the POSYDON two-star co-evolution movie.
- [CO-HMS_RLO compact-object binary](star-sim-co-hms-rlo.md) — `posydon_co.py` + `/co_binary_track`, parameterized by `kind`; the DCO/GW-progenitor classifier and the Eddington accretion-cue gating.
- [Coeval-ensemble overlay (BPASS)](star-sim-coeval-ensemble-bpass.md) — the first ENSEMBLE sibling: `bpass.py` + `/population` + `/population_hrd`, single-star vs +binaries.
- [Non-thermal SED](star-sim-nonthermal-sed-plan.md) — coronal X-ray + Güdel–Benz radio + the hot-star wind free–free excess; the spine touch `mdot_msun_yr`.

## The outward quartet
- [Observer's view / CMD (Axis A)](star-sim-observer-cmd.md) — `photometry.py` + `/photometry` + `/photometry_track`: distance + CCM89 extinction + synthetic mags → the observational (B−V, M_V) CMD panel (`cmd.js`).
- [Isochrone / cluster overlay (Axis B)](star-sim-isochrone-cluster.md) — `isochrone.py` + `/isochrone`: all masses at ONE age, the MS turnoff ringed (the age clock), the decoupled cluster-age slider.
- [Asteroseismology (Axis C)](star-sim-asteroseismology.md) — `seismo.js`: the seismic scaling relations → a schematic power spectrum + échelle diagram. Frontend-only.
- [Habitable-zone band (Axis D)](star-sim-habitable-zone.md) — `hz.js`/`scale.js` band + `hzhist.js` history panel (the hockey stick, CHZ annulus, Earth-exit deadline). Kopparapu 2014. Frontend-only.

## What-if overlays
- [Initial-helium (Y) overlay](star-sim-helium-overlay.md) — the globular-cluster 2nd-gen what-if (Y≈0.40 vs 0.27 → hotter/brighter/shorter). `helium.py` + `/helium`, MESA-vs-MESA only.
- [α-enhanced (equivalent-Z) overlay](star-sim-alpha-overlay.md) — the old-population [α/Fe] what-if (opposite sign to He). `alpha.py` + `/alpha`; collapsed to a Z-only change (Salaris 1993).
- [Ap/Bp peculiarity](star-sim-apbp-peculiarity.md) — evocative 3D what-if: co-rotating abundance spots on an oblique dipole. Frontend-only, byte-identical when off.
- [Gravity darkening](star-sim-gravity-darkening.md) — oblateness + pole-hot/equator-cool gradient for fast rotators; the inclination slider. Off the spine, frontend-only.

## Frontend & UX
- [Frontend UX](star-sim-frontend-ux.md) — the big one: age-window single-source, hover pedagogy, the visual passes, and the layout/anti-jump reservation discipline.
- [Draggable/responsive panels](star-sim-draggable-responsive-panels.md) — the dashboard: `layout.js` reorder-in-flow sortable, responsive canvases, the fitCanvas inline-width gotcha.
- [Phase 2 shaders](star-sim-phase2-shaders.md) — §7 beauty: Planck→CIE color, granulation, limb darkening, corona quad; the moiré fix.
- [True-size scale bar](star-sim-true-size-scale-bar.md) — `scale.js` log scale bar + the 3D star's tangent-cone clip math.
- [Instability-strip overlay](star-sim-instability-strip-overlay.md) — the opt-in variable-star-zones HR overlay; the first "show a subpopulation" feature.
- [Tooltip singleton](star-sim-tooltip-singleton.md) — one body-mounted `position:fixed` tooltip layer (`tooltip.js`) replacing clipping CSS hovers.
- [UX four fixes](star-sim-ux-four-fixes.md) — range quantization → source-of-truth values; SED X-ray gap marker; toggle-without-resize; `classify.js` MK type.
- [Age-tick fixes](star-sim-ux-age-tick-fixes.md) — five age-slider landmark-tick bugs (quantization, dedup, endpoint snap, label stagger, phone MIN_GAP).
- [Nine UX fixes](star-sim-ux-nine-fixes.md) — HR auto-fit; endgame quick-wins; the readout panel; the `/endgame?meta=1` fast-path; the linear-in-EEP age remap.

## Project & process
- [Hosted data assets](star-sim-hosted-data-assets.md) — the pre-baked GitHub Release tags and what each holds; which MESA output is hosted vs excluded; the adding-buckets test hazard.
- [Roadmap (future-work index)](../plans/ROADMAP.md) — the canonical index of everything proposed-but-unbuilt. Update this, not a second list.
- [GitHub repo](star-sim-github-repo.md) — public repo location + how it was created.
- [Always commit and push](always-commit-push.md) — standing preference: finish substantive changes by committing AND pushing unprompted.
- [Session-end ritual](session-end-ritual.md) — at batch/session end: update memory + docs, commit, push.
