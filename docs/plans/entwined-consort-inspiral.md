# Plan: The co-evolved binary — both stars on the HR through time (POSYDON)

## Status: Chunks 4a & 4b BUILT — the two-star TIME render is live. 310 pytest.

**Chunk 4b, as built (2026-07-07) — a deeper reveal INSIDE stripped-mode (mode stays
`"stripped"` throughout, mirroring the WD thermal-pulse showcase's sub-view pattern), not a
new top-level mode:**
- **Entry:** three CURATED demo systems (the plan's de-risking choice, not free q/P
  sliders yet) — SAME donor (M1=8.83, q=0.6), only the initial period differs, so the
  outcome contrast is purely "how close did they start": P=0.1 d → merger, P=3.73 d → the
  Gate-0 stripped+companion system, P=5179 d → detached. A "Co-evolve the system through
  time" button row in the endgame bar (visible whenever stripped-mode is active) fetches
  `/binary_track` once and enters `binaryView` (a JS flag, `body.binary-view` CSS class);
  a "← Back to the snapshot" button returns to the plain single-state donor view without
  leaving stripped-mode. The mass/[Fe/H] sliders are DISABLED while a demo is live (POSYDON's
  grid is independent of the MIST progenitor axes this demo isn't keyed on) — the main
  "← Back to the living star" button still fully exits, same as every other endgame.
- **The age slider becomes a system-time scrubber**, plain index-linear over the pre-fetched
  steps (the WR sub-track idiom — no fetch per frame, every row gets equal travel).
- **HR (`hr.js` `setBinaryTrack`/`updateBinaryIndex`/`clearBinaryTrack`):** a genuinely new
  drawing mode (`binaryMode`, checked before `endgameMode`) — BOTH stars' full tracks drawn
  Teff-colored with an independent past/future split at the scrubbed index (star_2's array
  may run shorter after a merger — truncated at the first null, never filtered, so index
  alignment with star_1 holds), both live markers labeled by FIXED IDENTITY ("donor"/
  "companion", never by which currently masses more — the reversal is the markers crossing,
  not a relabel). Axes auto-fit the WHOLE movie (both full tracks), unlike `setEndgame`'s
  marker-relative fit.
- **The Roche panel goes LIVE (`roche.js` new `drawLive`, alongside the untouched Chunk-3
  `drawPanel`):** per-step geometry from the track's REAL q(t)=m2_current/m1_current and
  separation(t) — a backend addition, `binary.track_roche_geometry` (see below), was
  needed for this (the plan's advisor-flagged "genuine architectural fork," not deferred).
  Two real upgrades over the static snapshot: (1) BOTH stars have a real modelled Teff/R at
  every step (no "unknown donor temperature" gap), so both draw as real Teff-colored discs
  always; (2) whichever star `mt_state` flags as CURRENTLY overflowing (RLOF1→donor,
  RLOF2→companion, contact→both) gets its lobe filled (translucent, its own color) + the
  stream — the other stays an unfilled outline. Measured gotcha kept honest in the caption:
  the real photospheric radius does NOT itself cross the lobe outline during RLOF (Roche
  overflow is a local excess at L1, not a whole-photosphere inflation past the mean lobe
  radius) — the fill is a labeled schematic "transferring now" cue, not a naive
  radius-vs-lobe comparison.
- **3D:** free — `star.update(s1, {companion: s2})` is the EXACT Chunk-2 companion call,
  now driven every scrub frame instead of once; both spheres evolve with zero star.js changes.
- **Advisor catch (a false-data leak, fixed before commit):** comp/spectrum/sed/structure
  are NOT wired to the per-step scrub (they'd stay frozen at whatever the Götberg stripped
  SNAPSHOT painted on stripped-mode entry) — unlike Chunk 2's fully-static stripped-mode,
  here the HR/3D/Roche panels visibly animate right beside them, so a frozen panel (e.g.
  comp showing the snapshot's He-rich surface next to an HR donor marker that starts
  H-rich) would read as stale AND misleading. Fixed by hiding all four via CSS
  (`body.binary-view .comp-panel, .spectrum-panel, .sed-panel, .structure-panel {
  display:none }`) — auto-reverts on exit, no JS needed, mirrors the roche-panel
  mode-hidden precedent. Verified round-trip: hidden on entry, reappear with the
  snapshot's real content on "Back to the snapshot."
- **Backend addition (`binary.py`):** the Chunk-3 `roche_geometry` engine was refactored
  into a pure `_roche_geometry_from_params(q, m1, m2, separation_rsun, n_samples)` (donor at
  origin, companion at (1,0), generalizes past the fixed q=0.8 CSV case — verified sane
  across q∈[0.1,9]) plus a new `track_roche_geometry(steps)` that calls it per POSYDON step
  at a DECIMATED angular resolution (40 vs the CSV path's 160 samples — measured ~2ms/step
  vs ~14ms/step, keeping a 271-step track fetch under ~1s). `posydon.py` imports
  `track_roche_geometry` from `binary.py` (a sibling calling a sibling, mirroring
  `structure.py`'s import of `lane_emden.solve_lane_emden` — no PROVIDER involved, so this
  doesn't violate §3) and folds a `roche` block into every `/binary_track` step. No
  `BAKE_VERSION`/`CACHE_VERSION` bump — computed at request time from already-baked columns.
  **4 new tests** in `test_binary.py` (duck-typed synthetic steps: matches the single-node
  engine at the same params, donor/companion lobe sizes swap across a synthetic reversal,
  `None` on a degenerate step) + **2 new tests** in `test_posydon.py` (the Gate-0 track's
  real lobes reshape + swap dominance through the real runtime; the `/binary_track` route
  carries a non-null `roche` block on every step). **310 pytest total.**
- Playwright-verified at 1440×1000 and 390×844 (phone width): the full flow (enter →
  scrub → markers cross in the Case-B demo → Roche lobes reshape/fill through a real
  detached→RLOF1→detached sequence → back to snapshot → re-enter a different demo → full
  exit) — zero console errors, no layout breakage, demo row stacks cleanly at phone width.
- **Chunk 4c (optional follow-ons, unbuilt)** unchanged from below: richer outcomes
  (common envelope / merger physics / compact-object channels), more metallicities, a
  population overlay. Free q/P sliders (vs. the three curated demos) are also a natural
  next increment if the curated set proves too narrow.

## Original design status (superseded by the above; kept for the Chunk 4b architecture)

**Chunk 4a, as built (2026-07-07) — corrections to this doc's original guesses, measured
against the real data:**
- The user landed ALL 8 metallicity tarballs + auxiliary (~84 GB) under `data/Posydon/`
  (not just one, as this doc assumed) — so the other 7 are available on disk for later
  chunks without another download, even though only solar is extracted + baked so far.
- **The raw grid HDF5 is already per-run** (`grid/run<i>/{binary_history,history1,
  history2}`), NOT POSYDON's packed `PSyGrid` format §"the architectural shift" worried
  about — so `scripts/bake_posydon.py` reads it directly with plain h5py, no host-side
  POSYDON-loader demux step was needed at all.
- **No eccentricity column** (HMS-HMS is tidally circularized) and **composition is C/N/O
  only** (not the full MIST 16-metal breakdown) — both real gaps vs this doc's schema
  guess, now baked in as documented honesty gaps (`BinaryStep.ecc` is a labeled 0.0;
  `metals_surf`/`metals_core` are 3-key partial dicts).
- **Gate 0 is CLOSED**, measured through the real runtime (`test_posydon.py`, the demo
  system M1=8.83/q=0.6/P=3.73 d, POSYDON's own `run86`): the mass ordering crosses at
  step 16/271 (donor 8.83→1.07 M☉, companion 5.30→5.94 M☉ — the Algol reversal live),
  the period widens 3.73→6.94 d as the separation grows 24.4→29.3 R☉, and `mt_state`
  fires a real detached→RLOF1→detached sequence, `outcome="stripped + companion"`.
- Built: `scripts/bake_posydon.py` (host-side h5py bake: filters `not_converged` +
  missing/misaligned-history runs, verifies the run↔`initial_values` index identity,
  decimates tracks >300 rows, writes a flat CSR-style `.npz` — 33,121 tracks / 1.48M rows
  / 142 MB from the 4.79 GB solar HMS-HMS grid); `star_sim/posydon.py` (the runtime
  sibling — zero h5py/POSYDON imports, snaps (M1,q,P,[Fe/H]) in normalized log-M1/log-P/
  linear-q space to the nearest track, builds `BinaryStep`/`BinaryTrack`); `/binary_track`
  + `/binary_track_meta` routes (bypass `PROVIDER`, snap-always, 422 only on structurally
  invalid input, 503 if unbaked); `requires_posydon_data` + 15 tests in `test_posydon.py`.
- **Next = Chunk 4b** (the two-star time render, frontend) — unchanged from the design
  below, now unblocked.

## Original design status (superseded by the above; kept for the Chunk 4b architecture)

DESIGN ONLY (no build, no data) at the time this was written. The recon is done (POSYDON, not BPASS); this is the architecture for the build, drafted so it executes fast once a data slice lands.

This is **path (b) Chunk 4** of the binary-stripped-star arc (`stripped-consort-unveiling.md`).
Chunks 1–3 built the companion on the HR, the 3D companion sphere, and the Roche / mass-
transfer geometry — all off the Götberg **snapshot** grid (one representative state per
stripped star). The one thing a snapshot cannot give is the payoff this chunk targets:
**both stars co-evolving on the HR *through time* — a real inspiral, mass transfer as it
happens, the Algol reversal as a movie, not a caption.** That needs a real binary grid.

## Recon result (measured 2026-07-06; see stripped-consort-unveiling.md Chunk 4)

- **POSYDON is the target** (Fragos+2023; v2 Andrews+2024): individual **co-evolved binary
  tracks** — detailed MESA-binary runs, HDF5, the full time history of BOTH stars + the
  orbit (`history1` / `history2` / `binary_history`, `final_profile1/2`, `initial/final_values`;
  columns off `dtype.names`). Zenodo DR2, DOI 10.5281/zenodo.15194708, code v2.0.0, **CC-BY**.
  8 metallicities, one ~10 GB tarball each (gitignored, never committed), 2 single + 5 binary
  grids per Z. The relevant grid is **HMS-HMS**; axes per track: **M1, q = M2/M1, P** at the
  grid Z (a 2D-in-(q,P) fan per M1).
- **BPASS is NOT this** (population synthesis — integrated SEDs, not tracks): a separate
  future thread (a population-spectrum sibling), out of scope here.
- **`fetch_posydon.py` is BUILT** (recipe + h5py validator, a host-side USER handoff). It
  prints the REAL HDF5 schema once a slice is extracted — the parser below is designed
  against the documented keys but **must be validated against that output before coding**,
  never hardcoded blind (the Gotberg-transcription / boron-b8 discipline).

## The architectural shift — the first TIME-SERIES, TWO-BODY sibling

Every sibling so far (`binary.py`, `supernova.py`, `structure.py`, `spectra.py`,
`lane_emden.py`) snaps to **one** representative state, or a single-star track. A POSYDON
track is a **time series of a two-body system**: at each timestep, two stars + an orbit.
That breaks the single-state mold in two ways the design must own:

1. **Two stars, not one.** A single-star `StellarState` cannot hold the companion or the
   orbit (§3). So a timestep is **two `StellarState`s** (star_1, star_2) + orbital scalars
   riding alongside — the exact pattern `/binary_pair` already uses for the companion, and
   `EndgameResult`/`StrippedStar` use for their off-state scalars. No `StellarState` change,
   no Protocol change (§3 held).
2. **A real time axis.** The frontend must scrub **system time** and watch both stars move.
   This is new: the age slider becomes a system-time scrubber (like the WD/WR/SN scrubbers,
   but driving a *two-star* paint), and the HR shows two markers tracing their tracks.

**A pure sibling — but "no POSYDON" is a RUNTIME rule, not an extraction rule (advisor
catch; do NOT assume bare-h5py per-track parsing until the schema is seen).** The recon
surfaced the tell: the raw Zenodo grid HDF5 is POSYDON's **`PSyGrid`** format — `oneline` +
`history` **packed** tables (ALL tracks concatenated). The clean `history1` / `history2` /
`binary_history` shape this doc maps against is **`PSyRunView`**, POSYDON's *code API* that
demuxes a single run out of that packed grid. So getting per-track, per-star histories with
bare h5py could mean reimplementing POSYDON's track-boundary indexing + its star_1/star_2/
binary column conventions — knowable only from the real file, possibly genuinely coupled to
the library. **The precedent that dissolves this is already in the repo — the MESA structure
sibling:** a heavy tool (Docker MESA) runs *host-side* to export flat `profile.data`
snapshots, and the runtime `structure.py` reads those flats with its own simple parser and
never imports MESA. Apply the same split:
- **Extraction (host-side, one-time — part of the `fetch_posydon.py` handoff):** use whatever
  the format needs, INCLUDING POSYDON's own `PSyGrid` loader (fine here — it is NOT a runtime
  dep), to export **flat per-track files** (CSV/npz: one file per (M1,q,P) track, with the
  star_1 / star_2 / orbit columns already demuxed) for the chosen slice.
- **Runtime (`posydon.py`):** reads those flat per-track files with its own simple parser —
  no POSYDON, no h5py-demux heroics. Imports only `state.StellarState` (+ stdlib/numpy);
  never `StellarStateProvider`. `/binary_track` bypasses `PROVIDER`.

The `fetch_posydon.py` validator already reveals which world we're in (it prints
`['oneline','history']` and won't find `history1` as a group if the grid is packed). **So the
parser section BRANCHES on that output** — if the extracted files are already per-run
(`PSyRunView`-style), bare h5py suffices; if packed (`PSyGrid`), the host-side loader does the
demux to flats first. Decide once the schema is seen; do not commit to either now.

## Data model (the shapes)

```
BinaryStep (one timestep):
  age_yr: float
  star_1: StellarState        # the initially-more-massive star (the eventual donor)
  star_2: StellarState        # the companion / accretor  (None after a merger)
  period_d: float             # orbital period (the binary_history column)
  separation_rsun: float      # orbital separation — the binary_separation column DIRECTLY
                              #   (it's in R☉); Kepler from (period, masses) only as a fallback
  ecc: float
  mt_state: str               # "detached" | "RLOF1" | "RLOF2" | "contact" | "CE" | "merged"
  mdot_msun_yr: float | None   # mass-transfer rate (real, from the track) when transferring

BinaryTrack (the snapped node):
  steps: list[BinaryStep]
  m1_init, q_init, p_init_d, feh    # the TRUE snapped grid node (never interpolated, §6)
  *_snapped_far flags + grid bounds  # honesty flags (the binary.py precedent)
  outcome: str                       # a data-derived end label: "stripped+MS" / "merger" /
                                     #   "compact-object binary" / "disrupted" …
```

`/binary_track?m1=&q=&p=&feh=` → the paired-state time series (JSON; each step's two
StellarStates as the §3 dict shape + the orbital scalars). `/binary_track_meta` → the grid
bounds (available M1 / q / P / Z ranges + node counts) to drive the UI gating, mirroring the
`/endgame?meta=1` fast-path precedent (don't ship the whole track just to gate a control).

## Mapping POSYDON columns → StellarState (validate against the real schema first)

Documented POSYDON `history{1,2}` columns map to `StellarState` like the MIST/MESA parsers:
`log_L`→L, `log_Teff`→Teff, `log_R`→R, `star_mass`→(current mass — a routing scalar, no home
on the state), `surface_h1`/`surface_he4`→X_surf/Y_surf, `center_*`→core fractions, `he_core_mass`
etc. → scalars. `binary_history`: `period_days`, `binary_separation`, `lg_mtransfer_rate`,
`rl_relative_overflow_1/2` (RLOF flags). **Caveats to bake in (the honesty discipline):**
- POSYDON history may not carry all 16 metals → `metals_surf` is an honest PARTIAL fill (or
  empty), never a fabricated breakdown (the boron-b8 rule).
- `star_mass` (current) has no home on `StellarState` (only `mass_init`) → routing scalar per
  step, exactly like `m_strip_msun` in `binary.py`.
- `mass_init_msun` on each state = the star's INITIAL mass (M1, or q·M1) — constant down the
  track; the changing mass is the routing scalar (the mass-transfer story).
- Merger/CE steps: `star_2` becomes `None` (merged) or the pair enters a CE flagged state —
  the frontend must render "one star" / "envelope" gracefully, not crash on a missing second.

## Measure-first gate (Gate 0 — BLOCKS the build, the project rule)

Before any control ships, verify through the REAL consumers that a POSYDON track shows
something visibly real AND distinct that the snapshot could not:
- the two markers **move** on the HR as system time scrubs, and **cross** (the Algol
  reversal happening — the donor swings blue-left and sub-luminous as it is stripped);
- the orbital period/separation **change** through the mass-transfer episode (the Roche
  lobes visibly tighten/reshape);
- the `mt_state` flags actually fire (a real detached→RLOF→detached sequence exists in the
  slice), so the live Roche stream turns on only during transfer.
If a track just looks like two independent single stars evolving side by side, stop — the
interaction is the whole feature. (Physics says it's dramatic; this is the discipline gate.)

## Chunked build (each chunk measured + Playwright-verified, the project cadence)

### Chunk 4a — data + parser vertical (backend), SOLAR-FIRST
- USER lands one metallicity's HMS-HMS slice (`fetch_posydon.py` recipe) → run the validator
  → **read the real schema** and pin the column mapping + the extraction-vs-runtime split
  (packed `PSyGrid` → host-side demux to flat per-track files; per-run already → bare parse).
- `posydon.py`: reads the flat per-track files (own parser, no POSYDON); `binary_track(m1, q,
  p, feh)` snaps (M1,q,P,Z)→nearest track
  (never interpolate — §6; a 4D nearest-node in a normalized metric, report the true node) →
  `BinaryTrack` of `BinaryStep`s. Downsample/decimate rows if a track is large (keep the RLOF
  episode dense). Data-derived `outcome` + `mt_state` from the real flags.
- `/binary_track` + `/binary_track_meta` routes (bypass PROVIDER; snap-always + in-band
  snapped-far flags, the `/binary` precedent; 422 only structurally-invalid input).
- `test_posydon.py` (gated `requires_posydon_data`): parse; snap honesty (returned node is a
  true grid node); both states valid §3 `StellarState`s; the **Gate-0 measure** as a
  regression (the reversal / orbit-change / RLOF-fires through the route); merger/CE handled.

### Chunk 4b — the two-star TIME render (frontend)
- A system-time scrubber: the age slider drives the `BinaryStep` index (like the WD/WR/SN
  scrubs pick by index), painting BOTH stars per step.
- **HR co-evolution:** both markers trace their tracks as time scrubs (reuse `hr.setCompanion`
  + the living-track machinery; now both move, and a faint past-trail shows where each has
  been). The reversal is the two markers crossing in mass-ordering — LIVE, not a caption.
- **The Roche panel goes LIVE (the Chunk-3 payoff pays off twice):** recompute the lobes per
  step from the track's real q(t) and a(t) — watch the donor swell to fill its lobe, the
  stream switch on only during `mt_state∈{RLOF1,RLOF2}`, the orbit tighten. `roche.js` already
  draws from a pushed geometry block; here the block is per-step, real, and animated.
- **3D:** both spheres evolve (Teff/size per step). Separation stays schematic (caption-owned,
  the Chunk-2 precedent) OR tracks real a(t) on a log scale as a stretch goal.
- **New controls:** q and P sliders (the two axes POSYDON adds beyond the single-star mass) —
  OR, to de-risk the UI, start with a curated set of DEMO SYSTEMS (a few (M1,q,P) that show
  the cleanest stripping / merger / wide-binary outcomes) and add free sliders later.
- Entry point (settle with an advisor consult, the Chunk-2 precedent): most likely a deeper
  reveal inside stripped-mode ("Co-evolve the system" — the snapshot → the movie) rather than
  a whole new top-level mode, so it composes with the existing companion machinery.

### Chunk 4c — OPTIONAL follow-ons (recorded so they're not re-proposed as "the build")
- Richer mass-transfer outcomes: common envelope, merger, second RLOF, the compact-object
  channels (the CO-HMS / CO-HeMS grids) → a binary that ends as an X-ray binary / a GW
  progenitor (ties to the SN/remnant arc).
- More metallicities (drop-in per-Z tarballs, the multi-Z-by-snapping precedent).
- A population overlay (this is where BPASS would legitimately enter, as a SEPARATE sibling).

## Open questions (settle as they come up — several need the real data)
1. **Grid granularity** — how many M1/q/P nodes per Z, and how many time rows per track
   (enough for a smooth scrub)? The validator answers both; it decides snap coarseness + UI.
2. **Payload size** — 2 stars × N rows × full StellarState could be heavy; decimate rows +
   trim columns for the frontend (the frontend needs L/Teff/R/mass/X/Y per marker, not the
   full 16-metal dict). Mirror how `/track` already ships a compact per-row state.
3. **Entry UX** — deeper-reveal-in-stripped-mode vs a new top-level "Binary system" mode
   (needs the new q/P controls either way). Advisor consult at Chunk 4b.
4. **Merger/CE rendering** — how the two-star render degrades to one star (merger) or a
   shared envelope (CE) without reading as a bug.
5. **Which M1 range** — the HMS-HMS grid spans a wide M1; the stripped/WR story lives at the
   intermediate/massive end (matches the Götberg 2–18 M☉), a natural first slice.

## Honesty tiering (the project rule, applied)
- **Tier 1/2 (real, measured):** both stars' L/Teff/R/composition vs time, the orbital
  period/separation vs time, the RLOF timing + mass-transfer rate — all straight from the
  POSYDON MESA-binary track. The Algol reversal, the orbit tightening, the stripping are all
  *measured*, not narrated.
- **Schematic (caption-owned, the established precedents):** the Roche mass-transfer STREAM
  shape (but its ON/OFF and the lobe sizes are now real); the 3D side-by-side separation
  (unless a(t) is drawn); any illustrative inspiral easing.
- **Gate 0 first:** visible-and-real through the runtime before any control ships.

## References
POSYDON: Fragos et al. 2023 (ApJS 264, 45); Andrews et al. 2024 (POSYDON v2). Data: Zenodo
10.5281/zenodo.15194708 (DR2, CC-BY). Binary interaction / Algol: Paczyński 1967; Sana+2012.
Stripped endpoint (path (a), the snapshot this animates): Götberg+2018. See also
`stripped-consort-unveiling.md` (the parent arc) and `whirling-cohort-atlas.md` (Tier-D
binarity, where BPASS-as-population-sibling would live).
