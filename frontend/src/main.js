// Orchestration for the Phase 0 shell.
//
// The spine in action (STAR_SIM_SPEC.md §3 & §5): controls -> fetch one
// StellarState from the backend -> every panel re-renders from that single
// object. No panel knows what produced it.

import { createStar } from "./star.js";
import { createScale } from "./scale.js";
import { createHR } from "./hr.js";
import { createComp } from "./comp.js";
import { createLane } from "./lane.js";
import { createStructure } from "./structure.js";
import { createSpectrum } from "./spectrum.js";
import { createSED } from "./sed.js";
import { createClassification } from "./classify.js";
import { makeSortable } from "./layout.js";
import { initTooltips } from "./tooltip.js";
import { teffToCSS } from "./color.js";
import { OBSERVED_SNE } from "./sn.js";

// Same origin when served by FastAPI (uvicorn); fall back to localhost:8000 when
// index.html is opened directly via file://.
const API = (location.protocol === "http:" || location.protocol === "https:")
  ? ""
  : "http://127.0.0.1:8000";

const els = {
  mass: document.getElementById("mass"),
  feh: document.getElementById("feh"),
  age: document.getElementById("age"),
  massNum: document.getElementById("mass-num"),
  fehNum: document.getElementById("feh-num"),
  ageNum: document.getElementById("age-num"),
  massTicks: document.getElementById("mass-ticks"),
  fehTicks: document.getElementById("feh-ticks"),
  ageTicks: document.getElementById("age-ticks"),
  massMarks: document.getElementById("mass-marks"),
  fehMarks: document.getElementById("feh-marks"),
  ageMarks: document.getElementById("age-marks"),
  readout: document.getElementById("readout"),
  status: document.getElementById("status"),
  // Rotation control (rotation Chunk 3): the unified control below [Fe/H]. Two facets —
  // the vvcrit track TOGGLE (massive stars) and the period slider (cool-MS activity, the
  // #sed-rot block moved here from the SED panel; sed.js still owns it by id).
  rotControl: document.getElementById("rot-control"),
  rotToggleRow: document.getElementById("rot-toggle-row"),
  rotToggle: document.getElementById("rot-toggle"),
  rotNote: document.getElementById("rot-note"),
  sedRot: document.getElementById("sed-rot"),
  // Stellar-endgame gateway + white-dwarf mode (smoldering-cinder-gateway.md).
  gateway: document.getElementById("gateway"),
  gatewayWd: document.getElementById("gateway-wd"),
  gatewayWr: document.getElementById("gateway-wr"),
  gatewaySn: document.getElementById("gateway-sn"),          // now a BUTTON (was the note)
  gatewaySnNote: document.getElementById("gateway-sn-note"), // the foreshadowing note
  gatewayLoading: document.getElementById("gateway-loading"),
  endgameBar: document.getElementById("endgame-bar"),
  endgameBack: document.getElementById("endgame-back"),
  endgameResnapNote: document.getElementById("endgame-resnap-note"),
  endgameAgeCaption: document.getElementById("endgame-age-caption"),
  // The ⁵⁶Ni-mass slider (SN endgame, Tier-3) — the one free knob of the light curve.
  snControl: document.getElementById("sn-control"),
  snMni: document.getElementById("sn-mni"),
  snMniNum: document.getElementById("sn-mni-num"),
  snMniMarks: document.getElementById("sn-mni-marks"),
  snMniNote: document.getElementById("sn-mni-note"),
};

const star = createStar(document.getElementById("star-canvas"));
// The spectral-classification line under the 3D star is a SIBLING text view like
// scale.js: it reads the marker's Teff/log g/phase and writes a schematic MK type
// (e.g. "G2 V — yellow dwarf"). No fetch; updated in refresh().
const classification = createClassification(document.getElementById("star-class-line"));
// The true-size scale bar (under the 3D star) is a SIBLING like sed.js: it reads the
// marker's radius and redraws the star's real size against the Solar System — the
// honest counterpart to the log-compressed 3D render. No fetch; updated in refresh().
const scale = createScale(document.getElementById("scale-canvas"));
const hr = createHR(document.getElementById("hr-canvas"));
const comp = createComp(document.getElementById("comp-canvas"));
// Composition view toggle: flip comp.js between the bulk H/He/metals bands, the
// per-element detail lines, and the light-element (Li/Be/F) view, and mirror the
// choice onto the panel (so the right legend shows, and the scale toggle shows only
// in the cno view) — purely a view switch, no refetch (the track already carries the
// metals). The mode-cno/mode-light classes are mutually exclusive; bulk has neither.
{
  const panel = document.querySelector(".comp-panel");
  const btns = panel.querySelectorAll(".comp-modes .mode-btn");
  btns.forEach((btn) =>
    btn.addEventListener("click", () => {
      const m = btn.dataset.mode;
      btns.forEach((b) => b.classList.toggle("active", b === btn));
      panel.classList.toggle("mode-cno", m === "cno");
      panel.classList.toggle("mode-light", m === "light");
      comp.setMode(m);
    }),
  );
  // Linear/log scale toggle for the per-element view (only shown in cno mode via
  // CSS). Log is what makes the trace elements — lithium especially — visible.
  const scaleBtns = panel.querySelectorAll(".scale-toggle .scale-btn");
  scaleBtns.forEach((btn) =>
    btn.addEventListener("click", () => {
      scaleBtns.forEach((b) => b.classList.toggle("active", b === btn));
      comp.setScale(btn.dataset.scale);
    }),
  );
  // Per-element on/off: click a cno legend entry to hide/show that line. comp.js
  // rescales the chart to the elements still shown (hiding O/C lets the trace
  // elements fill the height), and we mirror the off state onto the legend entry.
  // Delegated so it works for the inner ".tip" label too (closest finds data-el).
  const legendCno = panel.querySelector(".legend-cno");
  if (legendCno) {
    legendCno.addEventListener("click", (e) => {
      const entry = e.target.closest("span[data-el]");
      if (!entry) return;
      const visible = comp.toggleElem(entry.dataset.el);
      entry.classList.toggle("off", !visible);
    });
  }
}
// HR diagram variable-star overlay: a single on/off toggle that shades the
// instability strip (δ Scuti / RR Lyrae / Cepheids) plus the LBV and Mira zones as
// a labeled, schematic map of where variable stars live on the diagram. Pure view —
// no refetch; hr.js redraws the zones behind the retained track + marker. The button
// is a non-radio toggle, so it flips its own active/aria-pressed state and a panel
// class that reveals the legend.
{
  const panel = document.querySelector(".hr-panel");
  const btn = panel?.querySelector('.hr-modes [data-overlay="vars"]');
  if (btn) {
    btn.addEventListener("click", () => {
      const on = !btn.classList.contains("active");
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-pressed", String(on));
      panel.classList.toggle("show-vars", on);
      hr.setOverlay(on);
    });
  }
}

// The Lane–Emden interior panel (spec §8) is a SIBLING to the StellarState spine,
// not a consumer of it — it's driven by the polytropic index n alone and owns its
// own control + fetch. It's instantiated here but deliberately never wired into
// refresh()/refreshTrack(): it does not move with mass/[Fe/H]/age. (Kept as a ref
// only so the responsive-layout code below can call lane.resize().)
const lane = createLane({ api: API });

// The spectrum panel (spec §5) is a live consumer of the StellarState — it reads
// the marker's (Teff, log g, [Fe/H]) and fetches the matching synthetic spectrum.
// Like color.js it's a derived view of those three numbers (the backend route
// bypasses PROVIDER, the same way /polytrope does), so it's updated inside
// refresh() alongside the other panels — but owns its own debounced latest-wins
// fetch (it doesn't need the track, just the current state).
const spectrum = createSpectrum({ api: API });

// The real interior-structure panel (the honest successor to lane.js) — unlike lane,
// it IS a live consumer of the marker: update(state) reads (mass, [Fe/H], age) and
// fetches the matching MESA radial profile (/structure bypasses PROVIDER, like
// /polytrope). Snaps to the nearest saved snapshot; only main-sequence structure is on
// disk, so it's wired into paintState (the live path) and simply keeps its last profile
// through the WD/WR/SN endgame modes (no interior grid there).
const structure = createStructure({ api: API });

// The broadband SED panel (spec §5) is a SIBLING like lane.js — but, unlike lane,
// it DOES move with the star: it's the Planck blackbody across the whole EM
// spectrum, driven by Teff alone (a blackbody ignores log g and [Fe/H]), so it
// owns no fetch and just redraws from the live state inside refresh(). It is the
// zoomed-all-the-way-out companion to the synthetic-spectrum panel.
const sed = createSED(document.getElementById("sed-canvas"));

// --- draggable, responsive panel layout --------------------------------------
// The panels live in a flex-wrap container (styles.css) that auto-stacks them to
// the viewport width — several columns on a desktop, a single vertical column on a
// phone. makeSortable lets the user drag a panel by its grip to reorder; flow
// layout re-packs around the drop so panels never overlap, and the order persists.
const sortable = makeSortable(document.querySelector("main"));
const resetLayoutBtn = document.getElementById("reset-layout");
if (resetLayoutBtn) resetLayoutBtn.addEventListener("click", () => sortable.reset());

// Hover/focus pedagogy tooltips. A single body-mounted, viewport-clamped layer
// (tooltip.js) replaces the old per-element CSS `::after` tooltips, which clipped
// off the viewport edge once a panel was dragged near it. Delegated, so it also
// covers the JS-rendered readout-row "?" glyphs created later in refresh().
initTooltips();

// Make the plot canvases track their panel's width. fitCanvas sets an INLINE width
// that overrides any stylesheet width, so the canvases cannot be made responsive in
// CSS alone — each plot module exposes resize(w,h), and a ResizeObserver on the
// canvas's parent calls it with the available width (capped at the panel's design
// max, floored so a phone still gets a usable plot). Without this the 720px-wide
// spectrum/SED canvases overflow a ~360px phone panel. The 3D star is exempt:
// star.js already resizes its WebGL renderer from the canvas box every frame.
// maxW is set above any real panel's inner width (~668px at the widest 2-col size),
// so `avail` (the panel's content width) is what actually binds — each canvas fills
// its panel at every breakpoint, leaving little dead space inside the panel. Heights
// are fixed per panel, so the aspect ratio widens with the panel; the plots are
// PAD-based and redraw from retained state, so any width/height is fine.
const RESPONSIVE = [
  { id: "scale-canvas", mod: scale, maxW: 480, h: 150 },
  { id: "hr-canvas", mod: hr, maxW: 720, h: 320 },
  { id: "comp-canvas", mod: comp, maxW: 720, h: 340 },
  { id: "spectrum-canvas", mod: spectrum, maxW: 720, h: 280 },
  { id: "sed-canvas", mod: sed, maxW: 720, h: 300 },
  { id: "lane-canvas", mod: lane, maxW: 720, h: 340 },
  { id: "structure-canvas", mod: structure, maxW: 720, h: 340 },
];
for (const r of RESPONSIVE) {
  const canvas = document.getElementById(r.id);
  if (!canvas || !r.mod || typeof r.mod.resize !== "function") continue;
  const parent = canvas.parentElement;
  const ro = new ResizeObserver((entries) => {
    // Don't fight a panel that's locked to a fixed size mid-drag.
    const panel = canvas.closest(".panel");
    if (panel && panel.classList.contains("dragging")) return;
    const avail = Math.floor(entries[0].contentRect.width);
    r.mod.resize(Math.max(140, Math.min(r.maxW, avail)), r.h);
  });
  ro.observe(parent);
}

// --- slider <-> physical value mapping ---------------------------------------
let logMassMin = -1, logMassMax = Math.log10(40); // overwritten by /ranges
// `ageValue` (absolute years, below) is the SOURCE OF TRUTH for the desired age —
// analogous to `massValue`. `ageFraction` is the slider POSITION, now linear in EEP
// (Chunk E — see trackRowFromPos/posFromAge above), not in age. When mass/[Fe/H] changes
// (and the track/window move) we KEEP the absolute age and recompute the position as the
// nearest EEP row to it — so moving the mass slider doesn't change the age when it stays
// in range. ageValue is kept UNCLAMPED (the desired age); only the display clamps it, so
// dragging mass up through short-lived stars and back springs the age back instead of
// ratcheting it to zero.
let ageFraction = 0.46;   // slider position 0..1 (linear in EEP, -> a track row)
// The age window is read off the TRACK itself (first/last row's age_yr) — one
// source of truth, so the slider domain and the composition panel's EEP span can
// never disagree. They used to come from a separate, *unguarded* /age_range fetch:
// under overlapping requests `maxAge` could stay stuck on a stale mass while the
// (token-guarded) track settled to the new one — that was the "composition ends
// before the age slider" mismatch. age_yr is a StellarState field, so reading the
// window off the track is §3-clean (no provider internals leak).
let ageMin = 0, ageMax = 1e10;
// The age number input's spinner grid, set per-window by configureAgeNum(): a
// fixed step would be useless for short-lived massive stars (see configureAgeNum).
let ageNumStep = 0.01, ageNumDecimals = 2;
const DEFAULT_AGE_YR = 4.6e9;   // land the default star (the Sun) at ~4.6 Gyr
let ageValue = DEFAULT_AGE_YR;  // desired absolute age (yr); see ageFraction above
// The valid mass span tightens with [Fe/H] (the backend has a dead low-mass
// corner at high metallicity — super-solar M-dwarfs have no evolved tracks).
// Refetched from /mass_range whenever [Fe/H] changes; used to clamp the slider
// so the UI never requests an out-of-grid point (spec §6). The slider itself
// doesn't know *why* the span moves — just that it does (§3).
let validMassMin = 0.1, validMassMax = 40;
let providerName = "";    // filled from /health, shown in the status line
let fehMin = -0.5, fehMax = 0.5;   // feh slider bounds (overwritten by /ranges)
let currentTrack = null;           // last /track result; the source for age ticks
// Snap-tick positions in each slider's own coordinate (mass/age: 0..1; feh: dex).
let massTickPos = [], massTickVals = [], fehTickPos = [], ageTickPos = [];
const clamp01 = (x) => Math.min(1, Math.max(0, x));
// GLSL-style smoothstep on a scalar (used to drive the SN fireball grow/fade beats).
const smoothstep01 = (a, b, x) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };

// --- the age slider is LINEAR IN EEP, not in years (Chunk E) ------------------
// A star spends ~85–90% of its LIFE on the main sequence barely changing, so a slider
// linear in age is a long dead plateau — "age rises, nothing changes" (the user's item 2).
// The MIST track is one row per integer EEP (ZAMS..EAGB — a fixed 606 rows split MS 42% /
// RGB 25% / CHeB 17% / EAGB 17% at EVERY mass), so mapping the slider POSITION to EEP-row
// index gives every phase fair, mass-invariant travel. This is §6 ("interpolate on EEP, not
// age") applied to the slider's feel, and it matches comp.js's xOf(eep) axis EXACTLY — the
// age thumb and the composition-panel marker move in lockstep (both = (eep−e0)/(e1−e0)).
//
// The marker state is PICKED straight from the already-fetched track by row (like the WD/WR
// scrubs pick states[i]) — NEVER via a /state fetch. An age-based fetch would be DEGENERATE
// in flat-age bands: the 1 M☉ CHeB blue loop is 48 EEP rows spanning ~4800 yr, so age→EEP is
// near-vertical there and an age slider can't resolve those rows at all (measured). Picking by
// row gives those dramatic near-instant features (blue loops, the He flash) real travel.
//
// ageValue (yr) stays the honest readout/desired-age: it's DERIVED from the picked row on a
// scrub, and PRESERVED across a mass/[Fe/H] change (so the same absolute age survives a mass
// drag — the same-age-across-masses pedagogy; the thumb JUMPS because that age sits at a
// different EEP fraction per mass, which is correct and accepted).
//
// position (0..1) -> nearest EEP-row index of currentTrack.
function trackRowFromPos(pos) {
  if (!currentTrack || currentTrack.length < 2) return -1;
  const n = currentTrack.length;
  return Math.min(n - 1, Math.max(0, Math.round(clamp01(pos) * (n - 1))));
}
// absolute age (yr) -> slider position, by snapping to the nearest row whose age is
// closest (track ages are monotonically increasing). Used on a mass/[Fe/H] change to
// place the thumb at the preserved absolute age. Clamps out-of-window ages to 0 / 1.
function posFromAge(age) {
  const t = currentTrack;
  if (!t || t.length < 2) return 0;
  if (age <= t[0].age_yr) return 0;
  if (age >= t[t.length - 1].age_yr) return 1;
  let lo = 0, hi = t.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (t[mid].age_yr <= age) lo = mid; else hi = mid;
  }
  const i = (age - t[lo].age_yr) <= (t[hi].age_yr - age) ? lo : hi;
  return clamp01(i / (t.length - 1));
}

