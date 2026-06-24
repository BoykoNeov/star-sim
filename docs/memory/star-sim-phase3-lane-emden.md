---
name: star-sim-phase3-lane-emden
description: "Phase 3 §8 Lane–Emden interior panel — static polytrope solver, sibling to the §3 spine (not a provider), /polytrope endpoint, closed-form + Chandrasekhar validation, self-contained frontend panel."
metadata: 
  node_type: memory
  type: project
  originSessionId: 84a638c1-4a3b-42df-b449-95dd38526bd4
---

Phase 3 of the Star Simulator (spec §8) is **complete**: the Lane–Emden
interior-structure panel — a live-computed **static polytrope** (`P = K ρ^(1+1/n)`),
a teaching piece, explicitly **not** evolution.

**The architecture call that defines it:** Lane–Emden is a **sibling to the §3
StellarState spine, NOT a provider and NOT a `StellarState`.** The spec says it is
"never the evolution engine," so it does not route through `StellarStateProvider`.
`/polytrope?n=` is the one API route that does **not** touch `PROVIDER`. The
frontend panel is driven by the polytropic index `n` alone — decoupled from
mass/[Fe/H]/age. (Advisor confirmed this decisively; see [[star-sim-mist-provider]]
for the spine it sits beside.)

**Backend** (`backend/star_sim/lane_emden.py`): integrates θ″+(2/ξ)θ′=−θⁿ with a
series start off the ξ=0 singularity (θ≈1−ξ²/6+nξ⁴/120), `solve_ivp` DOP853
(rtol 1e-10), a **terminal event at θ=0** locating ξ₁, and `f=−max(θ,0)ⁿ` clamping
in the RHS (a non-integer power of a trial-point-negative θ is NaN, which poisons
the step — this clamp is mandatory, not optional). Returns a bounded profile
(ξ, θ, ρ/ρc=θⁿ) + ξ₁ + the Chandrasekhar mass invariant −ξ₁²θ′(ξ₁).

**Validation is the point** (`test_lane_emden.py`, no MIST data → always runs):
closed forms n=0 (ξ₁=√6, −ξ₁²θ′=2√6), n=1 (π, π), n=5 (no finite surface) checked
**pointwise across the whole domain** AND both invariants — a weak integrator can
hit ξ₁ while the profile is subtly wrong. Chandrasekhar (1939) Table 4
n=1.5/2/3/4 are **secondary cross-checks** with looser tol + a source comment
(recited digits mustn't impersonate an integrator bug). All passed first run.

**Two honesty fixes baked in:**
- Search cap is **ξ=100** (not 50). ξ₁ diverges as n→5 (n=4.5→31.8, n=4.7→54.8,
  n≈4.85+→genuinely none). A 50-cap would mislabel n=4.7's *real* surface as "no
  finite surface" — a reachable falsehood on the slider.
  `test_high_n_finite_surface_found_past_old_cap` guards it. No-surface case (n≥5)
  plots against **raw ξ** out to a readable 20 (decoupled from the search cap).
- **Auto-deriving n from the star was rejected as dishonest**: MIST gives no
  convective/radiative split, so drawing an inferred n as "the star's interior"
  fakes a fit. n is the user's to set; presets carry the physics as *labels*
  (n=1.5≈fully convective + non-rel degenerate, n=3≈Eddington standard
  model/radiative core).

**Frontend** (`frontend/src/lane.js`): self-contained — own n-slider (snap presets
0/1/1.5/3/5), own debounced latest-wins fetch, **never wired into `refresh()`**.
`main.js` just calls `createLane({api})`. Plots **ρ/ρc=θⁿ prominently** (the §8
payoff: central concentration ρc/ρ̄ jumps 1→54 from n=0→3) + θ fainter; x = r/R =
ξ/ξ₁; readout shows ξ₁, −ξ₁²θ′(ξ₁), ρc/ρ̄. Full-width third row under the 2×2
(`grid-column:1/-1`). No JS test harness — verified via headless SwiftShader
screenshots (n=0/1.5/3/4.7/5); the pytest suite is the real gate. See
[[star-sim-phase2-shaders]] for the same screenshot-as-regression convention.

**Next:** Phase 4+ (optional deeper science behind the §3 interface — MESAProvider,
per-element composition, eventually a live solver / nuclear network; spec §9).
