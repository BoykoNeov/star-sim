// Orchestration for the Phase 0 shell.
//
// The spine in action (STAR_SIM_SPEC.md §3 & §5): controls -> fetch one
// StellarState from the backend -> every panel re-renders from that single
// object. No panel knows what produced it.

import { createStar } from "./star.js";
import { createHR } from "./hr.js";
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
  massVal: document.getElementById("mass-val"),
  fehVal: document.getElementById("feh-val"),
  ageVal: document.getElementById("age-val"),
  readout: document.getElementById("readout"),
  status: document.getElementById("status"),
};

const star = createStar(document.getElementById("star-canvas"));
const hr = createHR(document.getElementById("hr-canvas"));

// --- slider <-> physical value mapping ---------------------------------------
let logMassMin = -1, logMassMax = Math.log10(40); // overwritten by /ranges
let ageFraction = 0.46;   // Sun's present age as a fraction of MS lifetime
let maxAge = 1e10;
// The valid mass span tightens with [Fe/H] (the backend has a dead low-mass
// corner at high metallicity — super-solar M-dwarfs have no evolved tracks).
// Refetched from /mass_range whenever [Fe/H] changes; used to clamp the slider
// so the UI never requests an out-of-grid point (spec §6). The slider itself
// doesn't know *why* the span moves — just that it does (§3).
let validMassMin = 0.1, validMassMax = 40;
let providerName = "";    // filled from /health, shown in the status line

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

// --- latest-request-wins -----------------------------------------------------
let reqToken = 0;

async function fetchJSON(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function renderReadout(s) {
  const rows = [
    ["Phase", s.phase],
    ["EEP", fmt(s.eep, 4)],
    ["Age", gyr(s.age_yr)],
    ["L", `${fmt(s.L_lsun)} L☉`],
    ["Teff", `${fmt(s.Teff_K, 4)} K`],
    ["R", `${fmt(s.R_rsun)} R☉`],
    ["log g", fmt(s.logg, 3)],
    ["X / Y / Z surf", `${fmt(s.X_surf)} / ${fmt(s.Y_surf)} / ${fmt(s.Z_surf, 2)}`],
    ["X / Y / Z core", `${fmt(s.X_core)} / ${fmt(s.Y_core)} / ${fmt(s.Z_core, 2)}`],
    ["v_rot", s.v_rot_kms === null ? "n/a" : `${fmt(s.v_rot_kms)} km/s`],
    ["activity", s.activity === null ? "n/a" : fmt(s.activity, 2)],
  ];
  els.readout.innerHTML = rows
    .map(([k, v]) => `<span class="k">${k}</span><span class="v">${v}</span>`)
    .join("");
}

async function refresh() {
  const token = ++reqToken;
  const mass = massFromSlider();
  const feh = Number(els.feh.value);
  const age = ageFraction * maxAge;

  // If [Fe/H] pushed the valid floor above the thumb, snap the thumb up to the
  // floor so it can't visually sit in the disabled (dead-corner) region.
  const clampedPos = sliderFromMass(mass);
  if (Math.abs(Number(els.mass.value) - clampedPos) > 1e-6) els.mass.value = clampedPos;

  els.massVal.textContent = fmt(mass);
  els.fehVal.textContent = feh.toFixed(2);
  els.ageVal.textContent = gyr(age);

  try {
    const s = await fetchJSON(
      `/state?mass=${mass}&feh=${feh}&age=${age}`,
    );
    if (token !== reqToken) return; // a newer request superseded this one
    star.update(s);
    hr.update(s);
    renderReadout(s);
    els.status.style.color = teffToCSS(s.Teff_K);
    els.status.textContent = `OK · ${s.phase}` + (providerName ? ` · ${providerName}` : "");
  } catch (err) {
    if (token !== reqToken) return;
    els.status.style.color = "#ff6b6b";
    els.status.textContent = `Error: ${err.message}`;
  }
}

// When mass/feh change, the valid age window changes too.
async function refreshAgeRangeThenState() {
  const mass = massFromSlider();
  const feh = Number(els.feh.value);
  try {
    const r = await fetchJSON(`/age_range?mass=${mass}&feh=${feh}`);
    maxAge = r.max;
  } catch {
    /* keep previous maxAge; refresh() will surface any real error */
  }
  await refresh();
}

// When [Fe/H] changes, the valid *mass* span can change (the dead corner), so
// refresh it before the age window — refreshAgeRangeThenState() reads the clamped
// mass, so the order matters.
async function refreshMassRangeThenState() {
  const feh = Number(els.feh.value);
  try {
    const mr = await fetchJSON(`/mass_range?feh=${feh}`);
    validMassMin = mr.min;
    validMassMax = mr.max;
  } catch {
    /* keep previous span; refresh() will surface any real error */
  }
  await refreshAgeRangeThenState();
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
    els.feh.step = 0.05; els.feh.value = 0;

    els.age.min = 0; els.age.max = 1; els.age.step = 0.0005;
    els.age.value = ageFraction;
  } catch (err) {
    els.status.style.color = "#ff6b6b";
    els.status.textContent =
      `Cannot reach backend (${err.message}). Start it with: ` +
      `cd backend && uvicorn star_sim.api:app --reload`;
    return;
  }

  els.mass.addEventListener("input", refreshAgeRangeThenState);
  els.feh.addEventListener("input", refreshMassRangeThenState);
  els.age.addEventListener("input", () => {
    ageFraction = Number(els.age.value);
    refresh();
  });

  await refreshMassRangeThenState();
}

init();
