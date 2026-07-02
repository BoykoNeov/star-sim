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
// The visible band (380–780 nm) is shaded with the true per-wavelength spectral
// colour (color.js' CIE fit), so the panel reads as a spectrograph's rainbow with
// dark lines carved out of it; UV/near-IR flanks are shown muted-grey.
//
// UNITS: the baked grid (and so every array here) is in Ångström — but the AXIS is
// labelled in nm (1 nm = 10 Å), the friendlier unit. The internal Å values are
// converted only at the display edges: /10 for the rainbow colour and for the x
// ticks. The line-feature wavelengths below stay in Å to match the data domain.

import { fitCanvas } from "./canvas.js";
import { wavelengthToCSS } from "./color.js";

const PAD_L = 44, PAD_R = 12, PAD_T = 30, PAD_B = 34;

// The visible window, in Ångström (380–780 nm). Outside it the eye sees nothing,
// so we shade it as a rainbow and grey-out the UV/IR flanks.
const VIS_LO = 3800, VIS_HI = 7800;

// Principal absorption features worth labelling — the pedagogy. Hydrogen Balmer
// series (peak at A stars) + Ca II H&K and Na D (strong in cool stars) are drawn
// always. Two TEMPERATURE-GATED families bracket them:
//
//   • Helium lines (`minTeff`) — the hot-star payoff of the OSTAR2002 splice (which
//     extended the grid past CAP18's 30000 K ceiling): He I 4471 in B/A and hotter,
//     He II 4686 only in O stars (>~30000 K), where it is THE defining feature.
//     Dragging into the O-star regime literally lights up the He II 4686 guide.
//
//   • Molecular bands (`maxTeff`) — the cool-star payoff of the Göttingen/PHOENIX
//     COOL splice (which extended the grid below CAP18's 3500 K floor to 2300 K):
//     TiO bandheads dominate the optical spectrum of M stars. They carry a `maxTeff`,
//     so dragging into the M-dwarf / red-giant-tip regime lights up the TiO guides —
//     the spectrum visibly turns into a forest of molecular troughs (which is exactly
//     why a 3500 K clamp was a poor stand-in for a 2800 K star: those bands deepen
//     fast below the old floor). Only TiO bandheads are MARKED: all three (5167/6159/
//     7053 Å) were verified through the runtime path as real, deep edges at the
//     coolest reachable stars (step ~0.5–0.75 at 2809 K vs ~0.03 in the Sun). VO and
//     other metal oxides also strengthen in the very latest M's, but they form no
//     single clean isolated bandhead in this grid's reachable range, so — per the
//     project's "don't label a non-feature" rule — they are described in the panel
//     prose but get no guide line.
//
// Drawn as faint vertical guides with a short label; only those inside the panel's
// λ range AND within the star's [minTeff, maxTeff] gate show.
const COL_HE = "rgba(150,205,255,0.55)";   // a cool-blue tint marks the hot-star He guides
const COL_MOL = "rgba(255,170,105,0.5)";   // a warm tint marks the cool-star molecular bands
// `balmer: true` marks the hydrogen Balmer series — the ONLY features of a pure-H
// DA white dwarf, so the WD endgame draws just these (no metals/He/molecular bands).
const LINES = [
  { lam: 3933, label: "Ca K" },
  { lam: 3968, label: "Ca H" },
  { lam: 4102, label: "Hδ", balmer: true },
  { lam: 4340, label: "Hγ", balmer: true },
  { lam: 4471, label: "He I", minTeff: 10000, col: COL_HE },   // neutral He — B/A and hotter
  { lam: 4686, label: "He II", minTeff: 30000, col: COL_HE },  // ionized He — O stars (the OSTAR splice regime; below 30000 K it's ~continuum)
  { lam: 4861, label: "Hβ", balmer: true },
  { lam: 5167, label: "TiO", maxTeff: 4000, col: COL_MOL },    // TiO γ′ bandhead (near Mg b) — mid/late M
  { lam: 5893, label: "Na D" },
  { lam: 6159, label: "TiO", maxTeff: 4300, col: COL_MOL },    // TiO γ bandhead — late K / M onward
  { lam: 6563, label: "Hα", balmer: true },
  { lam: 7053, label: "TiO", maxTeff: 4300, col: COL_MOL },    // TiO ε bandhead — the strongest red TiO trough in M
];

const COL_CURVE = "#eef2f9";   // the flux curve, bright over the shaded band
const COL_GRID = "#283149";

// --- rotational (v sin i) line broadening -----------------------------------
// A cheap client-side post-process on the baked spectrum (whirling-cohort-atlas.md,
// Tier B): a fast rotator's absorption lines are Doppler-smeared across ±Δλ_L =
// λ·v sin i/c, so they go SHALLOWER and WIDER while conserving equivalent width. We
// convolve the served flux with Gray's analytic rotation profile (Gray, *The
// Observation and Analysis of Stellar Photospheres*, the linear-limb-darkening form).
// v sin i is driven from the star's real surface rotation (state.v_rot_kms, from the
// MIST vvcrit axis) taken EDGE-ON (i = 90°, sin i = 1) — the MAXIMUM projected
// broadening; at other inclinations the lines would be sharper. The vvcrit toggle
// sets *whether* the star spins fast; this *shows* it in the lines.
const C_KMS = 299792.458;
const ROT_EPS = 0.6;             // linear limb-darkening coefficient (Gray's ε)
// Below this the smear is sub-pixel at the grid's R≈2400 (2.5 Å bins → ~115–190 km/s
// per pixel), so the kernel is ~identity and the note is suppressed (the Sun, v_rot=0,
// is correctly untouched). Reachable rotators run ~200–420 km/s, well above it.
const ROT_VISIBLE_KMS = 120;

