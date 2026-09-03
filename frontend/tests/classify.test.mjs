// classify.js — the MK-type / endgame label.
//
// This is the module structure-refactor.md §2.3 listed as "pure" but wasn't: its
// only export was createClassification(el), which writes innerHTML. The label
// decision was split out as classifyLabel(state, mode, opts) so it could be tested
// without a DOM shim; createClassification now does nothing but write the two spans.
//
// Everything below is a CAPTION-HONESTY test. CLAUDE.md's most-repeated defect is a
// label that overstates the data — "a 'helium-rich' tag on a carbon surface" is
// literally this module — so the tests are about which words the app is allowed to
// print for which state, not about numbers.

import test from "node:test";
import assert from "node:assert/strict";
import { classifyLabel } from "../src/classify.js";

const star = (o) => ({ Teff_K: 5800, logg: 4.4, phase: "MS", ...o });

test("the Sun classifies as a G-something main-sequence yellow dwarf", () => {
  const l = classifyLabel(star({ Teff_K: 5772, logg: 4.44, phase: "MS" }));
  assert.match(l.tag, /^G\d V$/, `the Sun got "${l.tag}"`);
  assert.equal(l.name, "yellow dwarf");
});

test("subclass numbering runs 0 at the hot end to 9 at the cool end", () => {
  // G spans 5200-6000 K, so 6000 K is G0 and 5200 K is G9 (the standard convention,
  // and the reason the Sun at 5772 K is an early G).
  assert.equal(classifyLabel(star({ Teff_K: 5999 })).tag.slice(0, 2), "G0");
  assert.equal(classifyLabel(star({ Teff_K: 5201 })).tag.slice(0, 2), "G9");
});

test("the temperature ladder is O B A F G K M, hot to cool", () => {
  const letters = [45000, 20000, 8000, 6500, 5500, 4500, 3000]
    .map((T) => classifyLabel(star({ Teff_K: T })).tag[0]);
  assert.deepEqual(letters, ["O", "B", "A", "F", "G", "K", "M"]);
});

test("O stars stay inside the real O2-O9 range and never become O0/O1", () => {
  for (const T of [52000, 60000, 200000]) {
    const sub = Number(classifyLabel(star({ Teff_K: T })).tag[1]);
    assert.ok(sub >= 2, `${T} K produced O${sub}, which is not a real spectral type`);
  }
});

test("phase beats gravity: a 40 M_sun O star is a DWARF despite log g 3.9", () => {
  // The bug this rule exists for: a pure log-g threshold would call it "III/IV".
  const l = classifyLabel(star({ Teff_K: 42000, logg: 3.9, phase: "MS" }));
  assert.ok(l.tag.endsWith(" V"), `got "${l.tag}"`);
  assert.equal(l.name, "blue main-sequence star");
});

test("'white dwarf' is never printed for a hot main-sequence star", () => {
  // "White dwarf" names a degenerate REMNANT. An A/B/O dwarf must get the longer,
  // unambiguous phrase instead.
  for (const T of [45000, 20000, 8000, 6500]) {
    const l = classifyLabel(star({ Teff_K: T, phase: "MS" }));
    assert.ok(!/dwarf$/.test(l.name) || /main-sequence/.test(l.name),
      `${T} K printed "${l.name}"`);
    assert.ok(!l.name.includes("white dwarf"), `${T} K printed "${l.name}"`);
  }
  // ...while the idiomatic yellow/orange/red dwarfs keep the short form.
  assert.equal(classifyLabel(star({ Teff_K: 4500 })).name, "orange dwarf");
  assert.equal(classifyLabel(star({ Teff_K: 3000 })).name, "red dwarf");
});

test("the luminosity ladder falls back to log g only for evolved phases", () => {
  assert.equal(classifyLabel(star({ phase: "SGB", logg: 3.5 })).tag.split(" ")[1], "IV");
  assert.equal(classifyLabel(star({ phase: "RGB", logg: 0.5 })).tag.split(" ")[1], "I");
  assert.equal(classifyLabel(star({ phase: "RGB", logg: 1.5 })).tag.split(" ")[1], "II");
  assert.equal(classifyLabel(star({ phase: "RGB", logg: 2.5 })).tag.split(" ")[1], "III");
  assert.equal(classifyLabel(star({ phase: "RGB", logg: null })).tag.split(" ")[1], "III");
});

