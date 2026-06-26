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

// A "?" help glyph whose pedagogy shows on hover/focus (CSS tooltip via data-tip).
// Used for the JS-rendered readout rows (controls panel → open leftward); the
// static panels use the same markup written directly in index.html.
function help(tip) {
  return `<span class="help help-left" tabindex="0" data-tip="${escAttr(tip)}">?</span>`;
}

// A glyph-free hover tooltip: the text *is* the affordance (subtle dotted
// underline, no "?"). Used for the status-line tokens. Opens upward (tip-up)
// because the status line sits low in the panel.
function tipSpan(text, tip) {
  return `<span class="tip tip-up" tabindex="0" data-tip="${escAttr(tip)}">${escAttr(text)}</span>`;
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
      "EEP-interpolated in mass and [Fe/H]. Every panel above is built only on " +
      "this one interface; swapping it (e.g. for the data-free StubProvider) " +
      "would change nothing downstream."
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
  // so each one stays visible.
  buildTickStrip(els.ageMarks,
    opts.map((o) => ({ pos01: o.pos, label: o.label })), { stagger: true });
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
    if (token !== reqToken) return; // a newer request superseded this one
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
    if (token !== trackToken) return; // a newer track will drive its own refresh
    currentTrack = t;
    hr.setTrack(t);
    comp.setTrack(t);
    if (t.length) {
      ageMin = t[0].age_yr;
      ageMax = t[t.length - 1].age_yr;
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
  els.mass.addEventListener("input", () => {
    const r = massFromSliderInput(Number(els.mass.value));
    els.mass.value = r.pos;
    massValue = r.mass;
    setNum(els.massNum, fmt(massValue));
    debouncedTrack();
  });
  els.mass.addEventListener("change", () => debouncedTrack.flush());
  els.feh.addEventListener("input", () => {
    els.feh.value = snap(Number(els.feh.value), fehTickPos, fehMin, fehMax);
    setNum(els.fehNum, Number(els.feh.value).toFixed(2));
    debouncedMassRangeTrack();
  });
  els.feh.addEventListener("change", () => debouncedMassRangeTrack.flush());
  els.age.addEventListener("input", () => {
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
  });

  // Number inputs commit on change (Enter/blur) and BYPASS snapping — the exact
  // hand-typed value is honored, only clamped to the valid range.
  els.massNum.addEventListener("change", () => {
    if (els.massNum.value.trim() === "") return;
    const m = Number(els.massNum.value);
    if (!isFinite(m)) return;
    massValue = Math.min(Math.max(m, validMassMin), validMassMax);
    els.mass.value = clamp01(sliderFromMass(massValue));
    refreshTrack();
  });
  els.fehNum.addEventListener("change", () => {
    if (els.fehNum.value.trim() === "") return;
    const f = Number(els.fehNum.value);
    if (!isFinite(f)) return;
    els.feh.value = Math.min(Math.max(f, fehMin), fehMax);
    refreshMassRangeThenTrack();
  });
  els.ageNum.addEventListener("change", () => {
    if (els.ageNum.value.trim() === "" || !(ageMax > ageMin)) return;
    const gy = Number(els.ageNum.value);
    if (!isFinite(gy)) return;
    ageValue = gy * 1e9;   // the typed absolute age is the new desired value
    ageFraction = clamp01((ageValue - ageMin) / (ageMax - ageMin));
    els.age.value = ageFraction;
    refresh();
  });

  await refreshMassRangeThenTrack();
}

init();