// --- stellar-endgame gateway + white-dwarf mode ------------------------------
// (docs/plans/smoldering-cinder-gateway.md, Chunk 2). `mode` is the one switch: the
// living-star path (everything above) vs the reversible white-dwarf endgame. The
// endgame snaps to ONE real grid track (never interpolated — §6), so the WD scrub is
// SIMPLER than the live path: it picks states[i] from the pre-fetched /endgame result
// and feeds the consumers directly — no /state fetch, no window build, no phase snap.
let mode = "live";              // "live" | "wd" | "wr" | "sn"
// --- rotation axis (rotation Chunk 3) ----------------------------------------
// `rotationOn` is the user's TOGGLE INTENT (persisted across mass/[Fe/H] changes, like
// massValue): turning rotation on at a massive star and dragging the mass down keeps the
// intent, the toggle just greys (the rotating track is then a bit-identical no-op). The
// EFFECTIVE vvcrit sent to the backend gates that intent on `has_grid` — so a metallicity
// with no rotating grid (or any non-MIST provider) silently falls back to non-rotating,
// and /track?vvcrit=0.4 can never hit an [Fe/H] the rotating axis lacks (a 422). MIST
// publishes only {0.0, 0.4}, so this is a snap, not a blend (see whirling-cohort-atlas.md).
const ROT_VVCRIT = 0.4;
let rotationOn = false;
// The latest /rotation_status for the current (mass, [Fe/H]) — the data-derived honesty
// gate (has_grid / threshold_msun / active). Refreshed (awaited) before any track/endgame
// fetch on a mass/[Fe/H] change, so the effective vvcrit below is always current.
let rotStatus = { has_grid: false, threshold_msun: null, active: false };
const effVvcrit = () => (rotationOn && rotStatus.has_grid ? ROT_VVCRIT : 0.0);

// Whether this star is in the cool main-sequence DYNAMO FAMILY — i.e. its track has any
// cool MS row (Teff < 6500 K). This gates the rotation-PERIOD facet's VISIBILITY, and it
// is age-INDEPENDENT (a property of the whole track = mass/[Fe/H]), NOT of the marker.
// Critical for no-jitter: the facet sits right above the Age slider, so if visibility
// tracked the marker's per-age dynamo state (sed.rotationAllowed) it would hide/show
// mid-scrub and the Age thumb would jump under the cursor. Instead the facet stays put for
// the whole scrub and sed.js's rot.sync() GREYS it for the ages/phases where the dynamo
// isn't active (off the MS) — visibility stable, enabled-state honest.
const COOL_MS_TEFF = 6500;
const coolDynamoFamily = () =>
  !!currentTrack && currentTrack.some(
    (s) => s.phase === "MS" && s.Teff_K != null && s.Teff_K < COOL_MS_TEFF);

let endgame = null;             // the latest /endgame result (type, states, masses…)
let endgameKey = null;          // the requested (mass|feh) the `endgame` data is for
let endgameToken = 0;           // latest-wins guard for /endgame fetches
let endgameLoading = false;     // a live-gateway /endgame fetch is in flight (drives the
                                // "computing…" placeholder; cleared on settle, success OR
                                // fail, by the latest token only — so a stale/failed fetch
                                // can't leave a stuck spinner)
let endgameMeta = null;         // type-only /endgame?meta=1 result for the CURRENT star —
                                // {type, mass_init_msun, has_states, …}. Lights the gateway
                                // button (greyed, foreshadowing) the instant a track lands,
                                // ~120 B, WITHOUT waiting on the ~1 MB full fetch (which still
                                // loads in the background for the HR preview + a warm enter
                                // cache, so the slam-to-the-end gesture stays instant).
let endgameMetaKey = null;      // the (mass|feh) key endgameMeta is for (staleness guard)
let endgameMetaToken = 0;       // latest-wins guard, SEPARATE from endgameToken — the full
                                // fetch's stabilized machinery (Chunk D) is left untouched
let wdFraction = 0;             // slider position 0..1 inside the WD endgame scrub
let wrFraction = 0;             // slider position 0..1 inside the WR endgame scrub
// --- supernova endgame (SN Chunk 2) ------------------------------------------
// Unlike WD/WR (which snap to a pre-fetched track and scrub states[i]), the SN endgame is a
// COMPUTED model fetched from /supernova (the sibling route): a ⁵⁶Ni light curve + a set of
// homologous-photosphere StellarStates on a log time grid. `snModel` is that result; the age
// slider becomes a LINEAR-DAYS time scrubber (matching the light-curve panel's linear x-axis,
// so the marker tracks the slider and the ⁵⁶Co tail stays straight); `mniValue` is the one
// free knob (Tier-3), and changing it REFETCHES (debounced) — the plateau is ⁵⁶Ni-independent
// and the photosphere Teff depends on L_total, so client-side scaling would be wrong.
let snModel = null;             // the latest /supernova SupernovaModel
let snFraction = 0;             // slider position 0..1 in the SN time scrubber (linear in days)
let snToken = 0;                // latest-wins guard for /supernova fetches (enter + M_Ni + resnap)
let lastEgMass = 1, lastEgFeh = 0;   // last accepted endgame progenitor (for the revert)

// The ⁵⁶Ni-mass control (Tier-3). Bounds are the observed range the backend clamps to; the
// slider is LOG in M_Ni (it spans 0.001–0.3, ~2.5 decades). Canonical default 0.06.
const M_NI_DEFAULT = 0.06, M_NI_MIN = 0.001, M_NI_MAX = 0.3;
let mniValue = M_NI_DEFAULT;    // ⁵⁶Ni mass / M☉ — source of truth for the slider
const mniLogMin = Math.log10(M_NI_MIN), mniLogMax = Math.log10(M_NI_MAX);
const mniFromPos = (pos) => 10 ** (mniLogMin + clamp01(pos) * (mniLogMax - mniLogMin));
const posFromMni = (m) => clamp01((Math.log10(m) - mniLogMin) / (mniLogMax - mniLogMin));
const MNI_TICKS = [0.001, 0.01, 0.06, 0.1, 0.3];   // observed floor · low · canonical · high · ceiling
let pinAgeToEnd = false;        // one-shot: land the next track refresh at the very end

// The gateway button appears only once the star is scrubbed to the VERY end of its
// visible life (the EAGB giant) — not merely "near" it. These thresholds live in SLIDER-
// POSITION space (0..1). Now that the slider is linear in EEP (Chunk E), position maps to
// evolutionary progress, so 0.999 ≈ the last EEP row (the true end) and 0.9 ≈ deep into the
// EAGB — the post-RGB drama is no longer crammed into a sliver, so the threshold is robust
// to where the gate sits rather than fighting a near-flat age plateau (the old linear-age
// rationale for a tight gate is obsolete). At the true end the living EAGB giant is
// continuous with the endgame's first state (the first thermal pulse), so the corona /
// X-ray / radius all carry across smoothly. The age slider snaps drags within ~1.5% of the
// end to exactly 1.0, so reaching it stays a natural "slam to the right" gesture. The
// /endgame data is still PREFETCHED earlier (GATE_FETCH) so the button is instant when the
// user lands at the end.
const GATE_SHOW = 0.999, GATE_FETCH = 0.9;

// The WD endgame slider is a 3-zone piecewise map over the snapped cooling sequence —
// pulses → rise to the central star → cooling. The boundaries DERIVE from the data
// (last thermal-pulse row, hottest post-AGB row), but the slider BANDS are fixed so
// each act gets fair travel: a naive single log-cooling-age axis would let the 601
// chaotic pulse rows eat ~half the slider and crush the dramatic ~100 kK central-star
// spike to a sliver. With these bands the pulses compress to 12%, the rise to the
// central star gets 16%, and the long cooling fills 72% — and within the cooling zone
// the MIST rows are already ~even in log(cooling age), so plain index-linear there
// gives each cooling decade visible travel (verified against the 1 M☉ track).
const WD_FP = 0.12;   // [0, WD_FP)      → thermal pulses
const WD_FR = 0.28;   // [WD_FP, WD_FR)  → rise to the central star; [WD_FR, 1] → cooling

// The three zones of one snapped endgame sequence, derived from its phases.
function wdZones(states) {
  let tpEnd = -1, knee = -1, kneeT = -Infinity;
  for (let i = 0; i < states.length; i++) {
    if (states[i].phase === "TPAGB") tpEnd = i;
    else if (states[i].phase === "post-AGB" && states[i].Teff_K > kneeT) {
      kneeT = states[i].Teff_K; knee = i;
    }
  }
  if (knee < 0) knee = Math.min(states.length - 1, Math.max(0, tpEnd + 1));
  return { tpEnd, knee, last: states.length - 1, kneeT };
}

// slider fraction (0..1) -> state index, via the 3-zone band map above.
function wdIndexFromFraction(frac, z) {
  frac = clamp01(frac);
  const haveTP = z.tpEnd >= 0;
  if (haveTP && frac < WD_FP) return Math.round((frac / WD_FP) * z.tpEnd);
  if (frac < WD_FR) {
    const lo = haveTP ? z.tpEnd : 0;
    const base = haveTP ? WD_FP : 0;
    const t = (frac - base) / (WD_FR - base);
    return Math.round(lo + t * (z.knee - lo));
  }
  const t = (frac - WD_FR) / (1 - WD_FR);
  return Math.round(z.knee + t * (z.last - z.knee));
}

// Snap the WD scrub to its landmarks (pulses / central star / cold cinder).
function snapWDFraction(raw) {
  const thresh = 0.015;
  let best = raw, bestD = thresh;
  for (const t of [0, WD_FR, 1]) {
    const d = Math.abs(raw - t);
    if (d < bestD) { bestD = d; best = t; }
  }
  return clamp01(best);
}

// The WD landmark ticks: only three, well separated — no stagger needed.
function rebuildWDTicks() {
  if (!endgame || !endgame.states.length) return;
  const z = wdZones(endgame.states);
  const kneeKK = Math.round(z.kneeT / 1000);
  buildTickStrip(els.ageMarks, [
    { pos01: 0, label: "thermal pulses" },
    { pos01: WD_FR, label: `central star ~${kneeKK} kK` },
    { pos01: 1, label: "cold WD" },
  ]);
  els.ageTicks.innerHTML = "";   // the WD snap uses its own targets, not the datalist
}

// --- the Wolf–Rayet endgame scrub (Chunk 4) ----------------------------------
// Unlike the WD cooling sequence (a 3-zone piecewise map dodging the chaotic thermal
// pulses), the WR sub-track is ONE clean, dense, monotonically-stripping run of phase-9
// rows, so the scrub is plain index-linear — every real WR row gets equal travel. The
// one landmark is the WN→WC transition: where core-helium burning surfaces carbon and
// oxygen and the stripped surface flips from helium-dominant (nitrogen sequence) to
// C/O-dominant (carbon/oxygen sequence). Derived from the data (first row whose surface
// metals dominate, Z_surf ≥ 0.4); wc = -1 for a star that stays WN to the end (measured:
// ~35 M☉ at [Fe/H]=+0.5 never reaches WC).
function wrZones(states) {
  let wc = -1;
  for (let i = 0; i < states.length; i++) {
    if ((states[i].Z_surf ?? 0) >= 0.4) { wc = i; break; }
  }
  return { wc, last: states.length - 1 };
}

// slider fraction (0..1) -> WR state index (plain index-linear, see wrZones).
function wrIndexFromFraction(frac, z) {
  return Math.round(clamp01(frac) * z.last);
}

// Snap the WR scrub to its landmarks (onset / WN→WC transition / hottest stripped end).
function snapWRFraction(raw) {
  if (!endgame || !endgame.states.length) return clamp01(raw);
  const z = wrZones(endgame.states);
  const targets = [0, 1];
  if (z.wc > 0 && z.last > 0) targets.push(z.wc / z.last);
  const thresh = 0.015;
  let best = raw, bestD = thresh;
  for (const t of targets) {
    const d = Math.abs(raw - t);
    if (d < bestD) { bestD = d; best = t; }
  }
  return clamp01(best);
}

// The WR landmark ticks: the WN onset, the WN→WC transition (only if the star reaches it),
// and the hottest stripped core. Few and well separated — no stagger needed.
function rebuildWRTicks() {
  if (!endgame || !endgame.states.length) return;
  const z = wrZones(endgame.states);
  const marks = [{ pos01: 0, label: "WN (He surface)" }];
  if (z.wc > 0 && z.last > 0)
    marks.push({ pos01: z.wc / z.last, label: "WC/WO (C·O surface)" });
  marks.push({ pos01: 1, label: "hottest core" });
  buildTickStrip(els.ageMarks, marks);
  els.ageTicks.innerHTML = "";   // the WR snap uses its own targets, not the datalist
}

// A transient note below the sliders (e.g. after a mass re-snap left the WD range). It
// grows the panel downward instead of shoving the sliders, so it lives under the age
// caption, not in the endgame bar above the controls.
function setWDResnapNote(msg) {
  if (!els.endgameResnapNote) return;
  els.endgameResnapNote.textContent = msg || "";
  els.endgameResnapNote.hidden = !msg;
}

// The endgame-cache key includes the effective rotation: toggling rotation changes the
// fate (rotation lowers the WR threshold), so a cached endgame for the other vvcrit is stale.
const egKey = () => `${massValue.toFixed(4)}|${Number(els.feh.value).toFixed(2)}|${effVvcrit()}`;

// Trailing debounce for the EXPENSIVE backend fetch behind a slider drag. Each
// /track rebuilds the full (mass,[Fe/H]) EEP
// interpolation window on the backend, so a fast slider fling firing dozens of
// `input` events would spin the CPU computing intermediate stars whose results the
// latest-wins token then just throws away. We defer only the fetch — the cheap UI
// (thumb, number box, snap) stays synchronous so the slider never feels laggy.
// `wrapped()` collapses a burst to ONE trailing call; `wrapped.flush()` cancels the
// pending timer and runs it immediately (used on the slider's `change`, which fires
// once on release / on a single click) so *clicking* and *letting go* are instant
// while only *sliding* defers. Both read the latest globals/DOM at exec time.
const SLIDER_FETCH_DELAY_MS = 140;
function debounce(fn, delay) {
  let timer = null;
  const run = () => { timer = null; fn(); };
  const wrapped = () => {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(run, delay);
  };
  // No-op when nothing is pending: if the timer already fired, the latest value was
  // fetched and the slider hasn't moved since, so there's nothing left to flush.
  wrapped.flush = () => { if (timer !== null) { clearTimeout(timer); run(); } };
  return wrapped;
}

// `massValue` is the SOURCE OF TRUTH for the mass in use (fetch + display). The range
// slider can't represent a round mass exactly — its `step` quantizes the thumb
// position, so re-deriving the mass from els.mass.value yields 0.999 for "1". So the
// real mass lives here: drags snap to the exact round mass at a tick, the number box
// stores the exact typed value, and refresh()/refreshTrack() read this (then sync the
// thumb). The slider position stays a *display* of massValue, never its source.
let massValue = 1.0;

// The slider position spans the full bounding box; the physical mass is then clamped
// to the span valid at the current [Fe/H] — a soft floor that moves with metallicity.
const massFromSliderPos = (pos) =>
  Math.min(Math.max(
    10 ** (logMassMin + pos * (logMassMax - logMassMin)),
    validMassMin), validMassMax);
const sliderFromMass = (m) =>
  (Math.log10(m) - logMassMin) / (logMassMax - logMassMin);

