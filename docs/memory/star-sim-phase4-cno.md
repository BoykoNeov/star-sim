---
name: star-sim-phase4-cno
description: "Phase 4 per-element composition — StellarState metals dicts, MIST C/N/O (cache v2) → +Ne/Mg/Fe (v3) → +Si/S/Ca/Ti (v5) → +Na/Al/P (v6) → +Li (v7) → +Be/F light-element panel (v8; sixteen elements, sum ~0.99 Z). comp.js has THREE views: bulk, per-element detail (14, linear/log toggle), and a light view (mode=light, Li/Be/F, log forced) — the panel where fragile light-element depletion shows. Key gotchas: MIST diffusion → surface Fe NOT flat on MS; Na NOT inert (Ne-Na ×1.4); Li NOT inert (depletes ×74 @3M☉ tip) AND ~1e-10 of mass → INVISIBLE on linear → needed a log scale; Cr/Mn/Ni NOT in MIST's network; BORON dropped — MIST's only B isotope is radioactive b8 (~1e-83, not stable boron); Be depletes ×0.35 (more robust than Li), F flat (preserved this side of AGB) — fragility tracks burning T; every feh=0 test short-circuits _blend_windows (verify off-grid); chrome --headless --screenshot hijacks the user's running Chrome → use Playwright's bundled Chromium."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8091e83a-354e-4426-adb2-be1e38dc1644
---

Phase 4 (per-element composition) first path — **C/N/O** — is complete and
verified. Extends [[star-sim-composition-panel]] and the [[star-sim-mist-provider]]
pipeline; sits entirely behind the §3 boundary (no consumer learns where the
numbers came from).

**Boundary (`state.py`):** `StellarState` gained `metals_surf`/`metals_core`,
`dict[str, float]` of element symbol → mass fraction — a **breakdown of the
lumped Z**, not a replacement (X/Y/Z stay). Deliberately a **dict, not flat
fields**: the element set is open-ended (Fe/Ne/Mg are a one-line add later) and
element symbols are pure physics, not provider columns. Default empty so any
provider still satisfies the contract. `api.py` is unchanged — `asdict` carries
the new keys; the §3 swap point holds.

**Provider (`mist.py`):** v1 exposes C, N, O, each summed over isotopes
(C=c12+c13, N=n13+n14+n15, O=o14…o18) from `surface_`/`center_` columns. `_Track`
arrays Cs/Ns/Os/Cc/Nc/Oc; added to `_TRACK_COLS` with **`CACHE_VERSION` 1→2**
(old `.npz` rejected → one ~60 s reparse); mixed linearly in `_grid_window` +
`_blend_windows` (convex → §10 lies-between preserved); `_state_from_row` emits
**float-wrapped** values (raw np.float64 trips JSON at the API edge). Stub: a
**flat solar-ratio C/N/O split of Z** (no processing → surface==core, honest
"flavor").

**Tests (the proof, `test_mist_provider.py`):** CNO bounds (0≤elem≤Z, ΣCNO≤Z);
Sun surface solar-ballpark; **first dredge-up** at a 3 M☉ **grid point** (raw
MIST, no interp, clear of the ~2 M☉ roughness) ZAMS→max-R tip — surface N ×3.15,
C ×0.63, **assert N↑/C↓ only** (O barely moves, ×0.92 — flaky); core
CNO-equilibrium (core N≫surface N, core C≪surface C). `EXPECTED_KEYS` in
`test_stub_provider.py` updated. 58 pass.

**The verification trap (advisor catch):** every test + screenshot used
`feh=0.0`, which short-circuits `_bracket_feh` to the solar grid — so the six new
keys in `_blend_windows` never ran. Closed by **curl** at off-grid mass×[Fe/H]
(2.55/0.25 → p000↔p050; 1.3/−0.25 → m050↔p000): bounded CNO, no KeyError. If you
add columns to the blend, re-run this — `feh=0` will not exercise it.

**Frontend (`comp.js`):** a **bulk ↔ CNO toggle** (`setMode`). CNO view draws
C/N/O as lines with **independent core/surface y-scales** — core C/O reach tens
of % during CHeB (He→C,O) while surface stays ~1%, so a shared scale would erase
the surface dredge-up (the teaching moment). Toggle + swapping legends in
`index.html`/`styles.css`/`main.js`. No JS test harness — headless SwiftShader
screenshots are the regression check (Sun + 3 M☉ dredge-up confirmed). The Phase
4 CNO edits to index.html/styles.css were committed **together with** the
[[star-sim-frontend-ux]]-style Lane–Emden pedagogy pass, since they shared those
two files (user chose one combined commit).

