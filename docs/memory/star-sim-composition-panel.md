---
name: star-sim-composition-panel
description: "Star Simulator §5.4 composition panel + /track endpoint — EEP-axis stacked areas, track returns list[StellarState], one endpoint also feeds the HR track."
metadata: 
  node_type: memory
  type: project
  originSessionId: 94685f81-1c81-42b7-a3d4-96bca8d7979b
---

The §5.4 composition panel landed (Phase 1). Frontend `frontend/src/comp.js`,
backend `track(mass, feh)` provider method + `/track` endpoint.

Key decisions (non-obvious, worth not re-litigating):

- **x-axis = EEP, NOT linear age.** The teaching payoff — core H converting to
  He as the star leaves the MS — happens near TAMS; on a linear-age axis the MS
  eats ~90% of the width and that transition is an invisible sliver. EEP gives
  even phase spacing. Verified: core H 0.71→0 across MS→RGB renders as a clean
  curve.
- **`/track` returns `list[StellarState]`** (same §3 dataclass, ordered by EEP),
  never the provider's internal interp window — leaking its `logL`/`Xs` keys
  would be the §3 boundary bug. The §3 spine applies to the track too. See
  [[star-sim-mist-provider]].
- **Track is age-independent:** fetched only on mass/[Fe/H] change (its own
  latest-wins token in `main.js`); the marker moves on age scrub. The fetch reads
  `massFromSlider()` *after* the dead-corner clamp, so super-solar [Fe/H] requests
  the track at the clamped mass floor, not the raw slider value.
- **One endpoint, two consumers:** the same `/track` draws the HR diagram's
  full-track polyline (§5.2, which was a standing TODO) — `hr.js` and `comp.js`
  share a `setTrack()`/`update()` split.
- Provider `state_at` and `track` share one `_state_from_row(win, frac, ...)`
  helper so the marker and the track can't disagree; the unchanged Sun anchor
  (L≈1.07, Teff≈5834) proves the refactor preserved `state_at`.

Layout: frontend `main` grid is now 2×2 (star | HR / composition | controls).

**Why:** these are the design forks an advisor resolved and a future session
shouldn't silently undo (esp. the EEP axis and the list[StellarState] boundary).
**How to apply:** when extending the panel (per-element abundances, more phases)
or adding new track consumers, keep `/track` returning StellarStates and keep the
EEP axis.
