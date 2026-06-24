// Synthetic-spectrum panel (STAR_SIM_SPEC.md §5).
//
// A SIBLING-flavoured panel: it shows the synthetic spectrum (flux vs wavelength,
// with real absorption lines) for the current star's (Teff, log g, [Fe/H]) — the
// very spectrum color.js already collapses into the star's one-pixel colour. The
// spectra were baked once from MSG (Townsend's spectral grids) into a flux cube;
// the backend interpolates that cube (no MSG/Fortran at run time) and serves it at
// /spectrum?teff=&logg=&feh=. So although /spectrum bypasses PROVIDER (a derived
// view, not a StellarState — like /polytrope), this panel IS a live consumer of
// the state: update(state) reads Teff_K/logg/feh_init off the marker and refetches.
//
// Display choice: flux is NORMALIZED to its own peak. Absolute flux scales ~3000×
// from a cool M to a hot O star (that brightness lives in the 3D star + the L
// readout); here the story is the CONTINUUM SLOPE (which way the blackbody tilts)
// and the ABSORPTION LINES cut into it — both preserved by per-spectrum
// normalization, neither legible if a hot star pinned the cool ones to the floor.
//
// The visible band (3800–7800 Å) is shaded with the true per-wavelength spectral
// colour (color.js' CIE fit), so the panel reads as a spectrograph's rainbow with
// dark lines carved out of it; UV/near-IR flanks are shown muted-grey.

import { fitCanvas } from "./canvas.js";
import { wavelengthToCSS } from "./color.js";

const PAD_L = 44, PAD_R = 12, PAD_T = 30, PAD_B = 34;

// The visible window, in Ångström (380–780 nm). Outside it the eye sees nothing,
// so we shade it as a rainbow and grey-out the UV/IR flanks.
const VIS_LO = 3800, VIS_HI = 7800;

// Principal absorption lines worth labelling — the pedagogy. Hydrogen Balmer
// series (peak at A stars) + Ca II H&K and Na D (strong in cool stars) are drawn
// always. The helium lines are the hot-star payoff of the OSTAR2002 splice (which
// extended the grid past CAP18's 30000 K ceiling): they carry a `minTeff`, so a
// guide appears only once the star is hot enough to actually show the line — He I
// 4471 in B/A stars and hotter, He II 4686 only in O stars (>~30000 K — the OSTAR
// splice regime), where it is THE defining feature. So dragging into the O-star regime
// literally lights up the He II 4686 guide. Drawn as faint vertical guides with a
// short label; only those inside the panel's λ range (and past minTeff) show.
const COL_HE = "rgba(150,205,255,0.55)";   // a cool-blue tint marks the hot-star He guides
const LINES = [
  { lam: 3933, label: "Ca K" },
  { lam: 3968, label: "Ca H" },
  { lam: 4102, label: "Hδ" },
  { lam: 4340, label: "Hγ" },
  { lam: 4471, label: "He I", minTeff: 10000, col: COL_HE },   // neutral He — B/A and hotter
  { lam: 4686, label: "He II", minTeff: 30000, col: COL_HE },  // ionized He — O stars (the OSTAR splice regime; below 30000 K it's ~continuum)
  { lam: 4861, label: "Hβ" },
  { lam: 5893, label: "Na D" },
  { lam: 6563, label: "Hα" },
];

const COL_CURVE = "#eef2f9";   // the flux curve, bright over the shaded band
const COL_GRID = "#283149";