// Map a raw (dragged) slider position to {pos, mass}. If it lands within the snap
// threshold of a round-mass tick, return that tick's EXACT mass (so the slider can
// represent 1.0, not the quantized 0.999); otherwise derive the mass from the
// position. This is the slider's own snap — the number box deliberately bypasses it
// (the arbitrary-precision escape hatch: typing 0.99 must stay 0.99, not snap to 1).
function massFromSliderInput(rawPos) {
  const thresh = 0.015;
  let bestIdx = -1, bestD = thresh;
  for (let i = 0; i < massTickPos.length; i++) {
    const d = Math.abs(rawPos - massTickPos[i]);
    if (d < bestD) { bestD = d; bestIdx = i; }
  }
  if (bestIdx >= 0) return { pos: massTickPos[bestIdx], mass: massTickVals[bestIdx] };
  return { pos: rawPos, mass: massFromSliderPos(rawPos) };
}

// --- number formatting -------------------------------------------------------
function fmt(x, sig = 3) {
  if (x === null || x === undefined) return "—";
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return x.toExponential(2);
  return Number(x.toPrecision(sig)).toString();
}
function gyr(yr) {
  if (yr >= 1e9) return `${fmt(yr / 1e9)} Gyr`;
  if (yr >= 1e6) return `${fmt(yr / 1e6)} Myr`;
  return `${fmt(yr)} yr`;
}

// --- snap-to-landmark + editable values --------------------------------------
// The sliders snap to critical points (round masses, solar/grid metallicities,
// evolutionary landmarks); the number inputs are the arbitrary-precision escape
// hatch and deliberately bypass snapping.

// Snap a raw slider value to the nearest tick within 1.5% of its range —
// landmarks are magnetic, but every value between them stays reachable.
function snap(value, ticks, min, max) {
  const thresh = (max - min) * 0.015;
  let best = value, bestD = thresh;
  for (const t of ticks) {
    const d = Math.abs(value - t);
    if (d < bestD) { bestD = d; best = t; }
  }
  return best;
}

// Snap an age-slider POSITION (0..1, linear in EEP) to a landmark row or to a track
// endpoint. The endpoints (0 = ZAMS, 1 = the final EAGB state) are snap targets too, so
// dragging fully right always reaches the true end of the track — even when a late
// landmark (CHeB/EAGB) sits within the snap radius of 1.0, which used to capture the
// whole right edge and trap the slider short of the end. Returns the EXACT float (never
// the range input's step-quantized value) so the row index round() lands exactly on the
// snapped landmark's EEP row.
function snapAge(raw) {
  const thresh = 0.015;
  let best = raw, bestD = thresh;
  for (const t of [0, ...ageTickPos, 1]) {
    const d = Math.abs(raw - t);
    if (d < bestD) { bestD = d; best = t; }
  }
  return best;
}

// Populate a <datalist> (a native, browser-dependent tick hint) from {pos,label}.
// Kept as a bonus; the visible, reliable marks are the custom strip below.
function buildDatalist(el, opts) {
  el.innerHTML = opts
    .map((o) => `<option value="${o.pos}"${o.label ? ` label="${o.label}"` : ""}></option>`)
    .join("");
}

// Render the visible snap marks (a tick line + small label) under a slider. The
// strip is inset by the thumb radius in CSS, so pos01 (0..1) lines up under the
// thumb. Labels are EDGE-ANCHORED (centered in the middle, left-/right-aligned near
// the ends) so a landmark near either end extends inward instead of off-canvas.
// With { stagger:true } — the age strip, whose evolutionary landmarks crowd the
// right edge on a linear-age axis — a label that would collide with one already
// placed is pushed onto the next stacked ROW instead of being dropped, so every
// landmark stays visible (the user's "move it above/aside when ticks are close").
// mass/feh keep the simpler single-row collision-skip (those strips rarely crowd,
// and a dropped round-mass label is low-stakes). Layout-independent (normalized
// pos), so it survives responsive resizes with no relayout.
function buildTickStrip(el, marks, opts = {}) {
  if (!el) return;
  const stagger = opts.stagger === true;
  const sorted = marks.slice().sort((a, b) => a.pos01 - b.pos01);
  const anchor = (p) => (p < 0.1 ? "left" : p > 0.9 ? "right" : "");
  // Big enough that two same-row labels never overlap even on a narrow phone strip
  // (a label is ~0.10 of the strip width there) — close ones stack instead. Chosen
  // for phone-safety, NOT to limit stacking: chronological order is guaranteed by the
  // chain logic below regardless of this value, so the only cost of a generous gap is
  // that low-mass stars (and ~20 M☉) stack the crowded late phases into a clean 3-row
  // staircase. Layout-independent (no pixel measurement / resize hook).
  const MIN_GAP = 0.11;
  let maxRow = 0;
  let prevPos = -1, prevRow = 0;   // chain state for the stagger
  let lastShown = -1;              // last labeled pos (single-row / non-stagger case)

  const html = sorted
    .map((m) => {
      let showLabel = m.label != null;
      let row = 0;
      if (showLabel) {
        if (stagger) {
          // Chain stacking: a label close to its predecessor drops ONE row below it;
          // a real gap resets to row 0. This keeps the rows in chronological order
          // (earlier phase always above a later one — a greedy "lowest free row"
          // would let a later label grab the freed top row and invert the order).
          row = prevPos >= 0 && m.pos01 - prevPos < MIN_GAP ? prevRow + 1 : 0;
          prevPos = m.pos01; prevRow = row;
          if (row > maxRow) maxRow = row;
        } else if (m.pos01 - lastShown < 0.08) {
          showLabel = false;
        } else {
          lastShown = m.pos01;
        }
      }
      const a = anchor(m.pos01);
      const lbl = showLabel
        ? `<span class="tick-label"${a ? ` data-anchor="${a}"` : ""}` +
          `${row ? ` data-row="${row}"` : ""}>${escAttr(m.label)}</span>`
        : "";
      return `<span class="tick" style="left:${(m.pos01 * 100).toFixed(2)}%">${lbl}</span>`;
    })
    .join("");

  el.innerHTML = html;
  el.classList.toggle("stagger", stagger);
  // Grow the strip + its slider-wrap's bottom margin to fit the stacked rows (CSS
  // reads --tick-rows). Non-staggered strips pin it to 1 (the default height).
  el.parentElement.style.setProperty("--tick-rows", stagger ? String(maxRow + 1) : "1");
}

// Minimal escaping for text dropped into markup / attributes (tick labels, the
// help-glyph tooltips). The prose carries the odd & / < / " — keep them literal.
function escAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// A "?" help glyph whose pedagogy shows on hover/focus (the shared tooltip layer,
// tooltip.js, reads data-tip). Used for the JS-rendered readout rows; the static
// panels use the same markup written directly in index.html. Placement is now
// viewport-clamped in JS, so no per-glyph open-direction class is needed.
function help(tip) {
  return `<span class="help" tabindex="0" data-tip="${escAttr(tip)}">?</span>`;
}

// A glyph-free hover tooltip: the text *is* the affordance (subtle dotted
// underline, no "?"). Used for the status-line tokens; the shared layer flips the
// tooltip above the token automatically when it would overflow the bottom.
function tipSpan(text, tip) {
  return `<span class="tip" tabindex="0" data-tip="${escAttr(tip)}">${escAttr(text)}</span>`;
}

// Pedagogy for the status-line tokens. The phase token is dynamic, so each
// evolutionary phase gets its own gloss; unknown labels fall back to a generic
// line. These read the meaning of MIST's phase strings — a §3-clean consumer of
// StellarState.phase, not provider internals.
const PHASE_TIP = {
  PMS: "Pre-main-sequence — still gravitationally contracting toward the main " +
    "sequence, not yet in steady core hydrogen fusion.",
  MS: "Main sequence — steady core hydrogen fusion. Stars spend ~90% of their " +
    "life here; the Sun is a main-sequence star.",
  SGB: "Subgiant branch — core hydrogen is spent and the inert helium core " +
    "contracts while a hydrogen shell ignites around it; the star crosses " +
    "toward the red-giant branch.",
  RGB: "Red-giant branch — hydrogen burns in a shell around a growing helium " +
    "core; the envelope swells and cools, so the star becomes large and red.",
  CHeB: "Core-helium burning — helium has ignited in the core (via the He flash " +
    "for low-mass stars); the star settles onto the horizontal branch / red " +
    "clump or runs a blue loop.",
  EAGB: "Early asymptotic-giant branch — core helium is spent; the star ascends a " +
    "second time as helium and hydrogen burn in shells around an inert carbon-" +
    "oxygen core. It swells into a huge, cool, low-gravity giant (so the surface " +
    "shows just a handful of enormous convective cells). The simulation stops here, " +
    "before the thermally-pulsing AGB — those helium-shell flashes are too chaotic " +
    "to interpolate honestly across mass.",
  TPAGB: "Thermally-pulsing asymptotic-giant branch — the dying giant's final act: " +
    "helium-shell flashes (thermal pulses) drive strong winds that shed the envelope. " +
    "Shown only inside the white-dwarf endgame (snapped to one real track, never " +
    "interpolated across mass — the pulses are too chaotic for that).",
  "post-AGB": "Post-AGB — the bared, contracting stellar core: it heats to ~100 000 K " +
    "as a planetary-nebula central star, then cools for billions of years into a " +
    "degenerate white dwarf (a cold, Earth-sized cinder).",
  WR: "Wolf–Rayet — a very massive star whose powerful winds have stripped its hydrogen " +
    "envelope, baring the hot helium- and carbon-burning core (climbing toward ~250 000 K). " +
    "The exposed surface tells the WN→WC→WO story: helium with nitrogen, then carbon and " +
    "oxygen. Shown only inside the Wolf–Rayet endgame (snapped to one real track). After " +
    "this the core collapses to a neutron star or black hole — which this simulator doesn't model.",
  SN: "Supernova — the iron core of a massive star has collapsed and the star explodes. " +
    "This is a COMPUTED semi-analytic model (the tracks end at collapse): a ⁵⁶Ni→⁵⁶Co→⁵⁶Fe " +
    "radioactive light curve powering a homologously expanding ejecta photosphere. The " +
    "explosion mechanism (the neutrino-driven bounce) is NOT modeled — only its aftermath. " +
    "Shown inside the supernova endgame, with the brightness scale set by the ⁵⁶Ni slider.",
};
const phaseTip = (phase) =>
  PHASE_TIP[phase] ||
  "Evolutionary phase read straight off the track (a StellarState field).";

// "OK" / error health of the last fetch.
const STATUS_OK_TIP =
  "Backend health — the provider returned a valid StellarState for the current " +
  "mass, [Fe/H] and age. This token turns red with the error message if a fetch " +
  "fails (e.g. the backend isn't running).";

// Which data source is behind the §3 interface right now.
const providerTip = (name) =>
  name === "MISTProvider"
    ? "Data source (spec §3) — real MIST v2.5 stellar-evolution tracks, " +
      "EEP-interpolated in mass and [Fe/H]. A faithful model, but an approximation: " +
      "L☉ and R☉ are *defined* as 1, yet MIST predicts L≈1.07, R≈1.01 for the Sun " +
      "at 4.6 Gyr — a few-percent residual."
    : "The StellarStateProvider feeding every panel (spec §3). It is " +
      "interchangeable behind one interface — nothing downstream knows or cares " +
      "which provider is active.";

const ROUND_MASSES =
  [0.1, 0.2, 0.3, 0.5, 0.8, 1, 1.5, 2, 3, 5, 8, 12, 20, 30, 40, 60, 100, 200, 300];

// Round masses worth snapping to, filtered to the span valid at this [Fe/H]. The
// masses are kept alongside their positions (massTickVals) so a snap can recover the
// EXACT round mass — see massFromSliderInput.
function rebuildMassTicks() {
  const opts = [];
  for (const m of ROUND_MASSES) {
    if (m < validMassMin - 1e-9 || m > validMassMax + 1e-9) continue;
    opts.push({ pos: clamp01(sliderFromMass(m)), label: `${m}`, mass: m });
  }
  massTickPos = opts.map((o) => o.pos);
  massTickVals = opts.map((o) => o.mass);
  buildDatalist(els.massTicks, opts);
  buildTickStrip(els.massMarks, opts.map((o) => ({ pos01: o.pos, label: o.label })));
}

// Solar (0) and quarter-dex marks within the grid's [Fe/H] range.
function rebuildFehTicks() {
  const vals = [];
  for (const v of [fehMin, -0.25, 0, 0.25, fehMax]) {
    if (v < fehMin - 1e-9 || v > fehMax + 1e-9) continue;
    if (!vals.some((x) => Math.abs(x - v) < 1e-6)) vals.push(v);
  }
  vals.sort((a, b) => a - b);
  fehTickPos = vals;
  const span = (fehMax - fehMin) || 1;   // feh slider is in dex; normalize for the strip
  buildDatalist(els.fehTicks, vals.map((v) => ({ pos: v, label: v.toFixed(2) })));
  buildTickStrip(els.fehMarks,
    vals.map((v) => ({ pos01: clamp01((v - fehMin) / span), label: v.toFixed(2) })));
}

// The evolutionary landmarks on the age axis, read straight off the track
// (phase transitions + the RGB tip) — all StellarState fields, so deriving them
// here is §3-clean (no special endpoint needed).
function criticalAges(track) {
  const pts = [];
  let prev = null;
  for (let i = 0; i < track.length; i++) {
    const s = track[i];
    if (s.phase !== prev) {
      // Phase transitions are the real landmarks — kind:"phase" marks them as
      // never-droppable (dropping CHeB was the "CHeB is nowhere as a tick" bug). The
      // row INDEX `i` is the EEP-axis position (the slider is linear in EEP now, Chunk E).
      if (prev !== null) pts.push({ i, label: s.phase, kind: "phase" });
      prev = s.phase;
    }
  }
  // First-ascent RGB tip = max radius among the RGB-phase rows. Restricted to RGB
  // (not the global max) because the window now reaches the early-AGB, whose radius
  // can exceed the RGB tip for intermediate masses — the global max would mislabel
  // an EAGB state as the "RGB tip". Skipped if the star never has an RGB phase.
  // Tagged kind:"tip": for every star that ignites helium the tip coincides with
  // CHeB onset (the He flash happens AT the tip — it sits one EEP row before CHeB onset),
  // so rebuildAgeTicks drops it as a redundant mark when CHeB sits on top of it, leaving
  // it only for stars whose window ends mid-RGB (no CHeB).
  let tip = null, tipI = -1;
  for (let i = 0; i < track.length; i++)
    if (track[i].phase === "RGB" && (tip === null || track[i].R_rsun > tip.R_rsun)) {
      tip = track[i]; tipI = i;
    }
  if (tip !== null) pts.push({ i: tipI, label: "RGB tip", kind: "tip" });
  return pts;
}

