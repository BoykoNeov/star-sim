// HR diagram (STAR_SIM_SPEC.md §5): log L vs log Teff, Teff axis REVERSED (hot on
// the left). Draws the full evolutionary track for the chosen (mass, [Fe/H]) with
// a marker at the current age — setTrack() takes the list from /track, update()
// moves the marker from /state (same split the composition panel uses).

import { teffToCSS } from "./color.js";
import { fitCanvas } from "./canvas.js";

// Plot bounds (log10): covers cool red dwarfs to hot O stars, and ~1e-4..1e6 L.
const LOGT_MIN = 3.4;   // ~2500 K  (right edge, cool)
const LOGT_MAX = 4.7;   // ~50000 K (left edge, hot)
const LOGL_MIN = -4;
const LOGL_MAX = 6;
// Asymmetric left pad: the y-axis needs two lanes side by side — the rotated
// "L / L☉" title in the far-left lane, the 1e-3..1e6 tick numbers in the lane
// just inside it — so they stop overlapping. Top/right/bottom stay at PAD.
const PAD = 30;
const PAD_L = 50;

export function createHR(canvas, cssW = 300, cssH = 260) {
  // Crisp at an explicit (smaller) display size; draw in logical W×H units.
  // W/H are `let` (not destructured const) so resize() can re-fit the canvas to
  // a new display size and the xOf/yOf closures below — which capture the W/H
  // *bindings* — pick up the new values on the next draw().
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, cssW, cssH));

  // Teff reversed: hot (high logT) on the LEFT.
  const xOf = (logT) =>
    PAD_L + (LOGT_MAX - logT) / (LOGT_MAX - LOGT_MIN) * (W - PAD_L - PAD);
  const yOf = (logL) =>
    H - PAD - (logL - LOGL_MIN) / (LOGL_MAX - LOGL_MIN) * (H - 2 * PAD);

  function drawAxes() {
    ctx.clearRect(0, 0, W, H);
    ctx.strokeStyle = "#283149";
    ctx.fillStyle = "#8a93a6";
    ctx.font = "12px system-ui, sans-serif";
    ctx.lineWidth = 1;

    // frame
    ctx.strokeRect(PAD_L, PAD, W - PAD_L - PAD, H - 2 * PAD);

    // Teff gridlines (label in kK), centered under each line.
    ctx.textAlign = "center";
    for (const logT of [4.5, 4.0, 3.7, 3.5]) {
      const x = xOf(logT);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(x, PAD); ctx.lineTo(x, H - PAD); ctx.stroke();
      ctx.globalAlpha = 1;
      const kK = Math.round(10 ** logT / 100) / 10;
      ctx.fillText(`${kK}kK`, x, H - PAD + 15);
    }
    // L gridlines — tick numbers right-aligned in the lane just left of the
    // frame, so they never collide with the rotated axis title further left.
    ctx.textAlign = "right";
    for (const logL of [-3, 0, 3, 6]) {
      const y = yOf(logL);
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(PAD_L, y); ctx.lineTo(W - PAD, y); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(`1e${logL}`, PAD_L - 6, y + 4);
    }
    // axis titles
    ctx.textAlign = "center";
    ctx.fillText("Teff →  (hot left)", W / 2, H - 6);
    ctx.save();
    ctx.translate(12, H / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("L / L☉", 0, 0);
    ctx.restore();
    ctx.textAlign = "left";   // reset for any later text draws
  }

  let track = null;    // array of StellarState (age-independent, set per mass/feh)
  let marker = null;   // current StellarState (moves as age scrubs)

  function drawTrack() {
    if (!track || track.length < 2) return;
    ctx.beginPath();
    track.forEach((s, i) => {
      const x = xOf(Math.log10(s.Teff_K)), y = yOf(Math.log10(s.L_lsun));
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "rgba(231,236,245,0.45)";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function draw() {
    drawAxes();
    drawTrack();
    if (!marker) return;
    const x = xOf(Math.log10(marker.Teff_K));
    const y = yOf(Math.log10(marker.L_lsun));
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fillStyle = teffToCSS(marker.Teff_K);
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#e7ecf5";
    ctx.stroke();
  }

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }

  // Re-fit to a new display size (the responsive layout calls this when the
  // panel's width changes) and redraw from the retained track + marker.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
  }

  return { setTrack, update, resize };
}
