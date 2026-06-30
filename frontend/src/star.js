// Phase 2 star renderer (STAR_SIM_SPEC.md §7): a sphere whose every visual
// parameter is driven by a real number from StellarState. Layers, in the spec's
// order of physical rigor:
//
//   * COLOR     — Planck->CIE->sRGB from Teff (color.js); the honest pixel.
//   * GRANULATION — Worley/cellular noise whose cell density comes from the
//                 pressure scale height H_p ∝ Teff / g (via logg). A compact
//                 dwarf shows fine granules; a low-gravity giant shows a handful
//                 of enormous convective cells. This single relation makes the
//                 aesthetics encode genuine physics.
//   * LIMB DARKENING — a standard quadratic law across the disk.
//   * ROTATION  — differential (faster equator) shear of the noise field, since
//                 the v/vcrit=0 MIST grid gives no real v_rot (state.v_rot_kms is
//                 null); the rate here is a plausible *visual* one, not measured.
//   * CORONA    — an additive outer glow whose brightness/extent track the
//                 `activity` proxy. EVOCATIVE, NOT PREDICTIVE (spec §7): real
//                 coronae/winds are magnetic (cool stars) or radiatively driven
//                 (hot O/B stars) structure we are not modeling. A hot, low-
//                 activity star is therefore near-glowless on purpose.
//
// All of it reads from the one StellarState the HR marker is showing, so the
// picture, the diagram and the numbers always describe one consistent star (§3).

import * as THREE from "three";

import { teffToLinearRGB } from "./color.js";

// Map a physical radius (R_sun, ~0.05 .. ~1000) onto an on-screen sphere radius
// via log scaling, so dwarfs and giants both stay visible. The true R is always
// in the readout; the *granule* density is independent of this on-screen size
// (it's a shader frequency, set from physics — see granuleCells).
function displayRadius(rRsun) {
  const lr = Math.log10(Math.max(1e-3, rRsun)); // ~ -3 .. 3
  const t = (lr + 2) / 5; // normalize roughly [-2, 3] -> [0, 1]
  const base = 0.45 + 2.0 * Math.max(0, Math.min(1, t));
  // Render ~20% larger than the historical sizing (a UX ask). Clamped so the very
  // largest giants still fit the frame: the camera (z=8, 40° vertical FOV) sees a
  // sphere out to its tangent cone, where the disk edge clips at asin(R/8)=20° -> R≈
  // 2.74. 2.65 keeps a small margin (+ antialiasing room); everything up to ~250 R☉
  // gets the full 1.2×, only the biggest giants are gently compressed to fit.
  return Math.min(2.65, 1.2 * base);
}

// Granule cell frequency across a stellar radius from the pressure scale height:
// H_p = kT/(μ m_H g) ∝ T/g, and the number of granules across the disk ~ R/H_p
// ∝ R·g/T. With g = 10^logg (cgs), the dimensionless Q = R·10^logg/Teff carries
// it; the Sun (Q≈4.8) is tuned to ~22 cells. Clamped: the LOW floor *is* the
// spec's "handful of enormous cells" for a supergiant (Q drives it well below 1);
// the high cap stops a compact dwarf aliasing into noise.
function granuleCells(state) {
  const g = Math.pow(10, state.logg);
  const Q = (state.R_rsun * g) / state.Teff_K;
  return Math.max(2.5, Math.min(90, 4.6 * Q));
}

// 0..1 activity proxy (spec §7) drives the corona; null (unmodeled) -> 0.
const activityOf = (state) =>
  state.activity == null ? 0 : Math.max(0, Math.min(1, state.activity));

// --- shared GLSL --------------------------------------------------------------
// linear sRGB -> display sRGB (the gamma transfer applied ONCE, at the end of
// each shader, so all surface math stays in physically-linear light).
const GLSL_LIN2SRGB = `
vec3 lin2srgb(vec3 c) {
  c = max(c, 0.0);
  return mix(12.92 * c, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}`;

// --- surface shader -----------------------------------------------------------
const SURFACE_VERT = `
varying vec3 vObjPos;     // unit-sphere object position (scale-independent)
varying vec3 vViewNormal;
varying vec3 vViewPos;
void main() {
  vObjPos = normalize(position);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  vViewPos = mv.xyz;
  vViewNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * mv;
}`;