// Build the age ticks from the track. Position uses the SAME EEP-row map the slider
// uses — pos = i/(N−1) — so each landmark tick lands exactly under the marker at that
// EEP. (If this drifted from the slider's row map, snapping would jump the marker off
// the landmark — the invariant flagged at the els.age input handler.)
function rebuildAgeTicks() {
  if (!currentTrack || currentTrack.length < 2) return;
  const n = currentTrack.length;
  const all = criticalAges(currentTrack)
    .map((p) => ({ ...p, pos: clamp01(p.i / (n - 1)) }));
  // Phase transitions are always kept (the old global 0.01 dedup dropped CHeB — the
  // "CHeB is nowhere as a tick" bug). The RGB-tip is the only droppable point: it
  // sits one row before CHeB onset (the He flash is AT the tip), so it's dropped
  // whenever ANY phase tick is within 0.5% of it. Checked against the full phase set
  // — NOT in sort order — because the tip's pos is marginally *below* CHeB's, so an
  // order-dependent dedup would keep the tip (processed first, opts still empty) and
  // then snapAge would steal the snap onto the tip's still-RGB row → "snap to CHeB,
  // readout says RGB". The tip survives only for a star whose window ends mid-RGB.
  const phasePts = all.filter((p) => p.kind === "phase");
  const opts = [...phasePts,
    ...all.filter((p) => p.kind === "tip" &&
      !phasePts.some((q) => Math.abs(q.pos - p.pos) < 0.005)),
  ].sort((a, b) => a.pos - b.pos).map((p) => ({ pos: p.pos, label: p.label }));
  ageTickPos = opts.map((o) => o.pos);
  buildDatalist(els.ageTicks, opts);
  // On the EEP axis the landmarks are well spread (MS→RGB ~42%, →CHeB ~67%, →EAGB ~83%),
  // but neighbouring labels can still collide, so stagger them onto stacked rows (no-drop)
  // so each one stays visible. Prepend a "ZAMS" label at the LEFT end: the slider's zero
  // is the zero-age main sequence (where the window starts — the pre-main-sequence
  // contraction is clipped), NOT the star's literal birth. For a low-mass star the ZAMS
  // age is hundreds of Myr (a 0.3 M☉ sits at ~0.45 Gyr there), so without this the left
  // end reads as an arbitrary non-zero floor. Strip-label only — pos 0 is already a
  // snapAge target, and the age "?" tooltip carries the why.
  buildTickStrip(els.ageMarks,
    [{ pos01: 0, label: "ZAMS" }, ...opts.map((o) => ({ pos01: o.pos, label: o.label }))],
    { stagger: true });
}

// Write a number input's display value without fighting the user mid-type.
function setNum(el, value) {
  if (document.activeElement === el) return;
  el.value = value;
}
// The age number input shows Gyr, but lifetimes span ~5 decades (a 0.1 M☉ dwarf
// lives far longer than a 60 M☉ star, which reaches the early-AGB in ~3 Myr ≈
// 0.0035 Gyr). A FIXED 0.01 Gyr spinner step is useless for short-lived massive
// stars — their whole life is a sliver of one step, so the up/down buttons can
// only ever land on 0, and the browser even flags every in-window age as
// `:invalid`, offering 0 as the "nearest valid value". So the grid ADAPTS to the
// current age window: a "nice" 1/2/5×10^k step giving ~100 spinner clicks across
// the whole track (each click ≈ 1% of the lifetime — a clearly meaningful move),
// with exactly enough display decimals to show each click.
function niceAgeStep(spanGyr, targetSteps = 100) {
  if (!(spanGyr > 0)) return { step: 0.01, decimals: 2 };
  const raw = spanGyr / targetSteps;
  const exp = Math.floor(Math.log10(raw));
  const base = raw / 10 ** exp;                       // 1 ≤ base < 10
  const mult = base <= 1 ? 1 : base <= 2 ? 2 : base <= 5 ? 5 : 10;
  const step = mult * 10 ** exp;
  const decimals = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
  return { step, decimals };
}

// Snap the current age window onto the number input's min/max/step so every
// spinner click is a clean, in-range, step-aligned move (and the value is never
// `:invalid`). min/max are floored/ceiled to the step grid — aligning min is what
// keeps (value − min)/step integral, which is what prevents the step-mismatch
// validation bubble (setting min = ageMin unaligned would reintroduce it).
function configureAgeNum(minYr, maxYr) {
  const minG = minYr / 1e9, maxG = maxYr / 1e9;
  const { step, decimals } = niceAgeStep(maxG - minG);
  ageNumStep = step; ageNumDecimals = decimals;
  els.ageNum.step = step;
  els.ageNum.min = (Math.floor(minG / step) * step).toFixed(decimals);
  els.ageNum.max = (Math.ceil(maxG / step) * step).toFixed(decimals);
}

// Format an age (yr) for the number input. Show the TRUE value — NOT snapped onto
// the coarse spinner step. That snapping made two distinct entries collide: a 1.44 M☉
// star at 2.14 Gyr (X-ray gap) and 2.16 Gyr (coronal X-ray) both rendered "2.15" even
// though the star — and the SED — used the exact entered age (the readout already
// shows the truth via gyr()). Precision is tied to the VALUE (≥3 significant figures)
// so two nearby ages always read distinctly, with the window's adaptive `decimals`
// only as a FLOOR so a short-lived massive star can't collapse to "0.00". The spinner
// step/min/max (niceAgeStep) are untouched — the up/down arrows still snap to the nice
// grid; a hand-typed off-grid value is simply honored (there is no form to validate).
const gyrNum = (yr) => {
  const g = yr / 1e9;
  if (!(g > 0)) return g.toFixed(ageNumDecimals);
  const sig = Math.max(0, 2 - Math.floor(Math.log10(g)));   // decimals for 3 sig figs
  return g.toFixed(Math.max(ageNumDecimals, sig));
};

// --- latest-request-wins -----------------------------------------------------
// The track fetch (the only living-path network call now — the age scrub picks from the
// already-fetched track, Chunk E) carries a token so a stale response can't overwrite a
// newer one. (The endgame fetches carry their own separate tokens.)
let trackToken = 0;

async function fetchJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

// Each row is [term, description, value]. Mass and [Fe/H] come from the state
// itself (s.mass_init_msun / s.feh_init), NOT the slider DOM — so the whole
// readout stays a pure function of one StellarState (spec §3). The descriptions
// are the "what am I looking at" layer: this is a teaching tool.
function renderReadout(s) {
  const rows = [
    ["Mass",
      "initial mass in Suns — the single biggest lever on a star's luminosity, lifetime and ultimate fate",
      `${fmt(s.mass_init_msun)} M☉`],
    ["[Fe/H]",
      "metallicity: log₁₀ of the star's iron-to-hydrogen ratio relative to the Sun (0 = solar, + = metal-rich, − = metal-poor)",
      fmt(s.feh_init, 2)],
    ["Phase",
      "evolutionary stage — MS: core-hydrogen-burning main sequence · SGB/RGB: sub-/red-giant branch · CHeB: core-helium burning · EAGB: early asymptotic-giant branch (the second giant ascent, where the track ends)",
      s.phase],
    ["EEP",
      "equivalent evolutionary point — a phase-aligned index so stars of any mass line up stage-by-stage (it is the x-axis of the composition panel)",
      fmt(s.eep, 4)],
    ["Age",
      "time elapsed since birth on the zero-age main sequence",
      gyr(s.age_yr)],
    ["L",
      "luminosity — total power the star radiates, in Suns (1 L☉ = 3.83×10²⁶ W)",
      `${fmt(s.L_lsun)} L☉`],
    ["Teff",
      "effective temperature — the surface temperature that sets the star's color",
      `${fmt(s.Teff_K, 4)} K`],
    ["R",
      "radius, in solar radii (1 R☉ ≈ 696,000 km)",
      `${fmt(s.R_rsun)} R☉`],
    ["log g",
      "surface gravity, log₁₀ in cgs — high for compact dwarfs, low for puffed-up giants",
      fmt(s.logg, 3)],
    ["X / Y / Z surface",
      "surface mass fractions: hydrogen (X) / helium (Y) / metals (Z), summing to 1",
      `${fmt(s.X_surf)} / ${fmt(s.Y_surf)} / ${fmt(s.Z_surf, 2)}`],
    ["X / Y / Z core",
      "core mass fractions — watch hydrogen fall and helium rise as fusion proceeds",
      `${fmt(s.X_core)} / ${fmt(s.Y_core)} / ${fmt(s.Z_core, 2)}`],
    ["v_rot",
      "surface equatorial rotation velocity — MIST's own value for the selected " +
      "rotation. It is 0 on the non-rotating grid (and below the ~1.2 M☉ Kraft break, " +
      "where MIST zeroes rotation), and the real, evolving speed on the rotating grid: " +
      "fast on the zero-age main sequence, then falling as the star expands and its winds " +
      "carry off angular momentum. Toggle Rotation (below [Fe/H]) to switch grids.",
      s.v_rot_kms === null ? "n/a" : `${fmt(s.v_rot_kms)} km/s`],
    ["activity",
      "a 0–1 proxy for magnetic activity — the dynamo-driven surface magnetism " +
      "behind starspots, flares and chromospheric/coronal heating. Cool stars " +
      "with deep convective envelopes and fast rotation are the most active, and " +
      "activity fades as a star spins down with age. Here it is a hand-built, " +
      "evocative stand-in (spec §7): flavored by the star's state, not solved " +
      "from a real dynamo — it exists to drive the look of the corona in a later " +
      "phase, not to predict a star's true activity level.",
      s.activity === null ? "n/a" : fmt(s.activity, 2)],
  ];
  // The per-quantity pedagogy now lives behind a "?" (hover/focus to read it),
  // so the readout is a compact term → value table instead of a wall of prose.
  els.readout.innerHTML = rows
    .map(([k, d, v]) =>
      `<div class="row"><div class="term">${k} ${help(d)}</div>` +
      `<div class="v">${v}</div></div>`)
    .join("");
}

// The white-dwarf readout — a focused subset of the state's fields plus the two
// endgame-specific numbers (the final/remnant mass and the cooling age). Same row
// markup as renderReadout, but WD-relevant (no v_rot/activity — meaningless for a
// degenerate remnant; X/Y/Z surface kept, the thin envelope's make-up).
function renderWDReadout(s, z) {
  const knee = endgame.states[z.knee];
  const coolingAge = s.age_yr - knee.age_yr;     // since the central-star peak
  const rows = [
    ["Progenitor",
      "the initial main-sequence mass this white dwarf evolved from (snapped to the nearest real grid track — never interpolated)",
      `${fmt(s.mass_init_msun)} M☉`],
    ["[Fe/H]",
      "metallicity of the progenitor (snapped to the nearest grid value)",
      fmt(s.feh_init, 2)],
    ["Remnant mass",
      "the white dwarf's final mass — far less than the progenitor's, the rest returned to space as a planetary nebula and earlier winds (the initial–final mass relation)",
      endgame.final_mass_msun == null ? "—" : `${fmt(endgame.final_mass_msun)} M☉`],
    ["Phase",
      "TPAGB: thermal-pulsing AGB giant · post-AGB: the bared core heating to a planetary-nebula central star, then cooling to a degenerate white dwarf",
      s.phase],
    ["Age",
      "total age since birth on the zero-age main sequence — a low-mass white dwarf keeps cooling for tens of billions of years (longer than the present age of the Universe)",
      gyr(s.age_yr)],
    ["Cooling age",
      "time since the hot central-star peak — i.e. how long this object has been cooling as a white dwarf (negative before that peak, shown as —)",
      coolingAge > 0 ? gyr(coolingAge) : "—"],
    ["L",
      "luminosity in Suns — a fading central star can briefly outshine the Sun thousands-fold, then drops below 1e-4 L☉ as a cold cinder",
      `${fmt(s.L_lsun)} L☉`],
    ["Teff",
      "effective (surface) temperature — peaks near 100 000 K at the central-star stage, then falls for billions of years toward a few thousand K",
      `${fmt(s.Teff_K, 4)} K`],
    ["R",
      "radius in solar radii — a white dwarf is Earth-sized (~0.01 R☉), packing a stellar mass into a planet-sized sphere (see the true-size scale bar)",
      `${fmt(s.R_rsun)} R☉`],
    ["log g",
      "surface gravity, log₁₀ cgs — enormous (7–9) for a degenerate remnant, vs ~4.4 for the Sun: the signature of electron-degeneracy support",
      fmt(s.logg, 3)],
    ["X / Y / Z surface",
      "surface mass fractions: hydrogen (X) / helium (Y) / metals (Z). A thin residual envelope sits over the degenerate C/O core (the real DA/DB layering comes with the endgame spectra)",
      `${fmt(s.X_surf)} / ${fmt(s.Y_surf)} / ${fmt(s.Z_surf, 2)}`],
  ];
  els.readout.innerHTML = rows
    .map(([k, d, v]) =>
      `<div class="row"><div class="term">${k} ${help(d)}</div>` +
      `<div class="v">${v}</div></div>`)
    .join("");
}

// The Wolf–Rayet readout — the progenitor + the stripping story. The surface mass
// fractions ARE the WN→WC→WO sequence (hydrogen gone, helium then carbon/oxygen
// exposed), so they get pride of place; the final mass is the fully-stripped endpoint
// (the rest carried off by winds), after which the core collapses (not simulated). No
// cooling-age / remnant-mass rows (those are the WD's) — a WR doesn't leave a WD.
function renderWRReadout(s) {
  const ms = s.metals_surf || {};
  const rows = [
    ["Progenitor",
      "the initial main-sequence mass of this Wolf–Rayet (snapped to the nearest real grid track — never interpolated)",
      `${fmt(s.mass_init_msun)} M☉`],
    ["[Fe/H]",
      "metallicity of the progenitor (snapped to the nearest grid value). More metals drive stronger winds, so the envelope strips — and the WR phase begins — at a lower mass",
      fmt(s.feh_init, 2)],
    ["Final mass",
      "the fully-stripped mass at the end of the Wolf–Rayet phase — far below the progenitor's, the rest carried off by powerful winds. After this the core collapses to a neutron star or black hole (not simulated)",
      endgame && endgame.final_mass_msun != null ? `${fmt(endgame.final_mass_msun)} M☉` : "—"],
    ["Phase",
      "WR: the Wolf–Rayet phase — the stripped, blazing helium/carbon-burning core, badly exposed by winds. Its subtype (WN/WC/WO) is shown under the 3D star and read from the surface composition",
      s.phase],
    ["Age",
      "total age since birth on the zero-age main sequence — a massive star reaches the Wolf–Rayet phase in only a few million years",
      gyr(s.age_yr)],
    ["L",
      "luminosity in Suns — Wolf–Rayet stars are extremely luminous (10⁵–10⁶ L☉) despite their small stripped radii",
      `${fmt(s.L_lsun)} L☉`],
    ["Teff",
      "effective (surface) temperature — the bared core climbs toward ~250,000 K as the stripping deepens (far hotter than any main-sequence star)",
      `${fmt(s.Teff_K, 4)} K`],
    ["R",
      "radius in solar radii — the stripped core shrinks from a few R☉ to sub-solar as the envelope is peeled away",
      `${fmt(s.R_rsun)} R☉`],
    ["log g",
      "surface gravity, log₁₀ cgs — rising as the compact core is bared",
      fmt(s.logg, 3)],
    ["X / Y / Z surface",
      "surface mass fractions: hydrogen (X) / helium (Y) / metals (Z). This IS the Wolf–Rayet sequence: hydrogen vanishes (WN), then helium burning surfaces carbon and oxygen so Z climbs (WC/WO)",
      `${fmt(s.X_surf)} / ${fmt(s.Y_surf)} / ${fmt(s.Z_surf, 2)}`],
    ["surface C / N / O",
      "surface carbon / nitrogen / oxygen mass fractions — the spectral fingerprints: nitrogen marks the WN (nitrogen) sequence, carbon and oxygen the WC/WO (carbon/oxygen) sequence",
      `${fmt(ms.C ?? 0, 2)} / ${fmt(ms.N ?? 0, 2)} / ${fmt(ms.O ?? 0, 2)}`],
  ];
  els.readout.innerHTML = rows
    .map(([k, d, v]) =>
      `<div class="row"><div class="term">${k} ${help(d)}</div>` +
      `<div class="v">${v}</div></div>`)
    .join("");
}