// Wolf-Rayet wind-EMISSION lines (endgame Chunk 7) — drawn rising ABOVE the continuum,
// the opposite of the absorption guides above. The defining optical features: He II
// 4686 (THE WR line, all subtypes) + the He II Pickering series; nitrogen lines for WN
// (`wn`), carbon lines for WC (`wc`). Gated by the served subtype so we label only the
// species that grid actually shows (the "don't label a non-feature" rule).
const COL_WR = "rgba(120,230,180,0.6)";   // a wind-green tint marks WR emission guides
const WR_LINES = [
  { lam: 4058, label: "N IV", wn: true },
  { lam: 4604, label: "N V", wn: true },
  { lam: 4686, label: "He II" },          // the defining Wolf–Rayet emission line
  { lam: 4861, label: "He II" },          // Pickering (blends with Hβ)
  { lam: 5411, label: "He II" },
  { lam: 5696, label: "C III", wc: true },
  { lam: 5808, label: "C IV", wc: true }, // the defining WC line
  { lam: 5876, label: "He I" },
  { lam: 6560, label: "He II" },          // Pickering (blends with Hα)
];

// --- [α/Fe] enhancement overlay (atlas Tier B, whirling-cohort-atlas.md) -----
// A spectrum-only "what-if": the α-rich thick-disk/halo subpopulation. When the toggle
// is on we plot TWO Coelho-2014 model spectra from /alpha_spectrum — solar-scaled
// (α = 0) vs α-enhanced (α = +0.4) — so the GAP between them is the lesson. Both come
// from the SAME atmosphere code (never Coelho-α beside a CAP18-solar one — the code
// seam would masquerade as the α signal; the load-bearing rule). MIST evolution is
// solar-scaled, so this is a hypothesis about the SPECTRUM only: the HR track and the
// composition panel do not follow [α/Fe] (the caption says so).
const COL_ALPHA = "#ff9e64";                 // coral — the α = +0.4 overlay curve + guides
const COL_ALPHA_GUIDE = "rgba(255,158,100,0.5)";
// The honest α-domain, measured (Gate-1 depths + the loci fidelity spot-check):
//   • α metal-line deepening washes out above ~9000 K (marginal at A, dead ≥12 kK).
//   • Below 3800 K Coelho computed only GIANT gravities (log g ≤ 1.0); a cool DWARF
//     there would clamp-fill a giant spectrum, so gate it off (giants stay valid).
//   • The [Fe/H] window is enforced at runtime from the response's clamped `feh`
//     (the MVP cube is [Fe/H] {−0.5, 0}; this auto-widens when the cube is re-baked).
const ALPHA_TEFF_MAX = 9000;                 // hotter → hand off to the main cube
const ALPHA_COOL_TEFF = 3800;                // below this, only giants are real
const ALPHA_COOL_MAX_LOGG = 1.0;             // …so a cool dwarf (higher log g) is gated off
// The α-sensitive absorption lines to guide (coral), plus the odd-Z Na D CONTROL that
// moves the OPPOSITE way (shallower with α — the anti-normalization-artifact check).
const ALPHA_LINES = [
  { lam: 3933, label: "Ca K" },       // Ca II K — α (Ca) deepens
  { lam: 4227, label: "Ca I" },       // Ca I 4227 — strong α deepening at cool Teff
  { lam: 5175, label: "Mg b" },       // Mg b triplet — the classic α indicator
  { lam: 5893, label: "Na D", control: true },  // odd-Z control: goes the OTHER way
  { lam: 8542, label: "Ca II" },      // Ca II triplet — the giant α indicator
];