const SURFACE_FRAG = `
precision highp float;
uniform vec3  uColor;     // LINEAR sRGB base color (Teff)
uniform float uTime;      // seconds, from a real clock
uniform float uCells;     // granule frequency (cells across a radius)
uniform float uContrast;  // granule brightness contrast
uniform float uOmega;     // equatorial angular rate (rad/s, visual)
uniform float uShear;     // differential-rotation fraction (poles slower)
uniform float uLife;      // granule lifetime / reform cycle (s)
uniform float uGran;      // granulation amount (1 = living star, 0 = smooth WD)

varying vec3 vObjPos;
varying vec3 vViewNormal;
varying vec3 vViewPos;

${GLSL_LIN2SRGB}

// Hash a lattice point to a vec3 in 0..1 — a sin-free hash (Dave Hoskins'
// hash33). The classic fract(sin(dot(...))*k) hash loses precision in sin() of
// large arguments, and its linear dot-product inputs leave each cell's feature
// offset CORRELATED along the object axes — so at low cell counts (a supergiant's
// "handful of enormous cells") the Worley centres line up in rows/columns and the
// cubic lattice reads as a rectangular grid. This decorrelates the per-cell
// offsets, so even a few big cells scatter organically instead of tiling.
vec3 hash3(vec3 p) {
  p = fract(p * vec3(0.1031, 0.1030, 0.0973));
  p += dot(p, p.yxz + 33.33);
  return fract((p.xxy + p.yxx) * p.zyx);
}

// 3D Worley F1: distance to the nearest feature point, the points slowly
// orbiting inside their cells over time -> the convective "boil".
float worleyF1(vec3 x, float t) {
  vec3 ip = floor(x);
  vec3 fp = fract(x);
  float d = 1e9;
  for (int k = -1; k <= 1; k++)
  for (int j = -1; j <= 1; j++)
  for (int i = -1; i <= 1; i++) {
    vec3 g = vec3(float(i), float(j), float(k));
    vec3 o = hash3(ip + g);
    o = 0.5 + 0.5 * sin(t + 6.2831853 * o);   // animate each feature point
    vec3 r = g + o - fp;
    d = min(d, dot(r, r));                     // squared distance is fine
  }
  return sqrt(d);
}

// One generation of granulation: two Worley octaves at a sampling point rotated
// by ang about the pole, the cell layout reseeded per generation gen so
// successive generations are unrelated (granules fully reform). F1 ~0 at cell
// centers (bright granules), larger toward the intergranular lanes (dark).
//
// Each octave is antialiased independently against fw — the object-space size of
// one screen pixel (length(fwidth(vObjPos))). An octave at frequency F resolves
// only while a pixel spans well under one of its cells (F·fw ≲ 0.5); past that it
// can only beat against the pixel grid into moiré, so we fade it toward the Worley
// mean (≈0.54 → the smooth mean surface). Per-octave, not one fade on the sum: the
// fine 2.7× octave sub-pixels first, so on a mid star (an M dwarf) it dissolves
// while the coarse octave stays crisp; only on a compact dwarf, or at the
// foreshortened limb where fw blows up, do both octaves smooth out. Conserving the
// mean (mix toward WMEAN, not 0) keeps the smoothed disk the same brightness as a
// boiling one — no pop as detail fades.
float genGranule(vec3 p, float ang, float gen, float fw) {
  float ca = cos(ang), sa = sin(ang);
  vec3 q = vec3(p.x * ca - p.z * sa, p.y, p.x * sa + p.z * ca);
  vec3 seed = vec3(gen * 17.0, gen * 11.0, gen * 5.0);   // new layout each cycle
  const float WMEAN = 0.54;
  float a1 = 1.0 - smoothstep(0.5, 1.1, fw * uCells);
  float a2 = 1.0 - smoothstep(0.5, 1.1, fw * uCells * 2.7);
  float f  = mix(WMEAN, worleyF1((q + seed) * uCells, gen * 10.0 + uTime * 0.3), a1);
  f += 0.5 * mix(WMEAN, worleyF1((q + seed) * uCells * 2.7, gen * 13.0 + uTime * 0.45), a2);
  return f / 1.5;
}

// Granulation with STABLE rotation. The visible spin is a continuous *rigid*
// rotation (latitude-independent -> no shear, so it can never wind up). The
// differential part (faster equator, Ω = A − B·sin²lat) is applied only as a
// *bounded* shear that runs ±half a cycle and resets every granule lifetime;
// two generations offset by half a lifetime are cross-faded (triangle weights
// that sum to 1) so cells dissolve and reform — solar, and streak-proof, since
// the shear never accumulates past one lifetime.
float granulation(vec3 p0, float time, float fw) {
  float rigid = uOmega * time;                           // continuous, all latitudes
  float sinLat = clamp(p0.y, -1.0, 1.0);
  float diffRate = -uOmega * uShear * sinLat * sinLat;   // latitude-dependent deviation
  float tt = time / uLife;
  float sA = fract(tt),        sB = fract(tt + 0.5);
  float gA = floor(tt),        gB = floor(tt + 0.5);
  float wA = 1.0 - abs(2.0 * sA - 1.0);
  float wB = 1.0 - abs(2.0 * sB - 1.0);
  float fA = genGranule(p0, rigid + diffRate * (sA - 0.5) * uLife, gA, fw);
  float fB = genGranule(p0, rigid + diffRate * (sB - 0.5) * uLife, gB, fw);
  return (wA * fA + wB * fB) / max(1e-3, wA + wB);
}

void main() {
  // A cooling white dwarf's photosphere is a featureless, limb-darkened disk — its
  // atmosphere is in radiative equilibrium, not the convective "boil" of a cool MS
  // star — so uGran fades the granulation out entirely (smooth is the MORE accurate
  // look here, not a shortcut). uGran=1 keeps the full living-star granulation.
  // (Crystallization is a CORE phenomenon, shown in the structure panel — never on
  // this gaseous surface, which has no lattice.)
  // fw = object-space size of one screen pixel on the unit sphere; granulation()
  // uses it to antialias each Worley octave (fade sub-pixel boil to the smooth mean
  // instead of moiré — see genGranule). Analytic frequency, not fwidth(f): the
  // latter spikes on the Worley cell-edge ridges and would erode the dark lanes.
  float fw = length(fwidth(vObjPos));
  float f = granulation(vObjPos, uTime, fw);
  float lanes = clamp(f / 0.9, 0.0, 1.0);
  float granule = 1.0 - uContrast * lanes * uGran;

  // Limb darkening (quadratic law): μ = cos(angle to the viewer). The camera is
  // at the origin in view space, so the view direction is -normalize(vViewPos).
  vec3 viewDir = normalize(-vViewPos);
  float mu = clamp(dot(vViewNormal, viewDir), 0.0, 1.0);
  const float u1 = 0.4, u2 = 0.26;            // sun-like quadratic coefficients
  float limb = max(0.0, 1.0 - u1 * (1.0 - mu) - u2 * (1.0 - mu) * (1.0 - mu));

  vec3 surface = uColor * granule * limb;
  gl_FragColor = vec4(lin2srgb(surface), 1.0);
}`;