// Render the current white-dwarf endgame state (a pure function of the pre-fetched
// `endgame.states` + `wdFraction` — no fetch). The 3D star, scale bar, HR marker and
// composition take the StellarState as-is; classification/SED/spectrum are told it's
// the endgame (WD label; no dynamo overlay; spectrum placeholder).
function refreshWD() {
  if (!endgame || !endgame.states.length) return;
  const z = wdZones(endgame.states);
  const i = Math.max(0, Math.min(endgame.states.length - 1, wdIndexFromFraction(wdFraction, z)));
  const s = endgame.states[i];

  star.update(s, { endgame: "wd" });   // smooth degenerate sphere, cooling color, no corona
  classification.update(s, "wd");
  scale.update(s);
  hr.update(s);
  comp.update(s);                       // WD structure cross-section (comp is in endgame mode)
  sed.update(s, { endgame: true });
  // Phase-aware spectrum (Chunk 6): a TPAGB giant / contracting post-AGB star (low
  // surface gravity, cool) still has a real MAIN-cube spectrum, so route it through
  // the normal live consumer; the DEGENERATE remnant AND the hot central star go to
  // the WD cube (/wd_spectrum). Route there when log g ≥ 6 (the main(≤5)/Koester(≥6.5)
  // gravity gap) OR Teff > 55000 K — 55 kK is the MAIN cube's real ceiling (OSTAR, the
  // hottest grid in MSG), so above it ONLY the WD cube can serve a spectrum: the whole
  // post-AGB rise (~55–80 kK at log g ~5–6, Koester) through the ~100–190 kK central
  // star (TMAP, Chunk 6b) routes here continuously, no "no model" flash in between. The
  // cube's optical is log g-insensitive at those temperatures (measured Δ ~0.03), so
  // clamping the low-gravity rows up to the 6.5 floor is invisible.
  if (s.logg != null && (s.logg >= 6.0 || s.Teff_K > 55000)) spectrum.updateWD(s);
  else spectrum.update(s);
  renderWDReadout(s, z);

  els.status.style.color = teffToCSS(s.Teff_K);
  els.status.innerHTML =
    tipSpan("WD endgame",
      "The reversible white-dwarf endgame: a scrubbable sequence past the normal " +
      "track, snapped to one real grid track. Slide ‘Back to the living star’ to leave.") +
    " · " + tipSpan(s.phase, phaseTip(s.phase)) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");

  // The cooling caption names the current act and carries the TOTAL age (living life +
  // endgame cooling, measured from ZAMS — the same s.age_yr as the readout's Age row,
  // surfaced here where the eye is). The cooling age (since the central-star peak) is the
  // separate "how long a white dwarf" clock.
  const coolingAge = s.age_yr - endgame.states[z.knee].age_yr;
  const total = gyr(s.age_yr);
  let cap;
  if (i <= z.tpEnd)
    cap = `Thermal-pulse phase — the dying giant sheds its envelope · total age ${total} since ZAMS.`;
  else if (i < z.knee)
    cap = `Contracting toward the hot planetary-nebula central star · total age ${total} since ZAMS.`;
  else cap = `Cooling white dwarf · ${gyr(coolingAge)} since the central-star peak ` +
    `· total age ${total} since ZAMS · Teff ${fmt(s.Teff_K, 4)} K.`;
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = cap;
}

// Render the current Wolf–Rayet endgame state (a pure function of the pre-fetched
// `endgame.states` + `wrFraction` — no fetch, mirrors refreshWD). The composition panel
// uses its NORMAL burning-abundance views (the WR sub-track is a real EEP axis with an
// evolving surface — the WN→WC→WO story falls out of the data), so it's driven via the
// usual setTrack (in enterWR) + update here, not the WD structure view. The 3D star is a
// smooth hot sphere (the Chunk-5 wind shader is later); the spectrum is an honest
// placeholder (WR wind-emission spectra are Chunk 7); the SED drops the coronal band.
function refreshWR() {
  if (!endgame || !endgame.states.length) return;
  const z = wrZones(endgame.states);
  const i = Math.max(0, Math.min(endgame.states.length - 1, wrIndexFromFraction(wrFraction, z)));
  const s = endgame.states[i];

  star.update(s, { endgame: "wr" });   // smooth blazing-hot sphere (Chunk-5 wind shader later)
  classification.update(s, "wr");      // WN/WC/WO subtype, read from the surface composition
  scale.update(s);
  hr.update(s);
  comp.update(s);                       // normal views over the WR sub-track (stripped surface)
  sed.update(s, { endgame: "wr" });     // blackbody only — no coronal band (wind, not dynamo)
  // WR wind-emission spectrum (Chunk 7): the PoWR cube via /wr_spectrum. The runtime
  // places the star on PoWR's (T*, Rt) axes and either shows a real emission spectrum
  // (the cool, hydrogen-rich WNh entry) or an honest "no model" frame (the hot stripped
  // core, hotter/denser-wind than any PoWR model — recipe §7a). Either way it's driven
  // by the state, no placeholder.
  spectrum.updateWR(s);
  renderWRReadout(s);

  els.status.style.color = teffToCSS(s.Teff_K);
  els.status.innerHTML =
    tipSpan("WR endgame",
      "The reversible Wolf–Rayet endgame: a scrubbable sequence past the normal track, " +
      "snapped to one real grid track — the stripped, blazing core of a massive star. " +
      "Slide ‘Back to the living star’ to leave.") +
    " · " + tipSpan(s.phase, phaseTip(s.phase)) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");

  // The caption names the current act and, at the hot end, narrates the un-simulated gap
  // — the core-collapse supernova that follows the WR phase (the honest mirror of the WD
  // gateway's PN-ejection note; here the un-modeled step is the ENDPOINT, not the entry).
  const total = gyr(s.age_yr);
  let cap;
  if (i >= z.last)
    cap = `Hottest stripped core (~${Math.round(s.Teff_K / 1000)} kK) — next is ` +
      `core-collapse to a neutron star or black hole, which this simulator doesn't model ` +
      `· age ${total}.`;
  else if ((s.Z_surf ?? 0) >= 0.4)
    cap = `Carbon/oxygen surface (WC/WO) — core-helium burning has surfaced carbon and ` +
      `oxygen · age ${total} · Teff ${fmt(s.Teff_K, 4)} K.`;
  else if ((s.X_surf ?? 0) > 0.1)
    cap = `Hydrogen-rich helium surface (WNh) — winds are peeling away the last of the ` +
      `hydrogen envelope · age ${total} · Teff ${fmt(s.Teff_K, 4)} K.`;
  else
    cap = `Helium surface (WN) — the hydrogen envelope is gone, baring the helium core ` +
      `· age ${total} · Teff ${fmt(s.Teff_K, 4)} K.`;
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = cap;
}

// Show/hide the gateway button (or the supernova dead-end note) — only when in the
// living mode AND scrubbed to ~the end of the star's life AND we have endgame data
// matching the current (mass, [Fe/H]). WD / WR each get a "Continue" button; the
// core-collapse gap (SN) gets an honest note; "none" → nothing.
function updateGateway() {
  if (mode !== "live") return;   // the whole block is hidden inside an endgame
  const eg = (endgame && endgameKey === egKey()) ? endgame : null;
  const egMeta = (endgameMeta && endgameMetaKey === egKey()) ? endgameMeta : null;
  // The button's fate descriptor: prefer the FULL result (authoritative; it also backs
  // enter + the HR preview), but fall back to the tiny meta result so the button LIGHTS UP
  // before the ~1 MB full fetch lands. `has_states` (meta) mirrors `states.length` (full),
  // so the WD/WR "has a renderable sequence" guard is identical either way.
  const fType = eg ? eg.type : (egMeta ? egMeta.type : null);
  const fHas = eg ? eg.states.length > 0 : (egMeta ? !!egMeta.has_states : false);
  const fMass = eg ? eg.mass_init_msun : (egMeta ? egMeta.mass_init_msun : null);
  // Show the fate's control as soon as the endgame TYPE is known — fetchEndgameMeta fetches
  // it (~120 B) on every track, so the fate lights up almost immediately. The WD/WR
  // "Continue" button is shown but kept DISABLED (greyed) until the star is scrubbed to the
  // very end of its life, where it unlocks. So the button never pops into existence and
  // resizes the panel (item 4): it sits in place, foreshadowing the endgame, and "lights
  // up" when you arrive. The core-collapse note (no Continue — the remnant isn't modeled)
  // likewise shows from the start as an honest dead-end marker.
  const atEnd = ageFraction >= GATE_SHOW;
  const isWd = fType === "WD" && fHas;
  const isWr = fType === "WR" && fHas;
  const isSn = fType === "SN";
  els.gatewayWd.hidden = !isWd;
  els.gatewayWr.hidden = !isWr;
  els.gatewaySn.hidden = !isSn;
  // ENABLE gates on the FULL `eg` (not just `atEnd`): the button can now SHOW from the tiny
  // `egMeta` before the full fetch lands, but enterWD/WR read the full `endgame.states`, so
  // enabling on meta alone would make a click in the meta→full gap a silent no-op (a dead
  // button — reachable on the NORMAL path: change mass while pinned at end, or exit→re-enter
  // the reversible gateway, both of which restart the full fetch from null while atEnd holds).
  // So: appearance is instant (meta), but the button stays greyed until the data it acts on
  // is actually present. Happy path is unchanged (full loaded seconds ago → eg present).
  els.gatewayWd.disabled = !atEnd || !eg;
  els.gatewayWr.disabled = !atEnd || !eg;
  // SN differs: its model is NOT on the track (/endgame returns states=[]), so enterSN fetches
  // /supernova on click — the button only needs the SN classification (from EITHER cache), so
  // it enables on `atEnd` alone. The foreshadowing note shows from ZAMS (user-confirmed), now
  // pointing at the renderable light curve rather than the old "remnant not modeled" dead-end.
  els.gatewaySn.disabled = !atEnd;
  els.gatewaySnNote.hidden = !isSn;
  if (isSn) {
    els.gatewaySnNote.innerHTML =
      `<b>Core collapse.</b> A ${fmt(fMass)} M☉ star ends its life as a supernova. ` +
      `Scrub to the end, then continue to watch the ⁵⁶Ni-powered light curve.`;
  }
  // The "computing the star's fate…" placeholder shows exactly while a /endgame fetch is
  // IN FLIGHT and we don't yet have a resolved fate (from EITHER cache) for the current
  // (mass, [Fe/H]) — i.e. the brief gap after a mass/[Fe/H] change. Meta now resolves the
  // type in ~tens of ms (warm), so this barely flashes; it still covers the COLD case (the
  // classifier builds the full track, up to ~1 s on a cache miss). The moment a fetch
  // settles, endgameLoading clears (success → a fate is `known`; failure → no fate), so the
  // slot falls back to the real control or to blank — never a stuck spinner. (Gating on
  // endgameLoading, NOT on `!!known`: a fate stays unknown on a fetch failure, so `!known`
  // alone would re-show the placeholder forever.)
  const known = !!fType;
  els.gatewayLoading.hidden = !(endgameLoading && !known);
  els.gateway.hidden = false;   // block stays in the layout (reserved height); only its
                                // children toggle, so the panel never jitters in live mode
}

// --- rotation toggle: fetch the honesty gate + render the control ------------
// Fetch /rotation_status for a (mass, [Fe/H]). Tiny (~60 B) and AWAITED before the
// track/endgame fetch on a mass/[Fe/H] change, so the effective vvcrit is current
// (avoids a /track?vvcrit=0.4 422 at an [Fe/H] the rotating axis lacks). Never throws —
// a failure (or a provider with no rotation) degrades to "no grid" (toggle hidden).
async function fetchRotStatus(mass, feh) {
  try {
    return await fetchJSON(`/rotation_status?mass=${mass}&feh=${feh}`);
  } catch {
    return { has_grid: false, threshold_msun: null, active: false };
  }
}

// Render the UNIFIED rotation control (rotation Chunk 3 unify) — one control, two
// regime-gated facets, each shown only where it's honest:
//
//   * Track facet (the vvcrit toggle): shown where a rotating grid covers this [Fe/H]
//     (`has_grid`) AND toggling actually changes the track (`active`, i.e. above the ~1.2 M☉
//     Kraft break). Below the break it is a data-derived no-op (the rotating track is
//     bit-identical), so it is HIDDEN, not greyed — a greyed dead knob next to the live period
//     slider was confusing (user feedback; supersedes the earlier greyed-not-hidden design).
//   * Activity facet (the period slider, sed.js's #sed-rot): shown only in the cool
//     main-sequence dynamo regime (`sed.rotationAllowed()`), where the rotation period
//     sets the coronal X-ray line on the SED. sed.js owns the slider + draws the line.
//
// The two regimes barely overlap, so usually one facet shows; at the Sun ONLY the activity
// facet shows (the track facet is a no-op there → hidden). The whole control hides inside an
// endgame or where NEITHER facet is honest (e.g. a cool giant) — absent, not a dead knob.
function updateRotControl() {
  const c = els.rotControl;
  if (!c) return;
  if (mode !== "live") { c.hidden = true; return; }
  // Show the track toggle ONLY where it actually changes the track (above the ~1.2 M☉ Kraft
  // break, `active`) — NOT greyed below it. A greyed, no-op toggle sitting under the same
  // "Rotation" header as the live period slider (e.g. at the Sun) read as a confusing dead
  // knob; hiding it matches this control's own "absent, not a dead knob" philosophy and
  // leaves just the self-labeled "Rotation period" slider. (`active` is mass/[Fe/H]-derived,
  // stable across an age scrub, so this never causes a mid-drag reflow above the Age slider.)
  const showToggle = !!(rotStatus.has_grid && rotStatus.active);
  // VISIBILITY of the period facet = the cool-MS family (also track-stable); sed.js greys it
  // per-age via rot.sync(). Both facets are track-stable, so an age scrub never changes height.
  const showPeriod = coolDynamoFamily();
  c.hidden = !(showToggle || showPeriod);
  // -- track facet --
  els.rotToggleRow.hidden = !showToggle;
  els.rotNote.hidden = !showToggle;
  if (showToggle) {
    els.rotToggle.checked = rotationOn;
    els.rotToggle.disabled = false;                       // shown ⇒ always live now
    els.rotToggleRow.classList.remove("disabled");        // clear any stale greyed styling
    els.rotNote.textContent = rotationOn
      ? "Rotating track (v/vcrit 0.4): main-sequence N & He enrichment, longer life, shifted track."
      : "Non-rotating track — toggle to add MIST's v/vcrit = 0.4 rotation.";
  }
  // -- activity facet -- (sed.js syncs the slider/note internally via rot.sync())
  els.sedRot.hidden = !showPeriod;
}

// Type-only companion to fetchEndgamePreview: fetch JUST the fate metadata (~120 B via
// /endgame?meta=1) so the gateway button appears (greyed, foreshadowing) the instant a new
// track lands — instead of waiting ~150 ms+ for the full ~1 MB /endgame the preview/enter
// path fetches. Purely ADDITIVE: its OWN token + cache, never touches endgame/endgameToken,
// so the stabilized full-fetch machinery (Chunk D) is unchanged. updateGateway prefers the
// full `endgame` when present and falls back to `endgameMeta` for the button alone — enter
// + the HR preview + resnap all still read the full `endgame`, so this can't regress them.
async function fetchEndgameMeta() {
  if (mode !== "live") return;
  const key = egKey();
  const tok = ++endgameMetaToken;
  const mass = massValue, feh = Number(els.feh.value);
  try {
    const m = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}&meta=1`);
    // Drop a stale/superseded response, or one for a star we've since moved off of.
    if (tok !== endgameMetaToken || mode !== "live" || egKey() !== key) return;
    endgameMeta = m; endgameMetaKey = key;
    // Note: do NOT touch endgameLoading here. It's owned by the full fetch
    // (fetchEndgamePreview — Chunk D). The "computing…" placeholder hides via the `known`
    // flag in updateGateway the moment EITHER cache resolves, so a successful meta hides it
    // immediately; a FAILED meta leaves the placeholder up (correct — the fate is still
    // unknown until the full fetch lands), and the full fetch's settle is the sole owner
    // that finally clears endgameLoading. So a meta failure can never blank the slot early.
    updateGateway();
  } catch {
    // non-fatal: the full fetch still populates the button when it lands. Nothing to paint
    // from meta (endgameMeta stays null), and we must not clear endgameLoading (see above).
  }
}

// Fetch /endgame as soon as a new track lands, so the living HR can show a faint
// preview of where the star is headed (a white dwarf) — and the gateway data is already
// warm when the user scrubs to the very end. Only a WD endgame yields a preview; SN/WR
// stars show nothing (we never promise a remnant the star won't form). Latest-wins
// (shares endgameToken with maybeFetchEndgame, which then no-ops once this populated the
// cache). Fire-and-forget — never blocks the marker refresh. The ~1 MB fetch rides the
// track debounce (once per settled mass/[Fe/H]), so age scrubbing stays light.
async function fetchEndgamePreview() {
  if (mode !== "live") return;
  const key = egKey();
  const tok = ++endgameToken;
  endgameLoading = true;   // a fetch is now in flight → the placeholder is live
  const mass = massValue, feh = Number(els.feh.value);
  try {
    const eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`);
    // Drop a stale/superseded response, or one for a star we've since moved off of.
    if (tok !== endgameToken || mode !== "live" || egKey() !== key) return;
    endgame = eg; endgameKey = key;
    endgameLoading = false;
    hr.setEndgamePreview(eg.type === "WD" && eg.states.length ? eg.states : null);
    updateGateway();
  } catch {
    // non-fatal: no preview/gateway this time. Only the LATEST fetch clears the loading
    // flag (a stale failure mustn't blank a still-pending newer fetch), then repaints —
    // so a failed fetch falls back to the blank reserved slot, not a stuck spinner.
    if (tok === endgameToken && mode === "live") { endgameLoading = false; updateGateway(); }
  }
}

