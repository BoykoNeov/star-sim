// Lane–Emden interior-structure panel (STAR_SIM_SPEC.md §8).
//
// A SIBLING to the StellarState spine, not a consumer of it. It draws a single
// *static* polytrope — P = K·ρ^(1+1/n) — solved on the backend (/polytrope?n=)
// and is driven by the polytropic index n ALONE: it is deliberately independent
// of the mass/[Fe/H]/age controls and never touches refresh()/refreshTrack().
// MIST gives no convective/radiative split, so auto-deriving n from the star and
// drawing it as "the star's interior" would be faking a fit — instead n is the
// user's to set, and the presets carry the physics as honest *labels*.
//
// The payoff plot (§8) is the density profile ρ/ρc = θⁿ: raise n and the star
// becomes dramatically more centrally concentrated. θ (the Lane–Emden function)
// is shown as a fainter secondary line.

import { fitCanvas } from "./canvas.js";

const PAD_L = 40, PAD_R = 12, PAD_T = 14, PAD_B = 30;

const COL_RHO = "#ff9966";   // density ρ/ρc — the prominent, filled curve
const COL_THETA = "#5b8def"; // θ — the fainter dashed line

// Landmark indices worth snapping to, each with the physics it stands for (§8).
// These are the *labels* that carry the teaching; the curve itself is honest math.
const PRESETS = [
  { n: 0,   label: "0",   meaning: "n = 0 · uniform density — the crudest guess (the same density everywhere). No real star is this simple; it is the anchor at one extreme." },
  { n: 1,   label: "1",   meaning: "n = 1 · the exact closed form θ = sin ξ / ξ — a clean mathematical checkpoint, not a particular kind of star." },
  { n: 1.5, label: "1.5", meaning: "n = 1.5 · fully convective stars (red dwarfs, giant envelopes) and non-relativistic degenerate gas (white-dwarf & brown-dwarf cores)." },
  { n: 3,   label: "3",   meaning: "n = 3 · the textbook (Eddington) approximation to a Sun-like radiative star — and, by the same maths, a relativistic degenerate gas: a white dwarf near the Chandrasekhar mass. Its centre is ~54× denser than its average (the real Sun: ~110×)." },
  { n: 5,   label: "5",   meaning: "n = 5 · the gas is so compressible the star has no surface at all — its radius runs to infinity. The mathematical edge of the family." },
];
const N_MIN = 0, N_MAX = 5, N_DEFAULT = 3;

function fmt(x, sig = 4) {
  if (x === null || x === undefined || !isFinite(x)) return "—";
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return x.toExponential(2);
  return Number(x.toPrecision(sig)).toString();
}

function escAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
// "?" help glyph; the shared tooltip layer (tooltip.js) places it viewport-clamped.
const help = (tip) =>
  `<span class="help" tabindex="0" data-tip="${escAttr(tip)}">?</span>`;

// Physical gloss for the caption under the slider — exact for a landmark n,
// generic otherwise.
function meaningOf(n) {
  for (const p of PRESETS) if (Math.abs(p.n - n) < 1e-6) return p.meaning;
  return `n = ${fmt(n, 3)} · between the landmarks — higher n means more compressible gas and a more centrally concentrated star.`;
}

