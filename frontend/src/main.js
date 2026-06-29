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
import { createSpectrum } from "./spectrum.js";
import { createSED } from "./sed.js";
import { createClassification } from "./classify.js";
import { makeSortable } from "./layout.js";
import { initTooltips } from "./tooltip.js";
import { teffToCSS } from "./color.js";

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
  // Stellar-endgame gateway + white-dwarf mode (smoldering-cinder-gateway.md).
  gateway: document.getElementById("gateway"),
  gatewayWd: document.getElementById("gateway-wd"),
  gatewayWr: document.getElementById("gateway-wr"),
  gatewaySn: document.getElementById("gateway-sn"),
  endgameBar: document.getElementById("endgame-bar"),
  endgameBack: document.getElementById("endgame-back"),
  endgameResnapNote: document.getElementById("endgame-resnap-note"),
  endgameAgeCaption: document.getElementById("endgame-age-caption"),
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
// `ageValue` (absolute years, below) is the SOURCE OF TRUTH for the age — analogous
// to `massValue`. `ageFraction` is a *display* derived from it: each track has its
// own age window, so when mass/[Fe/H] changes (and the window moves) we KEEP the
// absolute age and recompute the fraction, clamped to the new window — so moving the
// mass slider doesn't change the age value when it stays in range. ageValue is kept
// UNCLAMPED (the desired age); only the fetch/display clamp it, so dragging mass up
// through short-lived stars and back springs the age back instead of ratcheting it
// to zero.
let ageFraction = 0.46;   // slider position 0..1, mapped into [ageMin, ageMax]
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

// --- stellar-endgame gateway + white-dwarf mode ------------------------------
// (docs/plans/smoldering-cinder-gateway.md, Chunk 2). `mode` is the one switch: the
// living-star path (everything above) vs the reversible white-dwarf endgame. The
// endgame snaps to ONE real grid track (never interpolated — §6), so the WD scrub is
// SIMPLER than the live path: it picks states[i] from the pre-fetched /endgame result
// and feeds the consumers directly — no /state fetch, no window build, no phase snap.
let mode = "live";              // "live" | "wd" | "wr"
let endgame = null;             // the latest /endgame result (type, states, masses…)
let endgameKey = null;          // the requested (mass|feh) the `endgame` data is for
let endgameToken = 0;           // latest-wins guard for /endgame fetches
let wdFraction = 0;             // slider position 0..1 inside the WD endgame scrub
let wrFraction = 0;             // slider position 0..1 inside the WR endgame scrub
let lastEgMass = 1, lastEgFeh = 0;   // last accepted endgame progenitor (for the revert)
let pinAgeToEnd = false;        // one-shot: land the next track refresh at the very end

// The gateway button appears only once the star is scrubbed to the VERY end of its
// visible life (the EAGB giant) — not merely "near" it. The age axis is linear in age,
// so the post-RGB drama (RGB tip → CHeB → EAGB) is crammed into the last ~2% of the
// slider; a looser threshold (the old 0.98) put the button up while the marker was still
// a mid-RGB star, so entering jumped RGB → AGB-giant (the "missing steps" the user felt).
// At the true end the living EAGB giant is continuous with the endgame's first state (the
// first thermal pulse), so the corona / X-ray / radius all carry across smoothly. The age
// slider snaps drags within ~1.5% of the end to exactly 1.0, so reaching it stays a
// natural "slam to the right" gesture. The /endgame data is still PREFETCHED earlier
// (GATE_FETCH) so the button is instant when the user lands at the end.
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

// A transient note in the endgame bar (e.g. after a mass re-snap left the WD range).
function setWDResnapNote(msg) {
  if (!els.endgameResnapNote) return;
  els.endgameResnapNote.textContent = msg || "";
  els.endgameResnapNote.hidden = !msg;
}

const egKey = () => `${massValue.toFixed(4)}|${Number(els.feh.value).toFixed(2)}`;

// Trailing debounce for the EXPENSIVE backend fetch behind a slider drag. Each
// /track (and the /state inside refresh()) rebuilds the full (mass,[Fe/H]) EEP
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

