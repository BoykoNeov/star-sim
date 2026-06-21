// Orchestration for the Phase 0 shell.
//
// The spine in action (STAR_SIM_SPEC.md §3 & §5): controls -> fetch one
// StellarState from the backend -> every panel re-renders from that single
// object. No panel knows what produced it.

import { createStar } from "./star.js";
import { createHR } from "./hr.js";
import { createComp } from "./comp.js";
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
const hr = createHR(document.getElementById("hr-canvas"));
const comp = createComp(document.getElementById("comp-canvas"));

// --- slider <-> physical value mapping ---------------------------------------
let logMassMin = -1, logMassMax = Math.log10(40); // overwritten by /ranges
let ageFraction = 0.46;   // slider position 0..1, mapped into [ageMin, ageMax]
// The age window is read off the TRACK itself (first/last row's age_yr) — one
// source of truth, so the slider domain and the composition panel's EEP span can
// never disagree. They used to come from a separate, *unguarded* /age_range fetch:
// under overlapping requests `maxAge` could stay stuck on a stale mass while the
// (token-guarded) track settled to the new one — that was the "composition ends
// before the age slider" mismatch. age_yr is a StellarState field, so reading the
// window off the track is §3-clean (no provider internals leak).
let ageMin = 0, ageMax = 1e10;
let firstTrackLoaded = false;
const DEFAULT_AGE_YR = 4.6e9;   // land the default star (the Sun) at ~4.6 Gyr
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
let massTickPos = [], fehTickPos = [], ageTickPos = [];
const clamp01 = (x) => Math.min(1, Math.max(0, x));

// The slider position spans the full bounding box; the physical mass is then
// clamped to the span valid at the current [Fe/H] — a soft floor that moves with
// metallicity.
const massFromSlider = () =>
  Math.min(Math.max(
    10 ** (logMassMin + Number(els.mass.value) * (logMassMax - logMassMin)),
    validMassMin), validMassMax);
const sliderFromMass = (m) =>
  (Math.log10(m) - logMassMin) / (logMassMax - logMassMin);

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

// Populate a <datalist> (a native, browser-dependent tick hint) from {pos,label}.
// Kept as a bonus; the visible, reliable marks are the custom strip below.
function buildDatalist(el, opts) {
  el.innerHTML = opts
    .map((o) => `<option value="${o.pos}"${o.label ? ` label="${o.label}"` : ""}></option>`)
    .join("");
}

// Render the visible snap marks (a tick line + small label) under a slider. The
// strip is inset by the thumb radius in CSS, so pos01 (0..1) lines up under the
// thumb. Labels are collision-skipped (in normalized space, layout-independent)
// so clustered landmarks — common on the age axis — don't overprint.
function buildTickStrip(el, marks) {
  if (!el) return;
  const sorted = marks.slice().sort((a, b) => a.pos01 - b.pos01);
  let lastLabel = -1;
  el.innerHTML = sorted
    .map((m) => {
      const showLabel = m.label != null && m.pos01 - lastLabel >= 0.08;
      if (showLabel) lastLabel = m.pos01;
      const lbl = showLabel
        ? `<span class="tick-label">${escAttr(m.label)}</span>` : "";
      return `<span class="tick" style="left:${(m.pos01 * 100).toFixed(2)}%">${lbl}</span>`;
    })
    .join("");
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

// Round masses worth snapping to, filtered to the span valid at this [Fe/H].
function rebuildMassTicks() {
  const opts = [];
  for (const m of [0.1, 0.2, 0.3, 0.5, 0.8, 1, 1.5, 2, 3, 5, 8, 12, 20, 30, 40]) {
    if (m < validMassMin - 1e-9 || m > validMassMax + 1e-9) continue;
    opts.push({ pos: clamp01(sliderFromMass(m)), label: `${m}` });
  }
  massTickPos = opts.map((o) => o.pos);
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
      if (prev !== null) pts.push({ age: s.age_yr, label: s.phase });
      prev = s.phase;
    }
  }
  let tip = track[0];
  for (const s of track) if (s.R_rsun > tip.R_rsun) tip = s;
  pts.push({ age: tip.age_yr, label: "RGB tip" });
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
  const opts = [];
  for (const p of criticalAges(currentTrack)) {
    const pos = clamp01((p.age - ageMin) / span);
    if (opts.some((o) => Math.abs(o.pos - pos) < 0.01)) continue; // dedup clustered
    opts.push({ pos, label: p.label });
  }
  ageTickPos = opts.map((o) => o.pos);
  buildDatalist(els.ageTicks, opts);
  buildTickStrip(els.ageMarks, opts.map((o) => ({ pos01: o.pos, label: o.label })));
}