// --- corona shader ------------------------------------------------------------
// A camera-facing additive quad with a radial glow that is brightest right at
// the star's limb and decays outward (an exponential falloff), so there's no
// detached ring. `uInnerFrac` is the star's silhouette as a fraction of the
// quad's half-size, so the glow is masked off the disk itself. The camera sits
// fixed on the z-axis looking at the origin, so a plane in the xy-plane already
// faces it — no billboard math needed.
const CORONA_VERT = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const CORONA_FRAG = `
precision highp float;
uniform vec3  uColor;       // LINEAR sRGB tint (star color)
uniform float uIntensity;   // overall glow strength (activity-driven)
uniform float uInnerFrac;   // star limb as a fraction of the quad half-size (=1/extent)
uniform float uFalloff;     // outward decay rate (larger -> tighter glow)
varying vec2 vUv;

${GLSL_LIN2SRGB}

void main() {
  float d = length(vUv - 0.5) * 2.0;          // 0 at center .. 1 at the quad edge
  // Work in units of the star's limb radius: rd = 1 exactly at the silhouette.
  // This keeps the inner softness a fixed few-percent of the star, independent
  // of how far the glow reaches.
  float rd = d / uInnerFrac;
  float rim = smoothstep(0.92, 1.06, rd);             // soft rise hugging the limb
  float decay = exp(-max(0.0, rd - 1.0) * uFalloff);  // fade outward (==1 over the disk)
  float edge = 1.0 - smoothstep(0.98, 1.0, d);        // clean cutoff at the quad edge
  float a = clamp(rim * decay * edge * uIntensity, 0.0, 1.0);
  // rgb = display hue, alpha = glow magnitude (AdditiveBlending: src.rgb*src.a).
  gl_FragColor = vec4(lin2srgb(uColor), a);
}`;

