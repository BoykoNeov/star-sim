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
import { createRoche } from "./roche.js";
import { createSpectrum } from "./spectrum.js";
import { createSED } from "./sed.js";
import { createCMD } from "./cmd.js";
import { createHZHist } from "./hzhist.js";
import { habitableZone } from "./hz.js";
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
  // Inclination facet (gravity darkening Chunk 2): the viewing-angle slider, main.js-owned.
  inclControl: document.getElementById("incl-control"),
  incl: document.getElementById("incl"),
  inclNum: document.getElementById("incl-num"),
  inclNote: document.getElementById("incl-note"),
  axisGridToggle: document.getElementById("axis-grid-toggle"),
  // Ap/Bp chemically-peculiar toggle (atlas Tier C): an evocative surface what-if, gated to
  // the A/B main-sequence mass regime. Independent of the Rotation control.
  peculiarControl: document.getElementById("peculiar-control"),
  peculiarToggle: document.getElementById("peculiar-toggle"),
  peculiarNote: document.getElementById("peculiar-note"),
  // Binary-stripped-star what-if toggle (Götberg 2018 — the ~70% WR channel). A mass-gated
  // entry into the reversible `stripped-mode` (a mid-life fork, not an end-of-life endgame).
  strippedControl: document.getElementById("stripped-control"),
  strippedBtn: document.getElementById("stripped-btn"),
  strippedNote: document.getElementById("stripped-note"),
  // Initial-helium (Y) what-if overlay (Phase 2 — the globular-cluster 2nd-generation effect).
  // A LIGHT HR overlay (not a mode-swap): two self-run MESA tracks, MIST spine hidden while on.
  heliumControl: document.getElementById("helium-control"),
  heliumToggle: document.getElementById("helium-toggle"),
  heliumNote: document.getElementById("helium-note"),
  // α-enhanced (equivalent-Z) what-if overlay (Phase 3 — the old-population [α/Fe] effect).
  // Same LIGHT HR-overlay machinery as the He one, and mutually exclusive with it.
  alphaControl: document.getElementById("alpha-track-control"),
  alphaToggle: document.getElementById("alpha-track-toggle"),
  alphaNote: document.getElementById("alpha-track-note"),
  // Coeval-population overlay (BPASS — the first ENSEMBLE feature). Unlike He/α (HR
  // overlays), this draws on the SED panel: single-star vs. +binaries integrated spectra.
  populationControl: document.getElementById("population-control"),
  populationToggle: document.getElementById("population-toggle"),
  populationNote: document.getElementById("population-note"),
  // Habitable-zone overlay (Axis D). A pure VIEW on the true-size scale bar — the circumstellar
  // liquid-water zone from L + Teff (Kopparapu 2014), marching outward as the star brightens.
  // Living-only (scale.js draws it only when setHZ(true) and not SN; dropped on any mode switch).
  hzToggle: document.getElementById("hz-toggle"),
  // Axis D2a — the HZ-history panel (temporal twin of the scale-bar band, governed by the same
  // #hz-toggle). Hidden unless the toggle is on in live mode; dropped on any mode switch.
  hzHistoryPanel: document.getElementById("hz-history-panel"),
  // Isochrone / cluster overlay (MIST .iso — Axis B). A LIGHT HR overlay like He/α (it owns the
  // HR panel while on, MIST track hidden) but a POPULATION view: the coeval-cluster locus at the
  // marker's age, turnoff ringed, the star sitting on it. Gated only on the fetched .iso grid.
  isochroneControl: document.getElementById("isochrone-control"),
  isochroneToggle: document.getElementById("isochrone-toggle"),
  isochroneNote: document.getElementById("isochrone-note"),
  // B3: an independent cluster-age slider — decouple the cluster's age from the star's age
  // slider so the turnoff can be swept down the MS on its own ("cluster aging" movie).
  isoDecoupleWrap: document.getElementById("iso-decouple-wrap"),
  isoDecoupleToggle: document.getElementById("iso-decouple-toggle"),
  isoClusterAgeRow: document.getElementById("iso-cluster-age-row"),
  isoClusterAge: document.getElementById("iso-cluster-age"),
  isoClusterAgeVal: document.getElementById("iso-cluster-age-val"),
  // Observer's view (Axis A) — distance + interstellar-dust knobs turning the intrinsic star
  // into what a telescope records. A pure VIEW: reddening.js reddens the Spectrum + SED curves
  // client-side, /photometry supplies the magnitude/colour readout. Living-only, gated on the
  // absolute-flux spectrum cube being present (probed once at init).
  observerPanel: document.getElementById("observer-panel"),
  obsDistance: document.getElementById("obs-distance"),
  obsDistanceVal: document.getElementById("obs-distance-val"),
  obsAv: document.getElementById("obs-av"),
  obsAvVal: document.getElementById("obs-av-val"),
  obsRv: document.getElementById("obs-rv"),
  obsRvVal: document.getElementById("obs-rv-val"),
  observerReadout: document.getElementById("observer-readout"),
  observerNote: document.getElementById("observer-note"),
  // path (b): "Show companion" — draw the un-stripped accretor as a 2nd HR marker (the Algol
  // reversal). Lives in the endgame bar, shown only in stripped-mode (CSS-gated).
  companionToggle: document.getElementById("companion-toggle"),
  // path (b) Chunk 4b: the co-evolving POSYDON binary demo picker — a deeper reveal inside
  // stripped-mode (binary-view). Curated demo systems, PLUS (Chunk 4c) free M1/q/P sliders
  // behind a fourth "Custom orbit" picker.
  binaryDemoRow: document.getElementById("binary-demo-row"),
  binaryDemoBack: document.getElementById("binary-demo-back"),
  // CE/compact-object tail Chunk 1b: the standalone CO-HMS_RLO demo (one curated system).
  // Chunk 1c: + a [Fe/H] picker and free M_star/M_co/P sliders behind "Custom system".
  coBinaryDemoXrb: document.getElementById("co-binary-demo-xrb"),
  coBinaryDemoCustom: document.getElementById("co-binary-demo-custom"),
  coBinaryDemoBack: document.getElementById("co-binary-demo-back"),
  coBinaryKind: document.getElementById("co-binary-kind"),
  coBinaryHelp: document.getElementById("co-binary-help"),
  coBinaryFeh: document.getElementById("co-binary-feh"),
  coBinaryFehNote: document.getElementById("co-binary-feh-note"),
  coBinaryDcoNote: document.getElementById("co-binary-dco-note"),
  coBinaryCustomControls: document.getElementById("co-binary-custom-controls"),
  coBinaryCustomMstar: document.getElementById("co-binary-custom-mstar"),
  coBinaryCustomMstarNum: document.getElementById("co-binary-custom-mstar-num"),
  coBinaryCustomMco: document.getElementById("co-binary-custom-mco"),
  coBinaryCustomMcoNum: document.getElementById("co-binary-custom-mco-num"),
  coBinaryCustomP: document.getElementById("co-binary-custom-p"),
  coBinaryCustomPNum: document.getElementById("co-binary-custom-p-num"),
  coBinaryCustomNote: document.getElementById("co-binary-custom-note"),
  binaryCustomControls: document.getElementById("binary-custom-controls"),
  binaryCustomM1: document.getElementById("binary-custom-m1"),
  binaryCustomM1Num: document.getElementById("binary-custom-m1-num"),
  binaryCustomQ: document.getElementById("binary-custom-q"),
  binaryCustomQNum: document.getElementById("binary-custom-q-num"),
  binaryCustomP: document.getElementById("binary-custom-p"),
  binaryCustomPNum: document.getElementById("binary-custom-p-num"),
  binaryCustomNote: document.getElementById("binary-custom-note"),
  binaryFeh: document.getElementById("binary-feh"),
  binaryFehNote: document.getElementById("binary-feh-note"),
  // Stellar-endgame gateway + white-dwarf mode (smoldering-cinder-gateway.md).
  gateway: document.getElementById("gateway"),
  gatewayWd: document.getElementById("gateway-wd"),
  gatewayWr: document.getElementById("gateway-wr"),
  gatewaySn: document.getElementById("gateway-sn"),          // now a BUTTON (was the note)
  gatewaySnNote: document.getElementById("gateway-sn-note"), // the foreshadowing note
  gatewayLoading: document.getElementById("gateway-loading"),
  endgameBar: document.getElementById("endgame-bar"),
  endgameBack: document.getElementById("endgame-back"),
  pulseToggle: document.getElementById("pulse-toggle"),   // WD-mode: open/close the thermal-pulse showcase
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

// The Roche-lobe / mass-transfer geometry panel (binary path (b) Chunk 3) — a pushed-data
// consumer (main.js hands it the /binary_pair `roche` block + companion state; it never
// fetches). Shown only in stripped-mode with "Show companion" on (CSS-gated on body
// .stripped-mode.companion-on); its panel is display:none otherwise, so its canvas is fit
// on first draw. It is the CAUSAL two-star render behind the stripped star.
const roche = createRoche();

// The broadband SED panel (spec §5) is a SIBLING like lane.js — but, unlike lane,
// it DOES move with the star: it's the Planck blackbody across the whole EM
// spectrum, driven by Teff alone (a blackbody ignores log g and [Fe/H]), so it
// owns no fetch and just redraws from the live state inside refresh(). It is the
// zoomed-all-the-way-out companion to the synthetic-spectrum panel.
const sed = createSED(document.getElementById("sed-canvas"));
// SED legend on/off: click a legend entry (swatch or label) to hide/show that series on the
// plot — the same idiom as the composition panel's per-element legend. Delegated so it also
// fires on the inner ".tip" pedagogy label (closest finds data-series). The "non-thermal edges"
// entry has no data-series (it names the floors, not a drawn curve), so it stays inert.
{
  const sedLegend = document.querySelector(".sed-panel .sed-legend");
  if (sedLegend) sedLegend.addEventListener("click", (e) => {
    const entry = e.target.closest("span[data-series]");
    if (!entry) return;
    const visible = sed.toggleSeries(entry.dataset.series);
    entry.classList.toggle("off", !visible);
  });
}

// The observational colour–magnitude diagram (Axis A3) — the observer's HR diagram in its
// own panel. A pushed-data consumer (like sed's population overlay): main.js fetches the
// intrinsic locus + the marker's exact magnitudes and pushes them in.
const cmd = createCMD(document.getElementById("cmd-canvas"));

// Habitable-zone history (Axis D2a) — the temporal twin of the scale-bar HZ band. A pure
// pushed-data consumer: main.js maps currentTrack through hz.js and pushes the per-row edges
// via setTrack(); the age slider pushes the current age via setNow(). Governed by #hz-toggle.
const hzhist = createHZHist(document.getElementById("hz-history-canvas"));

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
  { id: "cmd-canvas", mod: cmd, maxW: 560, h: 300 },
  { id: "hz-history-canvas", mod: hzhist, maxW: 560, h: 300 },
  { id: "lane-canvas", mod: lane, maxW: 720, h: 340 },
  { id: "structure-canvas", mod: structure, maxW: 720, h: 340 },
  { id: "roche-canvas", mod: roche, maxW: 720, h: 320 },
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
let mode = "live";              // "live" | "wd" | "wr" | "sn" | "stripped"
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

// Viewing inclination (gravity darkening Chunk 2), a persisted VIEWING choice shared by the
// 3D star (tilt) and the spectrum (v sin i). 0° = pole-on, 90° = edge-on; 60° is the
// isotropic-median inclination for a randomly-oriented star (the honest default). It is
// deliberately OFF the spine — intrinsic Teff/L is inclination-independent, so this never
// touches the HR marker; it only changes what is SEEN (3D) and OBSERVED (line broadening).
// The facet is gated on the rotating-track regime (updateRotControl); a round star ignores
// it. Pushing it to both consumers keeps them in lockstep with no dual-default drift.
let inclinationDeg = 60;
// Orientation-grid intent (the inclination cue on the 3D star). Default OFF; a ONE-SHOT
// auto-enable turns it on the first time a rotating star appears (gridAutoShown latches so it
// never re-fires), after which it follows the user's checkbox — turning it off is sticky, and
// cycling the star rotating↔non-rotating won't re-show it. Owned here, pushed to star.setAxisGrid.
let axisGridOn = false;
let gridAutoShown = false;
function applyInclination(deg) {
  inclinationDeg = Math.min(90, Math.max(0, Math.round(deg)));
  star.setInclination(inclinationDeg);
  spectrum.setInclination(inclinationDeg);
  if (els.inclNote) {
    els.inclNote.textContent =
      inclinationDeg <= 12 ? "Pole-on: looking down the hot pole — round disk, sharp lines."
      : inclinationDeg >= 78 ? "Edge-on: the oblate equator faces you — cool limb, broadest lines."
      : `i = ${inclinationDeg}° — the hot pole and cool equatorial band both in view.`;
  }
}

// Ap/Bp chemically-peculiar toggle intent (atlas Tier C — evocative surface what-if).
// Persisted across mass/[Fe/H]/age changes like rotationOn, and OFF the spine: it only
// changes the 3D star's look (co-rotating magnetic abundance spots), never the HR marker,
// spectrum or composition. Gated to the A/B main-sequence regime (updatePeculiarControl);
// star.js additionally fades the effect per-state outside the A/B-MS Teff window.
let peculiarOn = false;

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
// --- thermal-pulse showcase (a WD-mode sub-view) -----------------------------
// An opt-in zoom that lives INSIDE wd-mode: the WD scrub crushes the ~600 chaotic TPAGB
// rows into 12% of the slider (WD_FP) to protect the central-star spike; this sub-view
// gives that TPAGB slice the whole panel + slider so the He-shell-flash loops are legible.
// It's a boolean sub-state of wd-mode (NOT a top-level mode) — the endgame progenitor,
// re-snap, and Back button are all shared. `pulseGateOK` is the data-derived visibility
// gate (median per-pulse ΔlogL ≥ threshold); the toggle only appears when it passes.
let pulseView = false;          // true = the decompressed TPAGB view is active (still mode==="wd")
let pulseFraction = 0;          // slider position 0..1 across the TPAGB rows only
let pulseStates = null;         // the TPAGB-only slice of endgame.states (cached on enterWD)
let pulseGateOK = false;        // does the pulse amplitude clear the visibility gate?
const PULSE_GATE_DEX = 0.15;    // median per-pulse ΔlogL floor (measured: 1–3 M☉ ~0.3, 5 M☉ ~0.02)
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

// --- binary-stripped-star what-if (stripped-mode) ----------------------------
// UNLIKE wd/wr/sn (end-of-life endgames reached at the slider's end), the stripped star is a
// MID-LIFE FORK: "instead of expanding to a red giant, a close companion strips the envelope
// NOW → this hot He-star." So it's entered by a mass-gated TOGGLE (like Ap/Bp), not a
// gateway button — but it's still a reversible MODE that snaps the whole display (like
// wd/wr/sn), fetched from /binary (a sibling route, snap-always, no vvcrit). The exit is the
// SHARED endgame-bar "Back" (= exitEndgame), and unchecking the toggle calls the same path.
let strippedData = null;        // the latest /binary (or /binary_pair) payload (state + scalars)
let strippedToken = 0;          // latest-wins guard for /binary fetches (enter + re-snap)
// path (b): when true the stripped fetch hits /binary_pair (donor + companion) and the HR
// draws the companion as a second marker. Reset on every mode enter/exit — path (a) (the
// stripped star alone, "companion named not drawn") is the default; ticking "Show companion"
// reveals the accretor and the Algol mass-ratio reversal.
let companionOn = false;
let heliumOn = false;           // the initial-helium overlay is active (MIST HR track hidden)
let heliumToken = 0;            // latest-wins guard for the /helium fetch (mass/feh can change fast)
let heliumHasGrid = false;      // /helium_status: are the MESA runs present? (else never show the toggle)
// The eligible progenitor-mass range for the toggle's gate (the Götberg Z=0.014 grid spans
// ~2–18.2 M☉). Snap-always on the backend, so a drag past these inside the mode shows a
// snapped-far note rather than reverting; the toggle just doesn't OFFER entry outside them.
const STRIP_MASS_MIN = 2.0, STRIP_MASS_MAX = 18.2;
// Initial-helium overlay eligibility: the self-run MESA grid is 1/2/6 M☉ at solar Z, so the
// toggle is offered across a mass band that snaps sensibly (edges flagged "snapped-far" in-band)
// and only near solar [Fe/H] — the grid carries no other metallicity, so showing it elsewhere
// would mislabel a solar-Z pair as "at your [Fe/H]".
const HE_MASS_MIN = 0.7, HE_MASS_MAX = 7.0, HE_FEH_TOL = 0.25;
// α-enhanced overlay (Phase 3): the same self-run MESA grid shape as the He one (1/2/6 M☉ at
// solar [Fe/H]), so the same eligibility band — offered near solar Z where the equivalent-Z
// pair snaps sensibly, hidden elsewhere (the grid carries no other [Fe/H]).
let alphaOn = false;            // the α-enhanced overlay is active (MIST HR track hidden; shares the He slot)
let alphaToken = 0;            // latest-wins guard for the /alpha fetch
let alphaHasGrid = false;      // /alpha_status: are the MESA runs present? (else never show the toggle)
const ALPHA_MASS_MIN = 0.7, ALPHA_MASS_MAX = 7.0, ALPHA_FEH_TOL = 0.25;
// Coeval-population (BPASS) overlay on the SED panel. Unlike He/α it's NOT gated to a
// mass/[Fe/H] band — it applies at any marker (it reads only [Fe/H] + age), so the only
// gate is the host-baked cube being present (/population_status). It re-fetches when the
// snapped ([Fe/H], age) node could change; popNodeKey buckets requests so a same-node
// age-scrub doesn't refetch (the payload would be identical).
let populationOn = false;
let populationToken = 0;        // latest-wins guard for the /population fetch (feh/age move fast)
let populationHasGrid = false;  // /population_status: is the BPASS SED cube baked? (else hide the toggle)
let populationHasHRD = false;   // /population_status has_hrd: is the HR-diagram number cube baked?
let popNodeKey = "";            // last-fetched ([Fe/H], age-node) bucket — skip refetch if unchanged

// --- habitable-zone overlay (Axis D) -------------------------------------------
// A pure VIEW on the scale bar (scale.js), not on the HR panel: the circumstellar liquid-water
// zone from L + Teff. No fetch, no backend, no gate beyond "living mode" — scale.js self-gates by
// Kopparapu's Teff range (band absent for hot stars). Dropped on every endgame/stripped/binary
// switch (dropHZForModeSwitch) so it can't paint on a WD/WR/SN/stripped scale bar.
let hzOn = false;

// --- isochrone / cluster overlay (MIST .iso — Axis B) --------------------------
// Like the He/α overlays it OWNS the HR panel while on (MIST track/marker hidden, the locus
// drawn instead). Not mass-gated (reads only the marker's age + [Fe/H]); the only gate is the
// fetched .iso grid (/isochrone_status). The cluster ages with the age slider; isoNodeKey
// buckets so a same-node age-scrub skips the refetch but still repaints the moving marker.
let isoOn = false;
let isoToken = 0;               // latest-wins guard for the /isochrone fetch
let isoHasGrid = false;        // /isochrone_status: is the .iso grid fetched? (else hide the toggle)
let isoNodeKey = "";           // last-fetched (feh, age-node, vvcrit) bucket
let isoLastStates = null;      // cached locus states (redraw the marker within a node w/o refetch)
let isoLastTurnoff = null;     // cached MSTO for the same-node repaint
// B3: decoupled cluster-age slider. When isoDecoupled, the cluster's age comes from
// isoClusterLogAge (log10 yr) instead of the star's age — the star marker still moves with the
// star's own age, so it slides OFF the locus (that gap IS the age comparison). isoLogAges are the
// grid's tabulated log10 ages (served as available_log_ages) — the honest, grid-exact slider bounds.
let isoDecoupled = false;
let isoClusterLogAge = null;   // log10(age_yr) of the decoupled cluster; null until decoupled
let isoLogAges = null;         // available_log_ages from the last fetch (slider min/max)

// --- observer's view (Axis A) — its own panel: the observational CMD -----------
// The theory→telescope bridge, now a first-class panel (Axis A3). Whenever the panel is
// eligible (live star + the absolute-flux spectrum cube present) it is shown with the
// intrinsic CMD locus always drawn. The three knobs then apply DISTANCE (μ) + interstellar
// DUST (av, rv): the CMD marker/arrow move (client-side, instant, from the exact /photometry
// readout), and the reddening also reddens the Spectrum + SED curves CLIENT-SIDE (reddening.js
// CCM89, a verbatim port of photometry.py). The Spectrum/SED reddening is a no-op when av=0
// (setReddening guards on redAv>0), so the intrinsic view is byte-unchanged until dust is added.
// The magnitude/colour READOUT is fetched from /photometry (the tested absolute-flux path —
// filters/ZeroPoints/band integration stay server-side, never reimplemented). Living-only
// (magnitudes need the absolute-flux main cube; WD/WR/stripped cubes are continuum-normalized).
let observerOn = false;         // panel eligible & shown (live + cube present)
let observerToken = 0;          // latest-wins guard for the /photometry readout fetch
let observerHasData = false;    // /photometry reachable (spectrum cube present)? else hide the panel
let observerMarker = null;      // the last painted marker state (for a knob-drag readout refetch)
let obsDebounce = null;         // debounce for the readout fetch (the overlay itself is instant)
let obsTrackKey = null;         // "(mass,feh,vvcrit)" the CMD locus was last fetched for (dedupe)
let obsTrackToken = 0;          // latest-wins guard for the /photometry_track locus fetch
let obsDistancePc = 100;        // seeded distance (μ = 5) — a visible vertical arrow on first view
let obsAv = 0;                  // seeded dust-free (Spectrum/SED byte-unchanged until dust is added)
let obsRv = 3.1;                // diffuse-ISM reddening law (the near-universal default)
// The distance slider is log-spaced over 10 pc (absolute-mag reference) → 100 kpc (past the LMC).
const OBS_D_MIN = 10, OBS_D_MAX = 1e5;
const OBS_D_LO = Math.log10(OBS_D_MIN), OBS_D_HI = Math.log10(OBS_D_MAX);
const obsDistFromFrac = (v) => 10 ** (OBS_D_LO + v * (OBS_D_HI - OBS_D_LO));
const obsFracFromDist = (d) => (Math.log10(d) - OBS_D_LO) / (OBS_D_HI - OBS_D_LO);

