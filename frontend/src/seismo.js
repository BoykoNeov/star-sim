// Asteroseismology — the star rings like a bell (outward quartet, Axis C).
//
// A PURE function of three StellarState numbers — Teff, log g and R — turned into the two
// numbers that carry almost all of the seismic information: nu_max (the frequency of maximum
// oscillation power) and Delta-nu (the large frequency separation between consecutive radial
// overtones). It is a frontend-only panel (the sed.js / hz.js precedent): everything is derived
// from the marker's served state, no backend touch.
//
// THE PHYSICS (Tier-2, labeled approximate — this is NOT a pulsation solve). Solar-like p-modes
// are stochastically excited by the surface convection, so the whole feature exists ONLY for
// stars with a convective envelope: cool dwarfs (F/G/K/M) and red giants. The two seismic
// scaling relations (Kjeldsen & Bedding 1995; Huber et al. 2011) are:
//
//     nu_max / nu_max,sun = (g / g_sun) · (Teff / Teff_sun)^(-1/2)
//     Delta-nu / Delta-nu,sun = sqrt( rho_bar / rho_bar,sun ) = sqrt( (M/M_sun) / (R/R_sun)^3 )
//
// with the SOLAR anchors nu_max,sun = 3090 uHz, Delta-nu,sun = 135 uHz (Huber 2011), log g_sun =
// 4.4377 (cgs), Teff_sun = 5772 K. We use the REAL solar constants, not this sim's slightly-off
// Sun: the sim's Sun is documented as not solar-calibrated (Teff ~5835, log g ~4.425), so it rings
// at ~2984/132 uHz — ~3% below the canonical 3090/135. That offset is HONEST (a puffier, hotter
// "Sun" genuinely has a lower nu_max) and common-mode, so it cancels in every relative comparison
// and in the Delta-nu-relative echelle; only the absolute displayed number carries it. (The scaling
// relations themselves also carry a known few-% systematic — a tool reproducing 3090 exactly would
// overstate the method's precision.) See the caption caveat.
//
// THE M/R "RECOVERY" IS THE PRINCIPLE, NOT A MEASUREMENT. We compute nu_max/Delta-nu FROM g and R,
// so inverting the two relations for M and R recovers exactly the M and R we put in — the match is
// arithmetic, not an independent FFT of a light curve. That is a legitimate DEMONSTRATION of the
// method Kepler/TESS use to weigh hundreds of thousands of stars; the caption says "this is the
// principle", never "the sim measured this star's mass".
//
// THE HONESTY GATE IS INTRINSIC TO THE PHYSICS. Hot stars (Teff > ~6700 K) have radiative
// envelopes and do NOT ring this way; their opacity-driven delta-Sct / beta-Cep pulsations are the
// instability strip already overlaid on the HR panel. So above the gate the panel stays VISIBLE
// but blanks the spectrum and points the user at the instability strip (the HZ-band precedent:
// gate-to-caption, not hide). The other half of the gate is structural: main.js only ever feeds
// this panel a LIVING star (the shared mode-switch chokepoint drops it in every endgame) — a
// cooling white dwarf has log g ~8 and would slip a pure Teff gate to paint a garbage ~1e7 uHz
// spectrum, and WD pulsations aren't solar-like anyway.

import { fitCanvas } from "./canvas.js";

// Solar anchors (real Sun — Huber et al. 2011 + IAU nominal). See the header on why not the sim-Sun.
const NUMAX_SUN = 3090.0;   // uHz
const DNU_SUN = 135.0;      // uHz
const LOGG_SUN = 4.4377;    // log10 cgs
const TEFF_SUN = 5772.0;    // K

// Above this the envelope is radiative -> no solar-like oscillations (see the gate note in the
// header). Set no lower than ~6700: Procyon (Teff ~6530 K) is a textbook solar-like F oscillator, so
// a gate at 6000 would wrongly exclude real F-star oscillators.
export const TEFF_CONV_MAX = 6700;

