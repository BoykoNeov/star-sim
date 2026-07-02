// Spectral classification — the "what kind of star is this?" line under the 3D star.
//
// A Morgan–Keenan-style label: the effective temperature gives the temperature class
// (O B A F G K M, hot → cool, with a 0–9 subdivision) and the evolutionary phase
// (with surface gravity as a fallback) gives the luminosity class (I supergiant … V
// main-sequence dwarf). It is a SCHEMATIC mapping from the two numbers the panels
// already show (Teff, log g) plus the phase — NOT a real spectral-line classification
// (this simulator models the spectrum separately, in its own panel); the 3D-star
// panel's ? help says so. A sibling TEXT view like scale.js: update(state) reads the
// marker and rewrites the line, tinting the type with the star's true blackbody color.

import { teffToCSS } from "./color.js";

// Temperature classes: [letter, Tlo, Thi]. Subclass 0 = hot end of the class, 9 =
// cool end (the usual convention — the Sun, ~5800 K, is G2, near the hot end of G).
// Boundaries are standard teaching values. The O class top is open-ended (the hottest
// stars here reach ~50000 K and beyond), so its subclass is clamped to the real
// O2–O9 range rather than producing a nonexistent "O0".
const CLASSES = [
  ["O", 30000, 52000],
  ["B", 10000, 30000],
  ["A", 7500, 10000],
  ["F", 6000, 7500],
  ["G", 5200, 6000],
  ["K", 3700, 5200],
  ["M", 2400, 3700],
];

// Color words per temperature class — the eye's impression of the blackbody color.
const COLOR_WORD = {
  O: "blue", B: "blue-white", A: "white", F: "yellow-white",
  G: "yellow", K: "orange", M: "red",
};

function tempClass(teff) {
  for (const [letter, lo, hi] of CLASSES) {
    if (teff >= lo) {
      let sub = Math.round((9 * (hi - teff)) / (hi - lo));
      sub = Math.max(0, Math.min(9, sub));
      if (letter === "O") sub = Math.max(2, sub); // real O stars are O2–O9.5
      return { letter, sub };
    }
  }
  // Cooler than the M floor — clamp to the latest M (a very cool dwarf or giant tip).
  return { letter: "M", sub: 9 };
}

// Luminosity class: PHASE first — it is the honest evolutionary truth. A 40 M☉ O-star
// is a main-sequence DWARF (V) despite a giant-like luminosity and a log g ≈ 3.9 that
// a pure gravity threshold would mislabel "III/IV". Only for the evolved phases do we
// fall back to log g (giants/supergiants span a wide gravity range).
function lumClass(state) {
  const ph = state.phase;
  if (ph === "MS" || ph === "PMS") return { roman: "V", word: "main-sequence star" };
  if (ph === "SGB") return { roman: "IV", word: "subgiant" };
  const g = state.logg;
  if (g == null) return { roman: "III", word: "giant" };
  if (g < 1.0) return { roman: "I", word: "supergiant" };
  if (g < 2.0) return { roman: "II", word: "bright giant" };
  return { roman: "III", word: "giant" };
}

// A familiar common name for the headline. "<color> dwarf" is idiomatic only for
// G/K/M (yellow/orange/red dwarf); for hotter dwarfs it misleads — "white dwarf"
// especially names a degenerate stellar REMNANT, not an A main-sequence star — so we
// fall back to "<color> main-sequence star". Giants/supergiants get "<color> <word>".
function commonName(cls, lum) {
  const color = COLOR_WORD[cls.letter];
  if (lum.roman === "V") {
    if (cls.letter === "G" || cls.letter === "K" || cls.letter === "M")
      return `${color} dwarf`;
    return `${color} main-sequence star`;
  }
  return `${color} ${lum.word}`;
}

// The white-dwarf endgame is NOT a main-sequence MK type — a degenerate remnant has no
// O–M / I–V classification. So in endgame mode we replace the MK line with an honest
// endgame label, driven by the explicit mode flag (NOT a log g heuristic that would
// mislabel the low-gravity central-star rows "O2 III blue giant"). It still reads only
// StellarState fields (phase, log g, Teff): the thermal-pulsing AGB giant, then the hot
// contracting central star of the planetary nebula, then the cooling white dwarf. Real
// DA/DB spectral typing waits for the Chunk 6 white-dwarf spectra.
function wdLabel(state) {
  const g = state.logg, t = state.Teff_K;
  if (state.phase === "TPAGB") return { tag: "AGB", name: "thermal-pulsing giant" };
  if (g != null && g < 7) return { tag: "PN", name: "planetary-nebula central star" };
  const heat = t >= 20000 ? "hot " : t < 5000 ? "cool " : "";
  return { tag: "WD", name: `${heat}white dwarf` };
}

