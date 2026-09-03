# `frontend/tests` — the pure-helper harness

```
cd frontend/tests && node --test
```

Node ≥ 18, no npm install, no bundler, no config: the files are `.mjs` so bare Node
treats them as ES modules without a `package.json`, and they import the real
`frontend/src/*.js` unchanged. CI runs exactly this (`.github/workflows/ci.yml`,
the `frontend` job).

Run it from *inside* the directory with no argument, as above. Bare `node --test`
discovers `*.test.mjs` by Node's own naming convention on every version; a glob
argument needs Node ≥ 22, and passing the directory as an argument behaves
differently across versions (it fails outright on Node 24). One form that works
everywhere beats three that each work somewhere.

**What belongs here.** Only the modules that are pure functions of numbers —
`color.js`, `hz.js`, `seismo.js`, `gravdark.js`, `classify.js`, `reddening.js`,
`controls.js`.
Everything else in `frontend/src` draws on a canvas or owns DOM, and the
Playwright screenshot pass (1440 + 390 px, zero console errors) stays the
regression check for those. Do not add a DOM shim to widen this net: if a helper
is worth testing, extract the pure part into a named export the way
`classifyLabel` was extracted out of `createClassification`.

**What the tests assert, in priority order.**

1. **Identities the module's own header states** — `kEq²·kPol = 1`, flux
   conservation, the seismic relations inverting back to the inputs. These catch
   a flipped sign or a wrong exponent; a value pinned from today's output would
   preserve both.
2. **Honesty gates** — the documented refusals: out-of-range → `null`, a
   non-rotator → byte-identical round star, `A_V = 0` → exactly 1.0.
3. **Published anchors** — the Sun's habitable zone, the solar `ν_max`/`Δν`.
   These come from the literature, not from this code.
4. **Regressions for bugs the headers record** — 740 nm rendering green before
   the hue clamp; a bright giant flattening to a 1.5 axis ratio.

A number pinned by running the current implementation is labeled
**"pinned from current implementation"** in a comment. Anything not so labeled is
an independent check. Keeping that line visible is the point of the harness —
this project's recurring defect is *plausible but wrong*, and a golden value
harvested from the code under test cannot catch it.

`controls.js` is here for a second reason worth keeping in mind: it exists *because*
the wiring split needed something a test could hold. `main.js` itself can't be
imported here (it touches the DOM at module load), so the way to test anything it
does is to extract the numbers-only part — which is also how the seven copies of the
snap loop were found in the first place.

Note for whoever next edits `canvas.js`: `seismo.js` imports it, and importing it
under bare Node only works because `fitCanvas` touches `window` inside its body.
Hoisting a `window.devicePixelRatio` read to that module's top level would break
`seismo.test.mjs` with a confusing error a long way from the cause.
