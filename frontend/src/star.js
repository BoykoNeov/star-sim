// Phase 0 star renderer: a sphere whose COLOR comes from Teff and whose SIZE
// comes from R (STAR_SIM_SPEC.md §9, Phase 0 = "Teff->color and radius->size").
//
// Deliberately minimal: no granulation, no limb darkening, no activity-driven
// corona yet — those are Phase 2 and belong in a fragment shader. A faint static
// halo is included purely so the star doesn't read as a billiard ball; it is NOT
// the physical corona (that is driven by state.activity, later).

import * as THREE from "three";

import { teffToRGB } from "./color.js";

// Map a physical radius (R_sun, spanning ~0.05 .. ~1000) onto an on-screen
// sphere radius via log scaling, so dwarfs and giants both stay visible. The
// real number is always shown in the readout.
function displayRadius(rRsun) {
  const lr = Math.log10(Math.max(1e-3, rRsun)); // ~ -3 .. 3
  const t = (lr + 2) / 5; // normalize roughly [-2, 3] -> [0, 1]
  return 0.45 + 2.0 * Math.max(0, Math.min(1, t));
}

export function createStar(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
  camera.position.set(0, 0, 8);

  const geometry = new THREE.SphereGeometry(1, 64, 48);
  const material = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const star = new THREE.Mesh(geometry, material);
  scene.add(star);

  // Faint additive halo (placeholder, not physical — see header note).
  const haloMat = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 0.12,
    blending: THREE.AdditiveBlending, side: THREE.BackSide,
  });
  const halo = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), haloMat);
  scene.add(halo);

  function resize() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    if (canvas.width !== w || canvas.height !== h) {
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
  }

  function update(state) {
    const [r, g, b] = teffToRGB(state.Teff_K);
    material.color.setRGB(r, g, b);
    haloMat.color.setRGB(r, g, b);
    const rad = displayRadius(state.R_rsun);
    star.scale.setScalar(rad);
    halo.scale.setScalar(rad * 1.18);
  }

  let raf = 0;
  function animate() {
    resize();
    star.rotation.y += 0.0025; // gentle spin; real rotation rate is Phase 2
    halo.rotation.y = star.rotation.y;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(animate);
  }
  animate();

  return { update, dispose: () => cancelAnimationFrame(raf) };
}
