---
name: star-sim-init-scope
description: "Star Simulator — what \"init\" delivered, the non-negotiable architecture, and the next step"
metadata: 
  node_type: memory
  type: project
  originSessionId: 290b20fd-ed39-4580-b346-d5530ca27a5e
---

Star Simulator (M:\claud_projects\star-sim): interactive stellar simulator,
goals are teaching AND beauty. Full design in `STAR_SIM_SPEC.md`; operational
notes in `CLAUDE.md`.

Initialization (2026-06-20) scope was deliberately **foundation + the §3
spine + a runnable end-to-end stub**, NOT a MIST-backed Phase 0. Delivered:
StellarState dataclass + StellarStateProvider Protocol, a `StubProvider` (no
external data, Sun-anchored at 1 M☉), FastAPI (`/state /ranges /age_range
/health`, payload = exactly StellarState), a Three.js+canvas frontend shell,
pytest §10 sanity checks. One initial commit on `main`.

**Non-negotiable (spec §3):** everything is a function of one StellarState,
produced only through the provider interface; no consumer may import provider
internals. The single provider-swap point is `PROVIDER` in `backend/star_sim/api.py`.

**Two known, intentional limits of the stub:** (1) structure (L/Teff/R) depends
on mass & [Fe/H] only, so the **age scrubber is visually inert** — only the mass
slider transforms the star; the spec's "marker walks the track over age" is not
demonstrated yet. (2) Frontend was verified as *served* (HTTP 200, correct
content-types) and JS syntax-checked, but **not browser-render-confirmed**.

**Next step (DONE 2026-06-20):** `MISTProvider` landed — see
[[star-sim-mist-provider]]. Then Phase 1 (2D [Fe/H] EEP interpolation —
interpolate on EEP, never age) and Phase 2 (shader beauty). See
[[star-sim-stack-notes]].

Env: Python 3.14.3, node v24, venv at `backend/.venv` (editable install with
`[dev]`). numpy/scipy installed but not yet used (reserved for MISTProvider).