// Snap an age FRACTION (0..1) to a landmark or to a track endpoint. The endpoints
// (0 = ZAMS, 1 = the final EAGB state) are snap targets too, so dragging fully right
// always reaches the true end of the track — even when a late landmark (CHeB/EAGB)
// sits within the snap radius of 1.0, which used to capture the whole right edge and
// trap the slider short of the end. Returns the EXACT float (never the range input's
// step-quantized value): the phase boundaries are razor-sharp, so refresh() must
// derive the age from this exact fraction or the readout shows the previous phase.
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
  for (const s of track) {
    if (s.phase !== prev) {
      // Phase transitions are the real landmarks — kind:"phase" marks them as
      // never-droppable (dropping CHeB was the "CHeB is nowhere as a tick" bug).
      if (prev !== null) pts.push({ age: s.age_yr, label: s.phase, kind: "phase" });
      prev = s.phase;
    }
  }
  // First-ascent RGB tip = max radius among the RGB-phase rows. Restricted to RGB
  // (not the global max) because the window now reaches the early-AGB, whose radius
  // can exceed the RGB tip for intermediate masses — the global max would mislabel
  // an EAGB state as the "RGB tip". Skipped if the star never has an RGB phase.
  // Tagged kind:"tip": for every star that ignites helium the tip coincides with
  // CHeB onset (the He flash happens AT the tip — measured |Δpos| < 1.3e-4 across all
  // masses), so rebuildAgeTicks drops it as a redundant mark when CHeB sits on top of
  // it, leaving it only for stars whose window ends mid-RGB (no CHeB).
  let tip = null;
  for (const s of track)
    if (s.phase === "RGB" && (tip === null || s.R_rsun > tip.R_rsun)) tip = s;
  if (tip !== null) pts.push({ age: tip.age_yr, label: "RGB tip", kind: "tip" });
  return pts;
}