**Widening to Ne/Mg/Fe (second Phase 4 path, complete):** the per-element view now
exposes **six** — C, N, O **+ Ne, Mg, Fe**. The dict design paid off: **`state.py`
untouched**. Threading mirrors the CNO add exactly — `_Track` `Nes/Mgs/Fes` +
`Nec/Mgc/Fec` (Ne=ne18…22, Mg=mg23…26, **Fe=fe56** is a *single* isotope; `sum()`
over one-element gen still returns the array), `_TRACK_COLS` + **`CACHE_VERSION`
2→3** (one ~60 s reparse), linear mix in `_grid_window`/`_blend_windows`, six dict
entries in `_state_from_row`. Stub `CNO_OF_Z`→`METALS_OF_Z` (+Ne 0.112/Mg 0.047/Fe
0.085 solar-fraction-of-Z; six sum ~0.82 Z, so sum<Z holds with ~1e-3 headroom).

**The gotcha worth remembering — Fe is NOT inert on the MS (advisor catch).** MIST
(Choi+2016) models **gravitational settling / element diffusion**, so surface metals
sink during the main sequence: the **Sun's surface Fe dips ~10% ZAMS→4.6 Gyr**
(measured ×0.90). Diffusion is **mass-dependent** (suppressed at higher mass). So:
the "inert tracer" test runs at **3 M☉** (diffusion-quiet: Fe ×1.00, Ne ×0.99, Mg
×1.00 while N ×3.15) and asserts a **relative** bound (|Δ|<5%), *not* flatness. Don't
write a "surface Fe constant at 1 M☉" assertion — it's physically wrong here.

**Fe as the [Fe/H]-axis validator:** surface Fe at ZAMS scales ~10^Δ[Fe/H] per grid
(measured Fe(+0.5)/Fe(0)=2.85, Fe(0)/Fe(−0.5)=3.05 vs 10^0.5=3.16 — lands a touch
*under* because [Fe/H] is a number ratio vs H while we report mass fractions and X
shifts with Z). `rel=0.20`, multifeh-gated. New/updated tests:
`test_metal_breakdown_present_and_bounded` (set = the six), `test_heavy_tracers_inert_while_cno_processes`,
`test_iron_validates_the_feh_axis`, stub `test_stub_metal_breakdown_bounded`. 60 pass.
This time the feh-blend path was curl-verified live (off-grid 2.7 M☉ / [Fe/H]=0.25 →
six bounded keys, no KeyError; 505 track rows same keyset). Frontend: `comp.js`
`ELEMS`/`ELEM_COL`→six (atomic-number order; Fe steel-grey), drawing loop already
generic; legend 3→6 (flex-wraps), button→"per-element detail", **both** tooltips
updated, internal `mode="cno"` id kept. Verified by **headless Chrome** screenshot of
a throwaway probe rendering real 3 M☉ `/track` in cno mode (no SwiftShader needed;
chrome.exe `--headless=new --virtual-time-budget`).

**Widening to Si/S/Ca/Ti (third Phase 4 path, complete):** the per-element view now
exposes **ten** — the six **+ Si, S, Ca, Ti**. Dict design paid off a third time
(**`state.py` untouched**). Threading mirrors Ne/Mg/Fe exactly — `_Track`
`Sis/Ss/Cas/Tis` + `Sic/Sc/Cac/Tic` (Si=si27…30, S=s31…34, **Ca=ca40** & **Ti=ti48**
both *single* isotope like Fe — **verified against the real MIST track header before
coding, not assumed**), `_TRACK_COLS` + **`CACHE_VERSION` 4→5** (one ~60 s reparse),
linear mix in `_grid_window`/`_blend_windows`, ten dict entries in `_state_from_row`.
Field-name convention is trailing `s`=surface/`c`=core, so **`Sc` is sulfur-core, not
scandium** (commented). Stub `METALS_OF_Z` +Si 0.044/S 0.020/Ca 0.0042/Ti 0.0002
(solar fraction-of-Z; ten sum ~0.89 Z in the stub).