// Lazily fetch /endgame as the star nears the end of its life, so the gateway is ready
// when the user reaches the slider limit (keeps normal scrubbing light — no 1 MB fetch
// per mass drag). Latest-wins; re-fetches whenever (mass, [Fe/H]) changed.
async function maybeFetchEndgame() {
  if (mode !== "live" || ageFraction < GATE_FETCH) return;
  const key = egKey();
  if (endgame && endgameKey === key) return;
  const tok = ++endgameToken;
  endgameLoading = true;   // (the age-scrub path; the mass-change path fetches via
                           // fetchEndgamePreview, which sets this too)
  const mass = massValue, feh = Number(els.feh.value);
  try {
    const eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`);
    if (tok !== endgameToken || mode !== "live") return;
    endgame = eg; endgameKey = key;
    endgameLoading = false;
    // Set the HR preview here too, not just in fetchEndgamePreview: the two share
    // endgameToken, so if both ever race (e.g. a mass change fires the preview fetch, then
    // an age scrub past GATE_FETCH fires this one before the first lands) only the
    // token-winner runs its success branch — it must also set the preview, or the dashed
    // track silently fails to appear.
    hr.setEndgamePreview(eg.type === "WD" && eg.states.length ? eg.states : null);
    updateGateway();
  } catch {
    // non-fatal: no gateway this time. Latest-token-only clear + repaint (see above).
    if (tok === endgameToken && mode === "live") { endgameLoading = false; updateGateway(); }
  }
}

function updateLiveGateway() {
  if (mode !== "live") return;
  maybeFetchEndgame();   // async; calls updateGateway() again when it lands
  updateGateway();       // immediate, with whatever we currently have
}

// Enter the reversible white-dwarf endgame from the gateway button.
function enterWD() {
  if (!endgame || endgame.type !== "WD" || !endgame.states.length) return;
  mode = "wd";
  updateRotControl();   // hide the rotation toggle inside the endgame (mode != live)
  // Invalidate any in-flight live /track so it can't land and clobber the WD render
  // (the age scrub is fetch-free now, so /track is the only live fetch to guard).
  trackToken++;
  document.body.classList.add("wd-mode");
  lastEgMass = massValue; lastEgFeh = Number(els.feh.value);
  setWDResnapNote("");
  els.gateway.hidden = true;
  els.endgameBar.hidden = false;
  hr.setEndgame(endgame.states);
  comp.setEndgame(endgame.states);
  rebuildWDTicks();
  wdFraction = 0;                 // start at the first thermal pulse — scrub forward
  els.age.value = wdFraction;
  refreshWD();
}

// Enter the reversible Wolf–Rayet endgame from the gateway button (mirrors enterWD).
// The composition panel uses its NORMAL burning-abundance views (the WN→WC→WO surface
// story is real data on a real EEP axis), so it's fed via setTrack here — NOT the WD
// structure view (no comp.setEndgame).
function enterWR() {
  if (!endgame || endgame.type !== "WR" || !endgame.states.length) return;
  mode = "wr";
  updateRotControl();   // hide the rotation toggle inside the endgame (mode != live)
  // Invalidate any in-flight live /track so it can't land and clobber the WR render
  // (the age scrub is fetch-free now, so /track is the only live fetch to guard).
  trackToken++;
  document.body.classList.add("wr-mode");
  lastEgMass = massValue; lastEgFeh = Number(els.feh.value);
  setWDResnapNote("");
  els.gateway.hidden = true;
  els.endgameBar.hidden = false;
  hr.setEndgame(endgame.states, "wr");
  comp.setTrack(endgame.states);   // normal core/surface views over the WR sub-track
  rebuildWRTicks();
  wrFraction = 0;                   // start at the WR onset — scrub forward to the hot end
  els.age.value = wrFraction;
  refreshWR();
}

// Leave the endgame (WD or WR), reversibly — back to the living star at the end of its
// track. Shared by both modes: the only mode-specific consumer state is the comp panel's
// WD structure flag (clearEndgame is a no-op for WR, which used the normal views).
function exitEndgame() {
  mode = "live";
  document.body.classList.remove("wd-mode", "wr-mode", "sn-mode");
  els.endgameBar.hidden = true;
  els.snControl.hidden = true;   // hide the ⁵⁶Ni slider (SN-only)
  setWDResnapNote("");
  hr.clearEndgame();
  comp.clearEndgame();
  endgame = null; endgameKey = null;
  snModel = null; snToken++;     // drop the SN model + invalidate any in-flight /supernova fetch
  // Return to the LIVING version of the endgame progenitor we were viewing
  // (lastEgMass/Feh) — not whatever transient value massValue holds. This is robust to
  // the focus/blur race where a still-focused mass box re-commits a reverted-away value
  // on the click that triggers this exit. Sync the controls to it.
  massValue = lastEgMass;
  els.feh.value = lastEgFeh;
  els.mass.value = clamp01(sliderFromMass(massValue));
  setNum(els.massNum, fmt(massValue));
  setNum(els.fehNum, lastEgFeh.toFixed(2));
  pinAgeToEnd = true;   // land the rebuilt track at its very end
  // feh/mass may have re-snapped in WD mode, so refresh the mass range too before the
  // track; refreshMassRangeThenTrack() rebuilds the live track + age window + marker.
  refreshMassRangeThenTrack();
}

// Re-snap the WD progenitor after a mass/[Fe/H] change inside the endgame. If the new
// progenitor still ends as a white dwarf, swap in its cooling sequence (keeping the
// cooling fraction). If it now core-collapses (SN) or strips to a WR, there is no WD —
// revert to the last WD progenitor and say so (mirrors the live dead-corner clamp).
async function tryWDResnap() {
  if (mode !== "wd") return;
  const tok = ++endgameToken;
  const mass = massValue, feh = Number(els.feh.value);
  // Keep the rotation gate current as [Fe/H] drags (it may leave the rotating grid),
  // so effVvcrit() can fall back to non-rotating and /endgame never 422s off-grid.
  rotStatus = await fetchRotStatus(mass, feh);
  if (tok !== endgameToken || mode !== "wd") return;
  let eg;
  try { eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`); }
  catch { return; }
  if (tok !== endgameToken || mode !== "wd") return;
  if (eg.type === "WD" && eg.states.length) {
    endgame = eg; endgameKey = egKey();
    lastEgMass = mass; lastEgFeh = feh;
    setWDResnapNote("");
    hr.setEndgame(eg.states);
    comp.setEndgame(eg.states);
    rebuildWDTicks();
    refreshWD();
  } else {
    // Not a white-dwarf progenitor — revert to the last WD star.
    massValue = lastEgMass;
    els.feh.value = lastEgFeh;
    els.mass.value = clamp01(sliderFromMass(massValue));
    setNum(els.massNum, fmt(massValue));
    setNum(els.fehNum, lastEgFeh.toFixed(2));
    setWDResnapNote(eg.type === "SN"
      ? `A ${fmt(eg.mass_init_msun)} M☉ star core-collapses (supernova), not a white ` +
        `dwarf — reverted to ${fmt(lastEgMass)} M☉.`
      : eg.type === "WR"
        ? `That star strips to a Wolf–Rayet, not a white dwarf — reverted to ` +
          `${fmt(lastEgMass)} M☉.`
        : `No white-dwarf endgame for that star — reverted to ${fmt(lastEgMass)} M☉.`);
    refreshWD();
  }
}