// --- Wolf–Rayet wind shader (Chunk 5) -----------------------------------------
// The WR endgame's optically-thick-wind look. A WR's *apparent* surface is not the
// hydrostatic core but a dense, fast, radiatively-driven wind — so instead of a hard
// limb we wrap the (still-opaque) hot sphere in a luminous, streaming halo: an
// electron-scattering haze brightest right at the limb (softening the silhouette into
// the wind — the "pseudo-photosphere"), decaying outward, broken up by radial outflow
// filaments that drift away from the star over time. EVOCATIVE, NOT PREDICTIVE (the
// corona precedent, spec §7): the *color* is the honest blackbody at Teff, but the halo
// is illustrative — its brightness is NOT a measured mass-loss rate (the grid's star_mdot
// is deliberately not on StellarState) and the filaments are not real emission-line
// structure (the spectrum panel shows the honest "no WR model yet" placeholder). The only
// state-driven cues are the Teff color, the radius (fit-to-frame, below) and a Z_surf knob
// that makes the carbon/oxygen (WC/WO) wind denser and clumpier than the smoother helium
// (WN) wind. No granulation — a stripped, wind-driven core is not convective.
const WIND_FRAG = `
precision highp float;
uniform vec3  uColor;      // LINEAR sRGB continuum color (Teff) — the honest pixel
uniform float uTime;       // seconds (real clock) — animates the outflow
uniform float uIntensity;  // overall wind brightness (evocative; NOT a measured mass-loss rate)
uniform float uInnerFrac;  // star limb as a fraction of the quad half-size (= 1/extent)
uniform float uFalloff;    // radial decay of the haze beyond the limb
uniform float uDensity;    // filament contrast (0 ~ smooth WN haze .. 1 ~ clumpy WC/WO wind)
varying vec2 vUv;

${GLSL_LIN2SRGB}

// Cheap 2D value noise (hash + smooth bilinear) for the wind's turbulent filaments.
float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 345.45));
  p += dot(p, p + 34.345);
  return fract(p.x * p.y);
}
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
  vec2 c = vUv - 0.5;
  float d = length(c) * 2.0;                 // 0 at center .. 1 at the quad edge
  float rd = d / uInnerFrac;                 // radius in units of the star limb (1 = silhouette)
  vec2 dir = c / max(1e-4, length(c));       // outward unit direction

  // Electron-scattering haze: a smooth radial envelope brightest in a thin annulus AT
  // the limb (rd≈1) — softening the hard sphere edge into the wind (the optically-thick
  // pseudo-photosphere) — then decaying outward. Suppressed over the inner disk
  // (rd<~0.6) so the bright hot core stays readable rather than washed out.
  float core = smoothstep(0.6, 1.0, rd);
  float decay = exp(-max(0.0, rd - 1.0) * uFalloff);
  float haze = core * decay;

  // Radial outflow filaments: 2D value-noise turbulence sampled in cartesian space
  // (no atan -> no angular seam) and advected OUTWARD over time, so the wind visibly
  // streams away from the star. Two decorrelated octaves so low-frequency cells scatter
  // organically instead of lining up into spokes. The smooth haze is the base; uDensity
  // controls how much the filaments break it up (WN ~ smooth, WC/WO ~ clumpy).
  vec2 p1 = c * 6.0  - dir * uTime * 0.40;
  vec2 p2 = c * 11.0 - dir * uTime * 0.63 + 7.3;
  float turb = vnoise(p1) * 0.62 + vnoise(p2) * 0.38;
  float fil = mix(0.85, turb * 1.7, clamp(uDensity, 0.0, 1.0));

  float edge = 1.0 - smoothstep(0.95, 1.0, d);   // clean cutoff at the quad's own edge
  float a = clamp(haze * fil * edge * uIntensity, 0.0, 1.0);
  gl_FragColor = vec4(lin2srgb(uColor), a);
}`;

// --- supernova fireball shader (Chunk 3) --------------------------------------
// The core-collapse SN endgame's 3D: an expanding, cooling ball of homologously-
// expanding ejecta that, as it thins, dissipates to reveal the compact remnant. Like
// the WR wind it is EVOCATIVE, NOT PREDICTIVE (the corona precedent, spec §7) — but
// the one honest, load-bearing cue is the *color*: uColor is the real blackbody at the
// photosphere Teff, so the fireball blue-white→orange→red shift over the scrub is the
// genuine cooling of the expanding photosphere (the same Teff the readout and SED show).
// Everything else is illustrative: the turbulent cells are not resolved ejecta clumps,
// and the on-screen size is decoupled from the true R (the photosphere reaches hundreds
// of AU within months — the scale bar carries the honest radius). Rendered on a back-
// face-culled sphere (one additive layer, so a bounded per-fragment alpha keeps the hue
// and the cell structure instead of saturating to white), it boils via a bounded noise
// orbit (no unbounded drift / seam) and, as uFade rises, breaks into sparse filaments
// and dims toward nothing — clearing the frame for the remnant dot (or, for a black
// hole, leaving it dark: the star "winks out").
const FIREBALL_FRAG = `
precision highp float;
uniform vec3  uColor;      // LINEAR sRGB blackbody color at the photosphere Teff — the honest pixel
uniform float uTime;       // seconds (real clock) — boils the ejecta
uniform float uIntensity;  // overall fireball brightness (a gentle, clamped L tie; evocative)
uniform float uFade;       // 0 = young opaque fireball .. 1 = dissipated thin ejecta (remnant emerges)
varying vec3 vObjPos;
varying vec3 vViewNormal;
varying vec3 vViewPos;

${GLSL_LIN2SRGB}

// Scalar 3D value noise (hash + trilinear smoothstep) — the fireball's turbulence.
float hash31(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float vnoise3(vec3 x) {
  vec3 i = floor(x), f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  float n000 = hash31(i + vec3(0.0, 0.0, 0.0));
  float n100 = hash31(i + vec3(1.0, 0.0, 0.0));
  float n010 = hash31(i + vec3(0.0, 1.0, 0.0));
  float n110 = hash31(i + vec3(1.0, 1.0, 0.0));
  float n001 = hash31(i + vec3(0.0, 0.0, 1.0));
  float n101 = hash31(i + vec3(1.0, 0.0, 1.0));
  float n011 = hash31(i + vec3(0.0, 1.0, 1.0));
  float n111 = hash31(i + vec3(1.0, 1.0, 1.0));
  return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y),
             mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);
}
// fbm whose octaves each ride a slow, BOUNDED orbit (sin/cos of time) rather than a
// monotonic drift — so the surface roils like a fireball without any feature sliding off
// to infinity (uTime is the real, ever-increasing clock) or a directional seam.
float fireFbm(vec3 p, float t) {
  float a = 0.0, w = 0.55, freq = 1.0;
  for (int k = 0; k < 4; k++) {
    float fk = float(k);
    vec3 orbit = vec3(sin(t * 0.27 + fk), cos(t * 0.31 + fk * 1.7), sin(t * 0.23 + fk * 2.3)) * 0.45;
    a += w * vnoise3(p * freq + orbit);
    freq *= 2.03; w *= 0.5;
  }
  return a;   // ~0 .. ~1.1
}

void main() {
  vec3 viewDir = normalize(-vViewPos);
  float mu = clamp(dot(vViewNormal, viewDir), 0.0, 1.0);   // 1 face-on (centre) .. 0 limb

  float n = fireFbm(normalize(vObjPos) * 3.2, uTime);

  // A ball of fire: a bright hot core fading toward a softer limb (the optically-thick
  // photosphere is brightest seen face-on), broken up by the turbulent cells.
  float core = 0.35 + 0.65 * smoothstep(0.0, 0.9, mu);
  float edge = smoothstep(0.0, 0.16, mu);                  // soft round silhouette (no hard disk rim)
  float cells = mix(0.45, 1.15, smoothstep(0.25, 0.85, n));

  // As the ejecta thin (uFade→1) the smooth photosphere breaks into sparse bright
  // filaments and the whole ball dims toward nothing — the dissipation that reveals the remnant.
  float wisp = smoothstep(0.58, 0.86, n);
  float body = mix(cells, wisp, uFade);
  float dim  = 1.0 - 0.97 * uFade;

  float a = uIntensity * core * edge * body * dim;
  // Bounded so a single additive sphere layer keeps the Teff hue + cell structure (never white-out).
  gl_FragColor = vec4(lin2srgb(uColor), clamp(a, 0.0, 0.8));
}`;