test("endgame modes never emit an MK type", () => {
  const s = star({ Teff_K: 60000, logg: 4.0 });
  for (const mode of ["wd", "wr", "sn", "stripped"]) {
    const l = classifyLabel(s, mode, { mStrip: 3 });
    assert.ok(!/^[OBAFGKM]\d /.test(l.tag),
      `mode "${mode}" produced the MK-looking tag "${l.tag}"`);
  }
});

test("the WD arc is driven by the mode flag, not by a log g heuristic", () => {
  // A central star of a planetary nebula has a giant-like log g ~5; a pure gravity
  // rule would print "O2 III blue giant" for it.
  assert.equal(classifyLabel(star({ Teff_K: 100000, logg: 5.0 }), "wd").tag, "PN");
  assert.equal(classifyLabel(star({ phase: "TPAGB", logg: 0.5 }), "wd").tag, "AGB");
  assert.equal(classifyLabel(star({ Teff_K: 30000, logg: 8.0 }), "wd").name, "hot white dwarf");
  assert.equal(classifyLabel(star({ Teff_K: 4000, logg: 8.0 }), "wd").name, "cool white dwarf");
  assert.equal(classifyLabel(star({ Teff_K: 10000, logg: 8.0 }), "wd").name, "white dwarf");
});

test("the WR subtype follows the surface composition, not the temperature alone", () => {
  const wr = (o) => classifyLabel(star({ Teff_K: 80000, ...o }), "wr");
  // Helium-dominant surface with no carbon/oxygen -> nitrogen sequence; hydrogen
  // still present makes it the late, H-rich WNh.
  assert.equal(wr({ X_surf: 0.3, Z_surf: 0.01, metals_surf: {} }).tag, "WNh");
  assert.equal(wr({ X_surf: 0.0, Z_surf: 0.01, metals_surf: {} }).tag, "WN");
  // Carbon/oxygen surfaced -> carbon sequence, and the oxygen-strong extreme -> WO.
  assert.equal(wr({ X_surf: 0, Z_surf: 0.6, metals_surf: { C: 0.4, O: 0.15 } }).tag, "WC");
  assert.equal(
    classifyLabel(star({ Teff_K: 210000, X_surf: 0, Z_surf: 0.7, metals_surf: { C: 0.3, O: 0.3 } }), "wr").tag,
    "WO");
});

test("REGRESSION: a carbon-surfaced star is never called nitrogen-sequence", () => {
  // The caption-honesty rule CLAUDE.md names by example. A WC surface must not
  // inherit the WN wording.
  const l = classifyLabel(star({ Teff_K: 90000, X_surf: 0, Z_surf: 0.6, metals_surf: { C: 0.5, O: 0.1 } }), "wr");
  assert.ok(!l.name.includes("nitrogen"), `a carbon surface was labelled "${l.name}"`);
  assert.ok(l.name.includes("carbon"));
});

test("a failed supernova is not narrated as an expanding fireball", () => {
  const s = star({ Teff_K: 30000 });
  assert.equal(classifyLabel(s, "sn", { failed: true }).tag, "failed SN");
  assert.ok(classifyLabel(s, "sn", { failed: true }).name.includes("black hole"));
  // The Teff-keyed narration only applies to a real explosion.
  assert.equal(classifyLabel(star({ Teff_K: 30000 }), "sn").tag, "SN II");
  assert.ok(classifyLabel(star({ Teff_K: 7000 }), "sn").name.includes("plateau"));
  assert.ok(classifyLabel(star({ Teff_K: 3000 }), "sn").name.includes("nebular"));
});

test("the stripped-star label reads the surface, then the stripped mass", () => {
  const st = (o, mStrip) => classifyLabel(star({ Teff_K: 50000, ...o }), "stripped", { mStrip });
  // A thin H envelope survives -> hot subdwarf, still H-rich.
  assert.equal(st({ X_surf: 0.6, Y_surf: 0.38 }, 0.5).tag, "sdB/O");
  // Helium-surfaced: a helium subdwarf below 1.5 M_sun, a proto-WR He star above.
  assert.equal(st({ X_surf: 0.01, Y_surf: 0.97 }, 0.5).tag, "sdO");
  assert.equal(st({ X_surf: 0.01, Y_surf: 0.97 }, 5.0).tag, "He★");
});

test("a state the panel would decline to paint returns null, not a blank label", () => {
  assert.equal(classifyLabel(null), null);
  assert.equal(classifyLabel({}), null);
  assert.equal(classifyLabel({ Teff_K: null, logg: 4 }), null);
});