export function ringsSolarLike(Teff) {
  return Number.isFinite(Teff) && Teff <= TEFF_CONV_MAX;
}

// The seismic parameters for a star of effective temperature Teff (K), surface gravity log g (cgs)
// and radius R (R_sun). Returns { numax, dnu, mSeismic, rSeismic, mModel, envSigma } (frequencies in
// uHz, masses/radii in solar units), or null when the inputs are unusable. `rings` (does it oscillate
// solar-like?) is the caller's Teff gate, kept separate so a hot star still gets a params object for
// the readout if wanted — but here we return null above the gate so the panel blanks cleanly.
export function seismicParams(Teff, logg, R) {
  if (!(Teff > 0) || logg == null || !(R > 0)) return null;
  if (!ringsSolarLike(Teff)) return null;
  const gRatio = 10 ** (logg - LOGG_SUN);                 // g / g_sun
  const numax = NUMAX_SUN * gRatio * (Teff / TEFF_SUN) ** -0.5;
  // The star's CURRENT mass, exact from g and R (M/M_sun = (g/g_sun)(R/R_sun)^2) — this sidesteps
  // the mass_init vs mass-loss trap: log g on the state already encodes the current mass.
  const mModel = gRatio * R ** 2;
  const dnu = DNU_SUN * Math.sqrt(mModel / R ** 3);
  // The inverse scaling relations — recover M and R from (numax, dnu, Teff). By construction these
  // equal (mModel, R); we surface them to demonstrate invertibility (see the header).
  const rSeismic = (numax / NUMAX_SUN) * (dnu / DNU_SUN) ** -2 * (Teff / TEFF_SUN) ** 0.5;
  const mSeismic = (numax / NUMAX_SUN) ** 3 * (dnu / DNU_SUN) ** -4 * (Teff / TEFF_SUN) ** 1.5;
  // Oscillation-power envelope width (Gaussian sigma). Schematic — the true FWHM ~0.66·numax^0.88
  // (Mosser 2012); a plain sigma ~0.25·numax gives the right visual span and is labeled schematic.
  const envSigma = 0.25 * numax;
  return { numax, dnu, mSeismic, rSeismic, mModel, envSigma };
}

// A schematic value for epsilon, the phase offset of the asymptotic relation nu(n,l) ≈ dnu·(n +
// l/2 + eps) - l(l+1)·D0. It shifts every ridge together (wraps mod dnu), so its exact value is
// cosmetic for a SCHEMATIC echelle; the recognizable structure is the l=1 half-Delta-nu offset and
// the close l=0/l=2 pair. Kallinger-style: eps grows weakly with dnu; clamp to a sane band.
function epsilonOf(dnu) {
  const e = 0.60 + 0.52 * Math.log10(Math.max(dnu, 0.1));
  return Math.min(1.8, Math.max(0.4, e));
}

// The individual mode frequencies across the power envelope, each tagged with its angular degree l
// (0 = radial, 1 = dipole, 2 = quadrupole — the three that dominate solar-like spectra). Returns
// [{ freq, l, amp }] with amp = the Gaussian envelope value at that frequency (0..1), l=1 tallest,
// l=2 shortest (their real relative visibility). D0 ~ dnu/100 sets the small l=0/l=2 separation.
function modeFrequencies(numax, dnu, envSigma) {
  const eps = epsilonOf(dnu);
  const D0 = dnu / 100;                          // small separation scale (schematic)
  const gauss = (f) => Math.exp(-((f - numax) ** 2) / (2 * envSigma ** 2));
  const nCenter = numax / dnu - eps;
  const nLo = Math.max(1, Math.floor(nCenter - 3.2 * envSigma / dnu));
  const nHi = Math.ceil(nCenter + 3.2 * envSigma / dnu);
  const modes = [];
  for (let n = nLo; n <= nHi; n++) {
    const f0 = dnu * (n + eps);                  // l=0 radial
    const f1 = dnu * (n + 0.5 + eps) - 6 * D0;   // l=1 dipole, ~half-dnu above l=0
    const f2 = dnu * (n + eps) - 6 * D0;         // l=2 just below the NEXT... actually just below l=0
    if (f0 > 0) modes.push({ freq: f0, l: 0, amp: gauss(f0) });
    if (f1 > 0) modes.push({ freq: f1, l: 1, amp: gauss(f1) * 1.25 });
    if (f2 > 0) modes.push({ freq: f2, l: 2, amp: gauss(f2) * 0.6 });
  }
  return { modes, eps };
}