// --- compact-remnant dot shader (Chunk 3) -------------------------------------
// The tiny neutron star left at the centre once the ejecta have dissipated: a small,
// sharp glowing point with a soft halo, camera-facing (the corona-quad pattern). The
// COLOR HERE IS EVOCATIVE, NOT A BLACKBODY Teff (unlike the fireball and the living
// star): a neutron star's *optical thermal* emission is negligible — the Crab pulsar is
// visible only via synchrotron at V≈16 — so a "hot blue-white dot" is an illustrative
// marker for "a compact object is here", not a temperature claim (spec §7 honesty). A
// black hole / failed SN never shows this dot at all (the frame just goes dark — the
// star "winks out"); the intensity ramps in only as the fireball clears.
const REMNANT_FRAG = `
precision highp float;
uniform vec3  uColor;      // evocative hot tint (NOT a blackbody Teff — see the comment above)
uniform float uIntensity;  // 0 until the ejecta thin; ramps in as the remnant emerges (NS only)
varying vec2 vUv;

${GLSL_LIN2SRGB}

void main() {
  float d = length(vUv - 0.5) * 2.0;            // 0 centre .. 1 quad edge
  float pt   = exp(-d * d * 90.0);              // tiny sharp core
  float glow = 0.4 * exp(-d * d * 10.0);        // soft surrounding halo
  float a = clamp((pt + glow) * uIntensity, 0.0, 1.0);
  gl_FragColor = vec4(lin2srgb(uColor), a);
}`;