export function createLane({ api }) {
  const canvas = document.getElementById("lane-canvas");
  const slider = document.getElementById("lane-n");
  const num = document.getElementById("lane-n-num");
  const ticksEl = document.getElementById("lane-n-ticks");
  const marksEl = document.getElementById("lane-n-marks");
  const caption = document.getElementById("lane-caption");
  const readout = document.getElementById("lane-readout");
  if (!canvas) return { resize() {} };

  // W/H are `let` so resize() can re-fit to a new display width; draw() rebuilds
  // its xOf/yOf from the current W/H each call, so a resize just needs a redraw.
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, 380, 300));

  let profile = null;   // last /polytrope result

  // --- slider setup --------------------------------------------------------
  slider.min = N_MIN; slider.max = N_MAX; slider.step = 0.01;
  slider.value = N_DEFAULT;
  num.min = N_MIN; num.max = N_MAX; num.step = 0.1; num.value = N_DEFAULT;

  // Snap marks (reuses the global .ticks/.tick strip styling).
  ticksEl.innerHTML = PRESETS
    .map((p) => `<option value="${p.n}" label="${p.label}"></option>`).join("");
  const span = N_MAX - N_MIN;
  marksEl.innerHTML = PRESETS
    .map((p) => {
      const left = ((p.n - N_MIN) / span * 100).toFixed(2);
      return `<span class="tick" style="left:${left}%">` +
        `<span class="tick-label">${p.label}</span></span>`;
    }).join("");

  // Snap a raw slider value to the nearest preset within a small window; every
  // value between presets stays reachable (the number input bypasses snapping).
  function snap(value) {
    const thresh = span * 0.015;   // matches the spine's sliders — magnetic, not grabby
    let best = value, bestD = thresh;
    for (const p of PRESETS) {
      const d = Math.abs(value - p.n);
      if (d < bestD) { bestD = d; best = p.n; }
    }
    return best;
  }

  // --- latest-wins + debounce ----------------------------------------------
  // The n-slider drag fires fast; debounce so we don't hammer the endpoint, and
  // a token guards against a slow response overwriting a newer one (same pattern
  // the spine's fetches use — but on its OWN token, fully decoupled from them).
  let token = 0;
  let debounce = null;

  async function fetchProfile(n) {
    const mine = ++token;
    try {
      const res = await fetch(`${api}/polytrope?n=${n}`);
      if (!res.ok) throw new Error(`/polytrope -> ${res.status}`);
      const p = await res.json();
      if (mine !== token) return;   // a newer n superseded this one
      profile = p;
      draw();
      renderReadout();
    } catch {
      if (mine !== token) return;
      /* non-fatal: keep the last good profile on screen */
    }
  }

  function request(n, immediate = false) {
    caption.textContent = meaningOf(n);
    if (debounce) clearTimeout(debounce);
    if (immediate) { fetchProfile(n); return; }
    debounce = setTimeout(() => fetchProfile(n), 110);
  }

  // --- drawing -------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!profile) return;

    const finite = profile.has_finite_surface;
    const xi = profile.xi;
    // x axis: normalized radius r/R = ξ/ξ₁ when there's a surface; raw ξ (which
    // runs to ∞) when there isn't (n ≥ 5) — the advisor-recommended honest axis.
    const xDen = finite ? profile.xi1 : xi[xi.length - 1];
    const xLabel = finite ? "r / R  (normalized radius)" : "ξ  (no finite surface)";

    const xOf = (i) => PAD_L + (xi[i] / xDen) * (W - PAD_L - PAD_R);
    const yOf = (v) => H - PAD_B - v * (H - PAD_T - PAD_B);   // v in [0,1]

    drawGrid(finite, xDen, xLabel, xOf, yOf);

    // ρ/ρc — filled area + stroke, the prominent curve.
    ctx.beginPath();
    profile.rho_over_rhoc.forEach((v, i) =>
      i === 0 ? ctx.moveTo(xOf(i), yOf(v)) : ctx.lineTo(xOf(i), yOf(v)));
    ctx.lineTo(xOf(xi.length - 1), yOf(0));
    ctx.lineTo(xOf(0), yOf(0));
    ctx.closePath();
    ctx.fillStyle = "rgba(255,153,102,0.22)";
    ctx.fill();
    ctx.beginPath();
    profile.rho_over_rhoc.forEach((v, i) =>
      i === 0 ? ctx.moveTo(xOf(i), yOf(v)) : ctx.lineTo(xOf(i), yOf(v)));
    ctx.strokeStyle = COL_RHO; ctx.lineWidth = 2; ctx.setLineDash([]); ctx.stroke();

    // θ — fainter dashed line.
    ctx.beginPath();
    profile.theta.forEach((v, i) =>
      i === 0 ? ctx.moveTo(xOf(i), yOf(v)) : ctx.lineTo(xOf(i), yOf(v)));
    ctx.strokeStyle = COL_THETA; ctx.lineWidth = 1.5; ctx.setLineDash([4, 3]);
    ctx.stroke(); ctx.setLineDash([]);
  }

  function drawGrid(finite, xDen, xLabel, xOf, yOf) {
    ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);

    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";
    // y ticks 0..1
    ctx.textAlign = "right";
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      const y = yOf(v);
      ctx.globalAlpha = 0.30;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(v.toFixed(2), PAD_L - 5, y + 4);
    }
    // x ticks: 0..1 normalized radius, or 0..ξmax raw.
    ctx.textAlign = "center";
    const xTicks = finite ? [0, 0.25, 0.5, 0.75, 1] : niceTicks(xDen);
    for (const t of xTicks) {
      const frac = finite ? t : t / xDen;
      const x = PAD_L + frac * (W - PAD_L - PAD_R);
      ctx.globalAlpha = 0.25;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(finite ? t.toFixed(2) : String(t), x, H - PAD_B + 14);
    }
    ctx.fillText(xLabel, W / 2, H - 6);

    // y axis title
    ctx.save();
    ctx.translate(11, (H - PAD_B + PAD_T) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("θ  ·  ρ/ρc", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
  }

  // A few round x ticks for the raw-ξ (no-surface) axis.
  function niceTicks(max) {
    const step = max > 30 ? 10 : max > 12 ? 5 : 2;
    const out = [];
    for (let t = 0; t <= max + 1e-9; t += step) out.push(t);
    return out;
  }

  // --- readout (ξ₁ and the dimensionless invariants) -----------------------
  function renderReadout() {
    if (!profile) return;
    const p = profile;
    // Central concentration ρc/ρ̄ = ξ₁³ / (3·(−ξ₁²θ'₁)) — 1 for n=0 (uniform),
    // ~54 for the n=3 standard model, → ∞ as n → 5. A vivid single number for §8.
    const concentration = p.has_finite_surface
      ? (p.xi1 ** 3) / (3 * p.mass_invariant) : Infinity;
    const rows = [
      ["n", "polytropic index in P = K·ρ^(1+1/n) — the single knob for this panel; bigger n means more compressible gas and a denser-cored star.", fmt(p.n, 3)],
      ["ξ₁", "first zero of θ — the star's surface in dimensionless units (multiply by the physical scale length to recover the real radius). n ≥ 5 has none (radius → ∞).",
        p.has_finite_surface ? fmt(p.xi1, 5) : "∞"],
      ["−ξ₁²θ′(ξ₁)", "Chandrasekhar's dimensionless mass quantity; combined with K and the central density ρc it fixes the star's total mass.",
        p.has_finite_surface ? fmt(p.mass_invariant, 5) : "—"],
      ["ρc / ρ̄", "central-to-mean density ratio — how centrally concentrated the star is. 1 = uniform (n=0); ~54 for the n=3 standard model (the real Sun is ~110, so this model lands within roughly 2×).",
        p.has_finite_surface ? fmt(concentration, 4) : "∞"],
    ];
    readout.innerHTML = rows
      .map(([k, d, v]) =>
        `<div class="row"><div class="term">${k} ${help(d)}</div>` +
        `<div class="v">${v}</div></div>`)
      .join("");
  }

  // --- events --------------------------------------------------------------
  slider.addEventListener("input", () => {
    const n = snap(Number(slider.value));
    slider.value = n;
    if (document.activeElement !== num) num.value = Number(n.toPrecision(4));
    request(n);
  });
  num.addEventListener("change", () => {
    if (num.value.trim() === "") return;
    let n = Number(num.value);
    if (!isFinite(n)) return;
    n = Math.min(Math.max(n, N_MIN), N_MAX);
    slider.value = n;
    request(n, true);
  });

  // Re-fit to a new display size (responsive layout) and redraw the last profile.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

  // first paint
  caption.textContent = meaningOf(N_DEFAULT);
  request(N_DEFAULT, true);

  return { resize };
}