// --- path (b) Chunk 4b: the co-evolving POSYDON binary (a deeper reveal INSIDE ------
// stripped-mode — mode stays "stripped" throughout, mirroring how the thermal-pulse
// showcase is a sub-view of "wd", not its own top-level mode).
//
// Three curated demo systems (docs/plans/entwined-consort-inspiral.md's de-risking choice):
// the SAME donor (M1=8.83 M☉, q=0.6) at three real POSYDON grid periods, so the outcome
// contrast is purely "how close did they start" — merger (too close), stripped + companion
// (the Gate-0 system — a real Algol reversal), or detached (too wide to ever interact).
// Chunk 4c adds a fourth entry, "custom" — NOT in this array (its (m1,q,p) come from the
// customM1/customQ/customP sliders below, not a fixed triple) but handled by the same
// enterBinaryView/refreshBinary machinery throughout.
const BINARY_DEMOS = [
  { key: "merger", m1: 8.83, q: 0.6, p: 0.1 },
  { key: "stripped", m1: 8.83, q: 0.6, p: 3.73 },
  { key: "wide", m1: 8.83, q: 0.6, p: 5179 },
];
let binaryView = false;         // true = a demo is co-evolving (still mode === "stripped")
let binaryTrackData = null;     // the full /binary_track payload (steps[] + snap/outcome meta)
let binaryStar1 = null;         // data.steps[].star_1, pulled out once for hr.setBinaryTrack
let binaryStar2 = null;         // data.steps[].star_2 (may contain a trailing null — a merger)
let binaryFraction = 0;         // 0..1 slider position, index-linear over steps (the WR idiom)
let binaryDemoKey = null;       // which BINARY_DEMOS entry (or "custom") is live
let binaryToken = 0;            // latest-wins guard for /binary_track fetches

// CE/compact-object tail Chunk 1b: the CO-HMS_RLO demo — a compact object (NS/BH) orbiting a
// still hydrogen-rich star, the stage AFTER the HMS-HMS episode. A STANDALONE curated demo
// (the settled Chunk-1a navigation decision), solar-only, a sibling to the HMS-HMS movie but
// its OWN state + body class (.co-binary-view) so the two are mutually exclusive. The demo is
// the measured Gate-1 system (a 27.6 M☉ star + 14.7 M☉ BH → X-ray binary → stripped + BH).
// Chunk 2b: the CO grid KIND — the axis orthogonal to [Fe/H], mirroring the backend's three
// `kind` grids behind one route (default "co-hms-rlo", byte-compatible). Each kind is its OWN
// baked grid (different M_star/M_co/P spans + a different payoff), so a kind change is a fresh
// grid: it resets the custom triple to that kind's curated demo, invalidates the meta cache,
// and re-fetches — exactly like a [Fe/H] bucket change, just also swapping the demo node/labels.
//   * co-hms-rlo — compact object + still-H-rich star: the X-ray-binary accretion payoff.
//   * co-hems     — compact object + bare He star, detached inspiral: the double-compact-object
//                   (gravitational-wave-merger) CLASSIFICATION payoff (data.dco).
//   * co-hems-rlo — the same He star in Roche-lobe overflow: a He-donor X-ray binary (accretion
//                   cue fires) + a DCO endpoint (usually "no merger" — the He star ends a WD).
// The curated demo triples are the exact Chunk-2a-verified nodes (test_posydon_co_he.py) that
// are GUARANTEED to hit each kind's payoff node — never guessed (a guess can snap to a WD /
// unstable_MT node where the feature is gated off, showing a dead demo).
const CO_BINARY_DEMOS = {
  "co-hms-rlo":  { m_star: 27.61912143189711, m_co: 14.66048571159418, p: 203.9763401890043 },
  "co-hems":     { m_star: 16.559711, m_co: 5.990075, p: 0.561443 },   // BH+BH DCO progenitor
  "co-hems-rlo": { m_star: 1.422924, m_co: 10.248538, p: 0.045189 },   // He-donor X-ray binary
};
// Per-kind demo-button label + demo-row `?` tooltip (the H-rich default HTML tooltip would
// MISDESCRIBE a He kind — a false-data-in-caption leak, the class this project keeps catching).
const CO_KIND_UI = {
  "co-hms-rlo": {
    demoLabel: "Star + black hole → X-ray binary",
    tip: "A real POSYDON CO-HMS_RLO track (Fragos+2023): a black hole left behind by an already-dead star, still orbiting its living, hydrogen-rich companion. Scrub system time — the living star swells, fills its Roche lobe and pours gas onto the black hole (an X-ray binary), the black hole's mass grows by real accretion, the orbit widens. Only the living star is on the HR diagram (a black hole has no photosphere); the accretion power is a schematic L = η·Ṁ·c² estimate on the model's real transfer rate, not a measured X-ray spectrum.",
  },
  "co-hems": {
    demoLabel: "He star + black hole → BH+BH merger",
    tip: "A real POSYDON CO-HeMS track (Fragos+2023): the surviving companion has ALSO been stripped to a bare helium star, now orbiting the compact object — the direct progenitor of a double compact object (a gravitational-wave-merger source). Scrub system time: only the He star is on the HR diagram; the composition panel shows its measured helium-rich surface. The payoff is the endpoint (shown above the slider) — POSYDON's own predicted remnant of the He star, combined with the existing compact object: a BH+BH / NS+BH / NS+NS merger progenitor, or honestly no merger if either ends a white dwarf. This orbit is detached (no accretion cue) — the merger itself is not modeled (no natal kick, no merger time).",
  },
  "co-hems-rlo": {
    demoLabel: "He star + black hole → X-ray binary",
    tip: "A real POSYDON CO-HeMS_RLO track (Fragos+2023): a bare helium star overflowing its Roche lobe onto the compact object — a He-donor X-ray binary (Case BB/BC mass transfer). Scrub system time: only the He star is on the HR diagram (helium-rich surface in the composition panel); the accretion power onto the compact object is surfaced in the caption (schematic L = η·Ṁ·c²). The double-compact-object endpoint is shown above the slider — often 'no merger' here, since the He star frequently ends as a white dwarf.",
  },
};
function isHeKind(kind) { return kind === "co-hems" || kind === "co-hems-rlo"; }
let coKind = "co-hms-rlo";      // the selected CO grid (VALID_KINDS), orthogonal to coCustomFeh
let coBinaryView = false;
let coBinaryTrackData = null;   // the full /co_binary_track payload
let coBinaryStar = null;        // data.steps[].star, pulled out for hr.setBinaryTrack (star only)
let coBinaryFraction = 0;       // 0..1 slider position, index-linear over steps
let coBinaryToken = 0;          // latest-wins guard for /co_binary_track fetches
let coBinaryDemoKey = null;     // "xrb" (curated demo system) | "custom" — which is live

// Chunk 1c: the [Fe/H] picker + free M_star/M_co/P sliders. /co_binary_track was always
// general (snap-always over the WHOLE baked CO grid, §6) — the single curated demo was a
// de-risking UI choice, not a backend limit, so this needs no backend change (it mirrors
// how HMS-HMS Chunk 4c/4d added its own custom sliders + [Fe/H] picker). The CO axis is
// (M_star, M_co, P), NOT (M1, q, P): a compact object's mass is a real physical value, not
// a mass ratio, so all THREE are log-scale (each spans a wide dynamic range; M_co runs
// ~1.2–307 M☉). `coBinaryMeta` (the grid bounds — /co_binary_track_meta) is fetched lazily
// per [Fe/H] bucket and cached; the 8 POSYDON metallicities are separate grids with
// different spans, so a bucket change invalidates it (the exact stale-slider bug 4d fixed).
let coBinaryMeta = null;
let coBinaryMetaPromise = null;
let coBinaryMetaPromiseFeh = null;
let coBinaryMetaFeh = null;
// The meta cache also keys on KIND (Chunk 2b): each `kind` is its own grid with its own
// M_star/M_co/P spans, so switching kind at unchanged [Fe/H] must NOT reuse the old bounds
// (that would mis-position the custom sliders — the same class as the 4d stale-slider bug).
let coBinaryMetaKind = null;
let coBinaryMetaPromiseKind = null;
let coCustomMstar = CO_BINARY_DEMOS[coKind].m_star;
let coCustomMco = CO_BINARY_DEMOS[coKind].m_co;
let coCustomP = CO_BINARY_DEMOS[coKind].p;
let coCustomFeh = 0.0;          // the selected POSYDON metallicity bucket (solar by default),
                                // applies to EITHER CO demo (curated or custom) — orthogonal
                                // to which (M_star, M_co, P) is picked.

// The CO counterpart of ensureBinaryMeta — fetches /co_binary_track_meta for the current
// bucket, clamps the custom values into the new bucket's grid span, (re)builds the [Fe/H]
// options + slider bounds. Cached per-feh; a bucket change clears the cache (each POSYDON
// metallicity is a separate baked grid with its own M_star/M_co/P spans).
function ensureCoBinaryMeta() {
  if (coBinaryMeta && coBinaryMetaFeh === coCustomFeh && coBinaryMetaKind === coKind)
    return Promise.resolve(coBinaryMeta);
  if (coBinaryMetaPromise && coBinaryMetaPromiseFeh === coCustomFeh && coBinaryMetaPromiseKind === coKind)
    return coBinaryMetaPromise;
  const fehAtCall = coCustomFeh;   // snapshot — coCustomFeh/coKind may change again before this resolves
  const kindAtCall = coKind;
  coBinaryMetaPromiseFeh = fehAtCall;
  coBinaryMetaPromiseKind = kindAtCall;
  coBinaryMetaPromise = fetchJSON(`/co_binary_track_meta?feh=${fehAtCall}&kind=${kindAtCall}`)
    .then((meta) => {
      coBinaryMeta = meta;
      coBinaryMetaFeh = fehAtCall;
      coBinaryMetaKind = kindAtCall;
      coCustomMstar = Math.min(Math.max(coCustomMstar, meta.m_star_min), meta.m_star_max);
      coCustomMco = Math.min(Math.max(coCustomMco, meta.m_co_min), meta.m_co_max);
      coCustomP = Math.min(Math.max(coCustomP, meta.p_min), meta.p_max);
      populateCoBinaryFehOptions(meta.available_feh);
      configureCoBinaryCustomSliders();
      return meta;
    })
    .catch(() => { coBinaryMetaPromise = null; coBinaryMetaPromiseFeh = null; coBinaryMetaPromiseKind = null; return null; });
  return coBinaryMetaPromise;
}

// Build the CO [Fe/H] <select> from the real baked bucket list — never hardcoded, so a
// newly-baked bucket just appears (the HMS-HMS populateBinaryFehOptions twin). Skip if the
// list hasn't changed (keeps the user's own selection from being clobbered mid-interaction).
function populateCoBinaryFehOptions(list) {
  if (!els.coBinaryFeh || !list || !list.length) return;
  const current = [...els.coBinaryFeh.options].map((o) => Number(o.value));
  const same = current.length === list.length && current.every((v, i) => v === list[i]);
  if (!same) {
    els.coBinaryFeh.innerHTML = list.map((f) => `<option value="${f}">${f.toFixed(2)}</option>`).join("");
  }
  els.coBinaryFeh.value = String(coCustomFeh);
}