// The Wolf–Rayet endgame is the stripped, blazing core of a massive star — not an
// O–M / I–V main-sequence type either. The WR SUBTYPE is read from the surface
// composition (a StellarState field), data-driven and honest: a helium-dominant
// surface with nitrogen is the nitrogen sequence (WN); once helium burning surfaces
// carbon and oxygen the surface flips to the carbon/oxygen sequence (WC), and the very
// hottest, most-stripped end with strong oxygen is the WO branch. (Hydrogen still at
// the surface marks a late, H-rich WN — "WNh".) This is SCHEMATIC spectral typing from
// abundances, not real emission-line ratios; the 3D-star ? help says so.
function wrLabel(state) {
  const X = state.X_surf ?? 0, Z = state.Z_surf ?? 0;
  const ms = state.metals_surf || {};
  const cO = (ms.C ?? 0) + (ms.O ?? 0);
  if (Z < 0.4 || cO < 0.1) {                         // helium-dominant surface → WN
    return X > 0.1
      ? { tag: "WNh", name: "hydrogen-rich Wolf–Rayet (nitrogen sequence)" }
      : { tag: "WN", name: "Wolf–Rayet, nitrogen sequence" };
  }
  // carbon/oxygen-dominant surface → WC, or WO at the hottest, oxygen-strong end
  if (state.Teff_K >= 200000 && (ms.O ?? 0) > 0.2)
    return { tag: "WO", name: "Wolf–Rayet, oxygen sequence" };
  return { tag: "WC", name: "Wolf–Rayet, carbon sequence" };
}

// The supernova endgame is not a star at all but an expanding ejecta photosphere — no
// O–M / I–V type. The label narrates where the photosphere is in its evolution, read from
// the state (Teff cooling as the shell grows): a hot early fireball, the recombination
// photosphere through the plateau, then the cool, vast nebular phase. The "SN II" tag marks
// the v1 SN branch (purely hydrogen-rich Type II — the stripped Ib/c is the WR endpoint).
function snLabel(state, failed) {
  // A FAILED direct collapse is not an expanding fireball at all — it's a supergiant imploding
  // to a black hole, so the Teff-keyed fireball/plateau/nebular narration doesn't apply.
  if (failed) return { tag: "failed SN", name: "direct collapse — imploding to a black hole" };
  const t = state.Teff_K ?? 0;
  if (t >= 10000) return { tag: "SN II", name: "expanding fireball (hot photosphere)" };
  if (t >= 5000) return { tag: "SN II", name: "cooling photosphere — recombination plateau" };
  return { tag: "SN II", name: "cool, vast ejecta — nebular phase" };
}

// The binary-stripped star is a hot, helium-surfaced object — not a normal MS type. It is the
// missing link that unifies hot SUBDWARFS (low mass, sdO/sdB) with WOLF–RAYET stars (high mass)
// as one stripped-envelope sequence (Götberg 2018), so the label is keyed on the CURRENT
// (stripped) mass — threaded via opts.mStrip, since it has no home on the single-star state.
function strippedLabel(state, mStrip) {
  const heEnriched = (state.Y_surf ?? 0) > (state.X_surf ?? 0);
  const kind = heEnriched ? "helium" : "hydrogen-rich helium";
  if (mStrip != null && mStrip < 1.5)
    return { tag: "sdO/B", name: `hot subdwarf — a binary-stripped ${kind} core` };
  return { tag: "He★", name: `stripped ${kind} star (binary WR/subdwarf channel)` };
}

// Build the two child spans once; update() only rewrites their text + the type color.
export function createClassification(el) {
  if (!el) return { update() {} };
  el.innerHTML = `<span class="sc-type"></span><span class="sc-name"></span>`;
  const typeEl = el.querySelector(".sc-type");
  const nameEl = el.querySelector(".sc-name");

  return {
    // mode === "wd"/"wr"/"sn"/"stripped": show the endgame/what-if label, not the MK type.
    update(state, mode, opts) {
      if (!state || state.Teff_K == null) return;
      if (mode === "wd" || mode === "wr" || mode === "sn" || mode === "stripped") {
        const w = mode === "wr" ? wrLabel(state)
          : mode === "sn" ? snLabel(state, !!(opts && opts.failed))
          : mode === "stripped" ? strippedLabel(state, opts && opts.mStrip)
          : wdLabel(state);
        typeEl.textContent = w.tag;
        typeEl.style.color = teffToCSS(state.Teff_K);
        nameEl.textContent = w.name;
        return;
      }
      const t = tempClass(state.Teff_K);
      const lum = lumClass(state);
      typeEl.textContent = `${t.letter}${t.sub} ${lum.roman}`;
      typeEl.style.color = teffToCSS(state.Teff_K);
      nameEl.textContent = commonName(t, lum);
    },
  };
}