// Build the age ticks from the track (the single source for the age window now).
// Position uses the SAME map the slider uses — frac = (age - ageMin)/(ageMax -
// ageMin) — so each landmark tick lands exactly under the marker at that age. (If
// this drifted from refresh()'s `age = ageMin + frac*(ageMax-ageMin)`, snapping
// would jump the marker off the landmark.)
function rebuildAgeTicks() {
  if (!currentTrack || !(ageMax > ageMin)) return;
  const span = ageMax - ageMin;
  const all = criticalAges(currentTrack)
    .map((p) => ({ ...p, pos: clamp01((p.age - ageMin) / span) }));
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
  // The age axis is linear in age, so the evolutionary landmarks crowd the right edge
  // for low/intermediate-mass stars — stagger their labels onto stacked rows (no-drop)
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
// Two independent token streams: the per-change state fetch, and the track fetch
// (which only fires on mass/feh changes, so a slow track can't be clobbered by a
// fast age scrub). Each guards against a stale response overwriting a newer one.
let reqToken = 0;
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
      "surface rotation speed (not modeled by this provider)",
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
  spectrum.showPlaceholder(
    "White-dwarf atmospheres (log g 7–9) aren't in the spectral grid yet.");
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
  spectrum.showPlaceholder(
    "Wolf–Rayet wind-emission spectra aren't in the spectral grid yet.");
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
  const eg = (endgame && endgameKey === egKey()) ? endgame : null;
  const atEnd = mode === "live" && ageFraction >= GATE_SHOW && eg;
  const showWd = !!(atEnd && eg.type === "WD" && eg.states.length);
  const showWr = !!(atEnd && eg.type === "WR" && eg.states.length);
  const showSn = !!(atEnd && eg.type === "SN");
  els.gatewayWd.hidden = !showWd;
  els.gatewayWr.hidden = !showWr;
  if (showSn) {
    els.gatewaySn.innerHTML =
      `<b>Core collapse.</b> A ${fmt(eg.mass_init_msun)} M☉ star ends as a supernova, ` +
      `leaving a neutron star or black hole — a remnant this simulator doesn't model.`;
  }
  els.gatewaySn.hidden = !showSn;
  els.gateway.hidden = !(showWd || showWr || showSn);
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
  const mass = massValue, feh = Number(els.feh.value);
  try {
    const eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}`);
    // Drop a stale/superseded response, or one for a star we've since moved off of.
    if (tok !== endgameToken || mode !== "live" || egKey() !== key) return;
    endgame = eg; endgameKey = key;
    hr.setEndgamePreview(eg.type === "WD" && eg.states.length ? eg.states : null);
    updateGateway();
  } catch { /* non-fatal: no preview/gateway this time */ }
}

// Lazily fetch /endgame as the star nears the end of its life, so the gateway is ready
// when the user reaches the slider limit (keeps normal scrubbing light — no 1 MB fetch
// per mass drag). Latest-wins; re-fetches whenever (mass, [Fe/H]) changed.
async function maybeFetchEndgame() {
  if (mode !== "live" || ageFraction < GATE_FETCH) return;
  const key = egKey();
  if (endgame && endgameKey === key) return;
  const tok = ++endgameToken;
  const mass = massValue, feh = Number(els.feh.value);
  try {
    const eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}`);
    if (tok !== endgameToken || mode !== "live") return;
    endgame = eg; endgameKey = key;
    // Set the HR preview here too, not just in fetchEndgamePreview: the two share
    // endgameToken, so when both fire (e.g. exiting WD at ageFraction=1, where this
    // path wins the token race) only the winner runs its success branch — it must
    // also set the preview, or the dashed track silently fails to appear.
    hr.setEndgamePreview(eg.type === "WD" && eg.states.length ? eg.states : null);
    updateGateway();
  } catch { /* non-fatal: no gateway this time */ }
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
  // Invalidate any in-flight live fetch so it can't land and clobber the WD render.
  reqToken++; trackToken++;
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
  // Invalidate any in-flight live fetch so it can't land and clobber the WR render.
  reqToken++; trackToken++;
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
  document.body.classList.remove("wd-mode", "wr-mode");
  els.endgameBar.hidden = true;
  setWDResnapNote("");
  hr.clearEndgame();
  comp.clearEndgame();
  endgame = null; endgameKey = null;
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
  let eg;
  try { eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}`); }
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
  let eg;
  try { eg = await fetchJSON(`/endgame?mass=${mass}&feh=${feh}`); }
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

// Dispatch a mass/[Fe/H] re-snap to the active endgame mode.
function tryResnap() {
  if (mode === "wd") return tryWDResnap();
  if (mode === "wr") return tryWRResnap();
}

async function refresh() {
  const token = ++reqToken;
  // Clamp the source-of-truth mass to the span valid at this [Fe/H] (the dead
  // low-mass corner moves with metallicity) and PERSIST the clamp, then sync the
  // thumb so it can't visually sit in the disabled (dead-corner) region.
  massValue = Math.min(Math.max(massValue, validMassMin), validMassMax);
  const mass = massValue;
  els.mass.value = clamp01(sliderFromMass(mass));
  const feh = Number(els.feh.value);
  // Fetch + display at the desired age, CLAMPED to the current window. ageValue is
  // the unclamped source of truth; the thumb is set from it in refreshTrack() and the
  // age handlers — refresh() must NOT re-read els.age.value (that re-quantizes to the
  // 0.0005 step and reintroduces the razor-sharp-phase off-by-one). Display == fetch
  // == readout (all the clamped age), so the unclamped desired value is never shown.
  const age = Math.min(Math.max(ageValue, ageMin), ageMax);

  setNum(els.massNum, fmt(mass));
  setNum(els.fehNum, feh.toFixed(2));
  setNum(els.ageNum, gyrNum(age));

  try {
    const s = await fetchJSON(
      `/state?mass=${mass}&feh=${feh}&age=${age}`,
    );
    // Bail if a newer request superseded this one OR if we've since entered the WD
    // endgame — a live /state landing after enterWD() would clobber the WD render
    // (refreshWD doesn't bump reqToken, so the token alone wouldn't catch it).
    if (token !== reqToken || mode !== "live") return;
    star.update(s);
    classification.update(s);
    scale.update(s);
    hr.update(s);
    comp.update(s);
    spectrum.update(s);
    sed.update(s);
    renderReadout(s);
    els.status.style.color = teffToCSS(s.Teff_K);
    // Tokenize so each part carries its own hover pedagogy (no "?" glyph — the
    // text itself is the hover target). innerHTML, not textContent, for the spans.
    els.status.innerHTML =
      tipSpan("OK", STATUS_OK_TIP) +
      " · " + tipSpan(s.phase, phaseTip(s.phase)) +
      (providerName ? " · " + tipSpan(providerName, providerTip(providerName)) : "");
  } catch (err) {
    if (token !== reqToken) return;
    els.status.style.color = "#ff6b6b";
    els.status.textContent = `Error: ${err.message}`;
  }
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
  try {
    const t = await fetchJSON(`/track?mass=${mass}&feh=${feh}`);
    // A newer track will drive its own refresh; and a track landing after we entered
    // the WD endgame must not overwrite the endgame view.
    if (token !== trackToken || mode !== "live") return;
    currentTrack = t;
    hr.setTrack(t);
    comp.setTrack(t);
    // The star changed, so any cached endgame is stale — drop it + hide the gateway
    // (maybeFetchEndgame refetches when the user next scrubs near the end). Clear the
    // faint HR preview too, then refetch it for the new star (fire-and-forget, below).
    endgame = null; endgameKey = null; els.gateway.hidden = true;
    hr.setEndgamePreview(null);
    fetchEndgamePreview();
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
      // (ageValue) is preserved — recompute the slider fraction from it, clamped to
      // the new window, and sync the thumb. So changing mass/[Fe/H] keeps the age
      // fixed when it stays in range, and pins it to the nearest end when it doesn't
      // (ageValue itself stays unclamped, so dragging back springs it out again). On
      // the very first track ageValue is still the Sun's DEFAULT_AGE_YR, so this also
      // places the default star at ~4.6 Gyr — no first-track special case needed.
      if (ageMax > ageMin) {
        ageFraction = clamp01((ageValue - ageMin) / (ageMax - ageMin));
        els.age.value = ageFraction;
      }
      rebuildAgeTicks();
    }
  } catch {
    if (token !== trackToken) return;
    /* non-fatal: keep the last good track + window; refresh() surfaces errors */
  }
  if (token !== trackToken) return;
  await refresh();
  updateLiveGateway();   // if we landed at the end (e.g. exiting WD), offer the gateway
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
    // NOT debounced, on purpose. The /state it fetches costs the same backend window
    // build as a /track (state_at also rebuilds _interp_window), so age-fling CPU is
    // real — but age intermediates are *wanted*: scrubbing age is the "watch the star
    // evolve" experience, where every in-between frame is the point. Mass/[Fe/H]
    // intermediates are waste (only the endpoint is wanted), which is why those defer.
    // ageFraction is the SOURCE OF TRUTH (like massValue): keep the EXACT snapped
    // float, never the range input's step-quantized value. Re-reading els.age.value
    // would round to the 0.0005 step and land just below a razor-sharp phase
    // boundary — the "snap to CHeB, readout says RGB" off-by-one. The thumb is set
    // from the exact value purely as a display (the browser may re-quantize *that*).
    ageFraction = snapAge(Number(els.age.value));
    els.age.value = ageFraction;
    // ageValue (the source of truth) is the EXACT absolute age this fraction maps to
    // — keep the exact float so refresh() fetches at it (preserving the off-by-one
    // fix) and so a later mass/[Fe/H] change preserves *this* age, not a re-quantized
    // one.
    ageValue = ageMin + ageFraction * (ageMax - ageMin);
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
    ageFraction = clamp01((ageValue - ageMin) / (ageMax - ageMin));
    els.age.value = ageFraction;
    refresh();
    updateLiveGateway();
  });

  // The stellar-endgame gateway: enter the WD or WR endgame from the button at the slider
  // limit; the bar's "Back" button leaves it (reversible — Locked decision #1).
  if (els.gatewayWd) els.gatewayWd.addEventListener("click", enterWD);
  if (els.gatewayWr) els.gatewayWr.addEventListener("click", enterWR);
  if (els.endgameBack) els.endgameBack.addEventListener("click", exitEndgame);

  await refreshMassRangeThenTrack();
}

init();
