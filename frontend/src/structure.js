// Real interior-structure panel — the honest successor to Lane–Emden.
//
// Where lane.js draws an IDEALIZED static polytrope driven by an index n alone,
// this panel draws the REAL radial structure of the selected star — ρ(r), T(r),
// X(r) and the true convective/radiative split — from an offline MESA profile
// snapshot served at /structure?mass=&feh=&age=. So it IS a live consumer of the
// marker (update(state) reads mass/[Fe/H]/age off it and refetches), unlike lane.js.
//
// /structure bypasses PROVIDER (a derived view, not a StellarState — like
// /polytrope and /spectrum). It snaps to the nearest saved snapshot (a handful
// exist, not a continuum), so the panel JUMPS between profiles as age scrubs and
// always labels the true snapshot it is showing. When no grid covers the selected
// star it snaps to the nearest available (today: 1 M☉ solar) and says so plainly —
// never pretending a 20 M☉ request is really the 1 M☉ profile it drew.
//
// The two canonical polytropes (n = 3/2, n = 3) are overlaid as fixed dashed
// references — NOT fitted — so the real density can be seen departing from them
// (tight in the radiative core, pulling away in the convective envelope for the Sun).

import { fitCanvas } from "./canvas.js";

const PAD_L = 40, PAD_R = 12, PAD_T = 14, PAD_B = 30;

const COL_RHO = "#ff9966";    // ρ/ρc — the prominent, filled real-density curve
const COL_T = "#e5555f";      // T/Tc
const COL_P = "#9a7fd0";      // P/Pc — the steepest curve (∝ ρ·T, plunges below ρ)
const COL_X = "#5fbf7f";      // hydrogen mass fraction X(r)
const COL_POLY = "#7f8aa3";   // the canonical polytrope references (dashed)
const COL_CONV = "rgba(120,170,255,0.16)";  // convective-zone shading

// A requested vs snapped mass this close is "on grid" (no snapped-far note).
const MASS_MATCH_TOL = 0.05;
// The metallicity grid is coarse (a few [Fe/H] buckets, and only at 1 M☉), so a
// request this far from the nearest saved [Fe/H] is a real snap worth flagging.
const FEH_MATCH_TOL = 0.3;

function fmt(x, sig = 3) {
  if (x === null || x === undefined || !isFinite(x)) return "—";
  const a = Math.abs(x);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return x.toExponential(2);
  return Number(x.toPrecision(sig)).toString();
}

function ageStr(yr) {
  if (yr == null || !isFinite(yr)) return "—";
  if (yr >= 1e9) return `${(yr / 1e9).toPrecision(3)} Gyr`;
  if (yr >= 1e6) return `${(yr / 1e6).toPrecision(3)} Myr`;
  return `${yr.toExponential(2)} yr`;
}