const PAD_L = 44, PAD_R = 12, PAD_T = 18, PAD_B = 30;
const COL_AXIS = "#7f8aa3";
const COL_GRID = "rgba(127,138,163,0.14)";
const COL_INK = "#c9d3e6";
const COL_ENV = "rgba(214,178,96,0.85)";        // oscillation-power envelope — soft gold
const L_COLORS = ["#e8eefc", "#6fd3e8", "#e58fb0"];   // l = 0 white, 1 cyan, 2 pink
const L_NAMES = ["ℓ=0 radial", "ℓ=1 dipole", "ℓ=2 quadrupole"];

// A µHz axis formatter: giants ring at sub-µHz to tens of µHz, the Sun at thousands — pick sane digits.
function fmtFreq(v) {
  if (v >= 1000) return Math.round(v / 100) * 100 + "";
  if (v >= 100) return Math.round(v) + "";
  if (v >= 10) return v.toFixed(0);
  if (v >= 1) return v.toFixed(1);
  return v.toFixed(2);
}

export function createSeismo(canvas) {
  if (!canvas) return { update() { return null; }, clear() {}, resize() {} };
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, 460, 380));

  // Latest pushed state: the computed params (or null if it doesn't ring), plus the raw Teff/R for
  // the readout & the "hot star" caption branch.
  let params = null, teff = null, rModel = null;

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (params == null) {
      // Either nothing pushed yet, or a hot (radiative-envelope) star — the caption owns the "why".
      ctx.fillStyle = COL_AXIS;
      ctx.font = "12px system-ui, sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      if (teff != null && teff > TEFF_CONV_MAX) {
        ctx.fillText("Radiative envelope — no solar-like oscillations", W / 2, H / 2 - 8);
        ctx.font = "11px system-ui, sans-serif";
        ctx.fillStyle = COL_INK;
        ctx.fillText("hot stars ring via opacity-driven pulsation —", W / 2, H / 2 + 12);
        ctx.fillText("see the instability strip on the HR diagram", W / 2, H / 2 + 28);
      } else {
        ctx.fillText("Asteroseismic power spectrum", W / 2, H / 2);
      }
      return;
    }

    // Two stacked plots sharing the same frequency x-axis: the power spectrum on top, the echelle
    // diagram below. A thin gutter divides them.
    const gutter = 10;
    const topH = Math.round((H - PAD_T - PAD_B - gutter) * 0.46);
    const botTop = PAD_T + topH + gutter;
    const botH = H - PAD_B - botTop;
    drawPowerSpectrum(PAD_T, topH);
    drawEchelle(botTop, botH);
  }

  // --- the power spectrum: a Delta-nu comb of modes under a nu_max Gaussian envelope ---------------
  function drawPowerSpectrum(top, h) {
    const { numax, dnu, envSigma } = params;
    const plotW = W - PAD_L - PAD_R;
    const bottom = top + h;
    // x range: symmetric-ish around numax, wide enough to show the envelope fall off both sides.
    const fLo = Math.max(0, numax - 3.4 * envSigma);
    const fHi = numax + 3.4 * envSigma;
    const xOf = (f) => PAD_L + ((f - fLo) / (fHi - fLo)) * plotW;

    // frame + a few frequency ticks
    ctx.strokeStyle = COL_AXIS; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, top, plotW, h);
    ctx.font = "10px system-ui, sans-serif"; ctx.fillStyle = COL_AXIS;
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    const step = niceStep(fHi - fLo, 5);
    for (let v = Math.ceil(fLo / step) * step; v <= fHi + 1e-9; v += step) {
      const x = xOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(fmtFreq(v), x, bottom + 4);
    }
    ctx.fillStyle = COL_AXIS; ctx.textBaseline = "top";
    ctx.fillText("frequency (µHz)", PAD_L + plotW / 2, bottom + 15);
    // y label (power, schematic)
    ctx.save(); ctx.translate(11, top + h / 2); ctx.rotate(-Math.PI / 2);
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("power", 0, 0); ctx.restore();

    // the smooth envelope (gold)
    ctx.strokeStyle = COL_ENV; ctx.lineWidth = 1.4; ctx.globalAlpha = 0.9;
    ctx.beginPath();
    for (let px = 0; px <= plotW; px += 2) {
      const f = fLo + (px / plotW) * (fHi - fLo);
      const amp = Math.exp(-((f - numax) ** 2) / (2 * envSigma ** 2));
      const y = bottom - amp * (h - 6);
      if (px === 0) ctx.moveTo(PAD_L + px, y); else ctx.lineTo(PAD_L + px, y);
    }
    ctx.stroke(); ctx.globalAlpha = 1;

    // the mode comb — vertical peaks colored by l, height = envelope amplitude
    const { modes } = modeFrequencies(numax, dnu, envSigma);
    for (const m of modes) {
      if (m.freq < fLo || m.freq > fHi) continue;
      const x = xOf(m.freq);
      const amp = Math.min(1, m.amp);
      if (amp < 0.02) continue;
      const y = bottom - amp * (h - 6);
      ctx.strokeStyle = L_COLORS[m.l]; ctx.lineWidth = m.l === 0 ? 2 : 1.4;
      ctx.globalAlpha = 0.45 + 0.55 * amp;
      ctx.beginPath(); ctx.moveTo(x, bottom); ctx.lineTo(x, y); ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // nu_max marker (dashed vertical) + label
    const xm = xOf(numax);
    ctx.save(); ctx.setLineDash([3, 3]); ctx.strokeStyle = "rgba(214,178,96,0.6)"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(xm, top); ctx.lineTo(xm, bottom); ctx.stroke(); ctx.restore();
    ctx.fillStyle = COL_ENV; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    ctx.fillText("ν_max", xm, top - 1);

    // a Delta-nu span bracket between the two brightest radial peaks near numax
    drawDnuBracket(xOf, top, numax, dnu, envSigma);
  }

  // A little horizontal bracket spanning one Delta-nu between adjacent l=0 modes, labeled.
  function drawDnuBracket(xOf, top, numax, dnu, envSigma) {
    const eps = epsilonOf(dnu);
    const nNear = Math.round(numax / dnu - eps);
    const fA = dnu * (nNear + eps), fB = dnu * (nNear + 1 + eps);
    const xa = xOf(fA), xb = xOf(fB);
    const y = top + 10;
    ctx.strokeStyle = COL_INK; ctx.lineWidth = 1; ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.moveTo(xa, y + 4); ctx.lineTo(xa, y); ctx.lineTo(xb, y); ctx.lineTo(xb, y + 4);
    ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillStyle = COL_INK; ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "bottom";
    ctx.fillText("Δν", (xa + xb) / 2, y - 1);
  }

  // --- the echelle diagram: frequency mod Delta-nu (x) vs frequency (y) -> vertical ridges ---------
  function drawEchelle(top, h) {
    const { numax, dnu, envSigma } = params;
    const plotW = W - PAD_L - PAD_R;
    const bottom = top + h;
    const { modes } = modeFrequencies(numax, dnu, envSigma);
    const shown = modes.filter((m) => m.amp > 0.05);
    if (!shown.length) return;
    const fMin = Math.min(...shown.map((m) => m.freq));
    const fMax = Math.max(...shown.map((m) => m.freq));
    const yPad = (fMax - fMin) * 0.08 || dnu;
    const y0 = fMin - yPad, y1 = fMax + yPad;
    const xOf = (r) => PAD_L + (r / dnu) * plotW;              // reduced frequency 0..dnu
    const yOf = (f) => bottom - ((f - y0) / (y1 - y0)) * h;    // freq up

    // frame + x ticks (0..dnu) + y ticks (freq)
    ctx.strokeStyle = COL_AXIS; ctx.lineWidth = 1; ctx.strokeRect(PAD_L, top, plotW, h);
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "top"; ctx.fillStyle = COL_AXIS;
    const xstep = niceStep(dnu, 4);
    for (let v = 0; v <= dnu + 1e-9; v += xstep) {
      const x = xOf(v);
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(fmtFreq(v), x, bottom + 4);
    }
    ctx.fillStyle = COL_AXIS; ctx.textBaseline = "top";
    ctx.fillText("frequency mod Δν  (µHz)", PAD_L + plotW / 2, bottom + 15);
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    const ystep = niceStep(y1 - y0, 4);
    for (let v = Math.ceil(y0 / ystep) * ystep; v <= y1 + 1e-9; v += ystep) {
      const y = yOf(v);
      if (y < top || y > bottom) continue;
      ctx.strokeStyle = COL_GRID; ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(PAD_L + plotW, y); ctx.stroke();
      ctx.fillStyle = COL_AXIS; ctx.fillText(fmtFreq(v), PAD_L - 5, y);
    }

    // the mode dots — the ridges. l=0/l=2 pack into one ridge, l=1 sits ~half a Delta-nu across.
    for (const m of shown) {
      let r = ((m.freq % dnu) + dnu) % dnu;
      const x = xOf(r), y = yOf(m.freq);
      const rad = m.l === 0 ? 4 : m.l === 1 ? 3.4 : 2.6;
      ctx.beginPath(); ctx.arc(x, y, rad, 0, 2 * Math.PI);
      ctx.fillStyle = L_COLORS[m.l]; ctx.globalAlpha = 0.5 + 0.5 * Math.min(1, m.amp);
      ctx.fill();
      // a mode near the right edge is redrawn a Delta-nu to the LEFT so a ridge that wraps stays
      // visually continuous (the standard echelle "duplicate the seam" trick).
      if (r > dnu * 0.82) {
        ctx.beginPath(); ctx.arc(x - plotW, y, rad, 0, 2 * Math.PI); ctx.fill();
      } else if (r < dnu * 0.18) {
        ctx.beginPath(); ctx.arc(x + plotW, y, rad, 0, 2 * Math.PI); ctx.fill();
      }
    }
    ctx.globalAlpha = 1;

    // legend (l = 0/1/2)
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    let lx = PAD_L + 6, ly = top + 10;
    for (let l = 0; l < 3; l++) {
      ctx.beginPath(); ctx.arc(lx + 3, ly, 3.4, 0, 2 * Math.PI);
      ctx.fillStyle = L_COLORS[l]; ctx.fill();
      ctx.fillStyle = COL_INK; ctx.fillText(L_NAMES[l], lx + 11, ly);
      ly += 13;
    }
  }

  function niceStep(span, target) {
    const raw = span / Math.max(1, target);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * mag >= raw) return m * mag;
    return 10 * mag;
  }

  // main.js pushes the current living StellarState. Returns the computed params (or null when the
  // star doesn't ring solar-like) so the caller can fill the readout caption. Endgame/stripped
  // states never reach here (the mode-switch chokepoint drops the panel).
  function update(s) {
    if (!s) { params = null; teff = null; rModel = null; draw(); return null; }
    teff = s.Teff_K; rModel = s.R_rsun;
    params = seismicParams(s.Teff_K, s.logg, s.R_rsun);
    draw();
    return params ? { ...params, teff, rModel } : { rings: false, teff, rModel };
  }
  function clear() { params = null; teff = null; rModel = null; draw(); }
  function resize(cssW, cssH) {
    ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));
    draw();
  }

  draw();
  return { update, clear, resize };
}
