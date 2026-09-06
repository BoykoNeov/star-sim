---
name: star-sim-dco-endpoint-view
description: Chunk 2d — the render half of the double-compact-object channel: the scrub frame past the last living step where the collapsed He star and its compact companion are finally DRAWN. The measured scale wall (objects are 1.7e-9..6.3e-6 of the separation, so nothing can be to scale), the pre-collapse-orbit honesty limit, the Blaauw kick-free unbinding gate (935/66,599 = 1.40% refused), and the two defects only the real runtime caught (an unlandable 0.4% slot; a tick label dropped by MIN_GAP then colliding with the right-anchor).
metadata:
  type: project
---

Built 2026-09-06. The DCO channel had shipped in July 2026 with a classifier and a
one-line caption ("BH + BH merger progenitor") and **no picture at all**; the scrub
stopped at the last living step. This is the frame past it.

## What the data allows, and what it does not

**Gate 0 killed the obvious render.** Measured over both He grids: the larger of the two
compact objects is **1.7e-9 to 6.3e-6 of the orbital separation** — sub-pixel by six orders
of magnitude. A to-scale pair is impossible, so both bodies use the fixed-pixel schematic
glyph the accretor already had, and `size_over_separation` is served so the caption can
quote the measured ratio instead of saying "tiny". The repo already had the right wording
for this at `roche.js` (the Chunk-1b point-mass caption) — inherited, not reinvented.

**The orbit drawn is the PRE-collapse one.** POSYDON follows the binary to the collapse and
stops. The supernova then moves the orbit through mass loss *and* a natal kick, and the kick
is a prescription this grid does not serve. So the endpoint reuses the LAST STEP's own Roche
geometry — which also keeps the separation, lobe shapes and scale bar continuous with the
frame the scrub just left, so the only visible change is the star becoming a point. No
merger time, for the same reason. [[star-sim-co-hms-rlo]]

**The lobes stay, empty and dashed.** Not a leftover: the Roche potential is a two-point-mass
construction, so this is the one configuration where it is exact rather than approximate.
Nothing is near filling them, and the caption says both halves of that.

## The one gate, and why it is a gate and not a payoff

Symmetric mass loss unbinds a circular orbit once the ejected mass passes half the system
total (Blaauw 1961). That needs **no kick model** — it is the kick-FREE, most optimistic
case — so a track failing it is one the model's own numbers say does not survive as a pair,
whatever the kick does. Those keep the classifier's label and lose the frame.

**Measured over all 66,599 DCO tracks (both He grids x all 8 metallicity buckets): 935 fail
(1.40 %), worst ejected fraction 0.78 at [Fe/H] = -4.0** — concentrated at low Z, e.g. a
192 M☉ He star leaving a 13.3 M☉ BH beside a 2.4 M☉ NS. Rare but reachable through the UI's
own metallicity picker, so the note names the reason rather than leaving an unexplained gap.

**The advisor's steer, kept:** surface only the boolean. `a_f/a_i` and the eccentricity are
the merger-clock feature the user explicitly did NOT pick; computing them here would have
been scope creep wearing an honesty costume.

## Two defects only the served runtime caught

Both are the recurring "plausible but wrong" class, and neither is reachable by a unit test.

1. **The endpoint was 1 slot in ~250** — 0.4 % of the slider, practically unlandable by drag.
   The feature's whole payoff cannot be the hardest position to reach. It now owns a
   deliberate share of the travel (`CO_ENDPOINT_SHARE`), with the track linear in step index
   within the rest.
2. **The share value is not free.** At 0.08 the frame worked but its tick label *silently
   vanished* — `buildTickStrip` drops any label within `MIN_GAP = 0.11`. At 0.14 the label
   returned but **collided on screen**, because that helper right-ANCHORS a label past 0.9,
   so "after collapse" hangs left from the end while "end" sits centred just before it.
   **0.20** clears both. Each was found by looking at the rendered strip, not the numbers.

## Shape

- Backend `posydon_co.py`: `DcoEndpoint` + the pure `dco_endpoint()`, kept **separate** from
  `dco_classification` — that answers a physics verdict, this answers "what does the picture
  need", and a render concern must never be able to change the verdict. Returns None for
  `not is_dco`, so the WD/unresolved branches draw nothing rather than a hedged pair.
- **A BH radius is derived, a NS radius is not.** Schwarzschild follows from the mass; ~12 km
  is EOS-dependent. `*_radius_assumed` keeps them apart and the caption branches on it.
- **No re-bake** — `binary_separation`/`period_days` were already in the npz.
  `BAKE_VERSION_CO` untouched.
- Frontend: `roche.drawDcoEndpoint()` (new entry point; every sibling entry point clears the
  mode so a scrub back strands nothing), a second glyph mesh + `dcoPair` branch in `star.js`
  (its own material — uType is per-material, and the pair is routinely mixed), and the
  living-only teardown at the endpoint (no HR marker via an index one PAST the end, no
  surface composition via a third body class).
- Tests: 6 pure + 5 gated in `test_posydon_co_he.py`, including the MIN_GAP-independent
  invariants (endpoint presence tracks the classifier exactly; the orbit IS the last row;
  the Blaauw boundary from both sides) and the in-situ check that the unbound branch is
  both **reachable** and **rare** — a gate that can never fire is dead code in an honesty
  costume. 87 pytest in the two CO modules.
