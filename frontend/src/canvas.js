// Crisp 2D canvases on HiDPI displays, at an explicit CSS display size.
//
// The blur trap (the "low resolution" bug): a canvas with a small backing store
// (e.g. 360×320) stretched by CSS to a larger box is UPSCALED by the browser →
// fuzzy. Here we instead size the backing store to cssW·dpr × cssH·dpr (so it
// maps 1:1 onto physical pixels — no upscaling) and scale the drawing context by
// dpr, so all the plot code keeps working in logical cssW × cssH units. Returns
// the logical { ctx, W, H } to draw against.
//
// Setting canvas.width/height resets the context transform, so we set the sizes
// first and apply setTransform last; the transform then persists across redraws
// (the plots never resize, so we only need to call this once).
export function fitCanvas(canvas, cssW, cssH) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.style.width = cssW + "px";
  canvas.style.height = cssH + "px";
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, W: cssW, H: cssH };
}