**Headroom shrank as predicted — re-measure it, don't trust the green assert.** At the
Sun the ten MIST elements sum to **~0.98 of Z** (surface 0.982, core 0.976 — headroom
only ~3e-4, still ≫ 1e-9 slack). The bound is *physically* guaranteed (named elements
are a disjoint subset of the metals), so a sum >Z would mean a **double-counted
isotope** — re-measuring the real sum/Z is the actual correctness check; the
`sum<=z+1e-9` assert stays green either way and its docstring number silently rots.
Updated `test_metal_breakdown_present_and_bounded` (set = the ten; real sum/Z in
docstring) + extended `test_heavy_tracers_inert_while_cno_processes` to assert
Si/S/Ca/Ti also ×1.00 at the 3 M☉ RGB tip (genuinely inert this side of the AGB);
stub `test_stub_metal_breakdown_bounded`. **63 pass (unchanged count — extended
existing tests, no new ones).** Blend path verified again off-grid (2.7 M☉ /
[Fe/H]=0.25 → ten bounded keys; all 606 track rows same keyset & bounded). Frontend:
`comp.js` `ELEMS`/`ELEM_COL`→ten (atomic order C→Fe; four new fill the open hue gaps:
Si violet/S sulfur-chartreuse/Ca red/Ti cyan), drawing loop already generic; legend
6→10 (still flex-wraps, 4+4+2), both tooltips + panel `<h2>` updated, `mode="cno"` id
kept. Verified by headless Chrome (Playwright, present in the backend venv) screenshot
of the live app at 3 M☉ in cno mode: ten distinct lines, surface dredge-up + core C/O
spike intact, no JS errors.

**Widening to Na/Al/P (fourth Phase 4 path, complete):** the per-element view now
exposes **thirteen** — the ten **+ Na, Al, P** (odd-Z light metals). Dict design paid
off a fourth time (**`state.py` untouched**). Threading mirrors Si/S/Ca/Ti exactly —
`_Track` `Nas/Als/Ps` + `Nac/Alc/Pc` (Na=na21…24, Al=al25…27, P=p30+p31), `_TRACK_COLS`
+ **`CACHE_VERSION` 5→6** (one ~60 s reparse), linear mix in `_grid_window`/`_blend_windows`,
thirteen dict entries in `_state_from_row`. Stub `METALS_OF_Z` +Na 0.0020/Al 0.0038/P
0.0004 (Asplund fraction-of-Z; thirteen sum ~0.90 Z in stub). `Pc`=phosphorus-core
(commented by the `Sc`=sulfur-core note).

