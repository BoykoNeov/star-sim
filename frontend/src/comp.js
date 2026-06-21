// Composition panel (STAR_SIM_SPEC.md §5.4): surface & core mass fractions
// X=H, Y=He, Z=metals as stacked-area bands vs EEP, with a marker at the current
// age. Two sub-charts share one EEP axis — core on top (where the drama is),
// surface below.
//
// Why EEP and not linear age on the x-axis (§6): the teaching payoff — core
// hydrogen converting to helium as the star leaves the main sequence — happens
// near TAMS. On a linear-age axis the MS eats ~90% of the width and that
// transition is an invisible sliver; on an EEP axis the phases are evenly spaced
// and you can actually watch it.
//
// A consumer of StellarState ONLY (§3): it reads X/Y/Z and eep off the track and
// the marker, and knows nothing about where they came from. setTrack() takes the
// list from /track; update() moves the marker from /state. Same split as hr.js.

const PAD_L = 30, PAD_R = 10, PAD_T = 16, PAD_B = 26;
const GAP = 22;   // vertical gap between the core and surface sub-charts

// Band colors: H a cool blue, He a warm gold, metals a violet. Z is ~1.5% so its
// band is a thin sliver at the top — honest, not a rendering bug.
const COL = { X: "#5b8def", Y: "#ffce6b", Z: "#b083e0" };

export function createComp(canvas) {
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;

  let track = null;    // array of StellarState (age-independent, set per mass/feh)
  let marker = null;   // current StellarState (moves as age scrubs)

  function setTrack(t) { track = t && t.length ? t : null; draw(); }
  function update(state) { marker = state; draw(); }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (!track) return;

    const e0 = track[0].eep;
    const e1 = track[track.length - 1].eep;
    const span = e1 - e0 || 1;
    const xOf = (eep) => PAD_L + (eep - e0) / span * (W - PAD_L - PAD_R);

    const chartH = (H - PAD_T - PAD_B - GAP) / 2;
    const coreTop = PAD_T;
    const surfTop = PAD_T + chartH + GAP;

    // Fill one stacked band: cumulative-fraction boundaries lowFn..highFn, mapped
    // so fraction 0 sits at the chart's bottom and 1 at its top.
    function band(top, h, lowFn, highFn) {
      ctx.beginPath();
      track.forEach((s, i) => {
        const x = xOf(s.eep), y = top + h - highFn(s) * h;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      for (let i = track.length - 1; i >= 0; i--) {
        const s = track[i];
        ctx.lineTo(xOf(s.eep), top + h - lowFn(s) * h);
      }
      ctx.closePath();
      ctx.fill();
    }

    function stack(top, h, label, X, Y) {
      // bottom -> top: X (H), then Y (He), then Z (metals = remainder to 1).
      ctx.fillStyle = COL.X; band(top, h, () => 0, X);
      ctx.fillStyle = COL.Y; band(top, h, X, (s) => X(s) + Y(s));
      ctx.fillStyle = COL.Z; band(top, h, (s) => X(s) + Y(s), () => 1);

      ctx.strokeStyle = "#283149"; ctx.lineWidth = 1;
      ctx.strokeRect(PAD_L, top, W - PAD_L - PAD_R, h);

      ctx.fillStyle = "#cbd2e0"; ctx.font = "600 11px system-ui, sans-serif";
      ctx.fillText(label, PAD_L + 5, top + 13);
      // y ticks: 1 at top, 0 at bottom.
      ctx.fillStyle = "#8a93a6"; ctx.font = "10px system-ui, sans-serif";
      ctx.fillText("1", 14, top + 9);
      ctx.fillText("0", 14, top + h);
    }

    stack(coreTop, chartH, "core", (s) => s.X_core, (s) => s.Y_core);
    stack(surfTop, chartH, "surface", (s) => s.X_surf, (s) => s.Y_surf);

    drawPhaseDividers(xOf);
    drawMarker(xOf, e0, e1);
    drawAxis();
  }

  // Faint full-height line wherever the phase label changes, labeled once at the
  // top — turns the EEP axis into a readable MS | RGB map (a teaching cue).
  function drawPhaseDividers(xOf) {
    ctx.font = "10px system-ui, sans-serif";
    let prev = null, lastLabelX = -1e9;
    for (const s of track) {
      if (s.phase === prev) continue;
      prev = s.phase;
      const x = xOf(s.eep);
      if (x > PAD_L + 1) {
        ctx.strokeStyle = "rgba(138,147,166,0.30)"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      }
      if (x - lastLabelX > 34) {
        ctx.fillStyle = "#8a93a6";
        ctx.fillText(s.phase, x + 3, PAD_T - 5);
        lastLabelX = x;
      }
    }
  }

  function drawMarker(xOf, e0, e1) {
    if (!marker) return;
    const eep = Math.min(Math.max(marker.eep, e0), e1);
    const x = xOf(eep);
    ctx.strokeStyle = "#e7ecf5"; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
    // little caps so the marker reads as a marker, not a phase divider.
    ctx.fillStyle = "#e7ecf5";
    ctx.beginPath(); ctx.arc(x, PAD_T, 2.5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(x, H - PAD_B, 2.5, 0, Math.PI * 2); ctx.fill();
  }

  function drawAxis() {
    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";
    ctx.fillText("EEP →  (evolutionary phase)", W / 2 - 74, H - 8);
  }

  return { setTrack, update };
}
