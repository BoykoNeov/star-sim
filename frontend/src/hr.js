// HR diagram (STAR_SIM_SPEC.md §5): log L vs log Teff, Teff axis REVERSED (hot on
// the left). Phase 0 shows the current single point; the full evolutionary track
// is drawn here once the provider can return a track (Phase 0/1 with MIST).

import { teffToCSS } from "./color.js";

// Plot bounds (log10): covers cool red dwarfs to hot O stars, and ~1e-4..1e6 L.
const LOGT_MIN = 3.4;   // ~2500 K  (right edge, cool)
const LOGT_MAX = 4.7;   // ~50000 K (left edge, hot)
const LOGL_MIN = -4;
const LOGL_MAX = 6;
const PAD = 38;

export function createHR(canvas) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;

  // Teff reversed: hot (high logT) on the LEFT.
  const xOf = (logT) =>
    PAD + (LOGT_MAX - logT) / (LOGT_MAX - LOGT_MIN) * (W - 2 * PAD);
  const yOf = (logL) =>
    H - PAD - (logL - LOGL_MIN) / (LOGL_MAX - LOGL_MIN) * (H - 2 * PAD);

  function drawAxes() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#283149";
    ctx.fillStyle = "#8a93a6";
    ctx.font = "11px system-ui, sans-serif";
    ctx.lineWidth = 1;

    // frame
    ctx.strokeRect(PAD, PAD, W - 2 * PAD, H - 2 * PAD);

    // Teff gridlines (label in kK)
    for (const logT of [4.5, 4.0, 3.7, 3.5]) {
      const x = xOf(logT);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, H - PAD); ctx.stroke();
      ctx.globalAlpha = 1;
      const kK = Math.round(10 ** logT / 100) / 10;
      ctx.fillText(`${kK}kK`, x - 12, H - PAD + 14);
    }
    // L gridlines
    for (const logL of [-3, 0, 3, 6]) {
      const y = yOf(logL);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(PAD, y); ctx.lineTo(W - PAD, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`1e${logL}`, 4, y + 3);
    }
    ctx.fillText("Teff →  (hot left)", W / 2 - 36, H - 8);
    ctx.save();
    ctx.translate(12, H / 2 + 28); ctx.rotate(-Math.PI / 2);
    ctx.fillText("L / L☉", 0, 0);
    ctx.restore();
  }

  function update(state) {
    drawAxes();
    const x = xOf(Math.log10(state.Teff_K));
    const y = yOf(Math.log10(state.L_lsun));

    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = teffToCSS(state.Teff_K);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#e7ecf5";
    ctx.stroke();
  }

  return { update };
}