export function createSpectrum({ api }) {
  const canvas = document.getElementById("spectrum-canvas");
  const caption = document.getElementById("spectrum-caption");
  const alphaToggle = document.getElementById("alpha-toggle");
  const alphaToggleRow = document.getElementById("alpha-toggle-row");
  if (!canvas) return { update() {}, resize() {} };

  // W/H are `let` so resize() can re-fit to a new display width; draw() rebuilds
  // its xOf/yOf from the current W/H each call, so a resize just needs a redraw.
  let ctx, W, H;
  ({ ctx, W, H } = fitCanvas(canvas, 720, 260));

  let data = null;        // last /spectrum result
  let lastKey = null;     // dedup: skip a refetch if (Teff,logg,feh) didn't move
  let vRot = 0;           // marker's surface rotation (km/s) — drives v sin i broadening
  // Viewing inclination (gravity-darkening Chunk 2). The observable broadening is v·sin i,
  // NOT the full surface speed: only the projected rotation Doppler-smears the lines. The
  // angle is set by main.js in lockstep with the 3D star's tilt (a shared viewing choice),
  // so pole-on (i→0) sharpens the lines toward the rest spectrum and edge-on (i=90°) gives
  // the maximum smear. 60° (isotropic median) is only a pre-push default; retires the old
  // fixed sin i = 1 "edge-on" punt now that an inclination model exists.
  let inclinationDeg = 60;
  const inclDeg = () => inclinationDeg;
  const vsiniEff = () => vRot * Math.sin((inclinationDeg * Math.PI) / 180);   // projected v sin i
  let broadenedMemo = null;   // {src, v, flux} — cache so resize() doesn't reconvolve
  // [α/Fe] enhancement (spectrum-only what-if). `alphaOn` is the user's persisted TOGGLE
  // INTENT (kept across mass/age/[Fe/H] changes, like main.js's rotationOn); `lastState`
  // lets the toggle re-render the current star without a caller round-trip; `alphaOffNote`
  // carries the honest reason when α is enabled but off its domain (hot / cool dwarf /
  // outside the α grid's [Fe/H]) so we fell back to the standard spectrum.
  let alphaOn = false;
  let lastState = null;
  let alphaOffNote = null;
  // A caller-supplied placeholder message (the WD endgame: log g 7–9 is off the
  // main-sequence atmosphere grid, and the central-star rows would silently return a
  // wrong lower-gravity spectrum, so we draw an honest "no model yet" frame instead of
  // fetching). Set by showPlaceholder(); cleared by the next live update().
  let placeholderMsg = null;

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

  // The [α/Fe] overlay: fetch BOTH Coelho spectra (α = 0 and α = +0.4) under ONE token
  // (Promise.all, then a single latest-wins check) and draw them together. If the star's
  // [Fe/H] falls outside the α cube's range the backend clamps it, so the returned `feh`
  // diverges from the request — an honest edge: rather than plot an α comparison at the
  // wrong metallicity we drop back to the standard main cube with a note. (This reads the
  // clamp from the response, so it auto-widens when the cube is re-baked to more [Fe/H].)
  async function fetchAlpha(teff, logg, feh) {
    const mine = ++token;
    try {
      const q = `teff=${teff}&logg=${logg}&feh=${feh}`;
      const [r0, r4] = await Promise.all([
        fetch(`${api}/alpha_spectrum?${q}&afe=0`),
        fetch(`${api}/alpha_spectrum?${q}&afe=0.4`),
      ]);
      if (!r0.ok || !r4.ok) throw new Error(`/alpha_spectrum -> ${r0.status}/${r4.status}`);
      const [d0, d4] = await Promise.all([r0.json(), r4.json()]);
      if (mine !== token) return;   // a newer star superseded this one
      if (Math.abs((d0.feh ?? feh) - feh) > 0.05) {
        // Off the α grid's [Fe/H] window → fall back honestly. fetchSpectrum takes the
        // newest token, so latest-wins still holds through the chained fetch.
        alphaOffNote =
          `[α/Fe] comparison isn't available at [Fe/H] ${feh.toFixed(2)} ` +
          `(outside the α grid's metallicity range) — showing the standard spectrum.`;
        fetchSpectrum(teff, logg, feh);
        return;
      }
      data = {
        isAlpha: true,
        wavelength: d0.wavelength,
        flux0: d0.flux,          // α = 0 (solar-scaled) baseline
        flux4: d4.flux,          // α = +0.4 (α-rich) overlay
        teff: d0.teff, logg: d0.logg, feh: d0.feh, afe: d4.afe,
        teff_requested: d0.teff_requested, teff_max: d0.teff_max,
      };
      alphaOffNote = null;
      draw();
      renderCaption();
    } catch {
      if (mine !== token) return;
      if (!data && caption) {
        caption.textContent =
          "[α/Fe] spectrum unavailable — the Coelho α grid may not be baked yet " +
          "(python -m star_sim.fetch_coelho; python scripts/bake_alpha_spectra.py).";
      }
    }
  }

  // Consume the live StellarState: read the three numbers the spectrum depends on
  // and refetch (debounced). Dedup on a rounded key so an age scrub that doesn't
  // actually move Teff/log g won't hammer the endpoint.
  // Whether the [α/Fe] overlay is honest for this (Teff, log g): the metal-line deepening
  // is visible only up to ALPHA_TEFF_MAX (it washes out hotter), and the Coelho grid has
  // no cool-DWARF models below ALPHA_COOL_TEFF (only giants there). Off this domain we
  // fall back to the standard spectrum. (The [Fe/H] window is enforced separately, at
  // runtime, from the response's clamped feh — see fetchAlpha.)
  function alphaTeffLoggOk(teff, logg) {
    if (teff > ALPHA_TEFF_MAX) return false;                                  // hot: α dead
    if (teff < ALPHA_COOL_TEFF && logg > ALPHA_COOL_MAX_LOGG) return false;   // cool dwarf
    return true;
  }

  // `opts.endgame` marks a WD/WR/SN endgame render (e.g. the WD cooling scrub's opening
  // TPAGB-giant rows, which still have a real MAIN-cube spectrum and so come through here,
  // NOT updateWD). The α "what-if" is a LIVING-star control, so we hide its toggle and
  // never draw the overlay in an endgame — the plain spectrum only.
  function update(state, opts) {
    if (!state) return;
    placeholderMsg = null;   // a live star supersedes any endgame placeholder
    const inEndgame = !!(opts && opts.endgame);
    if (alphaToggleRow) alphaToggleRow.hidden = inEndgame;
    lastState = inEndgame ? null : state;   // the α toggle must not re-render an endgame state
    const teff = state.Teff_K, logg = state.logg, feh = state.feh_init;
    if (teff == null || logg == null) return;
    const newV = state.v_rot_kms ?? 0;
    const useAlpha = alphaOn && !inEndgame;
    // The key includes the α/endgame path so flipping the toggle (or entering an endgame at
    // the same Teff/log g) always refetches — the α overlay and the main cube are different
    // requests, never a stale dedup-skip.
    const key = `${useAlpha ? "a" : ""}${inEndgame ? "e" : ""}` +
      `${Math.round(teff)}|${logg.toFixed(2)}|${(feh ?? 0).toFixed(2)}`;
    if (key === lastKey) {
      // Same model atmosphere — but the marker's rotation may have moved (a rotation
      // toggle, or scrubbing along the track as the star spins down). Re-broaden the
      // cached spectrum and redraw, NO refetch (v sin i is a pure client-side post-
      // process). Only the live absorption cube reacts; a WD/WR/α frame ignores it.
      if (Math.abs(newV - vRot) > 0.5) {
        vRot = newV;
        if (data && !data.isWD && !data.isWR && !data.isAlpha) { draw(); renderCaption(); }
      }
      return;
    }
    vRot = newV;
    lastKey = key;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => dispatch(teff, logg, feh ?? 0, useAlpha), 90);
  }

  // Route the fetch: the [α/Fe] overlay cube when α-mode applies (on, and not in an endgame)
  // AND the star is in the honest (Teff, log g) domain; else the standard main cube —
  // recording WHY α was skipped (alphaOffNote) so the caption stays honest instead of
  // silently dropping it.
  function dispatch(teff, logg, feh, useAlpha) {
    if (useAlpha && alphaTeffLoggOk(teff, logg)) {
      alphaOffNote = null;
      fetchAlpha(teff, logg, feh);
    } else {
      alphaOffNote = !useAlpha ? null
        : teff > ALPHA_TEFF_MAX
          ? `[α/Fe] metal-line enhancement washes out above ~${ALPHA_TEFF_MAX} K — showing the standard spectrum.`
          : `the [α/Fe] grid has no cool-dwarf models below ~${ALPHA_COOL_TEFF} K (only giants there) — showing the standard spectrum.`;
      fetchSpectrum(teff, logg, feh);
    }
  }

  // The WD endgame's white-dwarf spectrum: a SECOND backend cube (Koester DA, log g
  // 6.5–9.5, pure hydrogen) served at /wd_spectrum. The WD panel calls this only for
  // the DEGENERATE remnant (high log g); the TPAGB-giant rows at the start of the
  // cooling scrub still have a real main-cube spectrum and go through update() above
  // (so the false "no model" placeholder no longer covers the giant phase). The draw
  // path is shared with update(); the response's `isWD`/`regime` flags steer the
  // guides (Balmer-only for DA, none for the cold DC continuum) and the captions.
  async function fetchWD(teff, logg) {
    const mine = ++token;
    try {
      const res = await fetch(`${api}/wd_spectrum?teff=${teff}&logg=${logg}`);
      if (!res.ok) throw new Error(`/wd_spectrum -> ${res.status}`);
      const d = await res.json();
      if (mine !== token) return;
      d.isWD = true;          // steer draw()/guides/caption onto the WD branch
      data = d;
      draw();
      renderCaption();
    } catch {
      if (mine !== token) return;
      if (!data && caption) {
        caption.textContent =
          "White-dwarf spectrum unavailable — the WD grid may not be baked yet " +
          "(python -m star_sim.fetch_koester; python -m star_sim.fetch_tmap; " +
          "python scripts/bake_wd_spectra.py --tmap-dir data/spectra/grids/tmap).";
      }
    }
  }

  function updateWD(state) {
    if (!state) return;
    placeholderMsg = null;
    if (alphaToggleRow) alphaToggleRow.hidden = true;   // the α main-cube what-if doesn't apply to a WD
    const teff = state.Teff_K, logg = state.logg;
    if (teff == null || logg == null) return;
    // A distinct key prefix from update()'s, so switching between cubes always
    // refetches (and a live star can never dedup-skip a WD frame, or vice versa).
    const key = `wd|${Math.round(teff)}|${logg.toFixed(2)}`;
    if (key === lastKey) return;
    lastKey = key;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => fetchWD(teff, logg), 90);
  }

  // The WR endgame's wind-EMISSION spectrum: a THIRD backend cube (PoWR) served at
  // /wr_spectrum, keyed on the WR axes (T*, Rt) rather than (Teff, log g). The backend
  // places the star (subtype from composition, Rt from L + a Nugis-Lamers Ṁ) and either
  // snaps to a real grid node (regime "WR") or reports off-grid (regime "none" — the hot
  // stripped core, hotter/denser-wind than any PoWR model). The response's `isWR`/
  // `off_grid` flags steer draw()/guides/caption onto the emission branch or the honest
  // no-model frame.
  async function fetchWR(teff, lum, xs, ys, zs, feh) {
    const mine = ++token;
    try {
      const res = await fetch(
        `${api}/wr_spectrum?teff=${teff}&lum=${lum}&xsurf=${xs}&ysurf=${ys}` +
        `&zsurf=${zs}&feh=${feh}`,
      );
      if (!res.ok) throw new Error(`/wr_spectrum -> ${res.status}`);
      const d = await res.json();
      if (mine !== token) return;
      d.isWR = true;          // steer draw()/guides/caption onto the WR emission branch
      data = d;
      draw();
      renderCaption();
    } catch {
      if (mine !== token) return;
      if (!data && caption) {
        caption.textContent =
          "Wolf–Rayet spectrum unavailable — the WR grid may not be baked yet " +
          "(python -m star_sim.fetch_powr; python scripts/bake_wr_spectra.py).";
      }
    }
  }

  function updateWR(state) {
    if (!state) return;
    placeholderMsg = null;
    if (alphaToggleRow) alphaToggleRow.hidden = true;   // …nor to a WR wind-emission spectrum
    const teff = state.Teff_K, lum = state.L_lsun;
    if (teff == null || lum == null) return;
    const xs = state.X_surf ?? 0, ys = state.Y_surf ?? 0, zs = state.Z_surf ?? 0;
    const feh = state.feh_init ?? 0;
    // Distinct key prefix, like updateWD — switching cubes always refetches.
    const key = `wr|${Math.round(teff)}|${zs.toFixed(3)}|${xs.toFixed(3)}`;
    if (key === lastKey) return;
    lastKey = key;
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => fetchWR(teff, lum, xs, ys, zs, feh), 90);
  }

  // Show an honest "no spectral model for this regime yet" frame instead of a
  // spectrum (the WD endgame, until the Chunk 6 white-dwarf grid lands). Bumps the
  // token + clears the dedup key so a pending live fetch can't overwrite it, and a
  // later live update() re-enables fetching.
  function showPlaceholder(msg) {
    token++;
    if (alphaToggleRow) alphaToggleRow.hidden = true;   // …nor to a placeholder regime (the SN ejecta)
    placeholderMsg = msg || "No spectral model for this regime yet.";
    lastKey = null;
    draw();
    if (caption) caption.textContent = msg || "";
  }

  // True when the star is hotter than the HOTTEST spectrum any baked grid covers
  // (teff_max comes from the response — the real ceiling, never a literal 55000,
  // so this auto-tracks a denser/hotter re-bake). Past it we have NO model
  // atmosphere: drawing the clamped ceiling spectrum would be a fake, so we blank
  // the panel and say so. Strictly the HOT end only — the cool end is now covered
  // down to 2300 K (the Göttingen/PHOENIX cool splice), below every reachable star
  // (~2800 K), so the cool floor no longer clamps a real star at all. And even if a
  // future grid floor sat above some star, a cool clamp would be an honest small
  // extrapolation (cool model atmospheres exist and are ingestible) — unlike the hot
  // end, where past 55000 K no model exists, so blanking is the only honest move.
  function teffAboveGrid() {
    return data && data.teff_requested != null && data.teff_max != null &&
      data.teff_requested > data.teff_max + 0.5;
  }

  // Convolve `flux` with Gray's rotation profile at v sin i = `vsini` km/s. The grid
  // is uniform in λ (2.5 Å), but Δλ_L = λ·v sin i/c grows with λ, so the kernel is
  // built PER PIXEL in local-pixel units — physically constant in velocity, wider in
  // the red. Weights follow Gray's linear-limb-darkening profile over x = Δλ/Δλ_L ∈
  // (−1, 1): 2(1−ε)√(1−x²) + (π ε/2)(1−x²), then normalized to sum = 1 so equivalent
  // width is conserved (lines get shallower + wider, not weaker). Sub-pixel widths
  // (slow rotators) collapse to identity; ends are edge-replicated (flat continuum).
  function rotBroaden(lam, flux, vsini) {
    const n = flux.length;
    const out = new Float64Array(n);
    const inv = vsini / C_KMS;                 // Δλ_L / λ
    for (let i = 0; i < n; i++) {
      const dl = i + 1 < n ? lam[i + 1] - lam[i] : lam[i] - lam[i - 1];
      const dLpix = (lam[i] * inv) / dl;       // half-width Δλ_L in pixels at this λ
      if (dLpix < 0.5) { out[i] = flux[i]; continue; }   // sub-pixel → identity
      const half = Math.ceil(dLpix);
      let acc = 0, sum = 0;
      for (let j = -half; j <= half; j++) {
        const x = j / dLpix;
        if (x <= -1 || x >= 1) continue;
        const s = 1 - x * x;
        const w = 2 * (1 - ROT_EPS) * Math.sqrt(s) + 0.5 * Math.PI * ROT_EPS * s;
        let idx = i + j;
        if (idx < 0) idx = 0; else if (idx >= n) idx = n - 1;   // edge-replicate
        acc += w * flux[idx];
        sum += w;
      }
      out[i] = sum > 0 ? acc / sum : flux[i];
    }
    return out;
  }

  // The flux to draw for the main absorption cube: the rotationally-broadened version
  // when the star spins fast enough to matter, else the raw served array. WD/WR frames
  // are NEVER broadened — a degenerate remnant rotates slowly (and its lines are
  // pressure-broadened), and a WR is already wind-broadened, so the progenitor's
  // v_rot would be meaningless there. Memoized on (source array, v_rot) so a resize
  // redraw reuses the last convolution.
  function mainFlux() {
    const raw = data.flux;
    const vsini = vsiniEff();   // projected v sin i (inclination folded in) — the observable
    if (data.isWD || data.isWR || !(vsini >= 1)) return raw;
    if (broadenedMemo && broadenedMemo.src === raw && broadenedMemo.v === vsini)
      return broadenedMemo.flux;
    const flux = rotBroaden(data.wavelength, raw, vsini);
    broadenedMemo = { src: raw, v: vsini, flux };   // key on the projected speed, not v_rot
    return flux;
  }

  // --- drawing ---------------------------------------------------------------
  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (placeholderMsg) { drawPlaceholder(placeholderMsg); return; }
    if (!data) return;
    if (teffAboveGrid()) { drawNoModel(); return; }
    // WR: the stripped core hotter/denser-wind than any PoWR model → honest no-model
    // frame; otherwise the wind-emission render (lines UP, not absorption notches).
    if (data.isWR && data.off_grid) { drawNoModel(); return; }
    if (data.isWR) { drawWR(); return; }
    if (data.isAlpha) { drawAlpha(); return; }   // the [α/Fe] two-curve overlay

    const lam = data.wavelength, flux = mainFlux();
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
    // Temperature-gated guides show only where they physically matter: a `minTeff`
    // line (the He guides) appears only when the star is that hot, a `maxTeff` line
    // (the TiO/VO molecular bands) only when it is that cool.
    // A cold DC white dwarf is a featureless continuum (Balmer faded) — no guides.
    if (data.isWD && data.regime === "DC") { ctx.textAlign = "left"; return; }

    ctx.lineWidth = 1;
    let lastLabelX = -1e9;
    for (const ln of LINES) {
      if (ln.lam <= lamLo || ln.lam >= lamHi) continue;
      if (data.isWD) {
        if (!ln.balmer) continue;            // a DA is pure H: only the Balmer series
      } else {
        if (ln.minTeff && data.teff < ln.minTeff) continue;   // hot-star lines: only when hot
        if (ln.maxTeff && data.teff > ln.maxTeff) continue;   // cool-star bands: only when cool
      }
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

    // x ticks at round wavelengths. Data is in Å; the axis is labelled in nm, so
    // we step in nm (every 100 nm = 1000 Å) and convert to Å for positioning.
    ctx.textAlign = "center";
    for (let nm = 400; nm * 10 <= lamHi; nm += 100) {
      const lA = nm * 10;
      if (lA <= lamLo) continue;
      const x = xOf(lA);
      ctx.globalAlpha = 0.22;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(String(nm), x, H - PAD_B + 14);
    }
    ctx.fillText("wavelength (nm)", W / 2, H - 6);

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

  // The [α/Fe] overlay render: two Coelho spectra on the same rainbow-shaded panel. The
  // α = 0 (solar-scaled) curve is the shaded white baseline — the star's own composition;
  // the α = +0.4 (α-rich) curve is the coral line over it. Where α deepens a metal line the
  // coral dips BELOW the white; at Na D (the odd-Z control) it rides ABOVE. Each curve is
  // normalized to its OWN peak (continua align at 1), so the vertical gap reads as the
  // line-DEPTH difference — the α signal — not an overall flux offset (measured: this
  // preserves both the Ca/Mg deepening and the Na-D-opposite control).
  function drawAlpha() {
    const lam = data.wavelength, f0 = data.flux0, f4 = data.flux4;
    const n = lam.length;
    const lamLo = lam[0], lamHi = lam[n - 1];
    let m0 = 0, m4 = 0;
    for (let i = 0; i < n; i++) { if (f0[i] > m0) m0 = f0[i]; if (f4[i] > m4) m4 = f4[i]; }
    if (!(m0 > 0)) m0 = 1;
    if (!(m4 > 0)) m4 = 1;

    const xOf = (l) => PAD_L + (l - lamLo) / (lamHi - lamLo) * (W - PAD_L - PAD_R);
    const yOf = (v) => H - PAD_B - v * (H - PAD_T - PAD_B);   // v is already normalized to [0,1]
    const yAxis = H - PAD_B;

    // 1) shade under the α = 0 baseline — spectral colour inside the visible band, muted
    //    grey outside; the coral overlay's deeper troughs then read against this reference.
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]);
      const w = i + 1 < n ? xOf(lam[i + 1]) - x + 1 : 1.5;
      const yTop = yOf(f0[i] / m0);
      if (lam[i] >= VIS_LO && lam[i] <= VIS_HI) {
        ctx.globalAlpha = 0.5;
        ctx.fillStyle = wavelengthToCSS(lam[i] / 10);
      } else {
        ctx.globalAlpha = 0.14;
        ctx.fillStyle = "#9aa6bd";
      }
      ctx.fillRect(x, yTop, w, yAxis - yTop);
    }
    ctx.globalAlpha = 1;

    drawAlphaGuides(xOf, lamLo, lamHi);

    // 2) α = 0 baseline (white), then α = +0.4 (coral) on top so its deeper metal troughs
    //    stand out against the solar-scaled reference.
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]), y = yOf(f0[i] / m0);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COL_CURVE; ctx.lineWidth = 1.1; ctx.stroke();

    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]), y = yOf(f4[i] / m4);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COL_ALPHA; ctx.lineWidth = 1.3; ctx.stroke();

    // 3) a small in-panel key (bottom-right, usually empty for the red end) so white vs
    //    coral is unambiguous without reading the caption.
    ctx.font = "10px system-ui, sans-serif"; ctx.textAlign = "right";
    ctx.fillStyle = COL_CURVE; ctx.fillText("α = 0 (solar-scaled)", W - PAD_R - 6, H - PAD_B - 16);
    ctx.fillStyle = COL_ALPHA; ctx.fillText("α = +0.4 (α-rich)", W - PAD_R - 6, H - PAD_B - 4);
    ctx.textAlign = "left";

    drawFrameAndAxes(xOf, lamLo, lamHi);
  }

  // The α-sensitive line guides (coral): the Ca / Mg deepeners + the Na D odd-Z CONTROL
  // (marked ↓ because it moves the OPPOSITE way). "Watch these features."
  function drawAlphaGuides(xOf, lamLo, lamHi) {
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.lineWidth = 1;
    let lastLabelX = -1e9;
    for (const ln of ALPHA_LINES) {
      if (ln.lam <= lamLo || ln.lam >= lamHi) continue;
      const x = xOf(ln.lam);
      ctx.strokeStyle = COL_ALPHA_GUIDE;
      ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.setLineDash([]);
      if (x - lastLabelX >= 26) {
        ctx.fillStyle = "#ffc79e";
        ctx.fillText(ln.control ? ln.label + " ↓" : ln.label, x, PAD_T - 4);
        lastLabelX = x;
      }
    }
    ctx.textAlign = "left";
  }

  // The Wolf-Rayet wind-EMISSION render: the same rainbow-shaded spectrograph, but the
  // flux is continuum-normalized (continuum ≈ 1) so the broad emission lines stand UP
  // above it instead of cutting absorption notches into it. The y-scale is the backend's
  // `display_max` (a touch above this spectrum's tallest line, capped) so one strong
  // He II 4686 line can't squash the continuum and weaker lines (the advisor's gate).
  function drawWR() {
    const lam = data.wavelength, flux = data.flux;
    const n = lam.length;
    const lamLo = lam[0], lamHi = lam[n - 1];
    const ftop = data.display_max || 3;

    const xOf = (l) => PAD_L + (l - lamLo) / (lamHi - lamLo) * (W - PAD_L - PAD_R);
    const yOf = (f) => H - PAD_B - Math.min(f, ftop) / ftop * (H - PAD_T - PAD_B);
    const yAxis = H - PAD_B;

    // shade under the curve — spectral colour inside the visible band, muted grey
    // outside; emission lines therefore read as tall colour spikes over a low continuum.
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]);
      const w = i + 1 < n ? xOf(lam[i + 1]) - x + 1 : 1.5;
      const yTop = yOf(flux[i]);
      if (lam[i] >= VIS_LO && lam[i] <= VIS_HI) {
        ctx.globalAlpha = 0.55;
        ctx.fillStyle = wavelengthToCSS(lam[i] / 10);
      } else {
        ctx.globalAlpha = 0.16;
        ctx.fillStyle = "#9aa6bd";
      }
      ctx.fillRect(x, yTop, w, yAxis - yTop);
    }
    ctx.globalAlpha = 1;

    // the continuum reference line at flux = 1 (so "emission" is unambiguous).
    const yc = yOf(1.0);
    ctx.strokeStyle = "rgba(180,190,205,0.30)"; ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(PAD_L, yc); ctx.lineTo(W - PAD_R, yc); ctx.stroke();
    ctx.setLineDash([]);

    drawWRGuides(xOf, lamLo, lamHi);

    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = xOf(lam[i]), y = yOf(flux[i]);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = COL_CURVE; ctx.lineWidth = 1.3; ctx.stroke();

    drawWRFrameAndAxes(xOf, lamLo, lamHi, ftop);
  }

  // WR emission-line guides — only the species the served subtype actually shows
  // (nitrogen for WN, carbon for WC, helium always), the "don't label a non-feature" rule.
  function drawWRGuides(xOf, lamLo, lamHi) {
    ctx.font = "10px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.lineWidth = 1;
    const sub = data.subtype || "";
    let lastLabelX = -1e9;
    for (const ln of WR_LINES) {
      if (ln.lam <= lamLo || ln.lam >= lamHi) continue;
      if (ln.wn && !sub.startsWith("WN")) continue;   // nitrogen only on the WN grids
      if (ln.wc && sub !== "WC") continue;            // carbon only on the WC grid
      const x = xOf(ln.lam);
      ctx.strokeStyle = COL_WR;
      ctx.setLineDash([2, 4]);
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.setLineDash([]);
      if (x - lastLabelX >= 26) {
        ctx.fillStyle = "#aef0cd";
        ctx.fillText(ln.label, x, PAD_T - 4);
        lastLabelX = x;
      }
    }
    ctx.textAlign = "left";
  }

  function drawWRFrameAndAxes(xOf, lamLo, lamHi, ftop) {
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);
    ctx.fillStyle = "#8a93a6"; ctx.font = "11px system-ui, sans-serif";

    ctx.textAlign = "center";
    for (let nm = 400; nm * 10 <= lamHi; nm += 100) {
      const lA = nm * 10;
      if (lA <= lamLo) continue;
      const x = xOf(lA);
      ctx.globalAlpha = 0.22;
      ctx.beginPath(); ctx.moveTo(x, PAD_T); ctx.lineTo(x, H - PAD_B); ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.fillText(String(nm), x, H - PAD_B + 14);
    }
    ctx.fillText("wavelength (nm)", W / 2, H - 6);

    ctx.save();
    ctx.translate(12, (H - PAD_B + PAD_T) / 2); ctx.rotate(-Math.PI / 2);
    ctx.fillText("flux / continuum (emission)", 0, 0);
    ctx.restore();

    // y ticks: 0, the continuum (1), and the display cap.
    ctx.textAlign = "right";
    const yFor = (f) => H - PAD_B - Math.min(f, ftop) / ftop * (H - PAD_T - PAD_B);
    for (const v of [0, 1, ftop]) {
      ctx.fillText(v.toFixed(v < 10 ? 1 : 0), PAD_L - 5, yFor(v) + 4);
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
    // The WR off-grid frame is its own story: the stripped core is hotter / denser-wind
    // than any *observed* WR the PoWR grid covers (the evolutionary-vs-spectroscopic Teff
    // gap), NOT simply "too hot for our cube" — so it gets a two-line explanation.
    if (data.isWR) {
      ctx.fillText("No Wolf–Rayet wind model for this stripped core", cx, cy - 14);
      ctx.fillStyle = "#8a93a6"; ctx.font = "12px system-ui, sans-serif";
      ctx.fillText(
        `Teff ≈ ${Math.round(data.teff_requested / 1000)} kK — hotter and more compact ` +
        `than any observed Wolf–Rayet star`, cx, cy + 6);
      ctx.fillText(
        "the PoWR grids model (it covers the cooler, hydrogen-rich WNh entry).",
        cx, cy + 22);
      ctx.textAlign = "left";
      return;
    }
    ctx.fillText("No spectral model for this temperature", cx, cy - 8);
    ctx.fillStyle = "#8a93a6"; ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(
      data.isWD
        ? `Our NLTE hot-WD/CSPN models (TMAP) reach ${Math.round(data.teff_max)} K — ` +
          `this central star is ≈ ${Math.round(data.teff_requested)} K.`
        : `Our model atmospheres reach ${Math.round(data.teff_max)} K — ` +
          `this star is ≈ ${Math.round(data.teff_requested)} K.`,
      cx, cy + 13,
    );
    ctx.textAlign = "left";
  }

  // A generic centered-message frame (the WD endgame placeholder). Reads as
  // intentionally empty, not broken — the same idiom as drawNoModel, but for a regime
  // we don't model yet rather than a too-hot clamp.
  function drawPlaceholder(msg) {
    ctx.strokeStyle = COL_GRID; ctx.lineWidth = 1;
    ctx.strokeRect(PAD_L, PAD_T, W - PAD_L - PAD_R, H - PAD_T - PAD_B);
    const cx = (PAD_L + W - PAD_R) / 2, cy = (PAD_T + H - PAD_B) / 2;
    ctx.textAlign = "center";
    ctx.fillStyle = "#aeb7c8"; ctx.font = "14px system-ui, sans-serif";
    ctx.fillText("No spectral model for this star yet", cx, cy - 8);
    ctx.fillStyle = "#8a93a6"; ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(msg, cx, cy + 13);
    ctx.textAlign = "left";
  }

  // The honest "what am I looking at" caption: the parameters the spectrum stands
  // for, plus — when the grid has no metallicity axis — a plain note that the
  // [Fe/H] control does not (yet) change this panel.
  function renderCaption() {
    if (!caption || !data) return;
    if (teffAboveGrid()) {
      caption.textContent = data.isWD
        ? `Teff ≈ ${Math.round(data.teff_requested)} K — this planetary-nebula central ` +
          `star is hotter than even our NLTE hot-WD/CSPN models (TMAP reaches ` +
          `${Math.round(data.teff_max)} K); only the most massive progenitors' central ` +
          `stars get this hot, a narrow residual gap.`
        : `Teff ≈ ${Math.round(data.teff_requested)} K is beyond our hottest ` +
          `model atmosphere (${Math.round(data.teff_max)} K) — no spectrum to show.`;
      return;
    }
    // The [α/Fe] overlay: the two-curve what-if. HONEST that it is spectrum-only — the
    // track and composition panel are solar-scaled MIST and do not follow [α/Fe] — and
    // names the Na-D-opposite control that makes the α signal trustworthy (not a scaling).
    if (data.isAlpha) {
      const t = Math.round(data.teff), g = Number(data.logg).toFixed(2);
      caption.textContent =
        `[α/Fe] what-if · Teff ${t} K · log g ${g} · [Fe/H] ${Number(data.feh).toFixed(2)} — ` +
        `comparing solar-scaled (α = 0, white) with α-enhanced (α = +0.4, coral) model ` +
        `spectra (Coelho 2014). An α-rich thick-disk / halo star shows DEEPER Ca, Mg and ` +
        `Ti lines; Na D (an odd-Z element, not an α-element) moves the opposite way — a ` +
        `control that this is real line chemistry, not a scaling shift. Spectrum-only: the ` +
        `HR track and composition panel are solar-scaled and do NOT follow [α/Fe].`;
      return;
    }
    // The WR endgame: PoWR wind-emission spectra. The caption is HONEST about the
    // assumption-mapping (advisor): the deep temperature is mapped (Teff→T*) and the
    // wind density is a Nugis-Lamers estimate (→Rt), NOT a fit — and off the cool WNh
    // entry, the stripped core is hotter/denser-wind than any modelled WR (no spectrum).
    if (data.isWR) {
      const metalName = { gal: "Galactic (Z☉)", lmc: "LMC (½ Z☉)", smc: "SMC (⅕ Z☉)" }[data.metal]
        || data.metal;
      if (data.off_grid) {
        caption.textContent =
          `Wolf–Rayet · Teff ≈ ${Math.round(data.teff_requested / 1000)} kK — this stripped ` +
          `core is hotter / denser-wind than any observed WR the PoWR grids cover (the ` +
          `evolutionary-vs-spectroscopic temperature gap). A real wind spectrum shows for the ` +
          `cooler, hydrogen-rich WNh entry of the scrub.`;
      } else {
        const sub = data.subtype;
        const subName = sub === "WC" ? "WC (carbon surface)"
          : sub === "WNL" ? "WNL (hydrogen-rich)" : "WNE (hydrogen-free)";
        const species = sub === "WC" ? "C IV 5808" : "N V / N IV";
        caption.textContent =
          `Wolf–Rayet ${subName} · ${metalName} · broad wind EMISSION lines (He II 4686, ` +
          `${species}) from PoWR models. T* and wind density are assumption-mapped from the ` +
          `track (Teff→T*, a Nugis–Lamers Ṁ→Rt), not a spectral fit.`;
      }
      return;
    }
    // The WD endgame: a DA's pressure-broadened Balmer lines, or — once the cinder
    // has cooled past the model floor — the featureless DC continuum. Pure hydrogen,
    // so [Fe/H] is meaningless (not merely "solar"), which the caption says plainly.
    if (data.isWD) {
      const t = Math.round(data.teff), g = Number(data.logg).toFixed(2);
      if (data.regime === "DC") {
        caption.textContent =
          `Cold DC white dwarf · Teff ${t} K · log g ${g} — below ~5000 K the hydrogen ` +
          `Balmer lines have faded; the spectrum is a featureless (blackbody) continuum.`;
      } else if (data.regime === "CSPN") {
        caption.textContent =
          `Hot central star (CSPN) · Teff ${t} K · log g ${g} — the ~100–190 kK post-AGB ` +
          `star ionizing its planetary nebula; hydrogen is mostly ionized, so the Balmer ` +
          `lines are weak on a steep blue continuum (NLTE TMAP models). Pure hydrogen, so ` +
          `[Fe/H] doesn't apply.`;
      } else {
        caption.textContent =
          `White dwarf (DA) · Teff ${t} K · log g ${g} — broad, pressure-broadened ` +
          `hydrogen Balmer lines (Koester DA models). Pure hydrogen, so [Fe/H] doesn't apply.`;
      }
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
    // Rotational broadening note — only when the PROJECTED v sin i is above the ~one-pixel
    // visibility floor (below it the smear is sub-pixel and the lines are visibly
    // untouched). v sin i folds in the viewing inclination (Chunk 2): pole-on it drops
    // toward zero (sharp lines) and edge-on it maxes out.
    const vsini = vsiniEff();
    if (vsini >= ROT_VISIBLE_KMS) {
      txt += ` · v sin i ≈ ${Math.round(vsini)} km/s (i = ${Math.round(inclDeg())}°) — ` +
        "rotation Doppler-broadens the absorption lines (shallower & wider); tilt toward " +
        "pole-on to sharpen them, edge-on to broaden them further.";
    }
    // The α toggle is on but this star is off its honest domain (hot / cool dwarf / off the
    // α grid's [Fe/H]) — say why the overlay isn't shown, rather than silently dropping it.
    if (alphaOffNote) txt += " · " + alphaOffNote;
    caption.textContent = txt;
  }

  // Re-fit to a new display size (responsive layout); redraw + re-caption from the
  // last /spectrum result (kept in `data`). No refetch — same star, new pixels.
  function resize(cssW2, cssH2) {
    if (cssW2 === W && cssH2 === H) return;
    ({ ctx, W, H } = fitCanvas(canvas, cssW2, cssH2));
    draw();
    renderCaption();
  }

  // The [α/Fe] toggle (spectrum-only what-if). Flipping it forces a refetch of the current
  // star onto the right cube (lastKey cleared so the dedup can't skip it); `alphaOn` then
  // persists across mass/age/[Fe/H] changes, like main.js's rotationOn intent.
  if (alphaToggle) {
    alphaToggle.addEventListener("change", () => {
      alphaOn = alphaToggle.checked;
      lastKey = null;
      if (lastState) update(lastState);
    });
  }

  // Set the viewing inclination (0°=pole-on … 90°=edge-on) — folds sin i into the v sin i
  // line broadening (gravity-darkening Chunk 2). A pure client-side post-process: no
  // refetch (the served rest spectrum is unchanged), just re-broaden the cached flux and
  // re-caption, mirroring the vRot-change path in update(). Only the live absorption cube
  // reacts — a WD/WR/α frame ignores rotation entirely. main.js keeps this in lockstep
  // with the 3D star's tilt so the two tell one coherent story.
  function setInclination(deg) {
    if (deg === inclinationDeg) return;
    inclinationDeg = deg;
    if (data && !data.isWD && !data.isWR && !data.isAlpha) { draw(); renderCaption(); }
  }

  return { update, updateWD, updateWR, setInclination, showPlaceholder, resize };
}