// Re-snap the WR progenitor after a mass/[Fe/H] change inside the endgame (mirrors
// tryWDResnap). If the new progenitor still strips to a Wolf–Rayet, swap in its
// sub-track (keeping the scrub fraction). If it now ends as a white dwarf or
// core-collapses (SN), there is no WR — revert to the last WR progenitor and say so.
async function tryWRResnap() {
  if (mode !== "wr") return;
  const tok = ++endgameToken;
  const mass = massValue, feh = Number(els.feh.value);
  // Keep the rotation gate current as [Fe/H] drags (see tryWDResnap).
  rotStatus = await fetchRotStatus(mass, feh);
  if (tok !== endgameToken || mode !== "wr") return;
  let eg;
  try { eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`); }
  catch { return; }
  if (tok !== endgameToken || mode !== "wr") return;
  if (eg.type === "WR" && eg.states.length) {
    endgame = eg; endgameKey = egKey();
    lastEgMass = mass; lastEgFeh = feh;
    setWDResnapNote("");
    hr.setEndgame(eg.states, "wr");
    comp.setTrack(eg.states);
    rebuildWRTicks();
    refreshWR();
  } else {
    // Not a Wolf–Rayet progenitor — revert to the last WR star.
    massValue = lastEgMass;
    els.feh.value = lastEgFeh;
    els.mass.value = clamp01(sliderFromMass(massValue));
    setNum(els.massNum, fmt(massValue));
    setNum(els.fehNum, lastEgFeh.toFixed(2));
    setWDResnapNote(eg.type === "SN"
      ? `A ${fmt(eg.mass_init_msun)} M☉ star core-collapses (supernova) without a ` +
        `Wolf–Rayet phase — reverted to ${fmt(lastEgMass)} M☉.`
      : eg.type === "WD"
        ? `That star ends as a white dwarf, not a Wolf–Rayet — reverted to ` +
          `${fmt(lastEgMass)} M☉.`
        : `No Wolf–Rayet endgame for that star — reverted to ${fmt(lastEgMass)} M☉.`);
    refreshWR();
  }
}

// --- the supernova endgame (SN Chunk 2) --------------------------------------
// The SN scrub axis is LINEAR in days (not the WD's piecewise log-cooling map): the
// light-curve panel's x-axis is linear days so the ⁵⁶Co tail stays straight (the Tier-1
// anchor), and the scrubber matches it so the marker tracks the slider — the long
// radioactive tail (where the ⁵⁶Ni story lives) gets the bulk of the travel, while the
// fast early rise compresses (the states are log-spaced in time, so the tail still has
// plenty of rows). Position 0 = the explosion; 1 = the last sample (~500 d).
function snMaxDay() {
  const t = snModel && snModel.light_curve && snModel.light_curve.time_days;
  return t && t.length ? t[t.length - 1] : 500;
}
// slider fraction (0..1, linear in days) -> nearest photosphere-state index by time.
function snStateIndex(frac) {
  const t = snModel.light_curve.time_days;
  const target = clamp01(frac) * snMaxDay();
  let best = 0, bestD = Infinity;
  for (let i = 0; i < t.length; i++) {
    const d = Math.abs(t[i] - target);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}
// Snap the SN scrub to its landmarks (explosion / plateau end / last sample).
function snapSNFraction(raw) {
  const maxDay = snMaxDay();
  const targets = [0, 1];
  if (snModel && snModel.has_plateau && snModel.plateau_duration_days)
    targets.push(clamp01(snModel.plateau_duration_days / maxDay));
  const thresh = 0.015;
  let best = raw, bestD = thresh;
  for (const t of targets) { const d = Math.abs(raw - t); if (d < bestD) { bestD = d; best = t; } }
  return clamp01(best);
}
// The SN time-scrub landmark ticks: the explosion, the plateau end (only if the curve has
// one), and the last sampled day. Few + well separated — no stagger.
function rebuildSNTicks() {
  if (!snModel || !snModel.light_curve) return;
  const maxDay = snMaxDay();
  const marks = [{ pos01: 0, label: "explosion" }];
  if (snModel.has_plateau && snModel.plateau_duration_days)
    marks.push({ pos01: clamp01(snModel.plateau_duration_days / maxDay),
      label: `plateau end ~${Math.round(snModel.plateau_duration_days)} d` });
  marks.push({ pos01: 1, label: `${Math.round(maxDay)} d` });
  buildTickStrip(els.ageMarks, marks);
  els.ageTicks.innerHTML = "";   // the SN scrub uses its own snap targets, not the datalist
}

// The ⁵⁶Ni-slider note (used by configure + both handlers). In a FAILED direct collapse the
// synthesized nickel all falls back into the black hole, so the slider is inert — say so (a
// control that visibly does nothing otherwise reads as broken).
const mniNote = () =>
  (snModel && snModel.failed_sn)
    ? `Direct collapse — all of the synthesized ⁵⁶Ni falls back into the black hole, so this ` +
      `slider has no effect here (the explosion failed; there is almost no light to scale).`
    : `⁵⁶Ni = ${fmt(mniValue)} M☉ — sets the brightness scale (canonical ${M_NI_DEFAULT}; ` +
      `observed ${M_NI_MIN}–${M_NI_MAX}). The plateau shape doesn't move; only the tail height.`;

// Configure the ⁵⁶Ni slider from the current mniValue (log scale + round-yield ticks). The
// slider is disabled in a failed state (all Ni falls back → it would do nothing).
function configureSNMni() {
  const inert = !!(snModel && snModel.failed_sn);
  els.snMni.min = 0; els.snMni.max = 1; els.snMni.step = 0.001;
  els.snMni.value = posFromMni(mniValue);
  els.snMni.disabled = inert;
  els.snMniNum.min = M_NI_MIN; els.snMniNum.max = M_NI_MAX; els.snMniNum.step = 0.001;
  els.snMniNum.disabled = inert;
  setNum(els.snMniNum, fmt(mniValue));
  buildTickStrip(els.snMniMarks,
    MNI_TICKS.map((m) => ({ pos01: posFromMni(m), label: m === M_NI_DEFAULT ? `${m}★` : `${m}` })));
  els.snMniNote.textContent = mniNote();
}

// The supernova readout — the progenitor + the explosion + the current photosphere. The
// explosion scalars come from snModel; the L/Teff/R from the scrubbed photosphere state.
function renderSNReadout(s) {
  const m = snModel;
  const failed = !!m.failed_sn;
  const phi = m.fallback_fraction ?? 0;
  const day = (s.age_yr ?? 0) * 365.25;
  const rows = [
    ["Progenitor",
      "the initial main-sequence mass that core-collapsed (snapped to the nearest real grid track)",
      `${fmt(m.mass_init_msun)} M☉`],
    ["[Fe/H]", "metallicity of the progenitor (snapped to the nearest grid value)", fmt(m.feh_init, 2)],
    ["Type",
      "the supernova class. This branch is Type II — the progenitor kept its hydrogen envelope (a fully stripped star is the Wolf–Rayet endpoint, a Type Ib/c, a later feature)",
      `SN ${m.type}`],
    ["Ejecta mass",
      "the mass thrown off in the explosion — the progenitor's final mass minus the compact remnant left behind",
      `${fmt(m.m_ej_msun)} M☉`],
    ["⁵⁶Ni synthesized",
      "the radioactive nickel forged in the explosion (the Tier-3 free knob) — its decay powers the tail, and the brightness scale rides on it. Drag the ⁵⁶Ni slider",
      `${fmt(m.m_ni_msun)} M☉`],
    ["⁵⁶Ni ejected",
      "how much of that nickel actually escapes. It is the deepest, innermost ash, so fallback onto the remnant swallows it first — for a heavy fallback black hole less escapes, and for a direct collapse essentially none does (the tail vanishes)",
      `${fmt(m.m_ni_ejected_msun)} M☉${phi > 0.01 ? ` (${Math.round(phi * 100)}% fell back)` : ""}`],
    ["Explosion energy",
      "the kinetic energy of the ejecta — a canonical 10⁵¹ erg (the explosion mechanism that sets it isn't modeled)",
      `${fmt(m.e_kin_erg / 1e51)}×10⁵¹ erg`],
    ["Remnant",
      "the compact object left at the centre. A labeled fallback continuum on the CO-core mass (a compactness proxy), NOT a crisp prediction: a neutron star, a fallback black hole, or — past full collapse — a direct-collapse black hole that ejects almost nothing. Real explodability is non-monotonic ('islands')",
      failed ? `black hole · ${fmt(m.remnant_mass_msun)} M☉ · direct collapse`
             : `${m.remnant_type} · ${fmt(m.remnant_mass_msun)} M☉`],
    ["Time",
      "time since the explosion — the age slider above scrubs this",
      day >= 1 ? `${fmt(day)} d` : `${fmt(day * 24)} h`],
    ["L",
      "bolometric luminosity of the expanding photosphere, in Suns — this is the light curve the panel plots",
      `${fmt(s.L_lsun)} L☉`],
    ["Teff",
      "effective temperature of the photosphere — hot at first, cooling as the ejecta expand",
      `${fmt(s.Teff_K, 4)} K`],
    ["Photosphere R",
      "radius of the expanding photosphere (R = v·t, homologous) — it swells to hundreds of AU within months (the true-size scale bar widens to show it dwarfing the planetary orbits)",
      `${fmt(s.R_rsun)} R☉`],
    ["Ejecta velocity",
      "the characteristic homologous expansion speed √(2E/M_ej) — a few thousand km/s, set by the energy and the ejecta mass",
      `${fmt(m.v_phot_kms)} km/s`],
  ];
  if (m.has_plateau) rows.push(["Plateau",
    "the recombination plateau the IIP light curve sits on — its luminosity and duration come from your star's ejecta mass and radius (Tier-2: robust in shape, ±dex in level). Heavier, more compact progenitors fall back more, so LESS ejecta gives a brighter, shorter plateau — until fallback becomes total and the explosion fails entirely (a direct collapse, no light). That bright-then-dark step at the threshold is a real explosion-vs-failure transition, not a smooth dimming",
    `${fmt(m.plateau_L_erg_s / 3.828e33)} L☉ · ${fmt(m.plateau_duration_days)} d`]);
  els.readout.innerHTML = rows
    .map(([k, d, v]) =>
      `<div class="row"><div class="term">${k} ${help(d)}</div>` +
      `<div class="v">${v}</div></div>`)
    .join("");
}

// Render the current supernova photosphere (a pure function of snModel + snFraction — no
// fetch). The light-curve panel (hr in SN mode) + the 3D star / scale / SED / classification
// / readout take the photosphere StellarState, but via the EXPLICIT {endgame:"sn"} signal
// (the ejecta log g is meaningless), so the consumers branch on the mode, not on log g.
function refreshSN() {
  if (!snModel || !snModel.states || !snModel.states.length) return;
  const i = snStateIndex(snFraction);
  const s = snModel.states[i];

  // Drive the 3D fireball→remnant (Chunk 3) from the scrubbed day: `snGrow` swells the ball
  // over the early scrub (an evocative "expanding" beat — the true AU-scale R is on the scale
  // bar), `snFade` dissipates it over the late tail to reveal the remnant. `remnant` selects
  // the NS dot vs the BH "winks out" (no dot). All evocative except the photosphere Teff color.
  const day = (s.age_yr ?? 0) * 365.25;
  const dayFrac = clamp01(day / snMaxDay());
  const failed = !!snModel.failed_sn;
  // A normal SN expands then dissipates (grow → fade). A FAILED direct collapse does NOT
  // expand — it implodes — so we skip the "expanding" beat (a small steady ball) and let it
  // fade from the start: a dim supergiant that simply winks out (star.js dims it too).
  const snGrow = failed ? 0.5 : 0.55 + 0.45 * smoothstep01(0, 0.14, dayFrac);
  const snFade = failed ? smoothstep01(0.0, 0.6, dayFrac) : smoothstep01(0.5, 0.95, dayFrac);
  // A brief shock-breakout FLASH at the explosion moment (first ~5% of the scrub) so the entry
  // reads as a violent burst rather than a dim little ball — 3D-only + evocative, gated off for
  // a failed direct collapse (there is no explosion to flash). star.js adds it to the intensity.
  const snShock = failed ? 0 : 1 - smoothstep01(0, 0.05, dayFrac);
  star.update(s, { endgame: "sn", remnant: snModel.remnant_type, failed, snGrow, snFade, snShock });
  classification.update(s, "sn", { failed });   // expanding-photosphere label (failed → direct-collapse)
  // true size — the fireball swells to ~AU scale; pass the model's PEAK radius so the scale
  // bar widens its axis to fit it (past Neptune) instead of pinning the marker to the edge.
  const snAxisMaxR = snModel.states.reduce((m, st) => Math.max(m, st.R_rsun || 0), 0);
  scale.update(s, { endgame: "sn", failed, axisMaxRsun: snAxisMaxR });
  hr.update(s);                        // the marker on the light curve (hr is in SN mode)
  comp.update(s);                      // no-op in SN mode (the onion is static, set by applySNModel)
  sed.update(s, { endgame: "sn", failed });   // blackbody only (failed → non-expanding caption)
  renderSNReadout(s);

  els.status.style.color = teffToCSS(s.Teff_K);
  els.status.innerHTML =
    tipSpan("SN endgame",
      "The core-collapse supernova endgame: a COMPUTED ⁵⁶Ni-powered light curve and an " +
      "expanding ejecta photosphere (not a snapped track — the explosion is a model). Slide " +
      "‘Back to the living star’ to leave.") +
    " · " + tipSpan(`SN ${snModel.type}`, phaseTip("SN")) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");

  let cap;
  if (failed) {
    // Direct collapse: no bright supernova at all — the progenitor implodes to a black hole
    // and fades from view (the "disappearing supergiant"). There is no plateau, no tail.
    cap = `Direct collapse — the core is so massive that fallback is total: almost no ⁵⁶Ni ` +
      `escapes and there is no bright explosion. The supergiant implodes to a black hole and ` +
      `simply winks out · day ${fmt(day)} · Teff ${fmt(s.Teff_K, 4)} K.`;
  } else if (snFade > 0.6) {
    // The ejecta have thinned: the 3D dissipates to the compact remnant. A NEUTRON STAR
    // emerges as a faint dot; a fallback BLACK HOLE drove a real (if fainter) supernova that
    // now fades to a dark, invisible remnant — NOT a "wink out" (that's the failed case above).
    const rem = snModel.remnant_type === "NS"
      ? `the thinning ejecta uncover a neutron star — a faint hot point (evocative: a real one ` +
        `is only ~20 km across and optically almost invisible, so it is NOT to scale)`
      : `a black hole formed at the centre — the supernova fades to a dark, invisible remnant`;
    cap = `Nebular phase — the ejecta thin and disperse; ${rem} · day ${fmt(day)} · ` +
      `Teff ${fmt(s.Teff_K, 4)} K.`;
  } else if (snModel.has_plateau && day <= snModel.plateau_duration_days)
    cap = `Recombination plateau — the shock-heated hydrogen envelope recombines at roughly ` +
      `constant luminosity · day ${fmt(day)} · Teff ${fmt(s.Teff_K, 4)} K.`;
  else
    cap = `Radioactive tail — ⁵⁶Co decay powers the fading light curve (its slope is the ` +
      `bullet-proof anchor) · day ${fmt(day)} · Teff ${fmt(s.Teff_K, 4)} K.`;
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = cap;
}

// Apply a freshly-fetched SupernovaModel to the panels (shared by enter / M_Ni refetch /
// re-snap): feed the light-curve panel + the composition placeholder + the spectrum
// placeholder, configure the ⁵⁶Ni slider, rebuild the ticks, and paint the current scrub.
function applySNModel(model) {
  snModel = model;
  hr.setSupernova(model, OBSERVED_SNE);
  comp.setSupernova(model);   // pre-collapse onion shell from the snapped core masses
  // SN spectra (P-Cygni absorption → nebular emission) aren't modeled — an honest
  // placeholder, NOT the living model-atmosphere spectrum (wrong for freely-expanding ejecta,
  // and the photosphere's negative log g would trip /spectrum anyway). Set once per model.
  spectrum.showPlaceholder(
    "Supernova spectra (P-Cygni lines, photospheric → nebular) aren't modeled yet — a later feature.");
  configureSNMni();
  rebuildSNTicks();
  refreshSN();
}

// Fetch the computed /supernova model for the current (mass, [Fe/H], vvcrit) + a ⁵⁶Ni mass.
// Returns the JSON (throws on a network/HTTP error). The route classifies via
// PROVIDER.endgame() then runs the sibling — so a non-SN re-snap target comes back
// is_supernova:false (the callers handle that).
async function fetchSNModel(mni) {
  const mass = massValue, feh = Number(els.feh.value);
  return fetchJSON(`/supernova?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}&m_ni=${mni}`);
}

// Enter the reversible supernova endgame from the gateway button. UNLIKE enterWD/enterWR
// (which render synchronously from the pre-fetched endgame.states), the SN model isn't on
// the track — /endgame returns states=[] for SN — so this FETCHES /supernova on click, with
// a loading caption + a latest-wins guard (a slow fetch can't paint after we've left).
async function enterSN() {
  mode = "sn";
  updateRotControl();   // hide the rotation control inside the endgame (mode != live)
  trackToken++;         // invalidate any in-flight live /track
  document.body.classList.add("sn-mode");
  lastEgMass = massValue; lastEgFeh = Number(els.feh.value);
  setWDResnapNote("");
  els.gateway.hidden = true;
  els.endgameBar.hidden = false;
  els.snControl.hidden = false;
  mniValue = M_NI_DEFAULT;
  snFraction = 0;
  els.age.value = snFraction;
  els.endgameAgeCaption.textContent = "Computing the supernova light curve…";
  const tok = ++snToken;
  let model;
  try { model = await fetchSNModel(mniValue); }
  catch {
    if (tok === snToken && mode === "sn")
      els.endgameAgeCaption.textContent = "Could not compute the supernova light curve.";
    return;
  }
  if (tok !== snToken || mode !== "sn") return;
  if (!model.is_supernova) { exitEndgame(); return; }   // defensive (the gateway only enables for SN)
  applySNModel(model);
}

// Refetch the light curve when the ⁵⁶Ni slider moves (mass/[Fe/H] fixed, so the progenitor
// can't change — always still an SN). Debounced + latest-wins, like the track fetch.
async function refetchSNMni() {
  if (mode !== "sn") return;
  const tok = ++snToken;
  let model;
  try { model = await fetchSNModel(mniValue); } catch { return; }
  if (tok !== snToken || mode !== "sn" || !model.is_supernova) return;
  applySNModel(model);
}

// Re-snap the SN progenitor after a mass/[Fe/H] change inside the endgame (mirrors
// tryWDResnap/tryWRResnap). If the new progenitor still core-collapses, swap in its computed
// model (keeping the ⁵⁶Ni + the scrub fraction). If it now ends as a white dwarf / strips to
// a Wolf–Rayet / has no endgame, there is no supernova — revert and say so.
async function trySNResnap() {
  if (mode !== "sn") return;
  const tok = ++snToken;
  const mass = massValue, feh = Number(els.feh.value);
  rotStatus = await fetchRotStatus(mass, feh);   // keep the rotation gate current as [Fe/H] drags
  if (tok !== snToken || mode !== "sn") return;
  let model;
  try { model = await fetchSNModel(mniValue); } catch { return; }
  if (tok !== snToken || mode !== "sn") return;
  if (model.is_supernova) {
    lastEgMass = mass; lastEgFeh = feh;
    setWDResnapNote("");
    applySNModel(model);
  } else {
    // Not a supernova progenitor — revert to the last SN star (snModel stays the old one).
    massValue = lastEgMass;
    els.feh.value = lastEgFeh;
    els.mass.value = clamp01(sliderFromMass(massValue));
    setNum(els.massNum, fmt(massValue));
    setNum(els.fehNum, lastEgFeh.toFixed(2));
    setWDResnapNote(model.type === "WD"
      ? `That star ends as a white dwarf, not a supernova — reverted to ${fmt(lastEgMass)} M☉.`
      : model.type === "WR"
        ? `That star strips to a Wolf–Rayet (its core-collapse is a stripped-envelope SN, a ` +
          `later feature) — reverted to ${fmt(lastEgMass)} M☉.`
        : `No core-collapse supernova for that star — reverted to ${fmt(lastEgMass)} M☉.`);
    refreshSN();
  }
}

// Dispatch a mass/[Fe/H] re-snap to the active endgame mode.
function tryResnap() {
  if (mode === "wd") return tryWDResnap();
  if (mode === "wr") return tryWRResnap();
  if (mode === "sn") return trySNResnap();
}

// Retire the first-load skeleton sheen (<body class="loading">, styles.css). Called on
// the first successful paint AND on the first-load error paths — an unreachable backend
// must show its error over quiet panels, not shimmer forever. Idempotent.
function endFirstLoad() {
  document.body.classList.remove("loading");
}

// Paint every living consumer (the 3D star, HR, composition, scale, spectrum, SED,
// classification + the readout/status) from one StellarState — the living marker.
// Shared by refresh() (the track-pick path) so the source of the state stays in one
// place. (The WD/WR endgame modes have their own render paths — refreshWD/refreshWR.)
function paintState(s) {
  endFirstLoad();   // first real paint — retire the first-load skeleton sheen
  star.update(s);
  classification.update(s);
  scale.update(s);
  hr.update(s);
  comp.update(s);
  spectrum.update(s);
  structure.update(s);
  sed.update(s);
  renderReadout(s);
  els.status.style.color = teffToCSS(s.Teff_K);
  // Tokenize so each part carries its own hover pedagogy (no "?" glyph — the
  // text itself is the hover target). innerHTML, not textContent, for the spans.
  els.status.innerHTML =
    tipSpan("OK", STATUS_OK_TIP) +
    " · " + tipSpan(s.phase, phaseTip(s.phase)) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");
}

function refresh() {
  // Clamp the source-of-truth mass to the span valid at this [Fe/H] (the dead
  // low-mass corner moves with metallicity) and PERSIST the clamp, then sync the
  // thumb so it can't visually sit in the disabled (dead-corner) region.
  massValue = Math.min(Math.max(massValue, validMassMin), validMassMax);
  const mass = massValue;
  els.mass.value = clamp01(sliderFromMass(mass));
  const feh = Number(els.feh.value);
  setNum(els.massNum, fmt(mass));
  setNum(els.fehNum, feh.toFixed(2));

  // The living marker is PICKED from the already-fetched track by EEP-row (Chunk E): the
  // slider is linear in EEP, so ageFraction → the nearest row, NO /state fetch. The track
  // holds every EEP state; age-based fetching is degenerate in flat-age bands (blue loops /
  // the He flash). If no track has landed yet (first call before /track), there's nothing
  // to paint — refreshTrack drives the first paint once currentTrack is set. Bail in an
  // endgame mode too (refreshWD/refreshWR own those).
  if (mode !== "live" || !currentTrack || !currentTrack.length) return;
  const i = trackRowFromPos(ageFraction);
  if (i < 0) return;
  const s = currentTrack[i];
  // The displayed age is the picked row's true age (honest by construction). Don't write
  // ageValue here: it's the preserved DESIRED age (source of truth for the spring-back
  // across a mass change); only an explicit age scrub / typed value commits it.
  setNum(els.ageNum, gyrNum(s.age_yr));
  paintState(s);
  // Re-evaluate the rotation control: the activity facet (cool-MS dynamo) appears/
  // disappears as age scrubs the star onto/off the main sequence — sed.update() (in
  // paintState) just refreshed sed.rotationAllowed(), so read it now.
  updateRotControl();
}

// The evolutionary track depends only on (mass, [Fe/H]), not age — so it's
// fetched on mass/feh change, never on an age scrub. It's also the DRIVER for
// those changes: when the new track lands it carries the age window (its first/
// last row), so this sets ageMin/ageMax, rebuilds the landmark ticks, then calls
// refresh() to settle the marker. One guarded fetch decides both the panels'
// track and the slider's domain — they can't disagree (the old /age_range race).
async function refreshTrack() {
  const token = ++trackToken;
  massValue = Math.min(Math.max(massValue, validMassMin), validMassMax);
  const mass = massValue;
  const feh = Number(els.feh.value);
  // Refresh the rotation gate FIRST (tiny, awaited) so the effective vvcrit is current for
  // this (mass, [Fe/H]) before the track/endgame fetches read it: has_grid depends on
  // [Fe/H], active on mass, and gating effVvcrit on has_grid keeps /track?vvcrit=0.4 from
  // ever hitting an [Fe/H] the rotating axis lacks (a 422). Token-guarded like the track.
  const rs = await fetchRotStatus(mass, feh);
  if (token !== trackToken || mode !== "live") return;
  rotStatus = rs;
  updateRotControl();
  try {
    const t = await fetchJSON(`/track?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`);
    // A newer track will drive its own refresh; and a track landing after we entered
    // the WD endgame must not overwrite the endgame view.
    if (token !== trackToken || mode !== "live") return;
    currentTrack = t;
    hr.setTrack(t);
    comp.setTrack(t);
    // The star changed, so any cached endgame is stale — drop BOTH caches (the full result
    // and the type-only fast-path one) + clear the gateway's CHILDREN (the buttons/note),
    // but leave the block itself in the layout so its reserved height holds while the new
    // fate loads (no reflow). On a track change two fetches fire: fetchEndgameMeta (~120 B,
    // lights the button almost immediately) and fetchEndgamePreview (the ~1 MB full result —
    // SOLE repopulator of `endgame`, backs the HR preview + the warm enter cache). The tail
    // calls updateGateway, NOT updateLiveGateway, so maybeFetchEndgame does NOT also fire
    // here (see the tail note). Clear the faint HR preview too, then refetch for the new star.
    endgame = null; endgameKey = null;
    endgameMeta = null; endgameMetaKey = null;
    els.gatewayWd.hidden = els.gatewayWr.hidden = els.gatewaySn.hidden = true;
    els.gatewaySnNote.hidden = true;     // the SN foreshadowing note rides the button's reset
    endgameLoading = true;               // a fetch is about to fire (meta + full)
    els.gatewayLoading.hidden = false;   // show "computing…" now (covers the await refresh()
                                         // window before updateGateway runs), so the slot
                                         // never flashes blank while the new fate loads
    hr.setEndgamePreview(null);
    fetchEndgameMeta();      // type-only → button lights up (greyed) almost immediately
    fetchEndgamePreview();   // full → HR preview + warm enter cache (slam-to-end stays instant)
    if (t.length) {
      ageMin = t[0].age_yr;
      ageMax = t[t.length - 1].age_yr;
      // Exiting the WD endgame pins the star to the very end of its (possibly
      // re-snapped) track — set the desired age to this window's end, once.
      if (pinAgeToEnd) { ageValue = ageMax; pinAgeToEnd = false; }
      // Re-grid the SPINNER to this window's span (step/min/max, so arrow clicks move
      // ~1% of the lifetime) BEFORE the refresh() below — its decimals become the
      // display-precision FLOOR. The displayed value itself is the true age, not
      // step-aligned (see gyrNum), so a hand-typed value is honored across the cycle.
      configureAgeNum(ageMin, ageMax);
      // The age WINDOW moved with the new track, but the desired absolute age
      // (ageValue) is preserved — recompute the slider position from it via posFromAge
      // (the nearest EEP row to that age, Chunk E), and sync the thumb. So changing
      // mass/[Fe/H] keeps the age fixed when it stays in range, and pins it to the nearest
      // end when it doesn't (ageValue itself stays unclamped, so dragging back springs it
      // out again). The thumb JUMPS when the absolute age survives but lands at a different
      // EEP fraction on the new track — that's correct (same age, different evolutionary
      // point per mass). On the very first track ageValue is still the Sun's DEFAULT_AGE_YR,
      // so this also places the default star at ~4.6 Gyr — no first-track special case.
      if (currentTrack && currentTrack.length > 1) {
        ageFraction = posFromAge(ageValue);
        els.age.value = ageFraction;
      }
      rebuildAgeTicks();
    }
  } catch (err) {
    if (token !== trackToken) return;
    // Non-fatal: keep the last good track + window if we have one (a transient failure
    // shouldn't wipe a working display). But with NO track yet (a first-load /track
    // failure while the backend is otherwise up — init() already covers backend-down)
    // there's nothing for refresh() to paint, so surface the error here (refresh() no
    // longer fetches /state, Chunk E, so it can't surface it as it used to).
    if (!currentTrack) {
      endFirstLoad();   // surface the error over quiet panels, not a skeleton shimmer
      els.status.style.color = "#ff6b6b";
      els.status.textContent = `Error: ${err.message}`;
      return;
    }
  }
  if (token !== trackToken) return;
  await refresh();
  // updateGateway (NOT updateLiveGateway): this path already fired fetchEndgamePreview
  // above, so the fate is on its way. Calling updateLiveGateway here would fire a SECOND
  // /endgame (maybeFetchEndgame) for the same star, which — sharing endgameToken — would
  // invalidate the preview fetch that was about to land, so the button would wait for the
  // later of two competing ~1 MB fetches instead of the one already in flight. Just paint
  // with what we have; fetchEndgamePreview's response repaints when it lands (faster).
  updateGateway();
}

// When [Fe/H] changes, the valid *mass* span can change (the dead corner), so
// refresh it before the track — refreshTrack() reads the clamped mass, so order
// matters. The track fetch then drives the marker + age window (see refreshTrack).
async function refreshMassRangeThenTrack() {
  const feh = Number(els.feh.value);
  try {
    const mr = await fetchJSON(`/mass_range?feh=${feh}`);
    validMassMin = mr.min;
    validMassMax = mr.max;
    rebuildMassTicks();   // the valid span moved, so the round-mass ticks do too
  } catch {
    /* keep previous span; refresh() will surface any real error */
  }
  await refreshTrack();
}

async function init() {
  try {
    const ranges = await fetchJSON("/ranges");
    logMassMin = Math.log10(ranges.mass_msun.min);
    logMassMax = Math.log10(ranges.mass_msun.max);
    validMassMin = ranges.mass_msun.min;
    validMassMax = ranges.mass_msun.max;
    try { providerName = (await fetchJSON("/health")).provider || ""; } catch { /* non-fatal */ }

    els.mass.min = 0; els.mass.max = 1; els.mass.step = 0.0005;
    els.mass.value = sliderFromMass(1.0); // default: the Sun
    massValue = 1.0;                       // source of truth (see massFromSliderPos)

    els.feh.min = ranges.feh.min; els.feh.max = ranges.feh.max;
    // 0.01 step (not 0.05): the provider interpolates [Fe/H] continuously, so a
    // fine grid lets hand-typed values land exactly while snapping still catches
    // the landmark metallicities (the range input would otherwise quantize them).
    els.feh.step = 0.01; els.feh.value = 0;
    fehMin = ranges.feh.min; fehMax = ranges.feh.max;

    els.age.min = 0; els.age.max = 1; els.age.step = 0.0005;
    els.age.value = ageFraction;

    // Editable number inputs (the hand-entry path) + their bounds.
    els.massNum.min = ranges.mass_msun.min; els.massNum.max = ranges.mass_msun.max;
    els.massNum.step = 0.01;
    els.fehNum.min = fehMin; els.fehNum.max = fehMax; els.fehNum.step = 0.01;
    els.ageNum.min = 0; els.ageNum.step = 0.01;

    rebuildMassTicks();
    rebuildFehTicks();   // age ticks wait for the first track + age window
  } catch (err) {
    endFirstLoad();   // surface the error over quiet panels, not a skeleton shimmer
    els.status.style.color = "#ff6b6b";
    els.status.textContent =
      `Cannot reach backend (${err.message}). Start it with: ` +
      `cd backend && uvicorn star_sim.api:app --reload`;
    return;
  }

  // Sliders snap to landmarks on drag. The editable number field is kept live
  // during the drag (cheap, no fetch) so it tracks the thumb instead of lagging a
  // fetch behind. The EXPENSIVE part — the /track (+/state) backend window build —
  // is debounced: mass/[Fe/H] intermediates during a fling are *waste* (the user
  // wants the endpoint, not every star in between), so we suppress them and fetch
  // once when the drag settles. `change` (fires on release, and on a single click)
  // flushes immediately, so clicking and letting go stay instant. (Age is the
  // deliberate exception — its scrub intermediates are *wanted*; see below.)
  const debouncedTrack = debounce(refreshTrack, SLIDER_FETCH_DELAY_MS);
  const debouncedMassRangeTrack = debounce(
    refreshMassRangeThenTrack, SLIDER_FETCH_DELAY_MS);
  // Inside an endgame (WD or WR), a mass/[Fe/H] drag re-snaps the progenitor (a different
  // remnant) instead of rebuilding the living track. The cheap thumb/number-box update
  // is shared; only the deferred fetch differs by mode (tryResnap dispatches by mode).
  const debouncedEgResnap = debounce(tryResnap, SLIDER_FETCH_DELAY_MS);
  els.mass.addEventListener("input", () => {
    const r = massFromSliderInput(Number(els.mass.value));
    els.mass.value = r.pos;
    massValue = r.mass;
    setNum(els.massNum, fmt(massValue));
    (mode !== "live" ? debouncedEgResnap : debouncedTrack)();
  });
  els.mass.addEventListener("change", () =>
    (mode !== "live" ? debouncedEgResnap : debouncedTrack).flush());
  els.feh.addEventListener("input", () => {
    els.feh.value = snap(Number(els.feh.value), fehTickPos, fehMin, fehMax);
    setNum(els.fehNum, Number(els.feh.value).toFixed(2));
    (mode !== "live" ? debouncedEgResnap : debouncedMassRangeTrack)();
  });
  els.feh.addEventListener("change", () =>
    (mode !== "live" ? debouncedEgResnap : debouncedMassRangeTrack).flush());
  els.age.addEventListener("input", () => {
    // In an endgame the age slider is the endgame scrubber (a pure pick from the
    // pre-fetched states — no fetch). Branch here, before the living-star age logic.
    if (mode === "wd") {
      wdFraction = snapWDFraction(Number(els.age.value));
      els.age.value = wdFraction;
      refreshWD();
      return;
    }
    if (mode === "wr") {
      wrFraction = snapWRFraction(Number(els.age.value));
      els.age.value = wrFraction;
      refreshWR();
      return;
    }
    if (mode === "sn") {
      // The SN time scrubber: a pure pick from the pre-computed photosphere states (no fetch),
      // linear in days so the marker tracks the slider on the linear-time light-curve panel.
      snFraction = snapSNFraction(Number(els.age.value));
      els.age.value = snFraction;
      refreshSN();
      return;
    }
    // NOT debounced, on purpose. The marker is now PICKED from the already-fetched
    // track (no fetch at all, Chunk E), so age-scrub frames are essentially free — and
    // age intermediates are *wanted*: scrubbing age is the "watch the star evolve"
    // experience, where every in-between frame is the point (mass/[Fe/H] intermediates
    // are waste, which is why those defer). ageFraction is the slider position in EEP
    // space; snapAge snaps it to the landmark ROW positions. Keep the EXACT snapped float
    // (the thumb is re-quantized to the 0.0005 step only for display) so the row index
    // round() lands exactly on the snapped landmark.
    ageFraction = snapAge(Number(els.age.value));
    els.age.value = ageFraction;
    // ageValue (the desired/displayed age, the source of truth for the spring-back across
    // a later mass/[Fe/H] change) is DERIVED from the picked EEP row — honest by
    // construction, and this is the ONLY place a scrub commits it. Picking the row directly
    // obsoletes the old "razor-sharp phase off-by-one": there's no age→EEP round-trip to
    // land on the wrong side of a boundary — the snapped position IS the row.
    const iScrub = trackRowFromPos(ageFraction);
    if (iScrub >= 0) ageValue = currentTrack[iScrub].age_yr;
    refresh();
    updateLiveGateway();   // offer the gateway once scrubbed to the end of the life
  });

  // Number inputs commit on change (Enter/blur) and BYPASS snapping — the exact
  // hand-typed value is honored, only clamped to the valid range.
  els.massNum.addEventListener("change", () => {
    if (els.massNum.value.trim() === "") return;
    const m = Number(els.massNum.value);
    if (!isFinite(m)) return;
    massValue = Math.min(Math.max(m, validMassMin), validMassMax);
    els.mass.value = clamp01(sliderFromMass(massValue));
    (mode !== "live" ? tryResnap : refreshTrack)();
  });
  els.fehNum.addEventListener("change", () => {
    if (els.fehNum.value.trim() === "") return;
    const f = Number(els.fehNum.value);
    if (!isFinite(f)) return;
    els.feh.value = Math.min(Math.max(f, fehMin), fehMax);
    (mode !== "live" ? tryResnap : refreshMassRangeThenTrack)();
  });
  els.ageNum.addEventListener("change", () => {
    if (mode !== "live") return;   // the age box is hidden in the endgame modes
    if (els.ageNum.value.trim() === "" || !(ageMax > ageMin)) return;
    const gy = Number(els.ageNum.value);
    if (!isFinite(gy)) return;
    ageValue = gy * 1e9;   // the typed absolute age is the new desired value
    ageFraction = posFromAge(ageValue);   // -> the nearest EEP row position (Chunk E)
    els.age.value = ageFraction;
    refresh();
    updateLiveGateway();
  });

  // Rotation toggle (rotation Chunk 3): flip the selected rotation and refetch the
  // (rotating / non-rotating) track + endgame for the current star. Only meaningful in
  // live mode and only enabled where rotation_status.active is true (updateRotControl
  // greys it otherwise), so a `change` here always refers to a real track swap.
  if (els.rotToggle) els.rotToggle.addEventListener("change", () => {
    if (mode !== "live") return;
    rotationOn = els.rotToggle.checked;
    refreshTrack();
  });

  // The stellar-endgame gateway: enter the WD / WR / SN endgame from the button at the slider
  // limit; the bar's "Back" button leaves it (reversible — Locked decision #1).
  if (els.gatewayWd) els.gatewayWd.addEventListener("click", enterWD);
  if (els.gatewayWr) els.gatewayWr.addEventListener("click", enterWR);
  if (els.gatewaySn) els.gatewaySn.addEventListener("click", enterSN);
  if (els.endgameBack) els.endgameBack.addEventListener("click", exitEndgame);

  // The ⁵⁶Ni-mass slider (SN endgame, Tier-3): moving it REFETCHES the light curve (the
  // tail/peak rescale; mass/[Fe/H] fixed, so the progenitor can't change). Debounced +
  // latest-wins, like the track fetch. The number box is the exact-entry escape hatch.
  const debouncedSNMni = debounce(refetchSNMni, SLIDER_FETCH_DELAY_MS);
  if (els.snMni) {
    els.snMni.addEventListener("input", () => {
      // snap to a round ⁵⁶Ni yield if close, else read the log position
      const raw = Number(els.snMni.value);
      let pos = raw, bestD = 0.02;
      for (const m of MNI_TICKS) {
        const p = posFromMni(m); const d = Math.abs(raw - p);
        if (d < bestD) { bestD = d; pos = p; }
      }
      els.snMni.value = pos;
      mniValue = mniFromPos(pos);
      setNum(els.snMniNum, fmt(mniValue));
      els.snMniNote.textContent = mniNote();
      debouncedSNMni();
    });
    els.snMni.addEventListener("change", () => debouncedSNMni.flush());
  }
  if (els.snMniNum) els.snMniNum.addEventListener("change", () => {
    if (mode !== "sn" || els.snMniNum.value.trim() === "") return;
    const m = Number(els.snMniNum.value);
    if (!isFinite(m)) return;
    mniValue = Math.min(Math.max(m, M_NI_MIN), M_NI_MAX);
    els.snMni.value = posFromMni(mniValue);
    els.snMniNote.textContent = mniNote();
    refetchSNMni();
  });

  await refreshMassRangeThenTrack();
}

init();