export function createStar(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camera.position.set(0, 0, 8);

  const surfaceMat = new THREE.ShaderMaterial({
    vertexShader: SURFACE_VERT,
    fragmentShader: SURFACE_FRAG,
    // fwidth() in the surface shader needs screen-space derivatives. Core in
    // WebGL2; on WebGL1 this flag makes three.js emit the GL_OES_standard_derivatives
    // #extension pragma. Used to antialias sub-pixel granulation (see SURFACE_FRAG).
    extensions: { derivatives: true },
    uniforms: {
      uColor: { value: new THREE.Color(1, 1, 1) },
      uTime: { value: 0 },
      uCells: { value: 22 },
      uContrast: { value: 0.34 },
      uOmega: { value: 0.12 },   // gentle visual spin (rad/s); not a real v_rot
      uShear: { value: 0.35 },   // poles ~35% slower than the equator
      uLife: { value: 8.0 },     // granule reform cycle (s) — bounds the shear
      uGran: { value: 1.0 },     // granulation amount (0 = smooth degenerate WD)
    },
  });
  const star = new THREE.Mesh(new THREE.SphereGeometry(1, 96, 64), surfaceMat);
  scene.add(star);

  // Corona (replaces the Phase-0 placeholder halo): a camera-facing additive
  // quad, masked off the star disk, drawn on top (no depth test) so the glow
  // always composites around the silhouette.
  const coronaMat = new THREE.ShaderMaterial({
    vertexShader: CORONA_VERT,
    fragmentShader: CORONA_FRAG,
    uniforms: {
      uColor: { value: new THREE.Color(1, 1, 1) },
      uIntensity: { value: 0.3 },
      uInnerFrac: { value: 0.7 },
      uFalloff: { value: 4 },
    },
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: false,
    depthWrite: false,
  });
  // PlaneGeometry(2,2) spans ±1, so the mesh scale becomes the quad half-size.
  const corona = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), coronaMat);
  corona.renderOrder = 2;
  scene.add(corona);

  // Wolf–Rayet wind halo (Chunk 5): a second camera-facing additive quad, hidden except
  // in the WR endgame (it never co-displays with the corona — the WR path zeroes the
  // corona via gDeg=0). Its uTime is driven by the clock in animate() so the outflow
  // streams; its size is fit-to-frame each frame (see applyWindScale) so the big cool
  // WNh entry star can't straight-edge-clip the viewport.
  const windMat = new THREE.ShaderMaterial({
    vertexShader: CORONA_VERT,
    fragmentShader: WIND_FRAG,
    uniforms: {
      uColor: { value: new THREE.Color(1, 1, 1) },
      uTime: { value: 0 },
      uIntensity: { value: 0.7 },
      uInnerFrac: { value: 0.6 },
      uFalloff: { value: 3.0 },
      uDensity: { value: 0.4 },
    },
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: false,
    depthWrite: false,
  });
  const wind = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), windMat);
  wind.renderOrder = 1;
  wind.visible = false;
  scene.add(wind);

  // Supernova fireball (Chunk 3): a second sphere sharing the star's geometry, shown ONLY
  // in the SN endgame (it never co-displays — the SN path hides the surface sphere). Additive
  // (a single back-face-culled layer, so the bounded shader alpha keeps the Teff hue rather
  // than washing to white); its uTime boils in animate(); its on-screen size is the same
  // displayRadius clamp as the star (already ~frame-filling for AU-scale ejecta — the sphere's
  // limb clips at the frame by construction, so no quad-style refit is needed).
  const fireballMat = new THREE.ShaderMaterial({
    vertexShader: SURFACE_VERT,
    fragmentShader: FIREBALL_FRAG,
    uniforms: {
      uColor: { value: new THREE.Color(1, 1, 1) },
      uTime: { value: 0 },
      uIntensity: { value: 0.9 },
      uFade: { value: 0 },
    },
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: false,
    depthWrite: false,
  });
  const fireball = new THREE.Mesh(star.geometry, fireballMat);
  fireball.renderOrder = 1;
  fireball.visible = false;
  scene.add(fireball);

  // Compact remnant dot (Chunk 3): a tiny camera-facing additive point, drawn on top of the
  // fading fireball. Shown only for a neutron-star remnant (a black hole "winks out" — no dot);
  // its intensity ramps in from zero as the ejecta dissipate, so it emerges rather than pops.
  const remnantMat = new THREE.ShaderMaterial({
    vertexShader: CORONA_VERT,
    fragmentShader: REMNANT_FRAG,
    uniforms: {
      uColor: { value: new THREE.Color(0.75, 0.85, 1.0) },  // evocative hot blue-white (NOT a Teff)
      uIntensity: { value: 0 },
    },
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthTest: false,
    depthWrite: false,
  });
  const remnant = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), remnantMat);
  remnant.renderOrder = 3;
  remnant.scale.setScalar(0.5);
  remnant.visible = false;
  scene.add(remnant);

  function resize() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    if (canvas.width !== w || canvas.height !== h) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  // Half-height of the camera frustum at the focal plane (z=0): the camera sits at z=8
  // with a 40° vertical FOV, so it sees ±8·tan(20°) ≈ ±2.91 world units vertically, and
  // ±that·aspect horizontally. The WR wind halo must stay inside this box or its additive
  // quad gets sliced by the viewport into a hard straight edge (the framing-pop family).
  const FRAME_HALF_H = 8 * Math.tan((40 * Math.PI / 180) / 2);

  // Size the WR wind quad to fit the frame. The wind *wants* an extended halo, but the WR
  // scrub opens on a huge cool WNh star (R≈33 R☉ → displayRadius near the clamp), where a
  // fixed extent would clip; so we cap the quad half-size at the tighter of the two frame
  // axes (horizontal binds at narrow/phone widths, aspect<1). A happy side effect: the
  // halo is thin at the big entry and grows fuller as the core strips and shrinks — both
  // physically apt and a gentle entry (no pop). Recomputed every frame so a live resize
  // can't reintroduce the clip. uInnerFrac = star limb / quad half-size = 1/extent.
  let windState = null;
  function applyWindScale() {
    if (!windState) return;
    const frameHalf = FRAME_HALF_H * Math.min(1, camera.aspect || 1);
    const half = Math.min(windState.rad * windState.desiredExtent, 0.95 * frameHalf);
    wind.scale.setScalar(half);
    windMat.uniforms.uInnerFrac.value = windState.rad / half;
  }

  // update(state, opts): opts.endgame === "wd" renders the white-dwarf endgame. The
  // look is driven by the star's OWN state (a degeneracy gate from log g), not a hard
  // mode switch, so the sequence is continuous: it opens on the thermally-pulsing AGB
  // giant (still boiling, still glowing — like the EAGB giant the user just left) and
  // ends on the degenerate remnant — a smooth, featureless cooling sphere (no
  // convective granulation, no corona), just the blackbody color at Teff (which sweeps
  // blue-white → white → yellow → red as it cools over Gyr) under limb darkening.
  // With no opts it is the normal living star (gate = 1 -> granulation + corona intact).
  function update(state, opts) {
    const eg = opts && opts.endgame;       // "wd" (cooling sphere) | "wr" (stripped core) | "sn"
    const wd = eg === "wd", wr = eg === "wr", sn = eg === "sn";
    const [r, g, b] = teffToLinearRGB(state.Teff_K);
    surfaceMat.uniforms.uColor.value.setRGB(r, g, b);
    coronaMat.uniforms.uColor.value.setRGB(r, g, b);
    surfaceMat.uniforms.uCells.value = granuleCells(state);
    // Degeneracy gate (WD endgame only): 1 for a convective giant (log g ≲ 1), fading
    // to 0 as the bared core contracts into a degenerate remnant (log g ≳ 4). The SAME
    // gate drives BOTH the granulation AND the corona below, so the two fade together —
    // and living stars always pass 1, leaving their look byte-identical. This is what
    // makes the gateway a CONTINUATION, not a cut: the thermally-pulsing AGB giant the
    // endgame opens on still boils and still glows (just like the EAGB giant the user
    // just left), and only the cooling remnant goes smooth and glowless.
    // WR (Chunk 4): a smooth, glowless hot sphere — a deliberate PLACEHOLDER for the
    // Chunk-5 optically-thick-wind shader. Granulation and corona are wrong for a
    // stripped, wind-driven core (it's not convective and has no dynamo corona), so gate
    // both fully off (gDeg=0); the blackbody color carries the blazing hot look for now.
    // SN (Chunk 2): the expanding ejecta photosphere is NOT a convective stellar surface
    // and has no dynamo corona, so gate granulation AND corona fully off — a smooth glowing
    // sphere coloured by the cooling Teff (an honest placeholder, like the WR sphere before
    // its wind shader landed; the expanding-fireball shader is Chunk 3). This is the explicit
    // {endgame:"sn"} signal the consumers branch on, NOT the meaningless ejecta log g.
    const gDeg = (wr || sn) ? 0.0
      : wd ? Math.max(0, Math.min(1, (4 - state.logg) / 3))
      : 1.0;
    surfaceMat.uniforms.uGran.value = gDeg;

    const rad = displayRadius(state.R_rsun);
    star.scale.setScalar(rad);

    // SN mode hides the living-star surface sphere and shows the fireball instead; every
    // other mode restores it. Set unconditionally (not just inside an `if (sn)`) so a mode
    // switch can never strand a stale mesh on screen.
    star.visible = !sn;
    fireball.visible = sn;

    // Corona: activity drives both how bright and how far the glow reaches; a small
    // floor keeps a faint neutral bloom so even a hot, inactive star isn't a hard-edged
    // disk (the activity-driven part is what actually grows). The quad half-size is
    // rad·extent, so the limb sits at fraction 1/extent of it; the falloff is scaled so
    // the glow has faded by the quad edge. In the WD endgame the degeneracy gate fades
    // the corona out over the SAME log g range as the granulation, so it doesn't vanish
    // abruptly at the gateway — it persists on the AGB giant and dies with the dynamo as
    // the remnant degenerates (a cold white dwarf has no steady corona; this is also why
    // the SED drops its coronal X-ray overlay over the same range). gDeg=1 living.
    const act = activityOf(state);
    const extent = 1.12 + 1.4 * act * gDeg;
    corona.scale.setScalar(rad * extent);
    coronaMat.uniforms.uInnerFrac.value = 1.0 / extent;
    coronaMat.uniforms.uFalloff.value = 3.2 / (extent - 1.0);
    coronaMat.uniforms.uIntensity.value = (0.3 + 1.4 * act) * gDeg;

    // WR wind halo (Chunk 5): shown ONLY in the WR endgame — hidden for the living star and
    // the WD endgame, so neither is touched. The color is the honest blackbody at Teff; the
    // halo's reach (desiredExtent) and density/clumpiness (uFalloff/uDensity) read from the
    // surface composition — a smoother, more extended helium (WN) wind sharpens into a
    // denser, clumpier carbon/oxygen (WC/WO) wind as Z_surf climbs. Intensity carries a
    // gentle, clamped luminosity tie — evocative, NOT a measured mass-loss rate (star_mdot
    // isn't on StellarState, by §3/Option B). applyWindScale() then fits it to the frame.
    wind.visible = wr;
    if (wr) {
      windMat.uniforms.uColor.value.setRGB(r, g, b);
      const z = Math.max(0, Math.min(1, (state.Z_surf ?? 0) / 0.6)); // 0 (WN) → 1 (WC/WO)
      windMat.uniforms.uFalloff.value = 2.4 + 1.4 * z;               // WC/WO: tighter, denser
      windMat.uniforms.uDensity.value = 0.25 + 0.75 * z;             // WN: smoother, WC/WO: clumpy
      const logL = Math.log10(Math.max(1, state.L_lsun));
      // The wind blazes UP as the star strips: ~0 while the entry star is still
      // hydrogen-rich (WNh, X_surf≈0.28), so the gateway is a CONTINUATION of the
      // near-glowless living CHeB star rather than a hard cut to a bright limb ring,
      // then rising to full as hydrogen vanishes and the bare He/C/O core is exposed
      // (WN→WC→WO — a real growth in the wind, not just the Z_surf clumpiness). Evocative:
      // it tracks strippedness for visual continuity, not a claim that WNh winds are weak.
      const wStrip = 1 - Math.max(0, Math.min(1, (state.X_surf ?? 0) / 0.25));
      windMat.uniforms.uIntensity.value =
        wStrip * (0.55 + 0.35 * Math.max(0, Math.min(1, (logL - 4.5) / 2)));
      windState = { rad, desiredExtent: 1.95 - 0.3 * z };
      applyWindScale();
    } else {
      windState = null;
    }

    // Supernova fireball + remnant (Chunk 3): the expanding ejecta photosphere as a cooling,
    // boiling ball that dissipates (uFade) to reveal the compact remnant. The one honest cue is
    // the blackbody color (the cooling Teff); the on-screen size, the turbulence and the remnant
    // dot are evocative (spec §7). uFade / uGrow come from the scrubbed day (main.js refreshSN):
    // grow swells the ball over the early scrub (an "expanding" beat — the on-screen size is
    // decoupled from the true AU-scale R, which the scale bar carries), fade dissipates it late.
    if (sn) {
      fireballMat.uniforms.uColor.value.setRGB(r, g, b);
      const fade = Math.max(0, Math.min(1, (opts && opts.snFade) ?? 0));
      const grow = Math.max(0.2, Math.min(1.5, (opts && opts.snGrow) ?? 1));
      fireballMat.uniforms.uFade.value = fade;
      // A gentle, clamped luminosity tie so the brightest moments read brighter — evocative,
      // NOT a measured photometric scale (the light-curve panel carries the real L).
      const logL = Math.log10(Math.max(1, state.L_lsun));
      fireballMat.uniforms.uIntensity.value = 0.6 + 0.4 * Math.max(0, Math.min(1, (logL - 5) / 4));
      fireball.scale.setScalar(rad * grow);

      // The remnant: a neutron star emerges as a tiny hot dot once the ejecta thin; a black
      // hole / failed SN shows nothing at all (the frame goes dark as the fireball fades —
      // the star "winks out"). The dot ramps in over the last of the fade so it emerges, not pops.
      const isNS = !!(opts && opts.remnant === "NS");
      remnant.visible = isNS;
      // Ramp from fade 0.6 (where refreshSN's "a neutron star emerges" caption appears) to 1,
      // so the dot begins emerging exactly when the text says it does — no caption/visual gap.
      remnantMat.uniforms.uIntensity.value =
        isNS ? Math.max(0, Math.min(1, (fade - 0.6) / 0.4)) : 0;
    } else {
      remnant.visible = false;
    }
  }

  const clock = new THREE.Clock();
  let raf = 0;
  function animate() {
    resize();
    // Drive time from a real clock so boil/rotation speed is frame-rate
    // independent (not a per-frame increment).
    const t = clock.getElapsedTime();
    surfaceMat.uniforms.uTime.value = t;
    // The WR wind outflow streams from the same clock (the corona has no uTime); refit it
    // to the frame each frame so a live resize can't slice the additive quad at the edge.
    if (wind.visible) {
      windMat.uniforms.uTime.value = t;
      applyWindScale();
    }
    // The SN fireball boils from the same clock (the remnant dot is static — no uTime).
    if (fireball.visible) fireballMat.uniforms.uTime.value = t;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(animate);
  }
  animate();

  return { update, dispose: () => cancelAnimationFrame(raf) };
}