export function createSpectrum({ api }) {
  const canvas = document.getElementById("spectrum-canvas");
  const caption = document.getElementById("spectrum-caption");
  if (!canvas) return { update() {} };

  const { ctx, W, H } = fitCanvas(canvas, 720, 260);

  let data = null;        // last /spectrum result
  let lastKey = null;     // dedup: skip a refetch if (Teff,logg,feh) didn't move

  // --- latest-wins + debounce (the lane.js idiom, on its OWN token) ----------
  let token = 0;
  let debounce = null;

  async function fetchSpectrum(teff, logg, feh) {
    const mine = ++token;
    try {
      const res = await fetch(
        `${api}/spectrum?teff=${teff}&logg=${logg}&feh=${feh}`,
      );
      if (!res.ok) throw new Error(`/spectrum -> ${res.status}`);
      const d = await res.json();
      if (mine !== token) return;   // a newer star superseded this one
      data = d;
      draw();
      renderCaption();
    } catch {
      if (mine !== token) return;
      // Keep the last good spectrum on a transient blip; but if we never got one
      // (fresh checkout: the grid isn't baked, so /spectrum 503s), say so plainly
      // rather than leaving the panel blank with no explanation.
      if (!data && caption) {
        caption.textContent =
          "Spectrum unavailable — the grid may not be baked yet " +
          "(see backend/docs/msg_spectra_build_recipe.md).";
      }
    }
  }

  // Consume the live StellarState: read the three numbers the spectrum depends on
  // and refetch (debounced). Dedup on a rounded key so an age scrub that doesn't
  // actually move Teff/log g won't hammer the endpoint.
  function update(state) {
    if (!state) return;
    const teff = state.Teff_K, logg = state.logg, feh = state.feh_init;
    if (teff == null || logg == null) return;
    const key = `${Math.round(teff)}|${logg.toFixed(2)}|${(feh ?? 0).toFixed(2)}`;
    if (key === lastKey) return;
    lastKey = key;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => fetchSpectrum(teff, logg, feh ?? 0), 90);
  }

  // True when the star is hotter than the HOTTEST spectrum any baked grid covers
  // (teff_max comes from the response — the real ceiling, never a literal 55000,
  // so this auto-tracks a denser/hotter re-bake). Past it we have NO model
  // atmosphere: drawing the clamped ceiling spectrum would be a fake, so we blank
  // the panel and say so. Strictly the HOT end only — the cool floor keeps its
  // honest clamp (a 3300 K red dwarf shown as 3500 K is a small extrapolation; a
  // 70000 K star shown as 55000 K is a different ionization regime entirely).
  function teffAboveGrid() {
    return data && data.teff_requested != null && data.teff_max != null &&
      data.teff_requested > data.teff_max + 0.5;
  }

  // --- drawing ---------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!data) return;
    if (teffAboveGrid()) { drawNoModel(); return; }

    const lam = data.wavelength, flux = data.flux;
    const n = lam.length;
    const lamLo = lam[0], lamHi = lam[n - 1];
    let fmax = 0;
    for (const v of flux) if (v > fmax) fmax = v;
    if (!(fmax > 0)) fmax = 1;

    const xOf = (l) => PAD_L + (l - lamLo) / (lamHi - lamLo) * (W - PAD_L - PAD_R);
    const yOf = (f) => H - PAD_B - (f / fmax) * (H - PAD_T - PAD_B);
    const yAxis = H - PAD_B;

    // 1) Shade the area under the curve. Each data point paints a thin column down
    //    to the axis: spectral colour inside the visible band, muted grey outside.
    //    The absorption lines (dips in the curve) therefore read as dark notches
    //    cut into the rainbow continuum.
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]);
      const w = i + 1 < n ? xOf(lam[i + 1]) - x + 1 : 1.5;
      const yTop = yOf(flux[i]);
      if (lam[i] >= VIS_LO && lam[i] <= VIS_HI) {
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = wavelengthToCSS(lam[i] / 10);   // Å -> nm
      } else {
        ctx.globalAlpha = 0.16;
        ctx.fillStyle = "#9aa6bd";
      }
      ctx.fillRect(x, yTop, w, yAxis - yTop);
    }
    ctx.globalAlpha = 1;

    drawGuides(xOf, lamLo, lamHi);

    // 2) The flux curve on top, bright so the line cores read crisply.
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]), y = yOf(flux[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COL_CURVE; ctx.lineWidth = 1.3; ctx.stroke();

    drawFrameAndAxes(xOf, lamLo, lamHi);
  }

  // Wien-peak marker + the principal absorption-line guides (only those inside
  // the panel's wavelength range).
  function drawGuides(xOf, lamLo, lamHi) {
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";

    // Wien peak: λ_max = 2.8978e7 Å·K / Teff. Often off-panel (UV for hot, IR for
    // cool stars); drawn only when it lands inside the window.
    const lpk = 2.8977719e7 / data.teff;
    if (lpk > lamLo && lpk < lamHi) {
      const x = xOf(lpk);
      ctx.strokeStyle = "rgba(255,210,127,0.55)"; ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#ffd27f";
      ctx.fillText("Wien peak", x, PAD_T - 16);
    }

    // Absorption-line guides. Every in-range line gets a dashed guide, but the
    // LABEL is collision-skipped (the Ca K / Ca H / Hδ cluster at the Balmer jump
    // would overprint into mush otherwise) — same idea as the slider tick strip.
    // A `minTeff` line (the He guides) is shown only when the star is that hot, so
    // helium appears exactly where it physically matters (hot stars).
    ctx.lineWidth = 1;
    let lastLabelX = -1e9;
    for (const ln of LINES) {
      if (ln.lam <= lamLo || ln.lam >= lamHi) continue;
      if (ln.minTeff && data.teff < ln.minTeff) continue;   // hot-star lines: only when hot
      const x = xOf(ln.lam);
      ctx.strokeStyle = ln.col || "rgba(231,236,245,0.35)";
      ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.setLineDash([]);
      if (x - lastLabelX >= 24) {     // skip labels that would overlap the last
        ctx.fillStyle = ln.col ? "#bcd8f4" : "#aeb7c8";
        ctx.fillText(ln.label, x, PAD_T - 4);
        lastLabelX = x;
      }
    }
    ctx.textAlign = "left";
  }

  function drawFrameAndAxes(xOf, lamLo, lamHi) {
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);

    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";

    // x ticks at round wavelengths.
    ctx.textAlign = "center";
    for (let l = 4000; l <= lamHi; l += 1000) {
      if (l <= lamLo) continue;
      const x = xOf(l);
      ctx.globalAlpha = 0.22;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(String(l), x, H - PAD_B + 14);
    }
    ctx.fillText("wavelength (Å)", W / 2, H - 6);

    // y label (normalized flux — absolute scale lives in the L readout).
    ctx.save();
    ctx.translate(12, (H - PAD_B + PAD_T) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("flux (per-spectrum max = 1)", 0, 0);
    ctx.restore();

    // y ticks 0 / 0.5 / 1.
    ctx.textAlign = "right";
    for (const v of [0, 0.5, 1]) {
      const y = H - PAD_B - v * (H - PAD_T - PAD_B);
      ctx.fillText(v.toFixed(1), PAD_L - 5, y + 4);
    }
    ctx.textAlign = "left";
  }

  // The "no model for this range" state: the star is hotter than every grid we
  // have, so there's nothing honest to plot. A faint frame keeps the panel reading
  // as intentionally empty (not broken); the message names the real ceiling and
  // this star's temperature so it's clear WHY it's blank — and it's distinct from
  // the "grid not baked" (503) message, a different failure entirely.
  function drawNoModel() {
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);
    const cx = (PAD_L + W - PAD_R) / 2, cy = (PAD_T + H - PAD_B) / 2;
    ctx.textAlign = "center";
    ctx.fillStyle = "#aeb7c8"; ctx.font = "14px system-ui, sans-serif";
    ctx.fillText("No spectral model for this temperature", cx, cy - 8);
    ctx.fillStyle = "#8a93a6"; ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(
      `Our model atmospheres reach ${Math.round(data.teff_max)} K — ` +
      `this star is ≈ ${Math.round(data.teff_requested)} K.`,
      cx, cy + 13,
    );
    ctx.textAlign = "left";
  }

  // The honest "what am I looking at" caption: the parameters the spectrum stands
  // for, plus — when the grid has no metallicity axis — a plain note that the
  // [Fe/H] control does not (yet) change this panel.
  function renderCaption() {
    if (!caption || !data) return;
    if (teffAboveGrid()) {
      caption.textContent =
        `Teff ≈ ${Math.round(data.teff_requested)} K is beyond our hottest ` +
        `model atmosphere (${Math.round(data.teff_max)} K) — no spectrum to show.`;
      return;
    }
    const t = Math.round(data.teff);
    const parts = [`Teff ${t} K`, `log g ${Number(data.logg).toFixed(2)}`];
    if (data.feh_varies) parts.push(`[Fe/H] ${Number(data.feh).toFixed(2)}`);
    let txt = parts.join(" · ");
    if (!data.feh_varies) {
      txt += " — solar-metallicity grid: the [Fe/H] control does not change this " +
        "panel yet (awaiting a metallicity-varying spectral grid).";
    }
    caption.textContent = txt;
  }

  return { update };
}