function escAttr(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
const help = (tip) => `<span class="help" tabindex="0" data-tip="${escAttr(tip)}">?</span>`;

export function createStructure({ api }) {
  const canvas = document.getElementById("structure-canvas");
  const caption = document.getElementById("structure-caption");
  const readout = document.getElementById("structure-readout");
  const note = document.getElementById("structure-note");
  if (!canvas) return { update() {}, resize() {} };

  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, 380, 300));

  let data = null;         // last /structure result
  let reqMass = null;      // the mass we asked for (to detect a far snap)
  let reqFeh = null;       // the [Fe/H] we asked for (to detect a far metallicity snap)
  let unavailable = false; // 503 — no profiles generated yet

  // --- latest-wins + debounce (the lane.js / spectrum.js idiom, own token) ---
  let token = 0;
  let debounce = null;
  let lastKey = null;

  async function fetchStructure(mass, feh, age) {
    const mine = ++token;
    try {
      const res = await fetch(
        `${api}/structure?mass=${mass}&feh=${feh}&age=${age}`);
      if (res.status === 503) {
        if (mine !== token) return;
        unavailable = true; data = null; draw(); renderText();
        return;
      }
      if (!res.ok) throw new Error(`/structure -> ${res.status}`);
      const d = await res.json();
      if (mine !== token) return;   // a newer star superseded this one
      unavailable = false;
      data = d;
      draw();
      renderText();
    } catch {
      if (mine !== token) return;
      /* non-fatal: keep the last good profile on screen */
    }
  }

  // A live consumer: read (mass, [Fe/H], age) off the marker and refetch (debounced),
  // deduped on a rounded key so an age scrub that snaps to the SAME snapshot doesn't
  // hammer the endpoint. Endgame states (WD/WR/SN) have no interior-structure grid, so
  // the panel keeps its last main-sequence profile and simply doesn't refetch.
  function update(state) {
    if (!state) return;
    const mass = state.mass_init_msun, feh = state.feh_init ?? 0, age = state.age_yr;
    if (mass == null || age == null || !(age > 0)) return;
    reqMass = mass;
    reqFeh = feh;
    // The backend snaps to a handful of ages, so round the request key coarsely —
    // sub-percent age moves cannot change which snapshot is nearest.
    const key = `${mass.toFixed(3)}|${feh.toFixed(2)}|${age.toExponential(2)}`;
    if (key === lastKey) return;
    lastKey = key;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => fetchStructure(mass, feh, age), 110);
  }

  // --- drawing -------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!data) return;

    const xOf = (r) => PAD_L + r * (W - PAD_L - PAD_R);        // r in [0,1] = r/R
    const yOf = (v) => H - PAD_B - v * (H - PAD_T - PAD_B);    // v in [0,1]

    // convective-zone shading (behind everything).
    for (const [a, b] of data.convective_zones || []) {
      ctx.fillStyle = COL_CONV;
      ctx.fillRect(xOf(a), PAD_T, xOf(b) - xOf(a), H - PAD_T - PAD_B);
    }

    drawGrid(xOf, yOf);

    // the two canonical polytrope references (dashed, thin) — drawn under the real
    // curves so the star's own density reads on top.
    ctx.setLineDash([4, 3]); ctx.strokeStyle = COL_POLY; ctx.lineWidth = 1.25;
    for (const p of data.polytropes || []) {
      if (!p.r_over_R || !p.r_over_R.length) continue;
      ctx.beginPath();
      p.r_over_R.forEach((r, i) =>
        i === 0 ? ctx.moveTo(xOf(r), yOf(p.rho_over_rhoc[i]))
                : ctx.lineTo(xOf(r), yOf(p.rho_over_rhoc[i])));
      ctx.stroke();
    }
    ctx.setLineDash([]);

    const r = data.r_over_R;
    // P/Tc, T/Tc and X(r) — thinner secondary lines. P/Pc ∝ ρ·T falls steepest
    // (∝ θ^(n+1) for a polytrope vs θ^n for ρ), so it reads as the lowest curve.
    line(r, data.P_over_Pc, COL_P, 1.25, xOf, yOf);
    line(r, data.T_over_Tc, COL_T, 1.5, xOf, yOf);
    line(r, data.X, COL_X, 1.5, xOf, yOf);

    // ρ/ρc — filled area + bold stroke, the prominent real curve (drawn last, on top).
    ctx.beginPath();
    r.forEach((rr, i) =>
      i === 0 ? ctx.moveTo(xOf(rr), yOf(data.rho_over_rhoc[i]))
              : ctx.lineTo(xOf(rr), yOf(data.rho_over_rhoc[i])));
    ctx.lineTo(xOf(r[r.length - 1]), yOf(0));
    ctx.lineTo(xOf(r[0]), yOf(0));
    ctx.closePath();
    ctx.fillStyle = "rgba(255,153,102,0.20)"; ctx.fill();
    line(r, data.rho_over_rhoc, COL_RHO, 2, xOf, yOf);
  }

  function line(xs, ys, color, width, xOf, yOf) {
    if (!ys) return;
    ctx.beginPath();
    xs.forEach((x, i) => i === 0 ? ctx.moveTo(xOf(x), yOf(ys[i]))
                                 : ctx.lineTo(xOf(x), yOf(ys[i])));
    ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash([]); ctx.stroke();
  }

  function drawGrid(xOf, yOf) {
    ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);
    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "right";
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      const y = yOf(v);
      ctx.globalAlpha = 0.30;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD_R, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(v.toFixed(2), PAD_L - 5, y + 4);
    }
    ctx.textAlign = "center";
    for (const t of [0, 0.25, 0.5, 0.75, 1]) {
      const x = xOf(t);
      ctx.globalAlpha = 0.25;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(t.toFixed(2), x, H - PAD_B + 14);
    }
    ctx.fillText("r / R  (normalized radius)", W / 2, H - 6);
    ctx.save();
    ctx.translate(11, (H - PAD_B + PAD_T) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("fraction of central value", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";
  }

  // --- caption / readout / note --------------------------------------------
  function renderText() {
    if (unavailable) {
      caption.textContent =
        "No MESA interior-structure profiles are on disk yet — generate them once " +
        "(see backend/docs/mesa_structure_recipe.md).";
      readout.innerHTML = ""; note.textContent = "";
      return;
    }
    if (!data) return;
    const snap = data.snapped;
    // A low-mass star can be FULLY convective — one zone spanning centre→surface. That
    // is a third regime (vs the Sun's radiative core / a massive star's convective
    // core), and it is the rare case where the idealized n=3/2 polytrope actually
    // matches the real profile (the real ρ hugs the dashed n=1.5 line) — the inversion
    // of the usual "the departure is the lesson".
    const zones = data.convective_zones || [];
    const fullyConvective =
      zones.length === 1 && zones[0][0] < 0.02 && zones[0][1] > 0.95;
    // State the core's STRUCTURE type → its canonical idealization — NOT a fit claim
    // (for the Sun/massive stars the real ρ visibly departs from that polytrope, which
    // is the whole point; the fully-convective M dwarf is the honest exception).
    const nName = fullyConvective
      ? "fully convective → canonical n = 3/2 — the rare case the real profile follows it"
      : data.expected_n === 1.5 ? "convective core → canonical n = 3/2"
                                : "radiative core → canonical n = 3";
    caption.innerHTML =
      `Nearest saved snapshot: <b>${fmt(snap.mass_msun)} M☉</b>, ` +
      `[Fe/H] ${snap.feh >= 0 ? "+" : ""}${snap.feh.toFixed(2)}, ` +
      `<b>${ageStr(snap.age_yr)}</b> — ${snap.phase}. <b>${nName}</b>.`;

    const c = data.central;
    const convBase = fullyConvective
      ? null   // no envelope base — the star convects all the way to the centre
      : zones.map((z) => z[0]).sort((a, b) => b - a)[0];   // outermost envelope base
    const rows = [
      ["ρc", "central density — how tightly the star's mass is packed into its core. The Sun's is ~150 g/cm³; a not-solar-calibrated MESA model lands near it.", `${fmt(c.rho_c_gcc)} g/cm³`],
      ["Tc", "central temperature — sets the nuclear burning rate. Hydrogen fusion needs ~10⁷ K; the Sun's core is ~1.5×10⁷ K.", `${fmt(c.T_c_K)} K`],
      ["Pc", "central pressure (dyne/cm²) — the weight of the whole star bearing down on its centre, balanced by gas + radiation pressure.", `${fmt(c.P_c_dyne)}`],
      ["R", "the model's surface radius, in solar radii.", `${fmt(c.R_surface_rsun)} R☉`],
      ["conv. base", "radius (as a fraction of R) where the outer convective envelope begins — below it the star is radiative. The single-index polytrope has no such boundary. It depends strongly on metallicity: fewer metals means a more transparent envelope, so the convection zone is shallower — a metal-poor ([Fe/H] = −1) Sun's envelope is a thin surface sliver, a metal-rich one's reaches deeper.", convBase != null ? convBase.toFixed(3) : "—"],
    ];
    readout.innerHTML = rows
      .map(([k, d, v]) =>
        `<div class="row"><div class="term">${k} ${help(d)}</div>` +
        `<div class="v">${v}</div></div>`)
      .join("");

    // Snapped-far note: the request's mass and/or [Fe/H] is well off the grid we have
    // (the mass grid is 0.25–25 M☉ at solar Z; the metallicity grid is only at 1 M☉).
    const massFar = reqMass != null && Math.abs(reqMass - snap.mass_msun) > MASS_MATCH_TOL;
    const fehFar = reqFeh != null && Math.abs(reqFeh - snap.feh) > FEH_MATCH_TOL;
    if (massFar && fehFar) {
      note.textContent =
        `No MESA interior grid for a ${fmt(reqMass)} M☉, [Fe/H] ${reqFeh >= 0 ? "+" : ""}` +
        `${reqFeh.toFixed(1)} star — showing the nearest available model ` +
        `(${fmt(snap.mass_msun)} M☉, [Fe/H] ${snap.feh >= 0 ? "+" : ""}${snap.feh.toFixed(1)}). ` +
        `Structure varies with both, so this is only a guide.`;
    } else if (massFar) {
      note.textContent =
        `No MESA interior grid for a ${fmt(reqMass)} M☉ star — showing the nearest ` +
        `available model (${fmt(snap.mass_msun)} M☉). The structure of a very ` +
        `different-mass star can differ substantially.`;
    } else if (fehFar) {
      note.textContent =
        `No MESA interior grid at [Fe/H] ${reqFeh >= 0 ? "+" : ""}${reqFeh.toFixed(1)} for ` +
        `this mass — showing the nearest metallicity (${fmt(snap.mass_msun)} M☉, ` +
        `[Fe/H] ${snap.feh >= 0 ? "+" : ""}${snap.feh.toFixed(1)}). Metallicity sets the ` +
        `convective-envelope depth, so this is only a guide.`;
    } else {
      note.textContent = "";
    }
  }

  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

  return { update, resize };
}