// Write a number input's display value without fighting the user mid-type.
function setNum(el, value) {
  if (document.activeElement === el) return;
  el.value = value;
}
const gyrNum = (yr) => Number((yr / 1e9).toPrecision(4));

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
      "evolutionary stage — MS: core-hydrogen-burning main sequence · SGB/RGB: sub-/red-giant branch · CHeB: core-helium burning",
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
  const mass = massFromSlider();
  const feh = Number(els.feh.value);
  const age = ageMin + ageFraction * (ageMax - ageMin);

  // If [Fe/H] pushed the valid floor above the thumb, snap the thumb up to the
  // floor so it can't visually sit in the disabled (dead-corner) region.
  const clampedPos = sliderFromMass(mass);
  if (Math.abs(Number(els.mass.value) - clampedPos) > 1e-6) els.mass.value = clampedPos;

  setNum(els.massNum, fmt(mass));
  setNum(els.fehNum, feh.toFixed(2));
  setNum(els.ageNum, gyrNum(age));

  try {
    const s = await fetchJSON(
      `/state?mass=${mass}&feh=${feh}&age=${age}`,
    );
    if (token !== reqToken) return; // a newer request superseded this one
    star.update(s);
    hr.update(s);
    comp.update(s);
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
  const mass = massFromSlider();
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
      els.ageNum.max = gyrNum(ageMax);
      // First track only: place the default star at its headline age (the Sun's
      // ~4.6 Gyr) rather than at a raw fraction — the window no longer starts at
      // age 0, so 0.46 would no longer mean "4.6 Gyr".
      if (!firstTrackLoaded && ageMax > ageMin) {
        firstTrackLoaded = true;
        ageFraction = clamp01((DEFAULT_AGE_YR - ageMin) / (ageMax - ageMin));
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
  // fetch behind.
  els.mass.addEventListener("input", () => {
    els.mass.value = snap(Number(els.mass.value), massTickPos, 0, 1);
    setNum(els.massNum, fmt(massFromSlider()));
    refreshTrack();
  });
  els.feh.addEventListener("input", () => {
    els.feh.value = snap(Number(els.feh.value), fehTickPos, fehMin, fehMax);
    setNum(els.fehNum, Number(els.feh.value).toFixed(2));
    refreshMassRangeThenTrack();
  });
  els.age.addEventListener("input", () => {
    els.age.value = snap(Number(els.age.value), ageTickPos, 0, 1);
    ageFraction = Number(els.age.value);
    refresh();
  });

  // Number inputs commit on change (Enter/blur) and BYPASS snapping — the exact
  // hand-typed value is honored, only clamped to the valid range.
  els.massNum.addEventListener("change", () => {
    if (els.massNum.value.trim() === "") return;
    const m = Number(els.massNum.value);
    if (!isFinite(m)) return;
    const clamped = Math.min(Math.max(m, validMassMin), validMassMax);
    els.mass.value = clamp01(sliderFromMass(clamped));
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
    ageFraction = clamp01((gy * 1e9 - ageMin) / (ageMax - ageMin));
    els.age.value = ageFraction;
    refresh();
  });

  await refreshMassRangeThenTrack();
}

init();