**The two findings worth keeping (both verify-don't-assume):**
1. **Cr/Mn/Ni do NOT exist in MIST v2.5** — the requested set was Na/Al/P **+ Cr/Mn/Ni**,
   but the real track header's isotope columns stop at the Ca40/Ti48/Fe56 region; there
   are *no* chromium/manganese/nickel columns. So only Na/Al/P were addable. (CLAUDE.md's
   old "Na/Al/P/Cr/Mn/Ni — same one-line add" backlog line was an untested assumption —
   exactly the Ca/Ti "check the header first" lesson again.)
2. **Na is NOT inert (advisor + measured)** — the Ne-Na cycle dredges it up, so surface
   Na rises **×1.41** at the 3 M☉ RGB tip (real Na-O / Na-rich-giant physics). So Na gets
   its *own* `>1.2` assertion in `test_heavy_tracers_inert_while_cno_processes`; only
   **Al/P** join the inert loop (both ×1.00). Don't put Na in the inert set.

**Honesty note (advisor) — this path is filler-plus-one-invisible-wrinkle.** `comp.js`'s
`region()` scales each sub-chart to one max (surface ≈ O at 7e-3); Na's 3e-5 enrichment is
a **sub-pixel wiggle**, and Al/P (5.9e-5 / 8e-6) join Ca/Ti as floor-huggers. So the Na
dredge-up is a *data-only* signal the user never sees — making it visible (per-line
normalize / log scale) is a separate rendering decision, not "add elements." Headroom held
but shrank: thirteen sum to **~0.99 of Z** at the Sun (surface 0.988, core 0.989, headroom
~2e-4). Updated `test_metal_breakdown_present_and_bounded` (set = thirteen, real surface+core
sum/Z in docstring) + `test_heavy_tracers_inert_while_cno_processes` (Al/P inert, Na carved
out); stub `test_stub_metal_breakdown_bounded`. **90 pass (unchanged — extended existing
tests).** Blend path verified off-grid (2.7 M☉ / [Fe/H]=0.25 → thirteen bounded keys; 606
rows same keyset). Frontend: `comp.js` `ELEMS`/`ELEM_COL`→thirteen (atomic order,
**interleaved** — Na after Ne, Al after Mg, P after Si, *not* appended; Na sodium-D
yellow/Al silver/P orchid fill open hue gaps), drawing loop already generic; legend 10→13,
both tooltips + `<h2>` updated, `mode="cno"` id kept. Verified by headless Chrome screenshot
of a throwaway probe rendering real 3 M☉ `/track` in cno mode (thirteen lines, dredge-up +
core spike intact, Na/Al/P as expected floor-huggers, legend wraps, no JS errors).

**Widening to Li + the log-scale view (fifth Phase 4 path, complete):** the per-element view
now exposes **fourteen** — the thirteen **+ Li** (li7, single isotope; placed *first* in
`ELEMS`, atomic Z=3). Threading mirrors Na/Al/P — `_Track` `Lis/Lic`, `_TRACK_COLS` +
**`CACHE_VERSION` 6→7** (one ~60 s reparse; full suite cold 227 s), linear mix in
`_grid_window`/`_blend_windows`, one dict entry in `_state_from_row`; stub `METALS_OF_Z`
Li 3.8e-9 (depleted-photospheric flat floor). **But the headline: this was NOT a one-line
dict add** (CLAUDE.md/this-memory's old "one-line add" claim was wrong — caught by advisor +
measurement *before* coding). Surface Li is **~1e-10 of mass** — a *million×* below Na, which
the Na path already called "a sub-pixel wiggle" — so on `comp.js`'s shared **linear** scale Li
renders flat on the zero axis. A data-only add = an invisible 14th line = the exact "dishonest
green check" the project guards against, defeating the whole reason Li was picked. **The visible
payoff required a rendering change.** Surfaced it to the user as a fresh decision (premise of
their pick changed); they chose a **linear/log toggle** (advisor's lean; linear stays default).

**The log path (`comp.js`):** `setScale("lin"|"log")` + `region()` log branch — a **decade-
rounded window capped to [4,10] decades** (so a lone ~1e-16 core-Li sample can't stretch the
axis to 15 decades), values at/below the floor (Li once it burns to ~0) **clamp to the bottom**
so the plunge reads as "off the bottom", not a NaN gap; faint decade gridlines + `1e±N` tick
labels. lin/log buttons in `.comp-modes` (shown only in cno mode via CSS), wired in `main.js`
like the mode toggle.

**Li physics (measured, grounds the tests):** surface Li at 3 M☉ ZAMS 1.0e-8 → RGB tip
1.35e-10 = **74× plunge** (tip/zams 0.0135); Sun ×0.87 over the MS (the famous solar-Li
problem) then ×~2400 by the RGB tip; core Li ~1e-16 (burned instantly the whole MS). **So Li
is NOT inert** — carved out of `test_heavy_tracers_inert_while_cno_processes` with its own
`<0.1` assertion (like Na), **plus** a dedicated `test_surface_lithium_depletes` (tip/zams<0.05
+ core Li ≪ surface Li). Bound set → fourteen (sum still ~0.99 Z, Li adds ~1e-10); stub set →
fourteen. **91 pass (was 90 — the new Li test).** Blend path verified off-grid (2.7 M☉ /
[Fe/H]=0.25 → 606 rows, fourteen bounded keys, surface Li depletes 1.93e-8→2.67e-10).

**Pedagogy (the user's explicit second ask: "why this happens, where to look"):** per-element
legend hover stories (Li: burns low-T → dredged down & destroyed, *switch to log to watch it
plunge*; C/N/O dredge-up; Na Ne-Na enrichment; Fe inert + low-mass diffusion; Ne/Mg/Al/Si/P/S/Ca/Ti
a per-element inert-tracer gloss), a `?` on the scale toggle for the log rationale, panel `<h2>`
+ mode-help prose updated. Verified the payoff via **Playwright** screenshot (linear → Li flat/
invisible; log → surface Li plunges off the bottom at the RGB, core Li pinned at floor; 14 lines
legible across decades, no JS errors). **Tooling gotcha:** the user's running Chrome **hijacks**
`chrome --headless --screenshot` ("Opening in existing browser session", even with a fresh
`--user-data-dir`) → the reliable headless path here is **Playwright's bundled Chromium** (`npm
i playwright` + `npx playwright install chromium` in the scratchpad); throwaway probe
`frontend/_li_probe.html` deleted after.

**Li/Be/F light-element panel (sixth Phase 4 path, complete) — the *panel*, not a one-off.** A
**third** comp view (`mode="light"`): the fragile light elements on a **forced-log** scale, where
their depletion shows — instead of three more floor-hugger lines in the fourteen-element cno view
(the whole point). Threading mirrors the Li add: `_Track.Bes/Fs` + `Bec/Fc` (Be=be7+be9+be10,
F=f17+f18+f19), `_TRACK_COLS` (Be after Li, F after O) + **`CACHE_VERSION` 7→8** (one ~60 s/grid
reparse), linear mix in `_grid_window`/`_blend_windows`, two dict entries each in `_state_from_row`;
field convention `Fs`/`Fc`=fluorine vs `Fes`/`Fec`=iron (commented). Stub `METALS_OF_Z` +Be 1.0e-8/
F 2.4e-5 (flat floors). Element set → **sixteen** (sum still ~0.99 Z).

**The finding that reshaped it — BORON WAS DROPPED (measured before coding, advisor-confirmed).**
The request was Be/**B**/F and the old CLAUDE.md/this-memory claimed "all three are in the network
like Li" — **wrong for boron.** MIST v2.5's *only* boron isotope is **`b8`, which is RADIOACTIVE**
(β⁺ decay, t½≈0.77 s — the pp-III branch that makes the high-energy solar neutrinos), so
`surface_b8` ≈ **1e-83** — a numerical-zero transient, not stable boron (no b10/b11 in the network).
A flat 1e-83 line on a log axis = the exact invisible floor-hugger the panel exists to avoid → **B
excluded.** Subtler than the Cr/Mn/Ni case: there the columns didn't exist; here the column exists
but its lone isotope is radioactive. (Same lesson regardless: **read the header / measure the real
abundance before believing an element is usable.**) So the deliverable is honestly **Li/Be/F**, not
Be/B/F — surfaced loudly to the user, didn't block on a question (Cr/Mn/Ni precedent).

**Be/F physics (measured, grounds the test) — fragility tracks burning temperature.** Surface
depletion at 3 M☉ ZAMS→first-ascent RGB tip: **Li ×0.0135** (~2.5 MK, plunges), **Be ×0.35**
(~3.5 MK, depletes modestly — *more robust* than Li), **F ×0.91** (preserved this side of the AGB —
the stable backdrop, the role Fe plays in the cno view; F's enrichment story is on the excluded
TPAGB). be9 dominates Be / f19 dominates F (be7 EC-decays ~53 d, f17/f18 short-lived) so all-isotope
sum = stable value. New `test_light_elements_deplete_in_burning_temperature_order` (Be `0.1<r<0.6`
AND `be_r>li_r`; F `0.8<r<1.1`) — **Be/F deliberately NOT in the inert loop.** Updated bound set +
stub set → sixteen, boron-absence documented. **92 pass (was 91).** Blend path verified off-grid
(2.7 M☉ / [Fe/H]=0.25 → 606 rows, sixteen bounded keys, ordering holds: Li 0.016/Be 0.40/F 0.93).

**Frontend (`comp.js`):** `LIGHT_ELEMS=[Li,Be,F]` + `drawLight()` reusing a **parameterized
`region(...,elems,useLog)`** (the cno view now passes `ELEMS, scale==="log"`); `setMode` accepts
"light"; third mode button + `legend-light` (per-element fragility hover stories) + CSS `mode-light`
rules (scale toggle stays **cno-only** — light is log-only); `main.js` toggles `mode-cno`/`mode-light`
mutually. Panel `<h2>` tooltip explains boron's absence in plain language. Verified via **Playwright
(bundled Chromium)** driving the *real served UI* (not a probe HTML this time): light button →
`mode-light` class + legend swap + scale-toggle hidden + no JS errors; screenshot = surface Li
plunging on the lower RGB, Be dipping modestly, F flat, and the cno-log view still renders fourteen
elements intact after the `region()` refactor.

**Next Phase 4 paths:** the per-element view is **done through Li** and the **light-element panel is
done (Li/Be/F)**. Lesson holds: **adding more individual metals is a dead end** — Cr/Mn/Ni aren't in
MIST, Na/Al/P are invisible floor-huggers, **boron's only isotope is radioactive**. The network has
no other clean fragile-light candidate (next nuclides up are the C/N/O the cno view covers).
Remaining bigger arcs: the solar MESA-Web grid (data task, see [[star-sim-phase4-mesa]]), deferred
**TPAGB thermal pulses** (§6 messy phase), eventually a live solver (out of scope).