// All three CO axes span a wide dynamic range (and M_co is a physical mass, not a <1-dex
// ratio like q) → log-scale position sliders on every one, the mni-slider idiom.
const coMstarFromPos = (pos) => {
  const lo = Math.log10(coBinaryMeta.m_star_min), hi = Math.log10(coBinaryMeta.m_star_max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
};
const posFromCoMstar = (m) => {
  const lo = Math.log10(coBinaryMeta.m_star_min), hi = Math.log10(coBinaryMeta.m_star_max);
  return clamp01((Math.log10(m) - lo) / (hi - lo));
};
const coMcoFromPos = (pos) => {
  const lo = Math.log10(coBinaryMeta.m_co_min), hi = Math.log10(coBinaryMeta.m_co_max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
};
const posFromCoMco = (m) => {
  const lo = Math.log10(coBinaryMeta.m_co_min), hi = Math.log10(coBinaryMeta.m_co_max);
  return clamp01((Math.log10(m) - lo) / (hi - lo));
};
const coPFromPos = (pos) => {
  const lo = Math.log10(coBinaryMeta.p_min), hi = Math.log10(coBinaryMeta.p_max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
};
const posFromCoP = (p) => {
  const lo = Math.log10(coBinaryMeta.p_min), hi = Math.log10(coBinaryMeta.p_max);
  return clamp01((Math.log10(p) - lo) / (hi - lo));
};

function configureCoBinaryCustomSliders() {
  if (!coBinaryMeta || !els.coBinaryCustomMstar) return;
  els.coBinaryCustomMstar.min = 0; els.coBinaryCustomMstar.max = 1; els.coBinaryCustomMstar.step = 0.001;
  els.coBinaryCustomMstar.value = String(posFromCoMstar(coCustomMstar));
  els.coBinaryCustomMstarNum.min = String(coBinaryMeta.m_star_min); els.coBinaryCustomMstarNum.max = String(coBinaryMeta.m_star_max);
  setNum(els.coBinaryCustomMstarNum, fmt(coCustomMstar));

  els.coBinaryCustomMco.min = 0; els.coBinaryCustomMco.max = 1; els.coBinaryCustomMco.step = 0.001;
  els.coBinaryCustomMco.value = String(posFromCoMco(coCustomMco));
  els.coBinaryCustomMcoNum.min = String(coBinaryMeta.m_co_min); els.coBinaryCustomMcoNum.max = String(coBinaryMeta.m_co_max);
  setNum(els.coBinaryCustomMcoNum, fmt(coCustomMco));

  els.coBinaryCustomP.min = 0; els.coBinaryCustomP.max = 1; els.coBinaryCustomP.step = 0.001;
  els.coBinaryCustomP.value = String(posFromCoP(coCustomP));
  els.coBinaryCustomPNum.min = String(coBinaryMeta.p_min); els.coBinaryCustomPNum.max = String(coBinaryMeta.p_max);
  setNum(els.coBinaryCustomPNum, fmt(coCustomP));
}

// The honesty line under the CO custom sliders (the updateBinaryCustomNote twin): always
// the TRUE snapped grid node the backend returned, never the raw drag; + the *_snapped_far
// off-grid flags; + a caveat when the snapped companion is a POSYDON "WD" (that channel is
// a placeholder in the source grid — every WD-companion node is exactly 1.00 M☉, not real
// data; the Chunk-1a schema recon, surfaced now that dragging M_co low can reach it).
function updateCoBinaryCustomNote() {
  if (!els.coBinaryCustomNote || !coBinaryTrackData) return;
  const t = coBinaryTrackData;
  const far = [];
  if (t.m_star_snapped_far) far.push("star mass");
  if (t.m_co_snapped_far) far.push("compact-object mass");
  if (t.p_snapped_far) far.push("P");
  if (t.feh_snapped_far) far.push("[Fe/H]");
  const farNote = far.length ? ` — snapped far off-grid on ${far.join(", ")}` : "";
  const wdNote = t.co_type === "WD"
    ? " Note: POSYDON's WD-companion channel is a placeholder (every WD node is exactly 1.00 M☉, not modelled)."
    : "";
  els.coBinaryCustomNote.textContent =
    `Nearest real POSYDON track: star ${fmt(t.m_star_init_msun)} M☉, ${t.co_type} ${fmt(t.m_co_init_msun)} M☉, ` +
    `P=${fmt(t.p_init_d)} d — outcome: ${t.outcome}${farNote}.${wdNote}`;
}

// The [Fe/H] snap-honesty line — shown for EITHER CO demo (curated or custom), unlike the
// M_star/M_co/P note above (only visible inside the custom controls). The updateBinaryFehNote twin.
function updateCoBinaryFehNote() {
  if (!els.coBinaryFehNote) return;
  if (!coBinaryTrackData) { els.coBinaryFehNote.textContent = ""; return; }
  const t = coBinaryTrackData;
  els.coBinaryFehNote.textContent = t.feh_snapped_far
    ? `Nearest available POSYDON metallicity: [Fe/H]=${fmt(t.feh, 2)} (snapped far off-grid).`
    : `POSYDON metallicity bucket: [Fe/H]=${fmt(t.feh, 2)}.`;
}

// path (b) Chunk 4c: free M1/q/P sliders behind the "Custom orbit" demo. /binary_track was
// always general (snap-always over the WHOLE POSYDON grid, §6) — the three curated demos
// were a de-risking UI choice, not a backend limit, so this needed no backend change.
// `binaryMeta` (the grid bounds — /binary_track_meta) is fetched once, lazily, on first use
// and cached; the log-scale M1/P slider math and the linear q slider both read its bounds,
// so nothing here is hardcoded against the actual grid span (3.9–286 M☉, 0.1–5179 d, q
// 0.05–0.99 — measured, not assumed).
let binaryMeta = null;
let binaryMetaPromise = null;
let binaryMetaPromiseFeh = null;   // which feh binaryMetaPromise was started for (dedupes
                                    // concurrent calls without returning a stale in-flight
                                    // promise for a since-changed feh selection)
let binaryMetaFeh = null;      // which customFeh the cached binaryMeta reflects — a change
                                // in customFeh invalidates it (the m1/q/p bounds are PER-bucket:
                                // the 8 POSYDON metallicities are separate grids, not one).
const BINARY_CUSTOM_DEFAULT = { m1: 8.83, q: 0.6, p: 3.73 };   // starts from the Case-B node
let customM1 = BINARY_CUSTOM_DEFAULT.m1;
let customQ = BINARY_CUSTOM_DEFAULT.q;
let customP = BINARY_CUSTOM_DEFAULT.p;
let customFeh = 0.0;           // the selected POSYDON metallicity bucket (solar by default),
                                // applies to EVERY demo (curated or custom) — orthogonal to
                                // which (M1,q,P) is picked, mirroring the MIST mass/[Fe/H] split.

function ensureBinaryMeta() {
  if (binaryMeta && binaryMetaFeh === customFeh) return Promise.resolve(binaryMeta);
  if (binaryMetaPromise && binaryMetaPromiseFeh === customFeh) return binaryMetaPromise;
  const fehAtCall = customFeh;   // snapshot — customFeh may change again before this resolves
  binaryMetaPromiseFeh = fehAtCall;
  binaryMetaPromise = fetchJSON(`/binary_track_meta?feh=${fehAtCall}`)
    .then((meta) => {
      binaryMeta = meta;
      binaryMetaFeh = fehAtCall;
      customM1 = Math.min(Math.max(customM1, meta.m1_min), meta.m1_max);
      customQ = Math.min(Math.max(customQ, meta.q_min), meta.q_max);
      customP = Math.min(Math.max(customP, meta.p_min), meta.p_max);
      populateBinaryFehOptions(meta.available_feh);
      configureBinaryCustomSliders();
      return meta;
    })
    .catch(() => { binaryMetaPromise = null; binaryMetaPromiseFeh = null; return null; });
  return binaryMetaPromise;
}

// Build the [Fe/H] <select> options from the real baked bucket list (8 POSYDON
// metallicities, roughly −4.0…+0.3) — never hardcoded, so a future bucket just
// appears. Cheap to rebuild every meta fetch; skip if the list hasn't changed
// (keeps the user's own selection from being clobbered mid-interaction).
function populateBinaryFehOptions(list) {
  if (!els.binaryFeh || !list || !list.length) return;
  const current = [...els.binaryFeh.options].map((o) => Number(o.value));
  const same = current.length === list.length && current.every((v, i) => v === list[i]);
  if (!same) {
    els.binaryFeh.innerHTML = list.map((f) => `<option value="${f}">${f.toFixed(2)}</option>`).join("");
  }
  els.binaryFeh.value = String(customFeh);
}

// M1 and P span a wide dynamic range (~1.9 / ~4.7 dex) — log-scale position sliders, the
// mni-slider idiom. q spans <1 dex and is a plain ratio, so its range input binds the
// physical value directly (no position indirection needed).
const customM1FromPos = (pos) => {
  const lo = Math.log10(binaryMeta.m1_min), hi = Math.log10(binaryMeta.m1_max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
};
const posFromCustomM1 = (m) => {
  const lo = Math.log10(binaryMeta.m1_min), hi = Math.log10(binaryMeta.m1_max);
  return clamp01((Math.log10(m) - lo) / (hi - lo));
};
const customPFromPos = (pos) => {
  const lo = Math.log10(binaryMeta.p_min), hi = Math.log10(binaryMeta.p_max);
  return 10 ** (lo + clamp01(pos) * (hi - lo));
};
const posFromCustomP = (p) => {
  const lo = Math.log10(binaryMeta.p_min), hi = Math.log10(binaryMeta.p_max);
  return clamp01((Math.log10(p) - lo) / (hi - lo));
};

function configureBinaryCustomSliders() {
  if (!binaryMeta || !els.binaryCustomM1) return;
  els.binaryCustomM1.min = 0; els.binaryCustomM1.max = 1; els.binaryCustomM1.step = 0.001;
  els.binaryCustomM1.value = String(posFromCustomM1(customM1));
  els.binaryCustomM1Num.min = String(binaryMeta.m1_min); els.binaryCustomM1Num.max = String(binaryMeta.m1_max);
  setNum(els.binaryCustomM1Num, fmt(customM1));

  els.binaryCustomQ.min = String(binaryMeta.q_min); els.binaryCustomQ.max = String(binaryMeta.q_max);
  els.binaryCustomQ.step = 0.01;
  els.binaryCustomQ.value = String(customQ);
  els.binaryCustomQNum.min = String(binaryMeta.q_min); els.binaryCustomQNum.max = String(binaryMeta.q_max);
  setNum(els.binaryCustomQNum, fmt(customQ));

  els.binaryCustomP.min = 0; els.binaryCustomP.max = 1; els.binaryCustomP.step = 0.001;
  els.binaryCustomP.value = String(posFromCustomP(customP));
  els.binaryCustomPNum.min = String(binaryMeta.p_min); els.binaryCustomPNum.max = String(binaryMeta.p_max);
  setNum(els.binaryCustomPNum, fmt(customP));
}

// The honesty line under the sliders: the dragged (M1,q,P) is NEVER what's shown — the
// panel always states the TRUE snapped grid node the backend actually returned (the §6
// snap-always discipline), plus an off-grid note when the drag lands far from any real
// track (the *_snapped_far flags /binary_track already computes).
function updateBinaryCustomNote() {
  if (!els.binaryCustomNote || !binaryTrackData) return;
  const t = binaryTrackData;
  const far = [];
  if (t.m1_snapped_far) far.push("M₁");
  if (t.q_snapped_far) far.push("q");
  if (t.p_snapped_far) far.push("P");
  if (t.feh_snapped_far) far.push("[Fe/H]");
  const farNote = far.length ? ` — snapped far off-grid on ${far.join(", ")}` : "";
  els.binaryCustomNote.textContent =
    `Nearest real POSYDON track: M₁=${fmt(t.m1_init_msun)} M☉, q=${fmt(t.q_init)}, ` +
    `P=${fmt(t.p_init_d)} d — outcome: ${t.outcome}${farNote}.`;
}

// The [Fe/H] counterpart of updateBinaryCustomNote — shown for EVERY demo (curated or
// custom), unlike the M1/q/P note above (which is only visible inside the "Custom orbit"
// controls): metallicity applies to whichever system is showing, so its snap honesty
// belongs outside that hidden block.
function updateBinaryFehNote() {
  if (!els.binaryFehNote) return;
  if (!binaryTrackData) { els.binaryFehNote.textContent = ""; return; }
  const t = binaryTrackData;
  els.binaryFehNote.textContent = t.feh_snapped_far
    ? `Nearest available POSYDON metallicity: [Fe/H]=${fmt(t.feh, 2)} (snapped far off-grid).`
    : `POSYDON metallicity bucket: [Fe/H]=${fmt(t.feh, 2)}.`;
}

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

// --- the thermal-pulse showcase (a wd-mode sub-view) -------------------------
// The TPAGB rows of a snapped endgame sequence (the He-shell-flash phase). Contiguous by
// construction (endgame() clips ZAMS→…→TPAGB→post-AGB in order), so a phase filter is exact.
function pulseTPSlice(states) {
  return states.filter((s) => s.phase === "TPAGB");
}

// The visibility gate: median per-pulse ΔlogL via local-extrema detection on surface log L.
// Consecutive turning points alternate peak/trough, so |Δ| between them is a flash amplitude;
// the median tracks metallicity and is NOT fooled by MIST's fine flash sampling (measured:
// 1–3 M☉ ≈ 0.26–0.34 dex, 5 M☉ ≈ 0.02 dex where hot-bottom burning flattens the loops). Below
// PULSE_GATE_DEX the "showcase" would be a near-flat line — so the toggle stays hidden (the
// honesty gate: only offer the view where there's something real to see).
function tpMedianPulseAmplitude(tp) {
  if (!tp || tp.length < 5) return 0;
  const y = tp.map((s) => Math.log10(s.L_lsun));
  const ext = [];
  for (let i = 1; i < y.length - 1; i++) {
    if ((y[i] > y[i - 1] && y[i] >= y[i + 1]) || (y[i] < y[i - 1] && y[i] <= y[i + 1])) ext.push(y[i]);
  }
  if (ext.length < 2) return 0;
  const amps = [];
  for (let i = 1; i < ext.length; i++) amps.push(Math.abs(ext[i] - ext[i - 1]));
  amps.sort((a, b) => a - b);
  return amps[Math.floor(amps.length / 2)];
}

// slider fraction (0..1) -> index within the TPAGB slice (linear — the whole point is that
// each pulse row gets equal travel, unlike the compressed WD_FP band).
function pulseIndexFromFraction(frac) {
  if (!pulseStates || !pulseStates.length) return 0;
  return Math.max(0, Math.min(pulseStates.length - 1, Math.round(clamp01(frac) * (pulseStates.length - 1))));
}

// Landmark ticks for the pulse scrub: the TPAGB onset (row 0 — the quiescent early-AGB rise
// begins here; the first ACTUAL flash comes ~½ Myr later) and the end of the AGB. The loops
// between are too many and too even to individually label — the sawtooth itself is the map.
function rebuildPulseTicks() {
  buildTickStrip(els.ageMarks, [
    { pos01: 0, label: "TPAGB onset" },
    { pos01: 1, label: "end of AGB" },
  ]);
  els.ageTicks.innerHTML = "";
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
  "stripped-envelope star":
    "Stripped-envelope star — the hot, compact core a close companion has bared by " +
    "stripping the hydrogen envelope (Case-B Roche-lobe overflow; Götberg 2018). The dominant " +
    "(~70%) channel for stripped/Wolf–Rayet stars, unifying hot subdwarfs (low mass) and " +
    "Wolf–Rayet stars (high mass). Shown as a what-if fork — one representative state (halfway " +
    "through core-helium burning), snapped to the nearest grid model; the companion is not drawn.",
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
  else spectrum.update(s, { endgame: "wd" });   // giant rows use the main cube, but hide the α what-if
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

// Render the current thermal-pulse showcase state (a wd-mode sub-view). The consumers behave
// exactly as in refreshWD's TPAGB branch — a TPAGB row is a cool, low-gravity giant, so the 3D
// star, comp cross-section, SED and (main-cube) spectrum are unchanged; ONLY the HR panel
// differs (it's in pulseMode via hr.setThermalPulses → the decompressed L-vs-kyr sawtooth) and
// the caption speaks to the flashes. A pure function of pulseStates + pulseFraction (no fetch).
function refreshPulse() {
  if (!pulseStates || !pulseStates.length) return;
  const i = pulseIndexFromFraction(pulseFraction);
  const s = pulseStates[i];

  star.update(s, { endgame: "wd" });   // smooth degenerate-envelope giant, cooling color
  classification.update(s, "wd");
  scale.update(s);
  hr.update(s);                         // hr is in pulseMode → the marker rides the sawtooth
  comp.update(s);
  sed.update(s, { endgame: true });
  spectrum.update(s, { endgame: "wd" });   // a TPAGB row is a cool giant → always the main cube
  renderWDReadout(s, wdZones(endgame.states));

  els.status.style.color = teffToCSS(s.Teff_K);
  els.status.innerHTML =
    tipSpan("thermal pulses",
      "The decompressed TPAGB helium-shell-flash phase — the same real grid track as the " +
      "white-dwarf scrub, given the whole panel so the luminosity loops are actually visible.") +
    " · " + tipSpan(s.phase, phaseTip(s.phase)) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");

  // Honest caption: this star's own median loop amplitude, the row count + no-interp
  // provenance, and where in the ~Myr pulse sequence the marker sits.
  const amp = tpMedianPulseAmplitude(pulseStates);
  const kyr = (s.age_yr - pulseStates[0].age_yr) / 1e3;
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent =
    `Thermal pulses — helium-shell flashes on the TPAGB, ~${amp.toFixed(2)} dex per loop, ` +
    `${pulseStates.length} MIST rows snapped to one real track (no interpolation) · ` +
    `${kyr.toFixed(0)} kyr since TPAGB onset · total age ${gyr(s.age_yr)} since ZAMS.`;
}

// Show the pulse toggle only in wd-mode when the amplitude gate passes; label it by state.
function updatePulseToggle() {
  if (!els.pulseToggle) return;
  els.pulseToggle.hidden = !(mode === "wd" && pulseGateOK);
  els.pulseToggle.textContent = pulseView ? "← Back to cooling" : "🔍 Thermal pulses";
}

// Enter the decompressed thermal-pulse view from the toggle (wd-mode only, gate already passed).
function enterPulseView() {
  if (mode !== "wd" || !pulseStates || !pulseStates.length) return;
  pulseView = true;
  hr.setThermalPulses(pulseStates);   // hr → pulseMode (endgameMode stays set underneath)
  rebuildPulseTicks();
  pulseFraction = 0;                  // land at the first pulse — scrub forward
  els.age.value = pulseFraction;
  updatePulseToggle();
  refreshPulse();
}

// Leave the pulse view back to the normal WD cooling scrub. Land the WD slider back inside its
// (compressed) pulse band, proportional to where we were in the decompressed scrub — so the
// round-trip is continuous (you return to roughly the same pulse you were watching).
function exitPulseView() {
  if (mode !== "wd") return;
  pulseView = false;
  hr.clearThermalPulses();            // hr → back to the endgame HR view (bounds unchanged)
  rebuildWDTicks();
  wdFraction = clamp01(pulseFraction * WD_FP);
  els.age.value = wdFraction;
  updatePulseToggle();
  refreshWD();
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
  // The Rotation SECTION stays present for every living star (reserving its space so a mass
  // drag across the Kraft break / dynamo edge doesn't make the Controls panel jump — user
  // request; see the index.html note). Its regime-specific FACETS still appear/disappear, and
  // when NONE applies we show a placeholder note that explains when they would — the advisor's
  // "reserve the section's outer height with a placeholder row" (greying each ill-defined facet
  // individually would be worse). This reverses the old "absent, not a dead knob" call here.
  c.hidden = false;
  // Show the track toggle ONLY where it actually changes the track (above the ~1.2 M☉ Kraft
  // break, `active`) — NOT greyed below it. Below the break the section still reserves space
  // via the period facet or the placeholder note, so this facet can hide without a panel jump.
  // (`active` is mass/[Fe/H]-derived, stable across an age scrub, so no mid-drag reflow.)
  const showToggle = !!(rotStatus.has_grid && rotStatus.active);
  // VISIBILITY of the period facet = the cool-MS family (also track-stable); sed.js greys it
  // per-age via rot.sync(). Both facets are track-stable, so an age scrub never changes height.
  const showPeriod = coolDynamoFamily();
  // Inclination facet (Chunk 2): shown when the rotating track is SELECTED on a star massive
  // enough for it to matter (showToggle ⇒ above the Kraft break) — i.e. exactly the gravity-
  // darkened population (an oblate marker ⇒ v_rot>0 ⇒ rotationOn). This gate is mass/[Fe/H]-
  // derived (TRACK-STABLE), so it never appears/disappears mid-age-scrub and can't jitter the
  // Age thumb: at giant ages the star simply isn't oblate and star.js keeps the tilt at 0
  // (round disk) while the slider stays put — per-age feedback lives in the note, not the
  // visibility. No need to compute rotationDistortion here.
  const showIncl = showToggle && rotationOn;
  const anyFacet = showToggle || showPeriod || showIncl;
  // -- track facet --
  els.rotToggleRow.hidden = !showToggle;
  if (showToggle) {
    els.rotToggle.checked = rotationOn;
    els.rotToggle.disabled = false;                       // shown ⇒ always live now
    els.rotToggleRow.classList.remove("disabled");        // clear any stale greyed styling
  }
  // -- rot-note: the track-facet note when the toggle shows; a PLACEHOLDER (explaining when the
  //    rotation controls appear) when no facet applies; otherwise hidden (the period/inclination
  //    facets carry their own notes, and an empty rot-note between the head and the slider would
  //    just add a gap). --
  if (showToggle) {
    els.rotNote.hidden = false;
    els.rotNote.textContent = rotationOn
      ? "Rotating track (v/vcrit 0.4): main-sequence N & He enrichment, longer life, shifted track."
      : "Non-rotating track — toggle to add MIST's v/vcrit = 0.4 rotation.";
  } else if (!anyFacet) {
    els.rotNote.hidden = false;
    els.rotNote.textContent =
      "Rotation shapes massive stars (a rotating evolutionary track — above ~1.2 M☉) and cool "
      + "dwarfs (magnetic activity, which sets the X-ray output); its controls appear for those stars.";
  } else {
    els.rotNote.hidden = true;
  }
  // -- activity facet -- (sed.js syncs the slider/note internally via rot.sync())
  els.sedRot.hidden = !showPeriod;
  // -- inclination facet -- reflect the persisted angle on the inputs when it (re)appears.
  if (els.inclControl) {
    els.inclControl.hidden = !showIncl;
    if (showIncl) {
      if (els.incl) els.incl.value = String(inclinationDeg);
      if (els.inclNum) els.inclNum.value = String(inclinationDeg);
      if (els.inclNote && !els.inclNote.textContent) applyInclination(inclinationDeg);
    }
  }
  // Inclination cue (user request): when the inclination control is available the 3D sphere tilts
  // toward the observer across the whole slider, and an optional orientation grid makes that tilt
  // legible on a near-round star. The grid is OFF by default but AUTO-SHOWS ONCE the first time a
  // rotating star appears (gridAutoShown latches so it never re-fires); after that it follows the
  // user's checkbox, so a manual "off" is sticky across rotating↔non-rotating cycles.
  if (showIncl && !gridAutoShown) {
    gridAutoShown = true;
    axisGridOn = true;
    if (els.axisGridToggle) els.axisGridToggle.checked = true;
  }
  if (els.axisGridToggle) els.axisGridToggle.checked = axisGridOn;
  star.setInclActive(showIncl);
  star.setAxisGrid(axisGridOn);
}

// Render a live-mode what-if TOGGLE so its space is RESERVED as the mass/[Fe/H] sliders cross
// the control's eligibility band — the Controls panel no longer jumps as controls appear and
// disappear (user request; see the index.html note). The three reasons a control is hidden get
// three treatments (advisor): (1) out-of-regime → GREY (present + disabled + a "when it
// activates" note — the whole point); (2) data-absent (no local grid) → still HIDE (a knob that
// can never activate in this deployment is the genuinely-dead knob the honesty gates avoid);
// (3) endgame/stripped mode → still HIDE (a deliberate mode switch, not a per-mass jump).
// `activeNote` may be null when a separate refresh owns the on-state caption (helium/alpha).
// Returns `eligible` so the caller can tear down a stranded overlay.
function reserveWhatIf(control, toggle, note, opts) {
  if (!control) return false;
  const { dataPresent, eligible, checked, activeNote, offerNote, gatedNote } = opts;
  if (!dataPresent || mode !== "live") { control.hidden = true; return false; }
  control.hidden = false;
  const row = control.querySelector(".rot-toggle-row");
  if (row) row.classList.toggle("disabled", !eligible);
  if (toggle) { toggle.disabled = !eligible; toggle.checked = eligible && checked; }
  if (note) {
    if (!eligible) note.textContent = gatedNote;
    else if (checked) { if (activeNote != null) note.textContent = activeNote; }
    else note.textContent = offerNote;
  }
  return eligible;
}

// Ap/Bp chemically-peculiar toggle (atlas Tier C — evocative). A magnetic-chemical what-if
// for A/B MAIN-SEQUENCE stars: nowhere in MIST, so it is OFFERED only for the A/B mass band
// (TRACK-STABLE on the ZAMS mass — massValue doesn't change on an age scrub, so it never
// flickers), and star.js fades the effect per-state outside the A/B-MS Teff window. Now
// PRESENT-but-greyed outside the band (space reserved) rather than absent; still hidden in
// every endgame (mode != live). Frontend-only (no grid), so it's never data-absent. Gate is
// INDEPENDENT of the rotation toggle: Ap/Bp is a magnetic peculiarity, not a rotation-axis
// effect (many Ap stars rotate slowly).
function updatePeculiarControl() {
  const eligible = massValue >= 1.6 && massValue <= 5.0;
  reserveWhatIf(els.peculiarControl, els.peculiarToggle, els.peculiarNote, {
    dataPresent: true, eligible, checked: peculiarOn,
    activeNote: "Co-rotating abundance spots on the oblique magnetic dipole (the α² CVn look) — evocative.",
    offerNote: "What if this A/B star were magnetic chemically-peculiar? (the α² CVn look — evocative)",
    gatedNote: "Appears for A/B main-sequence stars, 1.6–5 M☉ (only ~10% are magnetic Ap/Bp).",
  });
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
  dropHeliumForModeSwitch();
  mode = "wd";
  updateRotControl();   // hide the rotation toggle inside the endgame (mode != live)
  updatePeculiarControl();
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
  // Prep the thermal-pulse showcase gate (the opt-in decompressed sub-view). Cache the TPAGB
  // slice + test its median loop amplitude ONCE here; the toggle only appears when it clears
  // the visibility gate (weak ≥5 M☉ hot-bottom-burning pulses don't earn a "showcase").
  pulseView = false;
  pulseStates = pulseTPSlice(endgame.states);
  pulseGateOK = tpMedianPulseAmplitude(pulseStates) >= PULSE_GATE_DEX;
  updatePulseToggle();
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
  dropHeliumForModeSwitch();
  mode = "wr";
  updateRotControl();   // hide the rotation toggle inside the endgame (mode != live)
  updatePeculiarControl();
  // Invalidate any in-flight live /track so it can't land and clobber the WR render
  // (the age scrub is fetch-free now, so /track is the only live fetch to guard).
  trackToken++;
  document.body.classList.add("wr-mode");
  if (els.pulseToggle) els.pulseToggle.hidden = true;   // the pulse toggle is WD-only
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

// Leave the endgame (WD / WR / SN) OR the binary-stripped what-if, reversibly — back to the
// living star. Shared by all modes: mode-specific consumer state (the comp WD-structure /
// SN-onion / stripped-surface flags) is all cleared by comp.clearEndgame(); hr.clearEndgame()
// restores the living HR frame.
function exitEndgame() {
  const prevMode = mode;   // captured before the reset — decides the age landing (see below)
  mode = "live";
  document.body.classList.remove("wd-mode", "wr-mode", "sn-mode", "stripped-mode");
  els.endgameBar.hidden = true;
  els.snControl.hidden = true;   // hide the ⁵⁶Ni slider (SN-only)
  els.age.disabled = false;      // re-enable the age slider (stripped-mode disabled it)
  pulseView = false; pulseStates = null; pulseGateOK = false;   // drop the thermal-pulse sub-view
  updatePulseToggle();           // hides the toggle (mode is now live)
  setWDResnapNote("");
  hr.clearEndgame();
  comp.clearEndgame();
  endgame = null; endgameKey = null;
  snModel = null; snToken++;     // drop the SN model + invalidate any in-flight /supernova fetch
  strippedData = null; strippedToken++;   // drop the stripped model + invalidate its in-flight fetch
  companionOn = false;                     // reset the path (b) companion reveal (hr.clearEndgame drops its marker)
  document.body.classList.remove("companion-on");   // hide the Roche panel (path (b) Chunk 3)
  // path (b) Chunk 4b: drop the co-evolving binary sub-view too (hr.clearEndgame already
  // called hr.clearBinaryTrack() above; this resets main.js's own copy of the state).
  binaryView = false; binaryTrackData = null; binaryStar1 = null; binaryStar2 = null;
  binaryDemoKey = null; binaryToken++;
  document.body.classList.remove("binary-view");
  if (els.binaryCustomControls) els.binaryCustomControls.hidden = true;
  // Chunk 1b: drop the CO-HMS_RLO sub-view too (hr.clearBinaryTrack ran above).
  coBinaryView = false; coBinaryTrackData = null; coBinaryStar = null; coBinaryToken++;
  document.body.classList.remove("co-binary-view");
  document.body.classList.remove("co-he-kind");
  if (els.coBinaryDcoNote) els.coBinaryDcoNote.textContent = "";
  if (els.coBinaryDemoBack) els.coBinaryDemoBack.hidden = true;
  els.mass.disabled = false; els.feh.disabled = false;    // in case binaryView had disabled them
  if (els.massNum) els.massNum.disabled = false;
  if (els.fehNum) els.fehNum.disabled = false;
  updateBinaryDemoButtons();
  roche.clear();
  // Return to the LIVING version of the endgame progenitor we were viewing
  // (lastEgMass/Feh) — not whatever transient value massValue holds. This is robust to
  // the focus/blur race where a still-focused mass box re-commits a reverted-away value
  // on the click that triggers this exit. Sync the controls to it.
  massValue = lastEgMass;
  els.feh.value = lastEgFeh;
  els.mass.value = clamp01(sliderFromMass(massValue));
  setNum(els.massNum, fmt(massValue));
  setNum(els.fehNum, lastEgFeh.toFixed(2));
  // wd/wr/sn are END-of-life endgames → land at the very end. The stripped star is a MID-LIFE
  // fork → return to the age we forked FROM (ageValue is untouched inside stripped-mode, so
  // refreshTrack restores the thumb to it via posFromAge). So pin-to-end only when leaving a
  // true endgame, not the stripped what-if.
  pinAgeToEnd = prevMode !== "stripped";
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
    // Recompute the thermal-pulse slice + gate for the new progenitor.
    pulseStates = pulseTPSlice(eg.states);
    pulseGateOK = tpMedianPulseAmplitude(pulseStates) >= PULSE_GATE_DEX;
    if (pulseView && pulseGateOK) {
      // Stay in the decompressed pulse view — re-fit to the new star's loops (keep the scrub).
      hr.setThermalPulses(pulseStates);
      rebuildPulseTicks();
      updatePulseToggle();
      refreshPulse();
    } else {
      // The cooling scrub (or the new star's pulses are too weak to show → fall back to it).
      pulseView = false;
      hr.setEndgame(eg.states);
      comp.setEndgame(eg.states);
      rebuildWDTicks();
      els.age.value = wdFraction;
      updatePulseToggle();
      refreshWD();
    }
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
    // endgame (hence pulseStates) is unchanged on a revert — stay in whichever view is active.
    if (pulseView) refreshPulse(); else refreshWD();
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
  dropHeliumForModeSwitch();
  mode = "sn";
  updateRotControl();   // hide the rotation control inside the endgame (mode != live)
  updatePeculiarControl();
  trackToken++;         // invalidate any in-flight live /track
  document.body.classList.add("sn-mode");
  if (els.pulseToggle) els.pulseToggle.hidden = true;   // the pulse toggle is WD-only
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

// --- binary-stripped-star what-if (stripped-mode) ----------------------------
// The mass-gated entry BUTTON — a big gateway-style button (user request), but a MID-LIFE fork,
// not an end-of-life gateway. Like the WD/WR/SN gateway it is a one-way ENTER: it shows only for a
// LIVE star (hidden in stripped-mode and every other endgame — the endgame bar's "Back" is the
// exit), present-but-greyed (disabled) outside the eligible progenitor-mass band so the panel's
// height is reserved. Track-stable on massValue (no age-scrub flicker). The Götberg CSV is
// committed, so it's never data-absent — only regime-gated.
function updateStrippedControl() {
  const c = els.strippedControl;
  if (!c) return;
  if (mode !== "live") { c.hidden = true; return; }   // one-way: no re-click exit (Back handles it)
  c.hidden = false;
  const eligible = massValue >= STRIP_MASS_MIN && massValue <= STRIP_MASS_MAX;
  if (els.strippedBtn) els.strippedBtn.disabled = !eligible;
  if (els.strippedNote) els.strippedNote.textContent = eligible
    ? "What if a close companion stripped the envelope now? (the ~70% binary WR/subdwarf channel)"
    : `Appears for progenitors that leave a stripped core, ${STRIP_MASS_MIN}–${STRIP_MASS_MAX} M☉ (the Götberg grid).`;
}

// --- initial-helium (Y) what-if overlay --------------------------------------
// The mass/[Fe/H]-gated entry toggle for the GC 2nd-generation overlay. Shown in live mode
// within the MESA grid's mass band and near solar [Fe/H] (the grid is solar-Z only). Like the
// other what-ifs it's a track-stable gate on massValue/feh, not an age-scrub flicker. If the
// star drifts out of the eligible region while the overlay is ON, tear it down (restore the
// MIST HR track) so it can never linger mislabeled.
function updateHeliumControl() {
  const c = els.heliumControl;
  if (!c) return;
  const feh = Number(els.feh.value);
  const inRegime = mode === "live"
    && massValue >= HE_MASS_MIN && massValue <= HE_MASS_MAX
    && Math.abs(feh) <= HE_FEH_TOL;
  // Tear the overlay down FIRST if the star drifted out of the eligible region with it up —
  // greying the knob must not strand the HR overlay (advisor). heliumOff() re-invokes us with
  // heliumOn=false, so return to avoid a double render.
  if (!(heliumHasGrid && inRegime) && heliumOn) { heliumOff(); return; }
  // data-absent (no local MESA runs) → HIDE (honesty gate); in-regime → live; out of regime →
  // greyed placeholder (space reserved). activeNote is null: refreshHelium owns the on-caption
  // (both ZAMS He fractions + the τ_MS lifetimes — the lesson that has no HR axis).
  reserveWhatIf(els.heliumControl, els.heliumToggle, els.heliumNote, {
    dataPresent: heliumHasGrid, eligible: inRegime, checked: heliumOn, activeNote: null,
    offerNote: "What if this star were born helium-rich? (a globular-cluster 2nd-generation what-if)",
    gatedNote: `Appears near solar [Fe/H] for ${HE_MASS_MIN}–${HE_MASS_MAX} M☉ (the self-run MESA grid).`,
  });
}

// Turn the overlay OFF: restore the live MIST HR track + marker, drop the overlay note.
function heliumOff() {
  heliumOn = false;
  heliumToken++;                 // cancel any in-flight /helium apply
  if (els.heliumToggle) els.heliumToggle.checked = false;
  hr.clearHeliumOverlay();
  if (currentTrack && currentTrack.length) hr.setTrack(currentTrack);
  refresh();                     // re-place the marker on the restored track
  updateHeliumControl();         // reset the note text
}

// Turn the overlay ON (or re-fetch it after a mass/[Fe/H] change): fetch the baseline+enhanced
// MESA pair for the current mass and hand both tracks to the HR panel. Latest-wins guarded — a
// fast mass drag must not let a stale pair paint. The caption carries the WHOLE Gate-2 story:
// the two ZAMS helium fractions AND both main-sequence lifetimes (the shorter-lived effect has
// no HR axis, so it would silently vanish without this — advisor catch).
async function refreshHelium() {
  if (!heliumOn) return;
  const token = ++heliumToken;
  const mass = massValue;
  let data;
  try {
    data = await fetchJSON(`/helium?mass=${mass}`);
  } catch (e) {
    if (token !== heliumToken || !heliumOn) return;
    // Tear the overlay DOWN on failure (don't leave heliumOn stuck — that guards the live HR
    // calls off and FREEZES the panel with no overlay to justify it). heliumOff restores the
    // live track + unchecks; set the note AFTER it (its updateHeliumControl resets the default).
    heliumOff();
    if (els.heliumNote) els.heliumNote.textContent = "Helium-enhanced tracks unavailable (no MESA data).";
    return;
  }
  if (token !== heliumToken || !heliumOn || mode !== "live") return;
  const b = data.baseline, en = data.enhanced;
  hr.setHeliumOverlay(b.states, en.states, { yBase: b.y_init, yEnh: en.y_init });
  if (els.heliumNote) {
    const ratio = b.tau_ms_gyr / en.tau_ms_gyr;
    const snap = data.mass_snapped_far
      ? ` · snapped to ${fmt(data.mass_snapped)} M☉`
      : "";
    els.heliumNote.textContent =
      `Baseline Y ${b.y_init.toFixed(2)} vs. helium-enhanced Y ${en.y_init.toFixed(2)}, ` +
      `same mass & [Fe/H] (self-run MESA). Bluer + brighter, and shorter-lived: ` +
      `τ_MS ${fmtGyr(en.tau_ms_gyr)} vs. ${fmtGyr(b.tau_ms_gyr)} (${ratio.toFixed(1)}× shorter)${snap}.`;
  }
}

// Format a main-sequence lifetime for the caption: Gyr with a Myr fallback for the massive,
// short-lived end (6 M☉ enhanced is ~29 Myr — "0.03 Gyr" reads as noise).
function fmtGyr(gyr) {
  return gyr >= 0.1 ? `${gyr.toFixed(2)} Gyr` : `${Math.round(gyr * 1000)} Myr`;
}

// Drop the overlay STATE when another view (endgame / stripped / SN) takes over the HR panel —
// that view's own enter path repaints the panel, so unlike heliumOff() this does NOT restore the
// live track (the hr.setEndgame/setBinaryTrack/… entries already clear heliumMode). Both the
// helium and the target toggle can be visible at once in their overlapping mass band, so this is
// reachable; call it at the top of every mode-entry that isn't "live".
function dropHeliumForModeSwitch() {
  dropAlphaForModeSwitch();      // the two MESA what-ifs share the HR slot — drop both on a mode switch
  dropPopulationForModeSwitch(); // the SED population overlay is living-only — drop it on any mode switch too
  dropIsochroneForModeSwitch();  // the cluster-isochrone HR overlay is living-only — drop it too
  dropHZForModeSwitch();         // the habitable-zone scale-bar overlay is living-only — drop it too
  dropObserverForModeSwitch();   // the observer reddening/mag view is living-only — drop it too
  if (!heliumOn) return;
  heliumOn = false;
  heliumToken++;
  if (els.heliumToggle) els.heliumToggle.checked = false;
  if (els.heliumControl) els.heliumControl.hidden = true;   // updateHeliumControl re-shows it on return to live
}

// Habitable-zone overlay (Axis D) is living-only: the scale bar in every endgame/stripped/binary
// mode already shows a different axis (the WD cooling star, the SN fireball, the stripped donor),
// so a stale HZ band there would be meaningless. Called from dropHeliumForModeSwitch (the shared
// mode-switch chokepoint). CSS also hides the toggle in those modes; this clears the STATE so a
// return to live starts clean and scale.js stops drawing the band immediately.
function dropHZForModeSwitch() {
  // The temporal twin (D2a) follows the band: hide + clear it unconditionally (cheap; it's
  // already hidden when hzOn is false, but a mode switch must never leave it stranded).
  if (els.hzHistoryPanel) els.hzHistoryPanel.hidden = true;
  hzhist.clear();
  if (!hzOn) return;
  hzOn = false;
  if (els.hzToggle) els.hzToggle.checked = false;
  scale.setHZ(false);
}

// Map the current track's StellarStates through the (shared) Kopparapu HZ physics into the
// per-row series the history panel draws: the four edge distances in AU, or {oor:true} for a
// row whose Teff is outside the 2600–7200 K calibration range (hz.js returns null → a gap on
// the diagram, never an interpolated bridge). Same habitableZone() call as the scale bar, so
// the two panels agree at any age by construction.
function buildHZSeries(track) {
  return track.map((s) => {
    const h = habitableZone(s.Teff_K, s.L_lsun);
    return h ? { age: s.age_yr, ...h } : { age: s.age_yr, oor: true };
  });
}

// Show/hide the HZ-history panel and (re)push its whole-life series + the current "now" line.
// The series is age-independent (it depends only on the track), so this is the track-change /
// toggle-on entry point; the per-scrub "now" line is pushed separately from refresh().
function syncHZHistory() {
  const panel = els.hzHistoryPanel;
  if (!panel) return;
  const on = hzOn && mode === "live" && currentTrack && currentTrack.length > 1;
  panel.hidden = !on;
  if (!on) { hzhist.clear(); return; }
  hzhist.setTrack(buildHZSeries(currentTrack));
  const i = trackRowFromPos(ageFraction);
  if (i >= 0) hzhist.setNow(currentTrack[i].age_yr);
}

// --- observer's view (Axis A) — its own panel: the observational CMD ----------
// Gate mirrors the population/isochrone controls: the panel is shown only in live mode and only
// when the absolute-flux spectrum cube is present (magnitudes are meaningless without it). Unlike
// the old opt-in toggle, when eligible the panel is simply ON — the intrinsic CMD is always
// meaningful, and the sliders default to a dust-free view (av=0) so the Spectrum/SED stay
// byte-unchanged until the user adds dust.
function updateObserverControl() {
  const c = els.observerPanel;
  if (!c) return;
  const eligible = observerHasData && mode === "live";
  if (!eligible) {
    if (observerOn) observerOff();   // e.g. entering an endgame with the view up → restore intrinsic
    else c.hidden = true;
    return;
  }
  const wasOn = observerOn;
  observerOn = true;
  c.hidden = false;
  // Fetch the CMD locus for the current star (deduped by (mass,[Fe/H],vvcrit) — cheap per scrub).
  refreshPhotometryTrack();
  if (!wasOn) {
    // Just became eligible (first paint / return from an endgame): reflect the knob values and
    // drive the marker once. On subsequent paints paintState()'s refreshObserver(s) owns the marker.
    syncObserverKnobs();
    if (observerMarker) refreshObserver(observerMarker);
  }
}

// Turn the observer view OFF: hide the panel, restore the intrinsic (un-reddened) Spectrum + SED,
// clear the CMD. setReddening(false) is a no-op path on both panels, so this is byte-identical.
function observerOff() {
  observerOn = false;
  observerToken++;               // cancel any in-flight /photometry readout
  obsTrackToken++;               // cancel any in-flight /photometry_track locus fetch
  obsTrackKey = null;
  if (obsDebounce) { clearTimeout(obsDebounce); obsDebounce = null; }
  spectrum.setReddening(false, 0, obsRv);
  sed.setReddening(false, 0, obsRv);
  cmd.clear();
  if (els.observerPanel) els.observerPanel.hidden = true;
}

// Living-only, like the HZ band: the endgame/stripped spectra come from continuum-normalized or
// differently-ranged cubes, so a reddened overlay + an absolute magnitude there would be a silent
// wrong answer. Called from the shared mode-switch chokepoint (dropHeliumForModeSwitch).
function dropObserverForModeSwitch() {
  if (observerOn) observerOff();
  if (els.observerPanel) els.observerPanel.hidden = true;
}

// Fetch the intrinsic CMD locus (the whole track as B−V vs M_V) for the current star and push it
// to the panel. Deduped by (mass,[Fe/H],vvcrit) — the locus is age-independent, so scrubbing age
// never refetches it. Latest-wins guarded. Reads the current controls (same source as /track).
async function refreshPhotometryTrack() {
  if (!observerOn || mode !== "live" || !els.mass) return;
  const mass = massValue, feh = Number(els.feh.value), vv = effVvcrit();
  const key = `${mass}|${feh}|${vv}`;
  if (key === obsTrackKey) return;   // already have this locus
  obsTrackKey = key;
  const token = ++obsTrackToken;
  try {
    const d = await fetchJSON(`/photometry_track?mass=${mass}&feh=${feh}&vvcrit=${vv}`);
    if (token !== obsTrackToken || !observerOn || mode !== "live") return;
    cmd.setLocus(d.points, d.has_bv);
  } catch (e) {
    if (token !== obsTrackToken) return;
    obsTrackKey = null;   // let a later eligible refresh retry
    cmd.setLocus(null, false);
  }
}

// Reflect the current obsDistancePc/obsAv/obsRv onto the sliders + their value labels. Called on
// enable (with the seeded demo values) and after any programmatic change.
function syncObserverKnobs() {
  if (els.obsDistance) els.obsDistance.value = String(obsFracFromDist(obsDistancePc));
  if (els.obsAv) els.obsAv.value = String(obsAv);
  if (els.obsRv) els.obsRv.value = String(obsRv);
  if (els.obsDistanceVal) els.obsDistanceVal.textContent = fmtDistance(obsDistancePc);
  if (els.obsAvVal) els.obsAvVal.textContent = `${obsAv.toFixed(2)} mag`;
  if (els.obsRvVal) els.obsRvVal.textContent = obsRv.toFixed(1);
}

// A friendly distance label: pc up to ~1 kpc, then kpc.
function fmtDistance(pc) {
  if (pc < 1000) return `${pc < 100 ? pc.toFixed(1) : Math.round(pc)} pc`;
  return `${(pc / 1000).toFixed(pc < 10000 ? 2 : 1)} kpc`;
}

// Push the client-side reddening overlay (instant) and (debounced) fetch the magnitude/colour
// readout for the current marker. Called from paintState (marker moved) and from the knob-drag
// handlers (av/rv/distance changed). The overlay never waits on the network — only the numbers do.
function refreshObserver(s) {
  // Remember the latest live marker even when the panel isn't on yet, so updateObserverControl can
  // drive the CMD the instant the panel becomes eligible (first paint / return from an endgame).
  if (mode === "live" && s) observerMarker = s;
  if (!observerOn || mode !== "live" || !s) return;
  // The visual overlay is a pure client-side transform of the already-served Spectrum/SED curves.
  spectrum.setReddening(true, obsAv, obsRv);
  sed.setReddening(true, obsAv, obsRv);
  // The readout (apparent mag, reddened colour) needs the tested /photometry path — debounce it so
  // a fast age-scrub or A_V drag doesn't fire a spectrum compute per frame.
  if (obsDebounce) clearTimeout(obsDebounce);
  obsDebounce = setTimeout(() => fetchObserverReadout(s), 110);
}

async function fetchObserverReadout(s) {
  if (!observerOn || mode !== "live" || !s) return;
  const teff = s.Teff_K, logg = s.logg, feh = s.feh_init ?? 0, r = s.R_rsun;
  if (!(r > 0) || teff == null || logg == null) return;
  const token = ++observerToken;
  let data;
  try {
    data = await fetchJSON(
      `/photometry?teff=${teff}&logg=${logg}&feh=${feh}&radius_rsun=${r}` +
      `&distance_pc=${obsDistancePc}&av=${obsAv}&rv=${obsRv}`);
  } catch (e) {
    if (token !== observerToken || !observerOn) return;
    if (els.observerReadout) els.observerReadout.textContent = "";
    if (els.observerNote)
      els.observerNote.textContent = "Photometry unavailable (spectrum cube not present).";
    return;
  }
  if (token !== observerToken || !observerOn || mode !== "live") return;
  renderObserverReadout(data);
}

// Render the apparent-magnitude / observational-colour readout from a /photometry payload. The
// honesty caveats ride along: a hot star whose spectrum was clamped to the grid ceiling has a
// colour that is only a lower bound, and the synthetic (B−V) carries a known ~0.04-mag B-band
// zero-point convention offset that is common-mode (so it cancels in the CMD — see A3).
function renderObserverReadout(d) {
  if (!els.observerReadout) return;
  const mvAbs = d.mv_abs, mvApp = d.mv_app, mu = d.distance_modulus;
  const bv0 = d.bv0, bvObs = d.bv_obs, ebv = d.ebv;
  const parts = [];
  if (mvAbs != null) parts.push(`M<sub>V</sub> ${mvAbs.toFixed(2)}`);
  if (mvApp != null && mu != null)
    parts.push(`apparent V ${mvApp.toFixed(2)} <span class="obs-dim">(μ = ${mu.toFixed(2)})</span>`);
  if (bv0 != null && bvObs != null && ebv != null)
    parts.push(`(B−V)₀ ${bv0.toFixed(2)} → reddened ${bvObs.toFixed(2)} ` +
      `<span class="obs-dim">E(B−V) = ${ebv.toFixed(2)}</span>`);
  els.observerReadout.innerHTML = parts.join(" · ");
  // Push the EXACT intrinsic + observed positions to the CMD marker (the tested-path values, so the
  // arrow tip is never an approximation). observed==intrinsic when dust-free at 10 pc (zero arrow).
  if (bv0 != null && mvAbs != null) {
    const obs = (bvObs != null && mvApp != null) ? { bv: bvObs, mv: mvApp } : null;
    cmd.setMarker({ bv: bv0, mv: mvAbs }, obs);
  }
  // The honesty note: hot-clamp lower bound (if the spectrum hit the grid ceiling) + the standing
  // B-band ZP-convention caveat that keeps the absolute colour from over-claiming.
  if (els.observerNote) {
    const clamped = d.teff_requested != null && d.teff_max != null && d.teff_requested > d.teff_max + 1;
    els.observerNote.textContent = clamped
      ? `Spectrum clamped to the grid's ${Math.round(d.teff_max).toLocaleString()} K ceiling — ` +
        `this hot star's blue colour is a lower bound.`
      : "Synthetic (B−V) runs ~0.04 mag blue (a B-band zero-point convention) — common-mode, so it " +
        "cancels in the cluster CMD.";
  }
}

// --- coeval-population (BPASS) overlay on the SED panel -----------------------
// The first ENSEMBLE feature: single-star vs. +binaries integrated population spectra at
// the marker's ([Fe/H], age), drawn on the broadband SED panel (sed.js). Unlike He/α this
// is NOT a mode-swap and NOT mass-gated — it applies at any marker (reads only [Fe/H]+age).
// The only gate is the host-baked cube (/population_status). Living-star only.
function updatePopulationControl() {
  const c = els.populationControl;
  if (!c) return;
  const eligible = populationHasGrid && mode === "live";
  c.hidden = !eligible;
  if (!eligible) {
    if (populationOn) populationOff();   // e.g. mode changed under it → tear it down
    return;
  }
  if (els.populationToggle) els.populationToggle.checked = populationOn;
  if (!populationOn && els.populationNote)
    els.populationNote.textContent =
      "What would a whole population born with this star look like — and how do binaries change it?";
}

// Turn the overlay OFF: clear the SED-panel curves, uncheck, reset the note.
function populationOff() {
  populationOn = false;
  populationToken++;             // cancel any in-flight /population apply
  popNodeKey = "";
  if (els.populationToggle) els.populationToggle.checked = false;
  sed.clearPopulation();
  hr.clearPopulationHRD();        // remove the HR-panel population cloud too
  updatePopulationControl();     // reset the note text
}

// Drop the overlay when a non-live mode takes over (endgame/stripped/SN/binary). sed.js hides
// the population in endgame anyway, but clear the state so returning to live never flashes a
// stale population before the next fetch (called from dropHeliumForModeSwitch, the mode hook).
function dropPopulationForModeSwitch() {
  if (!populationOn) return;
  populationOn = false;
  populationToken++;
  popNodeKey = "";
  if (els.populationToggle) els.populationToggle.checked = false;
  if (els.populationControl) els.populationControl.hidden = true;
  sed.clearPopulation();
  hr.clearPopulationHRD();        // the HR-panel cloud is living-only — drop it on any mode switch
}

// Fetch + push the population spectra for the marker's ([Fe/H], age). Called from paintState;
// re-fetches only when the snapped node could change — popNodeKey buckets requests FINER than
// the BPASS grid so a same-node age scrub doesn't refetch (the payload would be identical).
// Latest-wins guarded. The note carries the snapped node + the measured UV-longevity lesson.
async function refreshPopulation(s) {
  if (!populationOn || mode !== "live" || !s) return;
  const feh = s.feh_init ?? 0;
  const ageGyr = (s.age_yr ?? 0) / 1e9;
  if (!(ageGyr > 0)) return;
  // Bucket the request finer than the grid (feh nodes ≥0.1 dex apart; age nodes ~0.1 dex),
  // so every node change flips the key while scrubbing within one node does not.
  const key = `${(Math.round(feh / 0.05) * 0.05).toFixed(2)}|` +
    `${(Math.round(Math.log10(ageGyr) / 0.03) * 0.03).toFixed(2)}`;
  if (key === popNodeKey) return;
  const token = ++populationToken;
  let data, hrd = null;
  try {
    // The SED spectrum (Chunk 1) is required; the HR-diagram number density (Chunk 2) is an
    // independent cube — fetch both in parallel, but degrade gracefully if only the HRD is
    // absent (its own .catch → null; hr.setPopulationHRD(null) just clears the HR cloud).
    const reqs = [fetchJSON(`/population?feh=${feh}&age_gyr=${ageGyr}`)];
    reqs.push(populationHasHRD
      ? fetchJSON(`/population_hrd?feh=${feh}&age_gyr=${ageGyr}`).catch(() => null)
      : Promise.resolve(null));
    [data, hrd] = await Promise.all(reqs);
  } catch (e) {
    if (token !== populationToken || !populationOn) return;
    popNodeKey = "";
    populationOff();
    if (els.populationNote)
      els.populationNote.textContent = "Population spectra unavailable (BPASS cube not baked).";
    return;
  }
  if (token !== populationToken || !populationOn || mode !== "live") return;
  popNodeKey = key;
  sed.setPopulation(data);
  hr.setPopulationHRD(hrd);   // the coeval-population cloud on the HR panel (null-safe: clears)
  if (els.populationNote) {
    const fehNote = data.feh_snapped_far ? " (off-grid, snapped)" : "";
    const ageNote = data.age_snapped_far ? " (age off-grid)" : "";
    // When the HR-diagram cube is present, add the number-density lesson (the magenta cells)
    // and the measured stripped-star excess at this age — the HR-panel counterpart of the wedge.
    let hrdLine = "";
    if (hrd) {
      const rs = hrd.stripped_sin, rb = hrd.stripped_bin;
      const ratio = rs > 0 ? (rb / rs) : (rb > 0 ? Infinity : 0);
      const ratioTxt = ratio === Infinity ? "only binaries make them here"
        : ratio >= 2 ? `~${ratio < 10 ? ratio.toFixed(1) : Math.round(ratio)}× more with binaries`
        : "similar in both";
      hrdLine = ` On the HR diagram, magenta cells mark stars binaries populate that single-star ` +
        `evolution leaves empty (blue stragglers, stripped-He stars — ${ratioTxt}).`;
    }
    els.populationNote.textContent =
      `A coeval population at [Fe/H] ${data.feh_snapped.toFixed(2)}${fehNote}, ` +
      `age ${fmtPopAge(data.age_gyr_snapped)}${ageNote}: the magenta WEDGE marks where binaries ` +
      `exceed single-star only (dashed) — dominantly the UV/ionizing light they sustain ` +
      `(stripped hot stars). Scrub younger for the ionizing extreme, ~1 Gyr for the FUV.` +
      hrdLine +
      ` Per 10⁶ M☉; BPASS Z_⊙=0.020 (HR numbers v2.2.1, spectra v2.3).`;
  }
}

// Format a population age for the note (the Gyr grid spans 1 Myr–100 Gyr).
function fmtPopAge(gyr) {
  if (gyr < 0.001) return `${(gyr * 1e6).toPrecision(2)} kyr`;
  if (gyr < 1) return `${Math.round(gyr * 1000)} Myr`;
  return `${gyr.toPrecision(3)} Gyr`;
}

// --- isochrone / cluster overlay (MIST .iso — Axis B) ------------------------
// The transpose of the track: all masses at one age, a coeval-cluster locus on the HR panel,
// the main-sequence turnoff ringed (the age clock), the user's star sitting on it. Owns the HR
// panel while on (MIST track/marker hidden) like the He/α overlays, and mutually exclusive with
// them; not mass-gated (reads only the marker's age + [Fe/H]). Living-star only.
function updateIsochroneControl() {
  const c = els.isochroneControl;
  if (!c) return;
  const eligible = isoHasGrid && mode === "live";
  c.hidden = !eligible;
  if (!eligible) {
    if (isoOn) isochroneOff();   // mode changed under it → tear it down, restore the live HR
    return;
  }
  if (els.isochroneToggle) els.isochroneToggle.checked = isoOn;
  // B3: the decouple sub-control lives only while the overlay is on; coupled-by-default off it.
  if (isoOn) {
    if (els.isoDecoupleWrap) els.isoDecoupleWrap.hidden = false;
  } else {
    resetIsoDecouple();
    if (els.isochroneNote)
      els.isochroneNote.textContent =
        "See this star's age as a whole cluster — where the main-sequence turnoff dates it.";
  }
}

// B3: the single shared teardown for the decoupled cluster-age slider — back to coupled-by-default
// (the byte-compatible state) and the sub-control hidden. Called from every isochrone teardown path
// (updateIsochroneControl when off, dropIsochroneForModeSwitch, and the toggle-ON reset) so the
// decoupled age can never survive a teardown and re-fetch at a stale cluster age with the row hidden.
function resetIsoDecouple() {
  isoDecoupled = false;
  isoClusterLogAge = null;
  if (els.isoDecoupleToggle) els.isoDecoupleToggle.checked = false;
  if (els.isoClusterAgeRow) els.isoClusterAgeRow.hidden = true;
  if (els.isoDecoupleWrap) els.isoDecoupleWrap.hidden = true;
}

// Turn the overlay OFF: restore the live MIST HR track + marker, drop the caption.
function isochroneOff() {
  isoOn = false;
  isoToken++;                    // cancel any in-flight /isochrone apply
  isoNodeKey = ""; isoLastStates = null; isoLastTurnoff = null;
  if (els.isochroneToggle) els.isochroneToggle.checked = false;
  hr.clearIsochroneOverlay();
  if (currentTrack && currentTrack.length) hr.setTrack(currentTrack);
  refresh();                     // re-place the marker on the restored track
  updateIsochroneControl();      // reset the note text
}

// Drop the overlay when a non-live mode takes over (endgame/stripped/SN/binary), mirroring
// dropPopulationForModeSwitch — the entry path repaints the HR panel, so just clear state so a
// return to live never flashes a stale locus. Called from dropHeliumForModeSwitch (the hook).
function dropIsochroneForModeSwitch() {
  if (!isoOn) return;
  isoOn = false;
  isoToken++;
  isoNodeKey = ""; isoLastStates = null; isoLastTurnoff = null;
  if (els.isochroneToggle) els.isochroneToggle.checked = false;
  if (els.isochroneControl) els.isochroneControl.hidden = true;
  resetIsoDecouple();            // B3: never leave a stale decoupled cluster age behind a mode swap
}

// Fetch + push the cluster isochrone for the marker's (age, [Fe/H], vvcrit). Called from
// paintState. Buckets by the snapped node so a same-node age-scrub skips the refetch — but
// STILL repaints (the marker moved even if the locus didn't; unlike the population cloud the
// marker here is drawn INSIDE the overlay, so a skipped repaint would freeze it). Latest-wins.
async function refreshIsochrone(s) {
  if (!isoOn || mode !== "live" || !s) return;
  const feh = s.feh_init ?? 0;
  // B3: when decoupled the cluster ages on its own clock (isoClusterLogAge); otherwise it
  // tracks the star's age. Only the AGE is decoupled — [Fe/H] stays the star's (age is the clock).
  const ageYr = isoDecoupled && isoClusterLogAge != null
    ? 10 ** isoClusterLogAge : (s.age_yr ?? 0);
  if (!(ageYr > 0)) return;
  const vvcrit = effVvcrit();
  // Bucket finer than the iso grid (feh nodes ≥0.25 dex apart, age nodes ~0.05 dex in log10).
  const key = `${(Math.round(feh / 0.1) * 0.1).toFixed(1)}|` +
    `${(Math.round(Math.log10(ageYr) / 0.025) * 0.025).toFixed(3)}|${vvcrit}`;
  if (key === isoNodeKey && isoLastStates) {
    hr.setIsochroneOverlay(isoLastStates, isoLastTurnoff, s);  // same locus, moved marker
    return;
  }
  const token = ++isoToken;
  let data;
  try {
    data = await fetchJSON(`/isochrone?age_yr=${ageYr}&feh=${feh}&vvcrit=${vvcrit}`);
  } catch (e) {
    if (token !== isoToken || !isoOn) return;
    isoNodeKey = "";
    isochroneOff();
    if (els.isochroneNote) els.isochroneNote.textContent = "Isochrone grid unavailable (not fetched).";
    return;
  }
  if (token !== isoToken || !isoOn || mode !== "live") return;
  isoNodeKey = key;
  isoLastStates = data.states; isoLastTurnoff = data.turnoff;
  if (Array.isArray(data.available_log_ages) && data.available_log_ages.length)
    isoLogAges = data.available_log_ages;   // B3: grid-exact slider bounds
  hr.setIsochroneOverlay(data.states, data.turnoff, s);
  if (els.isochroneNote) {
    const t = data.turnoff;
    const fehNote = data.feh_snapped_far ? " (off-grid, snapped)" : "";
    const ageNote = data.age_snapped_far ? " (age off-grid)" : "";
    // Only the non-rotating iso grid is baked — a rotating star (vvcrit=0.4) snaps to it. Surface
    // that so the cluster's rotation isn't silently mismatched with the star's (advisor catch).
    const rotNote = data.vvcrit_snapped_far
      ? ` The cluster is shown non-rotating (v/v_crit ${data.vvcrit}) though this star rotates.` : "";
    const toTxt = t
      ? `The turnoff (ring) is at ${Math.round(t.Teff_K).toLocaleString()} K, ` +
        `${t.L_lsun < 100 ? t.L_lsun.toPrecision(2) : Math.round(t.L_lsun)} L☉ ` +
        `(${t.mass_msun.toFixed(2)} M☉ leaving the main sequence now).`
      : "";
    // B3: branch the closing clause — "scrub the age to age the cluster" is FALSE once decoupled
    // (the star's age slider no longer moves the cluster), and the marker now sits off the locus.
    const closing = isoDecoupled
      ? `Your star sits at its own age ${fmtPopAge((s.age_yr ?? 0) / 1e9)}, so its marker lies ` +
        `OFF this cluster's locus — that gap is the age comparison: date a cluster by the ` +
        `isochrone whose turnoff matches it. Drag the cluster-age slider to march the turnoff ` +
        `down the main sequence.`
      : `Scrub the age to age the cluster: the turnoff marches down the main sequence — ` +
        `that luminosity is how clusters are dated.`;
    els.isochroneNote.textContent =
      `A coeval cluster at [Fe/H] ${data.feh.toFixed(2)}${fehNote}, ` +
      `age ${fmtPopAge(data.age_yr / 1e9)}${ageNote} — all masses at once, your star one point on it. ` +
      `${toTxt} ${closing}${rotNote}`;
  }
}

// --- α-enhanced (equivalent-Z) what-if overlay (Phase 3) ---------------------
// The same LIGHT HR overlay as the initial-helium one, MUTUALLY EXCLUSIVE with it — only one
// MESA baseline-vs-enhanced pair owns the HR panel at a time (they share the hr.js overlay slot,
// hence alphaOff also calls hr.clearHeliumOverlay). [α/Fe] raises the true total metallicity Z at
// fixed [Fe/H] (Salaris 1993 equivalent-Z), so the enhanced track is cooler/fainter/longer-lived
// — the opposite sign from the He effect. The honesty lesson, owned by the caption: the TRACK
// sees only total Z; α's own signature is spectroscopic (the already-shipped Coelho spectrum toggle).
function updateAlphaControl() {
  const c = els.alphaControl;
  if (!c) return;
  const feh = Number(els.feh.value);
  const inRegime = mode === "live"
    && massValue >= ALPHA_MASS_MIN && massValue <= ALPHA_MASS_MAX
    && Math.abs(feh) <= ALPHA_FEH_TOL;
  // Tear down first if the star drifted out of range with the overlay up (mirrors helium).
  if (!(alphaHasGrid && inRegime) && alphaOn) { alphaOff(); return; }
  // data-absent → HIDE; in-regime → live; out of regime → greyed placeholder. activeNote null:
  // refreshAlpha owns the on-caption (the Coelho-paired "track sees only total Z" lesson).
  reserveWhatIf(els.alphaControl, els.alphaToggle, els.alphaNote, {
    dataPresent: alphaHasGrid, eligible: inRegime, checked: alphaOn, activeNote: null,
    offerNote: "What if this star were α-enhanced? (an old-population [α/Fe] what-if, track-level)",
    gatedNote: `Appears near solar [Fe/H] for ${ALPHA_MASS_MIN}–${ALPHA_MASS_MAX} M☉ (the self-run MESA grid).`,
  });
}

// Turn the α overlay OFF: restore the live MIST HR track + marker, drop the overlay note.
function alphaOff() {
  alphaOn = false;
  alphaToken++;                  // cancel any in-flight /alpha apply
  if (els.alphaToggle) els.alphaToggle.checked = false;
  hr.clearHeliumOverlay();       // the shared MESA-overlay slot
  if (currentTrack && currentTrack.length) hr.setTrack(currentTrack);
  refresh();                     // re-place the marker on the restored track
  updateAlphaControl();          // reset the note text
}

// Turn ON (or re-fetch after a mass change): fetch the baseline+enhanced (equivalent-Z) MESA pair
// and hand both to the shared HR overlay slot. Latest-wins guarded. The caption carries the whole
// Gate-3 story AND the honesty framing: the effect is a pure total-Z shift (Salaris), with τ_MS
// (LONGER here — no HR axis) surfaced explicitly, and a pointer to the spectrum α-toggle for α's
// own (spectroscopic) fingerprint.
async function refreshAlpha() {
  if (!alphaOn) return;
  const token = ++alphaToken;
  const mass = massValue;
  let data;
  try {
    data = await fetchJSON(`/alpha?mass=${mass}`);
  } catch (e) {
    if (token !== alphaToken || !alphaOn) return;
    alphaOff();                  // don't leave alphaOn stuck (it guards the live HR calls off)
    if (els.alphaNote) els.alphaNote.textContent = "α-enhanced tracks unavailable (no MESA data).";
    return;
  }
  if (token !== alphaToken || !alphaOn || mode !== "live") return;
  const b = data.baseline, en = data.enhanced;
  // On-plot ZAMS labels show the equivalent [M/H] — the axis the TRACK actually sees (the lesson).
  hr.setHeliumOverlay(b.states, en.states, {
    labels: { enh: `α-enhanced  [M/H] ${fmtMH(en.mh)}`, base: `baseline  [M/H] ${fmtMH(b.mh)}` },
  });
  if (els.alphaNote) {
    const ratio = en.tau_ms_gyr / b.tau_ms_gyr;
    const snap = data.mass_snapped_far ? ` · snapped to ${fmt(data.mass_snapped)} M☉` : "";
    els.alphaNote.textContent =
      `[α/Fe] +${data.alpha_fe.toFixed(1)} raises the true metallicity to [M/H] ${fmtMH(en.mh)} ` +
      `(Salaris 1993 equivalent-Z), same mass (self-run MESA). Cooler + fainter, and longer-lived: ` +
      `τ_MS ${fmtGyr(en.tau_ms_gyr)} vs. ${fmtGyr(b.tau_ms_gyr)} (${ratio.toFixed(1)}× longer). ` +
      `The track sees only the total Z — α's own signature is spectroscopic (see the spectrum α-toggle)${snap}.`;
  }
}

// Signed [M/H] for the caption/labels: "+0.29" / "0.00" / "-0.10".
function fmtMH(mh) { return (mh >= 0 ? "+" : "") + mh.toFixed(2); }

// Drop the α overlay STATE when another view takes over the HR panel (see dropHeliumForModeSwitch).
function dropAlphaForModeSwitch() {
  if (!alphaOn) return;
  alphaOn = false;
  alphaToken++;
  if (els.alphaToggle) els.alphaToggle.checked = false;
  if (els.alphaControl) els.alphaControl.hidden = true;
}

// Fetch the computed stripped model for the current (mass, [Fe/H]). No vvcrit — the stripped
// grid is single-star-progenitor-parameterized only. When "Show companion" is on (path (b))
// this hits /binary_pair, whose payload is a strict superset of /binary (same top-level donor
// fields + a `companion` block); otherwise /binary (donor only). Throws on a network/HTTP error.
async function fetchStripped() {
  const mass = massValue, feh = Number(els.feh.value);
  const route = companionOn ? "binary_pair" : "binary";
  return fetchJSON(`/${route}?mass=${mass}&feh=${feh}`);
}

// Apply a freshly-fetched stripped model to the panels (shared by enter + re-snap). The HR
// keeps the progenitor's LIVING track as faint context and drops the marker blue-left of it
// (reuse setEndgame's auto-fit over [strippedState] + the living track so neither clips); the
// comp panel shows the single-state SURFACE view; the spectrum is the star's REAL CMFGEN
// spectrum (Chunk 3) — the /stripped_spectrum cube keyed on the SAME (Z, M_init) node
// /binary snapped, so it's guaranteed the same star as the marker (absorption at the
// subdwarf end → He II 4686 emission at the He-star end). Then paint the current state.
function applyStrippedModel(data) {
  strippedData = data;
  const s = data.state;
  hr.setEndgame([s], "stripped");   // faint living context + fitted axes (single point, no line)
  // path (b): the companion (accretor) as a second HR marker, when "Show companion" is on and
  // the payload carried one (/binary_pair). setCompanion re-fits the axes to enclose it (at low
  // mass it outshines the sub-luminous donor and would otherwise clip the top).
  hr.setCompanion(companionOn && data.companion ? data.companion.state : null);
  comp.setStripped(s);
  spectrum.updateStripped(s);       // real stripped-star spectrum (replaces the Chunk-2 placeholder)
  // path (b) Chunk 3: the mass-transfer / Roche-lobe panel — the CAUSAL two-star render.
  // Shown only with the companion reveal on (it is inherently a two-star view); the body
  // class CSS-reveals its panel, and roche.draw fits its (previously hidden) canvas.
  const showRoche = companionOn && data.roche && data.companion;
  document.body.classList.toggle("companion-on", !!showRoche);
  if (showRoche) roche.draw(data.roche, data.companion.state);
  else roche.clear();
  refreshStripped();
}

// Paint the stripped star. UNLIKE the wd/wr/sn scrubbers there is nothing to scrub (one
// representative state), so this is a one-shot paint (re-run only on a mass/[Fe/H] re-snap).
// The spectrum is set once in applyStrippedModel (the real /stripped_spectrum cube, Chunk 3),
// not per-frame — there's nothing to scrub. Structure is still deliberately NOT called (it
// would fetch a normal ZAMS profile for the progenitor mass; keeps its last profile like the
// wd/wr/sn modes), and comp's burning-abundance views are skipped (no measured core; the
// surface view is set separately).
function refreshStripped() {
  if (!strippedData) return;
  const s = strippedData.state;
  const mStrip = strippedData.m_strip_msun;
  // path (b) Chunk 2: with "Show companion" on, draw the accretor as a REAL second sphere
  // beside the stripped donor (star.js lays them side by side, fit-to-frame). The companion
  // is a modeled single-star state, so the sphere is honest; the placement is schematic (no
  // orbit is modeled — the caption owns that). Off ⇒ no opts ⇒ the lone stripped star.
  const cState = companionOn && strippedData.companion ? strippedData.companion.state : null;
  star.update(s, cState ? { companion: cState } : undefined);
  classification.update(s, "stripped", { mStrip });
  scale.update(s);                                // radius-based true-size bar (honest)
  hr.update(s);                                   // the marker, blue-left of the living track
  // comp: static SURFACE view (set by comp.setStripped) — no per-frame redraw
  sed.update(s);                                  // blackbody only (mdot=None → no wind tail; hot → no corona)
  // spectrum/structure: intentionally NOT called (see the header note)
  renderStrippedReadout(s, strippedData);

  els.status.style.color = teffToCSS(s.Teff_K);
  els.status.innerHTML =
    tipSpan("stripped what-if",
      "A binary-stripped-star what-if (Götberg 2018): the hot stripped star a close companion " +
      "would bare by stripping the hydrogen envelope. Snapped to the nearest grid model (never " +
      "interpolated). Untick ‘Stripped in a binary’, or ‘Back to the living star’, to leave.") +
    " · " + tipSpan("stripped-envelope star", phaseTip("stripped-envelope star")) +
    (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");

  // The age caption owns the counterfactual + any snapped-far honesty. The "hot helium" phrasing
  // only holds where the surface is actually He-rich (the high-mass end); the low-mass end keeps
  // a thin H envelope (an sdB-like subdwarf), so the wording follows the real surface X vs Y.
  const heRich = (s.Y_surf ?? 0) > (s.X_surf ?? 0);
  const core = heRich ? "hot helium bared" : "hot stripped core (a thin-H subdwarf)";
  let cap =
    `Stripped in a close binary — ${fmt(mStrip)} M☉ of ${core} from a ` +
    `${fmt(strippedData.m_init_msun)} M☉ progenitor (one representative state, halfway ` +
    `through core-helium burning). `;
  // path (b): with the companion drawn, narrate the Algol mass-ratio reversal off the served
  // scalars; otherwise the path (a) framing (companion named, not drawn).
  const cpn = companionOn ? strippedData.companion : null;
  if (cpn) {
    cap +=
      `Its companion (the accretor, drawn beside the donor in 3D and on the HR) started at ` +
      `${fmt(cpn.mass_msun)} M☉ — 0.8× the donor — and is now the HEAVIER star: the Algol ` +
      `mass-ratio reversal (donor ${fmt(mStrip)} < companion ${fmt(cpn.mass_msun)} M☉). It is a ` +
      `~${Math.round(cpn.state.Teff_K / 1000)} kK main-sequence star, still burning hydrogen. ` +
      `Each star is a real modeled star, but their side-by-side placement is schematic — the ` +
      `separation and orbit are not modeled.`;
  } else {
    cap += `The companion is named, not drawn — tick “Show companion” to add it.`;
  }
  if (strippedData.mass_snapped_far || strippedData.feh_snapped_far) {
    const bits = [];
    if (strippedData.mass_snapped_far)
      bits.push(`no grid model at this mass — nearest progenitor ${fmt(strippedData.m_init_msun)} M☉ ` +
        `(grid ${fmt(strippedData.mass_grid_min)}–${fmt(strippedData.mass_grid_max)} M☉)`);
    if (strippedData.feh_snapped_far)
      bits.push(`nearest grid [Fe/H] ${fmt(strippedData.feh_snapped, 2)}`);
    cap += ` Snapped: ${bits.join("; ")}.`;
  }
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = cap;
}

// The stripped-star readout — the CURRENT (stripped) mass + the progenitor it came from, plus
// the measured surface (hydrogen-poor, helium-rich). The current mass `m_strip` is a routing
// scalar with no home on the single-star state, so it's threaded from strippedData (not s).
function renderStrippedReadout(s, d) {
  // The He-richness is the HIGH-mass end; the low-mass end keeps a thin H envelope (sdB-like),
  // so the class + surface framing follow the real X vs Y, never a hardcoded "helium".
  const heRich = (s.Y_surf ?? 0) > (s.X_surf ?? 0);
  const cls = !heRich ? "hot subdwarf (sdB/O)"
    : d.m_strip_msun < 1.5 ? "helium subdwarf (sdO)" : "helium star";
  const rows = [
    ["Stripped mass",
      "the stripped star's CURRENT mass, in Suns — the bared helium core after the companion removed the envelope (far less than the progenitor's initial mass)",
      `${fmt(d.m_strip_msun)} M☉`],
    ["Progenitor",
      "the initial main-sequence mass this star was BEFORE stripping (snapped to the nearest grid model — never interpolated)",
      `${fmt(d.m_init_msun)} M☉`],
    ["[Fe/H]",
      "metallicity of the model (snapped to the nearest grid value; the grid is solar-only for now, so a far snap is flagged in the caption)",
      fmt(s.feh_init, 2)],
    ["Class",
      "a hot stripped star — a thin-H-envelope subdwarf (sdB/sdO) at the low-mass end, grading into a helium-surfaced He-star / proto-Wolf–Rayet at high mass (the unified stripped-envelope sequence)",
      cls],
    ["L",
      "luminosity in Suns — a stripped star is sub-luminous FOR ITS TEMPERATURE (it sits blue-left of the single-star main sequence)",
      `${fmt(s.L_lsun)} L☉`],
    ["Teff",
      "effective temperature — tens of thousands of kelvin; the cool envelope that hid the core is gone (this is the spectroscopic Teff, not the inner T★)",
      `${fmt(s.Teff_K, 4)} K`],
    ["R",
      "radius in solar radii — small and compact, the bared core",
      `${fmt(s.R_rsun)} R☉`],
    ["log g",
      "surface gravity, log₁₀ cgs — high, between a main-sequence star and a white dwarf",
      fmt(s.logg, 3)],
    ["X / Y / Z surface",
      "surface mass fractions: hydrogen (X) / helium (Y) / metals (Z) — the measured headline. It runs the whole stripped sequence: hydrogen-rich (a thin envelope survives) at the low-mass subdwarf end, hydrogen-poor and helium-rich (the bared core) at higher mass",
      `${fmt(s.X_surf)} / ${fmt(s.Y_surf)} / ${fmt(s.Z_surf, 2)}`],
  ];
  // path (b): with "Show companion" on, add the accretor + the mass-ratio reversal (the payoff).
  if (companionOn && d.companion) {
    const cpn = d.companion, cs = cpn.state;
    rows.push(
      ["Companion",
        "the un-stripped companion (the accretor) — an ordinary main-sequence star produced by the single-star model at its known initial mass (0.8× the donor, the grid's fixed mass ratio), observed at the elapsed system age. Drawn as the second marker on the HR diagram",
        `${fmt(cpn.mass_msun)} M☉ · ${fmt(cs.Teff_K, 4)} K`],
      ["Mass ratio (now)",
        "companion mass ÷ stripped-donor mass. It starts at 0.8 (the companion is the lighter star); after stripping it rises above 1 — the Algol mass-ratio REVERSAL, the once-lighter companion is now the heavier one",
        fmt(cpn.mass_ratio_final, 2)],
    );
  }
  els.readout.innerHTML = rows
    .map(([k, dsc, v]) =>
      `<div class="row"><div class="term">${k} ${help(dsc)}</div>` +
      `<div class="v">${v}</div></div>`)
    .join("");
}

// Enter the reversible binary-stripped what-if from the toggle. Mirrors enterSN (it FETCHES a
// sibling route on entry, with a loading caption + latest-wins guard), but the entry is a
// mid-life toggle, not an end-of-life gateway. The shared endgame bar carries the "Back".
async function enterStripped() {
  dropHeliumForModeSwitch();
  mode = "stripped";
  updateRotControl();       // hide the rotation control inside the mode (mode != live)
  updatePeculiarControl();
  updateStrippedControl();  // hides the fork button in stripped-mode (exit is the Back bar)
  trackToken++;             // invalidate any in-flight live /track
  document.body.classList.add("stripped-mode");
  companionOn = false;      // path (a) by default — the companion is revealed by the toggle
  if (els.companionToggle) els.companionToggle.checked = false;
  binaryView = false; binaryTrackData = null; binaryStar1 = null; binaryStar2 = null;
  binaryDemoKey = null; binaryToken++;   // path (b) Chunk 4b — always land on the snapshot first
  document.body.classList.remove("binary-view");
  if (els.binaryCustomControls) els.binaryCustomControls.hidden = true;
  if (els.binaryFehNote) els.binaryFehNote.textContent = "";
  coBinaryView = false; coBinaryTrackData = null; coBinaryStar = null; coBinaryToken++;
  document.body.classList.remove("co-binary-view");   // Chunk 1b — snapshot first here too
  document.body.classList.remove("co-he-kind");
  if (els.coBinaryDcoNote) els.coBinaryDcoNote.textContent = "";
  if (els.coBinaryDemoBack) els.coBinaryDemoBack.hidden = true;
  updateBinaryDemoButtons();
  ensureBinaryMeta();   // pre-warm the [Fe/H] bucket list (populates the select) + the
                         // current bucket's M1/q/P bounds, so "Co-evolve" is instant on click
  ensureCoBinaryMeta(); // same for the CO-HMS_RLO [Fe/H] picker (Chunk 1c) — populates its
                         // select + M_star/M_co/P bounds so its custom system is instant too
  if (els.pulseToggle) els.pulseToggle.hidden = true;   // the pulse toggle is WD-only
  lastEgMass = massValue; lastEgFeh = Number(els.feh.value);
  setWDResnapNote("");
  els.gateway.hidden = true;
  els.endgameBar.hidden = false;
  els.snControl.hidden = true;
  els.age.disabled = true;   // one representative state — nothing to scrub
  els.endgameAgeCaption.textContent = "Fetching the stripped-star model…";
  const tok = ++strippedToken;
  let data;
  try { data = await fetchStripped(); }
  catch {
    if (tok === strippedToken && mode === "stripped")
      els.endgameAgeCaption.textContent = "Could not fetch the stripped-star model.";
    return;
  }
  if (tok !== strippedToken || mode !== "stripped") return;
  applyStrippedModel(data);
}

// Re-snap the stripped star after a mass/[Fe/H] change inside the mode (mirrors trySNResnap).
// UNLIKE the wd/wr/sn re-snaps there is no fate to revert on: /binary is snap-always, so a drag
// past the grid edges snaps to the nearest node and shows an in-band snapped-far note (owned by
// refreshStripped's caption) rather than reverting — the honest read of the Chunk-1 flags.
async function tryStrippedResnap() {
  if (mode !== "stripped") return;
  const tok = ++strippedToken;
  let data;
  try { data = await fetchStripped(); } catch { return; }
  if (tok !== strippedToken || mode !== "stripped") return;
  lastEgMass = massValue; lastEgFeh = Number(els.feh.value);
  applyStrippedModel(data);
}

// --- path (b) Chunk 4b: the co-evolving POSYDON binary ------------------------

// slider fraction (0..1) -> step index (plain index-linear — every real POSYDON row gets
// equal travel, mirroring the WR sub-track idiom: no piecewise compression, no snapping,
// since the whole point of scrubbing this movie is that every in-between frame is real).
function binaryIndexFromFraction(frac) {
  if (!binaryStar1 || !binaryStar1.length) return 0;
  return Math.max(0, Math.min(binaryStar1.length - 1, Math.round(clamp01(frac) * (binaryStar1.length - 1))));
}

// Landmark ticks: the endpoints, plus the first step flagged as actively transferring (if
// any — the merger/wide demos may have none), mirroring the WR scrub's wc/last idiom.
function rebuildBinaryTicks() {
  if (!binaryTrackData) return;
  const steps = binaryTrackData.steps;
  const n = steps.length;
  const marks = [{ pos01: 0, label: "start" }, { pos01: 1, label: "end" }];
  const mtStart = steps.findIndex((s) => s.mt_state !== "detached");
  if (mtStart > 0 && mtStart < n - 1) marks.push({ pos01: mtStart / (n - 1), label: "mass transfer begins" });
  buildTickStrip(els.ageMarks, marks);
  els.ageTicks.innerHTML = "";
}

function updateBinaryDemoButtons() {
  document.querySelectorAll(".binary-demo-btn").forEach((btn) => {
    btn.classList.toggle("active", binaryView && btn.dataset.demo === binaryDemoKey);
  });
}

// Pull a fresh /binary_track payload into the shared draw state (HR + ticks + the
// snapped-node note) — shared by a fresh entry (enterBinaryView) and a live re-fetch while
// scrubbing a custom orbit or switching [Fe/H] (refetchBinaryTrack); the caller owns
// binaryFraction/refreshBinary.
function _applyBinaryTrackData(data) {
  binaryTrackData = data;
  binaryStar1 = data.steps.map((s) => s.star_1);
  binaryStar2 = data.steps.map((s) => s.star_2);
  hr.setBinaryTrack(binaryStar1, binaryStar2);
  rebuildBinaryTicks();
  updateBinaryCustomNote();
  updateBinaryFehNote();
}

// Resolve the (m1,q,p) triple for a demo key — the curated table for the three fixed
// demos, or the free sliders for "custom". [Fe/H] is NOT part of this: it's the
// orthogonal `customFeh` selector, applied by the caller (mirrors the MIST mass/[Fe/H] split).
function _binaryParamsFor(demoKey) {
  if (demoKey === "custom") return { m1: customM1, q: customQ, p: customP };
  const demo = BINARY_DEMOS.find((d) => d.key === demoKey);
  return demo ? { m1: demo.m1, q: demo.q, p: demo.p } : null;
}

// Enter the co-evolving movie for a curated demo system OR the free "custom" orbit (mode
// stays "stripped" — this is a sub-view, like the WD thermal-pulse showcase). Fetches
// /binary_track once; the age slider then becomes a free system-time scrubber over the
// pre-fetched steps (no per-frame fetch, the same "scrub is free" idiom as the living
// track / WD / WR scrubs).
async function enterBinaryView(demoKey) {
  if (mode !== "stripped") return;
  // Mutually exclusive with the CO-HMS_RLO movie. Bump coBinaryToken UNCONDITIONALLY (not
  // only when coBinaryView is already true) — a CO track fetch may be IN FLIGHT (its view
  // class not set yet, so its demo button was still clickable), and a late-resolving CO
  // fetch must not re-open co-binary-view on top of this one.
  coBinaryToken++;
  if (coBinaryView) exitCoBinaryView();
  if (demoKey === "custom") {
    await ensureBinaryMeta();
    if (!binaryMeta) return;   // meta fetch failed — bail quietly, the /binary_track_meta 503 case
  }
  const params = _binaryParamsFor(demoKey);
  if (!params) return;
  const { m1, q, p } = params;
  const tok = ++binaryToken;
  binaryDemoKey = demoKey;
  updateBinaryDemoButtons();
  els.age.disabled = true;   // re-enabled once the track lands; disabled meanwhile (fetching)
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = "Fetching the co-evolved binary track…";
  let data;
  try { data = await fetchJSON(`/binary_track?m1=${m1}&q=${q}&p=${p}&feh=${customFeh}`); }
  catch {
    if (tok === binaryToken && mode === "stripped")
      els.endgameAgeCaption.textContent = "Could not fetch the co-evolved binary track.";
    return;
  }
  if (tok !== binaryToken || mode !== "stripped") return;
  _applyBinaryTrackData(data);
  binaryView = true;
  document.body.classList.add("binary-view");
  // Reveal the custom sliders only once binaryView is actually true (not before the fetch
  // above resolves) — a drag while it's still "fetching…" would hit refetchBinaryTrack's
  // `!binaryView` guard and get silently dropped, since nothing else in this view becomes
  // interactive (the demo buttons, the Back button) until this same point either.
  if (els.binaryCustomControls) els.binaryCustomControls.hidden = demoKey !== "custom";
  els.age.disabled = false;
  // POSYDON's (M1, q, P) grid is independent of the MIST mass/[Fe/H] axes this demo isn't
  // keyed on — disable rather than silently ignore a drag (tryResnap() also guards this).
  els.mass.disabled = true; els.feh.disabled = true;
  if (els.massNum) els.massNum.disabled = true;
  if (els.fehNum) els.fehNum.disabled = true;
  updateBinaryDemoButtons();
  binaryFraction = 0;
  els.age.value = binaryFraction;
  refreshBinary();
}

// Leave the movie, back to the plain stripped snapshot (still mode === "stripped" — the
// donor + its one representative state, exactly as it was before "Co-evolve" was clicked).
function exitBinaryView() {
  binaryView = false;
  binaryToken++;   // invalidate any in-flight /binary_track — leaving the view for ANY reason
                    // (incl. enterCoBinaryView's mutual-exclusivity exit) must not let a slow
                    // fetch re-apply binary-view on top of the view we switched to.
  binaryTrackData = null; binaryStar1 = null; binaryStar2 = null; binaryDemoKey = null;
  document.body.classList.remove("binary-view");
  if (els.binaryCustomControls) els.binaryCustomControls.hidden = true;
  if (els.binaryFehNote) els.binaryFehNote.textContent = "";
  hr.clearBinaryTrack();
  roche.clear();
  els.age.disabled = true;
  els.mass.disabled = false; els.feh.disabled = false;
  if (els.massNum) els.massNum.disabled = false;
  if (els.fehNum) els.fehNum.disabled = false;
  updateBinaryDemoButtons();
  if (strippedData) { hr.setEndgame([strippedData.state], "stripped"); refreshStripped(); }
}

// Re-fetch the CURRENTLY active demo/custom track (debounced, latest-wins — the
// refetchSNMni idiom) — shared by a custom M1/q/P slider drag AND a [Fe/H] bucket change
// (the two are orthogonal: [Fe/H] applies to whichever system is showing, curated or
// custom, unlike M1/q/P which only ever apply to "custom"). Unlike a fresh
// enterBinaryView, this PRESERVES the current scrub position (binaryFraction is a 0..1
// fraction, re-indexed against whatever length the new track happens to have) rather
// than resetting to the start — a slider/selector change is "show me this other
// system," not "restart the movie."
async function refetchBinaryTrack() {
  if (mode !== "stripped" || !binaryView || !binaryDemoKey) return;
  const demoKey = binaryDemoKey;
  const params = _binaryParamsFor(demoKey);
  if (!params) return;
  const { m1, q, p } = params;
  const tok = ++binaryToken;
  let data;
  try { data = await fetchJSON(`/binary_track?m1=${m1}&q=${q}&p=${p}&feh=${customFeh}`); }
  catch { return; }
  if (tok !== binaryToken || mode !== "stripped" || !binaryView || binaryDemoKey !== demoKey) return;
  _applyBinaryTrackData(data);
  refreshBinary();
}

// Paint step `i` (picked from binaryFraction — no fetch, mirrors refreshWR). Both stars'
// real modelled states drive the HR markers, the 3D pair (star.js's existing companion
// layout, Chunk 2), and the Roche panel (now LIVE off this step's own q(t)/a(t) geometry,
// the Chunk-3 panel's payoff paying off twice) — donor/companion stay fixed left/right by
// IDENTITY throughout, the reversal is the crossing, never a relabel.
function refreshBinary() {
  if (!binaryView || !binaryTrackData) return;
  const i = binaryIndexFromFraction(binaryFraction);
  const step = binaryTrackData.steps[i];
  const s1 = binaryStar1[i];
  const s2 = binaryStar2[i];   // may be null after a merger (not observed on the current bake)

  hr.updateBinaryIndex(i);
  star.update(s1, s2 ? { companion: s2 } : undefined);
  if (step.roche) roche.drawLive(step.roche, s1, s2, step.mt_state);
  else roche.clear();

  if (els.endgameAgeCaption) {
    const yrs = step.age_yr >= 1e6 ? `${(step.age_yr / 1e6).toFixed(2)} Myr`
      : step.age_yr < 1 ? "<1 yr" : `${Math.round(step.age_yr)} yr`;
    const sepAU = (step.separation_rsun / 215.032).toFixed(2);
    els.endgameAgeCaption.textContent =
      `System age ${yrs} · period ${step.period_d.toFixed(2)} d · separation ${step.separation_rsun.toFixed(0)} R☉ ` +
      `(${sepAU} AU) · M₁ ${step.m1_current_msun.toFixed(2)} M☉, M₂ ${step.m2_current_msun.toFixed(2)} M☉ · ${step.mt_state}` +
      (i === binaryStar1.length - 1 ? ` · outcome: ${binaryTrackData.outcome}` : "") +
      (s2 ? "" : " · the companion is lost past this point (a merger row)");
  }
}

// --- CO-HMS_RLO co-evolving view (CE/compact-object tail Chunk 1b) ------------------------
// A parallel, minimal sibling to enterBinaryView/refreshBinary. Kept SEPARATE (not an
// overloaded refreshBinary) because the step shape differs: one real star + a point-mass
// compact object (no star_2 StellarState), so the HR gets only ONE marker and the 3D/Roche
// panels draw a schematic CO glyph, never a second photosphere.
function coBinaryIndexFromFraction(frac) {
  if (!coBinaryStar || !coBinaryStar.length) return 0;
  return Math.max(0, Math.min(coBinaryStar.length - 1, Math.round(clamp01(frac) * (coBinaryStar.length - 1))));
}

function rebuildCoBinaryTicks() {
  if (!coBinaryTrackData) return;
  const steps = coBinaryTrackData.steps;
  const n = steps.length;
  const marks = [{ pos01: 0, label: "start" }, { pos01: 1, label: "end" }];
  const mtStart = steps.findIndex((s) => s.mt_state !== "detached");
  if (mtStart > 0 && mtStart < n - 1) marks.push({ pos01: mtStart / (n - 1), label: "accretion begins" });
  buildTickStrip(els.ageMarks, marks);
  els.ageTicks.innerHTML = "";
}

// Apply a fetched /co_binary_track payload to the CO view's consumers (HR, ticks, notes) —
// shared by a fresh entry (enterCoBinaryView) and a live re-fetch while scrubbing a custom
// system or switching [Fe/H] (refetchCoBinaryTrack); the caller owns coBinaryFraction/
// refreshCoBinary. The _applyBinaryTrackData twin.
function _applyCoBinaryTrackData(data) {
  coBinaryTrackData = data;
  coBinaryStar = data.steps.map((s) => s.star);
  // Only the living star goes on the HR diagram — the compact object has no photosphere, so
  // NO second marker (star2States = null); label the one marker "star" (not "donor").
  hr.setBinaryTrack(coBinaryStar, null, { s1: "star" });
  // Drive the He-kind body class + narration/comp swap off the SERVED kind (authoritative),
  // not the selector — so they can never desync from the track actually being shown.
  document.body.classList.toggle("co-he-kind", isHeKind(data.kind));
  updateCoBinaryDcoNote();
  rebuildCoBinaryTicks();
  updateCoBinaryCustomNote();
  updateCoBinaryFehNote();
}

// The double-compact-object endpoint line (He kinds only). Prints the classifier's OWN served
// one-liner verbatim (data.dco.label) — it resolves BH+BH/NS+BH/NS+NS/no-merger/unresolved, so
// it can't drift from the backend. Cleared for co-hms-rlo (data.dco is null there).
function updateCoBinaryDcoNote() {
  if (!els.coBinaryDcoNote) return;
  const dco = coBinaryTrackData && coBinaryTrackData.dco;
  if (!dco) { els.coBinaryDcoNote.textContent = ""; return; }
  // Prescription labeled by index (POSYDON ships 24 core-collapse models; index→mechanism
  // isn't verifiable from the grid file — the boron-b8 discipline), with a friendlier gloss.
  const presc = String(dco.sn_model).replace(/^S1_SN_MODEL_/, "");
  els.coBinaryDcoNote.textContent = `Endpoint: ${dco.label} (POSYDON core-collapse prescription ${presc}).`;
}

// Sync the demo-button label + the demo-row `?` tooltip to the selected grid kind. The HTML
// defaults describe co-hms-rlo (H-rich) only — for a He kind that text would MISDESCRIBE the
// system (a false-data-in-caption leak), so JS is the single source of truth per kind.
function applyCoKindUi() {
  const ui = CO_KIND_UI[coKind];
  if (!ui) return;
  if (els.coBinaryDemoXrb) els.coBinaryDemoXrb.textContent = ui.demoLabel;
  if (els.coBinaryHelp) els.coBinaryHelp.dataset.tip = ui.tip;
}

// Resolve the (m_star, m_co, p) triple for a CO demo key — the curated Gate-1 system, or the
// free sliders for "custom". [Fe/H] is NOT part of this: it's the orthogonal coCustomFeh
// selector, applied by the caller (the _binaryParamsFor twin).
function _coBinaryParamsFor(demoKey) {
  if (demoKey === "custom") return { m_star: coCustomMstar, m_co: coCustomMco, p: coCustomP };
  const d = CO_BINARY_DEMOS[coKind];   // the curated demo follows the selected grid kind
  return { m_star: d.m_star, m_co: d.m_co, p: d.p };
}

// Enter the CO-HMS_RLO movie (mode stays "stripped" — a sub-view, like the HMS-HMS one) for
// the curated "xrb" system OR the free "custom" one. Mutually exclusive with the HMS-HMS
// binary view: entering here exits that one first.
async function enterCoBinaryView(demoKey) {
  if (mode !== "stripped") return;
  // Mutually exclusive with the HMS-HMS movie. Bump binaryToken UNCONDITIONALLY (the
  // symmetric guard to enterBinaryView) — a /binary_track fetch may be IN FLIGHT with its
  // view class not yet set, so exitBinaryView() alone (which only runs if binaryView is
  // already true) would miss it and let it re-open binary-view over this one.
  binaryToken++;
  if (binaryView) exitBinaryView();
  if (demoKey === "custom") {
    await ensureCoBinaryMeta();
    if (!coBinaryMeta) return;   // meta fetch failed — bail quietly (the 503 case)
  }
  const { m_star, m_co, p } = _coBinaryParamsFor(demoKey);
  const tok = ++coBinaryToken;
  coBinaryDemoKey = demoKey;
  els.age.disabled = true;
  if (els.endgameAgeCaption) els.endgameAgeCaption.textContent = "Fetching the compact-object binary track…";
  let data;
  try {
    data = await fetchJSON(
      `/co_binary_track?m_star=${m_star}&m_co=${m_co}&p=${p}&feh=${coCustomFeh}&kind=${coKind}`);
  } catch {
    if (tok === coBinaryToken && mode === "stripped")
      els.endgameAgeCaption.textContent = "Could not fetch the compact-object binary track.";
    return;
  }
  if (tok !== coBinaryToken || mode !== "stripped") return;
  _applyCoBinaryTrackData(data);
  coBinaryView = true;
  document.body.classList.add("co-binary-view");
  // Reveal the custom sliders only once coBinaryView is actually true (not before the fetch
  // resolves) — a drag while it's still "fetching…" would hit refetchCoBinaryTrack's
  // !coBinaryView guard and get silently dropped (the exact Chunk-4c bug the Playwright
  // pass caught for HMS-HMS).
  if (els.coBinaryCustomControls) els.coBinaryCustomControls.hidden = demoKey !== "custom";
  if (els.coBinaryDemoBack) els.coBinaryDemoBack.hidden = false;
  els.age.disabled = false;
  els.mass.disabled = true; els.feh.disabled = true;    // POSYDON's grid, not the MIST axes
  if (els.massNum) els.massNum.disabled = true;
  if (els.fehNum) els.fehNum.disabled = true;
  coBinaryFraction = 0;
  els.age.value = coBinaryFraction;
  refreshCoBinary();
}

function exitCoBinaryView() {
  coBinaryView = false;
  coBinaryTrackData = null; coBinaryStar = null; coBinaryDemoKey = null;
  coBinaryToken++;
  document.body.classList.remove("co-binary-view");
  document.body.classList.remove("co-he-kind");
  if (els.coBinaryCustomControls) els.coBinaryCustomControls.hidden = true;
  if (els.coBinaryFehNote) els.coBinaryFehNote.textContent = "";
  if (els.coBinaryDcoNote) els.coBinaryDcoNote.textContent = "";
  if (els.coBinaryDemoBack) els.coBinaryDemoBack.hidden = true;
  hr.clearBinaryTrack();
  roche.clear();
  els.age.disabled = true;
  els.mass.disabled = false; els.feh.disabled = false;
  if (els.massNum) els.massNum.disabled = false;
  if (els.fehNum) els.fehNum.disabled = false;
  if (strippedData) { hr.setEndgame([strippedData.state], "stripped"); refreshStripped(); }
}

// Re-fetch the CURRENTLY active CO demo/custom track (debounced, latest-wins) — shared by a
// custom M_star/M_co/P slider drag AND a [Fe/H] bucket change (orthogonal: [Fe/H] applies to
// whichever system is showing, curated or custom, unlike M_star/M_co/P which only ever drive
// "custom"). PRESERVES the current scrub position (coBinaryFraction is a 0..1 fraction,
// re-indexed against the new track's length) — a change is "show me this other system," not
// "restart the movie." The refetchBinaryTrack twin.
async function refetchCoBinaryTrack() {
  if (mode !== "stripped" || !coBinaryView || !coBinaryDemoKey) return;
  const demoKey = coBinaryDemoKey;
  const { m_star, m_co, p } = _coBinaryParamsFor(demoKey);
  const tok = ++coBinaryToken;
  let data;
  try { data = await fetchJSON(`/co_binary_track?m_star=${m_star}&m_co=${m_co}&p=${p}&feh=${coCustomFeh}&kind=${coKind}`); }
  catch { return; }
  if (tok !== coBinaryToken || mode !== "stripped" || !coBinaryView || coBinaryDemoKey !== demoKey) return;
  _applyCoBinaryTrackData(data);
  refreshCoBinary();
}

// Paint step `i` (picked from coBinaryFraction — no fetch). The living star drives the ONE
// HR marker + the 3D star; the compact object is a schematic point-mass glyph in 3D and the
// Roche panel. The accretion power is surfaced RELATIVE to the star's own L (the pedagogy:
// an accreting compact object can outshine its donor — advisor).
function refreshCoBinary() {
  if (!coBinaryView || !coBinaryTrackData) return;
  const i = coBinaryIndexFromFraction(coBinaryFraction);
  const step = coBinaryTrackData.steps[i];
  const s = coBinaryStar[i];
  const coType = coBinaryTrackData.co_type;

  hr.updateBinaryIndex(i);
  star.update(s, { coMarker: coType });
  if (step.roche) roche.drawLiveCo(step.roche, s, coType, step.mt_state);
  else roche.clear();
  // He kinds (co-hems / co-hems-rlo): the surviving star is a bare He star with a REAL,
  // measured surface — drive the composition panel per step (the reused He-surface view; the
  // panel is CSS-hidden on the H-rich co-hms-rlo kind, so this is He-only). The surface
  // genuinely evolves over the scrub (He → C/O on the most massive ones — the surfKind branch
  // in drawStripped labels that honestly). source:"posydon" swaps the caption OFF the Götberg
  // single-snapshot provenance (this is a time-varying POSYDON binary track, not Götberg 2018).
  if (isHeKind(coBinaryTrackData.kind)) comp.setStripped(s, { source: "posydon" });

  if (els.endgameAgeCaption) {
    const yrs = step.age_yr >= 1e6 ? `${(step.age_yr / 1e6).toFixed(2)} Myr`
      : step.age_yr < 1 ? "<1 yr" : `${Math.round(step.age_yr)} yr`;
    const sepAU = (step.separation_rsun / 215.032).toFixed(2);
    let acc = "";
    if (step.accretion_lum_lsun != null) {
      const ratio = step.accretion_lum_lsun / Math.max(1e-30, s.L_lsun);
      acc = ` · accretion L ≈ ${step.accretion_lum_lsun.toExponential(1)} L☉ (≈${ratio.toFixed(1)}× the star's own L, schematic η·Ṁ·c²)`;
    }
    els.endgameAgeCaption.textContent =
      `System age ${yrs} · period ${step.period_d.toFixed(2)} d · separation ${step.separation_rsun.toFixed(0)} R☉ ` +
      `(${sepAU} AU) · star ${step.star_current_msun.toFixed(2)} M☉, ${coType} ${step.co_mass_msun.toFixed(2)} M☉ · ${step.mt_state}` +
      acc +
      (i === coBinaryStar.length - 1 ? ` · outcome: ${coBinaryTrackData.outcome}` : "");
  }
}

// Dispatch a mass/[Fe/H] re-snap to the active endgame / what-if mode.
function tryResnap() {
  // path (b) Chunk 4b: the co-evolving binary is keyed on POSYDON's own (M1, q, P) grid,
  // independent of the MIST progenitor mass/[Fe/H] — the mass/feh CONTROLS are disabled
  // while it's active (enterBinaryView/exitBinaryView), so this should be unreachable via
  // the UI; guarded here too so a stray resnap can't desync the HR/roche/3D from a stale
  // binary track (mode stays "stripped" throughout, so it would otherwise fall through
  // to tryStrippedResnap below and repaint the WRONG (single-donor) model over it).
  if (mode === "stripped" && binaryView) return;
  if (mode === "stripped" && coBinaryView) return;   // POSYDON CO grid, not the MIST axes
  if (mode === "wd") return tryWDResnap();
  if (mode === "wr") return tryWRResnap();
  if (mode === "sn") return trySNResnap();
  if (mode === "stripped") return tryStrippedResnap();
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
  // {peculiar} is the Ap/Bp evocative what-if (star.js regime-gates it per-state, and it's a
  // no-op unless the toggle is on) — living path only; the endgame refreshers paint the star
  // directly with their own {endgame:…} opts, so they're untouched.
  star.update(s, { peculiar: peculiarOn });
  classification.update(s);
  scale.update(s);
  // A MESA what-if overlay (initial-He or α-enhanced) owns the HR panel while on (two MESA
  // tracks, MIST spine hidden per the honesty rule) — so DON'T draw the live marker/track
  // there; 3D/comp/spectrum/etc. still track the current star as the user scrubs (advisor-scoped).
  if (!heliumOn && !alphaOn && !isoOn) hr.update(s);
  comp.update(s);
  spectrum.update(s);
  structure.update(s);
  sed.update(s);
  refreshPopulation(s);   // the coeval-population SED overlay (no-op unless the toggle is on)
  refreshIsochrone(s);    // the cluster-isochrone HR overlay (no-op unless the toggle is on)
  refreshObserver(s);     // the observer reddening/mag view (no-op unless the toggle is on)
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
  updatePeculiarControl();
  updateStrippedControl();   // the stripped what-if is offer-able only in the eligible mass band
  updateHeliumControl();     // the He overlay is offer-able only near the solar-Z MESA grid
  updateAlphaControl();      // likewise the α-enhanced overlay (same solar-Z MESA grid)
  updatePopulationControl(); // the coeval-population SED overlay (any marker; gated on the baked cube)
  updateIsochroneControl();  // the cluster-isochrone HR overlay (any marker; gated on the .iso grid)
  updateObserverControl();   // the observer's-view control (any marker; gated on the spectrum cube)
  if (hzOn) hzhist.setNow(s.age_yr);   // move the HZ-history "now" line with the age scrub (D2a)
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
  updatePeculiarControl();
  try {
    const t = await fetchJSON(`/track?mass=${mass}&feh=${feh}&vvcrit=${effVvcrit()}`);
    // A newer track will drive its own refresh; and a track landing after we entered
    // the WD endgame must not overwrite the endgame view.
    if (token !== trackToken || mode !== "live") return;
    currentTrack = t;
    if (!heliumOn && !alphaOn && !isoOn) hr.setTrack(t);   // a MESA/isochrone overlay owns the HR panel; its refresh re-asserts it
    comp.setTrack(t);
    syncHZHistory();   // the HZ-history panel's whole-life series is track-derived — re-push it (no-op unless hzOn)
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
  // The mass/[Fe/H] moved — re-fetch the He / α overlay pair for the new star (no-op unless that
  // overlay is on AND still eligible: refresh()'s update*Control just tore it down if not).
  refreshHelium();
  refreshAlpha();
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

// The helium/α-enhanced + cluster-isochrone overlays act on the HR-diagram panel, and the
// coeval-population overlay acts on the SED panel — so their controls belong UNDER those panels
// (user request: a click in the Controls column changed a panel that could be scrolled off-screen,
// reading as "nothing happened"). They are DECLARED in the Controls panel in index.html (grouped
// with the sliders they conceptually sit near) and relocated here at boot — layout.js's panel drag
// is the precedent for structural moves in JS. IDs are unchanged, so every update*/toggle handler,
// and the reserveWhatIf greying that travels with them, keeps working untouched.
function relocateOverlayControls() {
  const hr = document.querySelector(".hr-panel");
  const sed = document.querySelector(".sed-panel");
  if (hr) for (const id of ["helium-control", "alpha-track-control", "isochrone-control"]) {
    const el = document.getElementById(id);
    if (el) hr.appendChild(el);
  }
  if (sed) { const p = document.getElementById("population-control"); if (p) sed.appendChild(p); }
}

async function init() {
  relocateOverlayControls();   // move the overlay what-ifs onto the panels they drive (see above)
  try {
    const ranges = await fetchJSON("/ranges");
    logMassMin = Math.log10(ranges.mass_msun.min);
    logMassMax = Math.log10(ranges.mass_msun.max);
    validMassMin = ranges.mass_msun.min;
    validMassMax = ranges.mass_msun.max;
    try { providerName = (await fetchJSON("/health")).provider || ""; } catch { /* non-fatal */ }
    // The initial-helium overlay has data only if the (never-hosted) MESA runs were generated
    // locally — probe once so the toggle is hidden on a fresh clone (the /rotation_status gate
    // pattern; a control that could only ever 503 shouldn't appear).
    try { heliumHasGrid = !!(await fetchJSON("/helium_status")).has_grid; } catch { heliumHasGrid = false; }
    try { alphaHasGrid = !!(await fetchJSON("/alpha_status")).has_grid; } catch { alphaHasGrid = false; }
    // The coeval-population overlay likewise has data only if the BPASS cube was host-baked
    // (gitignored) — probe once so the toggle is hidden on a fresh clone.
    try {
      const ps = await fetchJSON("/population_status");
      populationHasGrid = !!ps.has_grid;    // SED-spectrum cube (Chunk 1) — gates the toggle
      populationHasHRD = !!ps.has_hrd;      // HR-diagram number cube (Chunk 2) — adds the HR cloud
    } catch { populationHasGrid = false; populationHasHRD = false; }
    try { isoHasGrid = !!(await fetchJSON("/isochrone_status")).has_grid; } catch { isoHasGrid = false; }
    // Observer's view (Axis A) needs the absolute-flux spectrum cube (filters.json is committed).
    // There's no dedicated status route (A2 is frontend-only), so probe /photometry once with the
    // Sun's parameters: a 200 means the cube is present → offer the toggle; a 503 hides it.
    try { await fetchJSON("/photometry?teff=5772&logg=4.44&feh=0&radius_rsun=1"); observerHasData = true; }
    catch { observerHasData = false; }

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

    // Inclination facet (Chunk 2): reflect the default (60°) on the inputs and push it to
    // both consumers so main.js is the single source of truth (no dual-default drift). The
    // facet stays hidden until updateRotControl shows it for a rotating massive star.
    if (els.incl) els.incl.value = String(inclinationDeg);
    if (els.inclNum) els.inclNum.value = String(inclinationDeg);
    applyInclination(inclinationDeg);

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
      if (pulseView) {
        // The decompressed pulse scrub: linear across the TPAGB rows (no snapping — every
        // pulse row is a wanted in-between frame, like the living age scrub).
        pulseFraction = clamp01(Number(els.age.value));
        refreshPulse();
        return;
      }
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
    if (mode === "stripped" && binaryView) {
      // path (b) Chunk 4b: the co-evolving binary's system-time scrubber — plain
      // index-linear over the pre-fetched steps (see binaryIndexFromFraction).
      binaryFraction = clamp01(Number(els.age.value));
      refreshBinary();
      return;
    }
    if (mode === "stripped" && coBinaryView) {
      // CE/compact-object tail Chunk 1b: the CO-HMS_RLO system-time scrubber.
      coBinaryFraction = clamp01(Number(els.age.value));
      refreshCoBinary();
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

  // Ap/Bp chemically-peculiar toggle (atlas Tier C): a pure 3D-look what-if — no fetch, no
  // track/HR/spectrum change (off the spine). refresh() repaints the current EEP row through
  // paintState -> star.update({peculiar}), so the spots appear/vanish instantly on the marker.
  if (els.peculiarToggle) els.peculiarToggle.addEventListener("change", () => {
    if (mode !== "live") return;
    peculiarOn = els.peculiarToggle.checked;
    updatePeculiarControl();
    refresh();
  });

  // Binary-stripped-star what-if BUTTON: clicking it enters the reversible stripped-mode (a
  // mid-life fork — the whole display snaps to the stripped He-star, fetched from /binary). It's a
  // one-way ENTER like the WD/WR/SN gateway buttons; the endgame bar's "Back" is the single exit
  // (exitEndgame). Disabled out of the eligible mass band, so the guard is belt-and-suspenders.
  if (els.strippedBtn) els.strippedBtn.addEventListener("click", () => {
    if (mode === "live" && !els.strippedBtn.disabled) enterStripped();
  });

  // Initial-helium overlay (Phase 2): a light HR overlay, not a mode-swap. Checking it fetches
  // the baseline+enhanced MESA pair and takes over the HR panel (MIST spine hidden); unchecking
  // restores the live track. Only meaningful in live mode within the eligible region — the
  // control is hidden otherwise, so this only fires when a real toggle is possible.
  if (els.heliumToggle) els.heliumToggle.addEventListener("change", () => {
    if (els.heliumToggle.checked) {
      if (mode !== "live") { els.heliumToggle.checked = false; return; }
      // Mutually exclusive with the α overlay (shared HR slot): clear α state first, no repaint
      // (refreshHelium repaints the slot). Reset α's note to its default prompt.
      if (alphaOn) { alphaOn = false; alphaToken++; if (els.alphaToggle) els.alphaToggle.checked = false; updateAlphaControl(); }
      if (isoOn) { isoOn = false; isoToken++; isoNodeKey = ""; isoLastStates = null; if (els.isochroneToggle) els.isochroneToggle.checked = false; hr.clearIsochroneOverlay(); updateIsochroneControl(); }
      heliumOn = true;
      if (els.heliumNote) els.heliumNote.textContent = "Loading helium-enhanced tracks…";
      refreshHelium();
    } else {
      heliumOff();
    }
  });

  // α-enhanced overlay (Phase 3): the twin of the He toggle, mutually exclusive with it. Checking
  // it fetches the baseline+enhanced (equivalent-Z) MESA pair and takes over the HR panel.
  if (els.alphaToggle) els.alphaToggle.addEventListener("change", () => {
    if (els.alphaToggle.checked) {
      if (mode !== "live") { els.alphaToggle.checked = false; return; }
      if (heliumOn) { heliumOn = false; heliumToken++; if (els.heliumToggle) els.heliumToggle.checked = false; updateHeliumControl(); }
      if (isoOn) { isoOn = false; isoToken++; isoNodeKey = ""; isoLastStates = null; if (els.isochroneToggle) els.isochroneToggle.checked = false; hr.clearIsochroneOverlay(); updateIsochroneControl(); }
      alphaOn = true;
      if (els.alphaNote) els.alphaNote.textContent = "Loading α-enhanced tracks…";
      refreshAlpha();
    } else {
      alphaOff();
    }
  });

  // Coeval-population (BPASS) overlay on the SED panel. Independent of the He/α HR overlays
  // (different panel), so NOT mutually exclusive with them. Checking it fetches /population for
  // the current marker and pushes the curves into the SED panel; paintState keeps it in sync.
  if (els.populationToggle) els.populationToggle.addEventListener("change", () => {
    if (els.populationToggle.checked) {
      if (mode !== "live") { els.populationToggle.checked = false; return; }
      populationOn = true;
      popNodeKey = "";     // force the first fetch (no cached node yet)
      if (els.populationNote) els.populationNote.textContent = "Loading population spectra…";
      // Pick the current marker exactly as refresh() does (linear-in-EEP row) and fetch now.
      if (currentTrack && currentTrack.length) {
        const i = trackRowFromPos(ageFraction);
        if (i >= 0) refreshPopulation(currentTrack[i]);
      }
    } else {
      populationOff();
    }
  });

  // Cluster-isochrone (MIST .iso) overlay on the HR panel. Owns the HR slot like the He/α
  // overlays, so mutually exclusive with them. Checking it fetches /isochrone for the marker's
  // (age, [Fe/H]) and draws the coeval-cluster locus; paintState keeps it in sync as the age
  // scrubs (the cluster ages with the slider).
  if (els.isochroneToggle) els.isochroneToggle.addEventListener("change", () => {
    if (els.isochroneToggle.checked) {
      if (mode !== "live") { els.isochroneToggle.checked = false; return; }
      if (heliumOn) { heliumOn = false; heliumToken++; if (els.heliumToggle) els.heliumToggle.checked = false; updateHeliumControl(); }
      if (alphaOn) { alphaOn = false; alphaToken++; if (els.alphaToggle) els.alphaToggle.checked = false; updateAlphaControl(); }
      isoOn = true;
      isoNodeKey = "";     // force the first fetch (no cached node yet)
      resetIsoDecouple();  // B3: a fresh entry always starts coupled (byte-compatible default)
      if (els.isoDecoupleWrap) els.isoDecoupleWrap.hidden = false;   // reveal the decouple sub-control
      if (els.isochroneNote) els.isochroneNote.textContent = "Loading cluster isochrone…";
      if (currentTrack && currentTrack.length) {
        const i = trackRowFromPos(ageFraction);
        if (i >= 0) refreshIsochrone(currentTrack[i]);
      }
    } else {
      isochroneOff();
    }
  });

  // Habitable-zone overlay (Axis D) on the scale bar. A pure L+Teff VIEW on a DIFFERENT panel than
  // the HR overlays, so it is NOT mutually exclusive with them (no HR-panel ownership). The only
  // gate is live mode; scale.js self-gates by Kopparapu's 2600–7200 K range (band absent for hot
  // stars). No fetch — setHZ redraws from the scale bar's retained state.
  if (els.hzToggle) els.hzToggle.addEventListener("change", () => {
    if (els.hzToggle.checked && mode !== "live") { els.hzToggle.checked = false; return; }
    hzOn = els.hzToggle.checked;
    scale.setHZ(hzOn);
    syncHZHistory();   // the same toggle governs the temporal twin (D2a) — show/hide + push
  });

  // Observer's view (Axis A) — distance + dust. A pure VIEW (never the HR marker), so NOT mutually
  // The three observer knobs. Each re-pushes the client-side reddening overlay INSTANTLY (so the
  // curve tracks the drag with no lag) and re-fetches the readout (debounced inside refreshObserver)
  // for the last painted marker. Distance is log-spaced; A_V/R_V are linear.
  const onObserverKnob = () => {
    syncObserverKnobs();
    if (observerMarker) refreshObserver(observerMarker);
  };
  if (els.obsDistance) els.obsDistance.addEventListener("input", () => {
    obsDistancePc = obsDistFromFrac(parseFloat(els.obsDistance.value));
    onObserverKnob();
  });
  if (els.obsAv) els.obsAv.addEventListener("input", () => {
    obsAv = parseFloat(els.obsAv.value);
    onObserverKnob();
  });
  if (els.obsRv) els.obsRv.addEventListener("input", () => {
    obsRv = parseFloat(els.obsRv.value);
    onObserverKnob();
  });

  // B3: decouple the cluster's age from the star's age slider. Checking it gives the cluster its
  // own log-age slider (bounds = the isochrone grid's tabulated ages, served as available_log_ages);
  // pin the star, sweep the cluster, watch the turnoff march down the MS. Only the AGE decouples —
  // [Fe/H] stays the star's. A fresh seed = the star's current age (a continuous hand-off).
  if (els.isoDecoupleToggle) els.isoDecoupleToggle.addEventListener("change", () => {
    if (!isoOn) { els.isoDecoupleToggle.checked = false; return; }
    if (els.isoDecoupleToggle.checked) {
      isoDecoupled = true;
      const lo = isoLogAges && isoLogAges.length ? isoLogAges[0] : 6;
      const hi = isoLogAges && isoLogAges.length ? isoLogAges[isoLogAges.length - 1] : 10.15;
      let seed = hi;
      if (currentTrack && currentTrack.length) {
        const i = trackRowFromPos(ageFraction);
        const a = i >= 0 ? (currentTrack[i].age_yr ?? 0) : 0;
        if (a > 0) seed = Math.min(hi, Math.max(lo, Math.log10(a)));
      }
      isoClusterLogAge = seed;
      if (els.isoClusterAge) {
        els.isoClusterAge.min = lo.toFixed(3);
        els.isoClusterAge.max = hi.toFixed(3);
        els.isoClusterAge.value = String(seed);
      }
      if (els.isoClusterAgeVal) els.isoClusterAgeVal.textContent = fmtPopAge(10 ** seed / 1e9);
      if (els.isoClusterAgeRow) els.isoClusterAgeRow.hidden = false;
    } else {
      isoDecoupled = false;
      isoClusterLogAge = null;
      if (els.isoClusterAgeRow) els.isoClusterAgeRow.hidden = true;
    }
    isoNodeKey = "";     // the age source changed → force a refetch (not a same-node repaint)
    if (currentTrack && currentTrack.length) {
      const i = trackRowFromPos(ageFraction);
      if (i >= 0) refreshIsochrone(currentTrack[i]);
    }
  });

  // B3: the decoupled cluster-age slider itself — drag to age the cluster (the star marker stays
  // at its own age, sliding off the locus). Node-key bucketing + latest-wins in refreshIsochrone
  // dedupe the fetch, so no separate debounce is needed (mirrors the star age-scrub path).
  if (els.isoClusterAge) els.isoClusterAge.addEventListener("input", () => {
    if (!isoOn || !isoDecoupled) return;
    isoClusterLogAge = parseFloat(els.isoClusterAge.value);
    if (els.isoClusterAgeVal)
      els.isoClusterAgeVal.textContent = fmtPopAge(10 ** isoClusterLogAge / 1e9);
    if (currentTrack && currentTrack.length) {
      const i = trackRowFromPos(ageFraction);
      if (i >= 0) refreshIsochrone(currentTrack[i]);
    }
  });

  // path (b): "Show companion" — reveal/hide the un-stripped accretor as a second HR marker.
  // Flipping it re-fetches the current node (now via /binary_pair or /binary) and re-applies,
  // so the companion appears/disappears with the reversal caption + readout in lockstep.
  if (els.companionToggle) els.companionToggle.addEventListener("change", () => {
    if (mode !== "stripped") return;
    companionOn = els.companionToggle.checked;
    tryStrippedResnap();   // re-fetch the current (mass, [Fe/H]) via the now-correct route + re-apply
  });

  // path (b) Chunk 4b/4c: the "Co-evolve the system" demo picker. Delegated (all four
  // buttons — three curated + "custom" — share the .binary-demo-btn class + a data-demo
  // key); the picker row itself is CSS-hidden once a demo is live, so this only fires from
  // a fresh stripped-mode entry. enterBinaryView already branches on demoKey === "custom".
  if (els.binaryDemoRow) els.binaryDemoRow.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".binary-demo-btn");
    if (btn && mode === "stripped") enterBinaryView(btn.dataset.demo);
  });
  if (els.binaryDemoBack) els.binaryDemoBack.addEventListener("click", () => {
    if (mode === "stripped" && binaryView) exitBinaryView();
  });

  // CE/compact-object tail Chunk 1b/1c: the standalone CO-HMS_RLO demo — the curated Gate-1
  // "xrb" system OR (Chunk 1c) a free "custom" one — + its own "Back to the snapshot".
  // Enters/exits the reversible co-binary-view, mutually exclusive with the HMS-HMS
  // "Co-evolve" movie (enterCoBinaryView exits it first). enterCoBinaryView branches on the
  // demo key (custom → reveal the M_star/M_co/P sliders once the view is live).
  if (els.coBinaryDemoXrb) els.coBinaryDemoXrb.addEventListener("click", () => {
    if (mode === "stripped") enterCoBinaryView("xrb");
  });
  if (els.coBinaryDemoCustom) els.coBinaryDemoCustom.addEventListener("click", () => {
    if (mode === "stripped") enterCoBinaryView("custom");
  });
  if (els.coBinaryDemoBack) els.coBinaryDemoBack.addEventListener("click", () => {
    if (mode === "stripped" && coBinaryView) exitCoBinaryView();
  });

  // Chunk 1c: the free M_star/M_co/P sliders behind the CO "Custom system" — dragging
  // refetches /co_binary_track (debounced + latest-wins) and re-snaps to the nearest real
  // track; updateCoBinaryCustomNote (inside _applyCoBinaryTrackData) always states the TRUE
  // snapped node + the WD-placeholder caveat, never the raw dragged number.
  const debouncedCoBinaryCustom = debounce(refetchCoBinaryTrack, SLIDER_FETCH_DELAY_MS);
  if (els.coBinaryCustomMstar) {
    els.coBinaryCustomMstar.addEventListener("input", () => {
      coCustomMstar = coMstarFromPos(Number(els.coBinaryCustomMstar.value));
      setNum(els.coBinaryCustomMstarNum, fmt(coCustomMstar));
      debouncedCoBinaryCustom();
    });
    els.coBinaryCustomMstar.addEventListener("change", () => debouncedCoBinaryCustom.flush());
  }
  if (els.coBinaryCustomMstarNum) els.coBinaryCustomMstarNum.addEventListener("change", () => {
    if (!coBinaryMeta || els.coBinaryCustomMstarNum.value.trim() === "") return;
    const m = Number(els.coBinaryCustomMstarNum.value);
    if (!isFinite(m)) return;
    coCustomMstar = Math.min(Math.max(m, coBinaryMeta.m_star_min), coBinaryMeta.m_star_max);
    els.coBinaryCustomMstar.value = String(posFromCoMstar(coCustomMstar));
    refetchCoBinaryTrack();
  });

  if (els.coBinaryCustomMco) {
    els.coBinaryCustomMco.addEventListener("input", () => {
      coCustomMco = coMcoFromPos(Number(els.coBinaryCustomMco.value));
      setNum(els.coBinaryCustomMcoNum, fmt(coCustomMco));
      debouncedCoBinaryCustom();
    });
    els.coBinaryCustomMco.addEventListener("change", () => debouncedCoBinaryCustom.flush());
  }
  if (els.coBinaryCustomMcoNum) els.coBinaryCustomMcoNum.addEventListener("change", () => {
    if (!coBinaryMeta || els.coBinaryCustomMcoNum.value.trim() === "") return;
    const m = Number(els.coBinaryCustomMcoNum.value);
    if (!isFinite(m)) return;
    coCustomMco = Math.min(Math.max(m, coBinaryMeta.m_co_min), coBinaryMeta.m_co_max);
    els.coBinaryCustomMco.value = String(posFromCoMco(coCustomMco));
    refetchCoBinaryTrack();
  });

  if (els.coBinaryCustomP) {
    els.coBinaryCustomP.addEventListener("input", () => {
      coCustomP = coPFromPos(Number(els.coBinaryCustomP.value));
      setNum(els.coBinaryCustomPNum, fmt(coCustomP));
      debouncedCoBinaryCustom();
    });
    els.coBinaryCustomP.addEventListener("change", () => debouncedCoBinaryCustom.flush());
  }
  if (els.coBinaryCustomPNum) els.coBinaryCustomPNum.addEventListener("change", () => {
    if (!coBinaryMeta || els.coBinaryCustomPNum.value.trim() === "") return;
    const p = Number(els.coBinaryCustomPNum.value);
    if (!isFinite(p)) return;
    coCustomP = Math.min(Math.max(p, coBinaryMeta.p_min), coBinaryMeta.p_max);
    els.coBinaryCustomP.value = String(posFromCoP(coCustomP));
    refetchCoBinaryTrack();
  });

  // The CO [Fe/H] picker — applies to WHICHEVER CO demo is showing (curated or custom), the
  // binaryFeh twin. A bucket change can shift the M_star/M_co/P grid bounds (each POSYDON
  // metallicity is its own baked grid), so invalidate the cached meta + await the bounds
  // refresh (which clamps/repositions the sliders) BEFORE re-fetching the track.
  if (els.coBinaryFeh) els.coBinaryFeh.addEventListener("change", async () => {
    const f = Number(els.coBinaryFeh.value);
    if (!isFinite(f)) return;
    coCustomFeh = f;
    coBinaryMeta = null; coBinaryMetaPromise = null; coBinaryMetaPromiseFeh = null; coBinaryMetaFeh = null;
    coBinaryMetaPromiseKind = null; coBinaryMetaKind = null;
    await ensureCoBinaryMeta();
    refetchCoBinaryTrack();
  });

  // Chunk 2b: the CO grid-KIND picker — orthogonal to [Fe/H], the axis that swaps between an
  // H-rich companion (CO-HMS_RLO) and a bare He star + compact object (CO-HeMS / CO-HeMS_RLO).
  // A kind change is a FRESH grid: reset the custom triple to that kind's curated demo (the
  // grids' spans differ wildly — CO-HMS_RLO periods ~200 d vs CO-HeMS ~0.5 d, so clamping the
  // old values alone would pin the sliders to a boundary), swap the button/tooltip text,
  // invalidate the cached meta + await the new bounds, then re-fetch the active track. When
  // NOT in the CO movie yet, refetch no-ops — the next demo click uses the updated coKind.
  applyCoKindUi();
  if (els.coBinaryKind) {
    els.coBinaryKind.value = coKind;
    els.coBinaryKind.addEventListener("change", async () => {
      const k = els.coBinaryKind.value;
      if (!(k in CO_BINARY_DEMOS)) return;
      coKind = k;
      applyCoKindUi();
      const d = CO_BINARY_DEMOS[coKind];
      coCustomMstar = d.m_star; coCustomMco = d.m_co; coCustomP = d.p;
      coBinaryMeta = null; coBinaryMetaPromise = null; coBinaryMetaPromiseFeh = null; coBinaryMetaFeh = null;
      coBinaryMetaPromiseKind = null; coBinaryMetaKind = null;
      await ensureCoBinaryMeta();
      refetchCoBinaryTrack();
    });
  }

  // path (b) Chunk 4c: the free M1/q/P sliders behind "Custom orbit". Dragging refetches
  // /binary_track (debounced + latest-wins, the ⁵⁶Ni-slider idiom) and re-snaps to the
  // nearest real POSYDON track — updateBinaryCustomNote (inside _applyBinaryTrackData)
  // always states the TRUE snapped node, never the raw dragged number.
  const debouncedBinaryCustom = debounce(refetchBinaryTrack, SLIDER_FETCH_DELAY_MS);
  if (els.binaryCustomM1) {
    els.binaryCustomM1.addEventListener("input", () => {
      customM1 = customM1FromPos(Number(els.binaryCustomM1.value));
      setNum(els.binaryCustomM1Num, fmt(customM1));
      debouncedBinaryCustom();
    });
    els.binaryCustomM1.addEventListener("change", () => debouncedBinaryCustom.flush());
  }
  if (els.binaryCustomM1Num) els.binaryCustomM1Num.addEventListener("change", () => {
    if (!binaryMeta || els.binaryCustomM1Num.value.trim() === "") return;
    const m = Number(els.binaryCustomM1Num.value);
    if (!isFinite(m)) return;
    customM1 = Math.min(Math.max(m, binaryMeta.m1_min), binaryMeta.m1_max);
    els.binaryCustomM1.value = String(posFromCustomM1(customM1));
    refetchBinaryTrack();
  });

  if (els.binaryCustomQ) {
    els.binaryCustomQ.addEventListener("input", () => {
      customQ = Number(els.binaryCustomQ.value);
      setNum(els.binaryCustomQNum, fmt(customQ));
      debouncedBinaryCustom();
    });
    els.binaryCustomQ.addEventListener("change", () => debouncedBinaryCustom.flush());
  }
  if (els.binaryCustomQNum) els.binaryCustomQNum.addEventListener("change", () => {
    if (!binaryMeta || els.binaryCustomQNum.value.trim() === "") return;
    const q = Number(els.binaryCustomQNum.value);
    if (!isFinite(q)) return;
    customQ = Math.min(Math.max(q, binaryMeta.q_min), binaryMeta.q_max);
    els.binaryCustomQ.value = String(customQ);
    refetchBinaryTrack();
  });

  if (els.binaryCustomP) {
    els.binaryCustomP.addEventListener("input", () => {
      customP = customPFromPos(Number(els.binaryCustomP.value));
      setNum(els.binaryCustomPNum, fmt(customP));
      debouncedBinaryCustom();
    });
    els.binaryCustomP.addEventListener("change", () => debouncedBinaryCustom.flush());
  }
  if (els.binaryCustomPNum) els.binaryCustomPNum.addEventListener("change", () => {
    if (!binaryMeta || els.binaryCustomPNum.value.trim() === "") return;
    const p = Number(els.binaryCustomPNum.value);
    if (!isFinite(p)) return;
    customP = Math.min(Math.max(p, binaryMeta.p_min), binaryMeta.p_max);
    els.binaryCustomP.value = String(posFromCustomP(customP));
    refetchBinaryTrack();
  });

  // The [Fe/H] metallicity-bucket picker — applies to WHICHEVER demo is showing (curated
  // or custom), unlike M1/q/P which only ever drive "custom". Switching buckets means the
  // M1/q/P grid bounds can shift too (each POSYDON metallicity is its own baked grid), so
  // this invalidates the cached binaryMeta and re-fetches it (refreshing the custom
  // sliders' bounds/clamps) alongside re-fetching whichever track is live.
  if (els.binaryFeh) els.binaryFeh.addEventListener("change", async () => {
    const f = Number(els.binaryFeh.value);
    if (!isFinite(f)) return;
    customFeh = f;
    binaryMeta = null; binaryMetaPromise = null; binaryMetaPromiseFeh = null; binaryMetaFeh = null;
    // Await the bounds refresh first: it clamps customM1/Q/P to the new bucket's grid and
    // repositions the sliders, so a subsequent refetch (below) matches what's now shown on
    // the sliders instead of fetching the OLD bucket's dragged values a moment before they
    // silently get re-clamped out from under it.
    await ensureBinaryMeta();
    refetchBinaryTrack();     // re-snap whichever demo/custom system is currently showing
  });

  // Inclination slider (gravity darkening Chunk 2): a pure VIEWING control — it re-tilts the
  // 3D star and re-broadens the spectrum's lines (v sin i) with NO refetch and NO track/HR
  // change (it's off the spine). Slider ↔ number input kept in sync; both drive
  // applyInclination, which pushes the angle to both consumers in lockstep.
  if (els.incl) els.incl.addEventListener("input", () => {
    const v = Number(els.incl.value);
    if (els.inclNum) els.inclNum.value = String(v);
    applyInclination(v);
  });
  if (els.inclNum) els.inclNum.addEventListener("change", () => {
    let v = Number(els.inclNum.value);
    if (!Number.isFinite(v)) v = inclinationDeg;
    v = Math.min(90, Math.max(0, Math.round(v)));
    els.inclNum.value = String(v);
    if (els.incl) els.incl.value = String(v);
    applyInclination(v);
  });
  // Orientation-grid toggle: a pure viewing aid on the 3D star (see axisGridOn). Manual changes
  // are sticky — the one-shot auto-enable (updateRotControl) is already latched by the time the
  // user can click, so unchecking here suppresses the grid for good across rotating↔non cycles.
  if (els.axisGridToggle) els.axisGridToggle.addEventListener("change", () => {
    axisGridOn = els.axisGridToggle.checked;
    star.setAxisGrid(axisGridOn);
  });

  // The stellar-endgame gateway: enter the WD / WR / SN endgame from the button at the slider
  // limit; the bar's "Back" button leaves it (reversible — Locked decision #1).
  if (els.gatewayWd) els.gatewayWd.addEventListener("click", enterWD);
  if (els.gatewayWr) els.gatewayWr.addEventListener("click", enterWR);
  if (els.gatewaySn) els.gatewaySn.addEventListener("click", enterSN);
  if (els.endgameBack) els.endgameBack.addEventListener("click", exitEndgame);
  // The thermal-pulse showcase toggle (wd-mode sub-view): open the decompressed loop view,
  // or return to the cooling scrub. Only visible when the amplitude gate passed (enterWD).
  if (els.pulseToggle) els.pulseToggle.addEventListener("click", () => {
    if (pulseView) exitPulseView(); else enterPulseView();
  });

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
