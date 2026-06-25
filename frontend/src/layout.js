// Draggable, reorder-in-flow panel layout (the "sortable").
//
// Requirement: the panels must be movable by the user, auto-stack to the viewport
// width (several columns on a desktop, a single vertical stack on a phone), and
// never overlap when moved. The only layout model that delivers all three at once
// is REORDER-IN-RESPONSIVE-FLOW, not free-floating windows:
//   * No overlap — flow layout (the CSS flex-wrap container in styles.css) can
//     never overlap its items, so "don't overlap when moved" is free.
//   * Stack to width — the column count is a pure function of viewport width
//     (flex-wrap), so a phone gets one column and a wide monitor several, with no
//     JS and no stored pixel positions to re-pack on resize.
// Dragging therefore changes only the ORDER of the panels in the flow; the browser
// re-packs around the drop. (Persisting absolute x/y would have to be discarded and
// re-packed on every resize — which *is* a flow layout, the long way round.)
//
// Touch-first, because phones are the headline device here:
//   * Pointer Events (not the HTML5 drag-and-drop API, which is unreliable on touch).
//   * `touch-action: none` on the grip (in CSS) so a touch-drag moves the panel
//     instead of scrolling the page.
//   * setPointerCapture + a small move threshold, so a tap on the header (or its
//     "?" glyph / mode buttons) still registers as a tap, not a drag.
// The grip is the ONLY drag handle, so every interactive control inside a panel
// (sliders, buttons, glyphs) stays fully usable — a whole-panel handle would
// swallow their events.

const THRESHOLD = 5; // px the pointer must travel before a drag begins (vs a tap)
// Edge auto-scroll: while dragging, if the pointer nears the top/bottom of the
// viewport, scroll the page so off-screen panels become reachable drop targets.
// Essential on a phone, where the single tall column is much taller than the
// viewport and touch-action:none + pointer capture stop the page scrolling on its
// own mid-drag (so without this you could only reorder panels already on screen).
const EDGE = 64;          // px from a viewport edge that triggers auto-scroll
const MAX_SCROLL = 20;    // px/frame cap at the very edge

export function makeSortable(container, { storageKey = "star-sim:panel-order" } = {}) {
  const panels = () =>
    [...container.children].filter((el) => el.classList.contains("panel"));
  const idOf = (el) => el.dataset.panelId;

  // The authored (default) DOM order — captured BEFORE any saved order is applied,
  // so reset() can restore it exactly.
  const defaultOrder = panels().map(idOf);

  // Inject a drag grip into each panel's first <h2> (its title bar).
  for (const panel of panels()) {
    const h2 = panel.querySelector("h2");
    if (!h2 || h2.querySelector(".drag-grip")) continue;
    const grip = document.createElement("span");
    grip.className = "drag-grip";
    grip.textContent = "⠿"; // ⠿ braille pattern — a conventional drag affordance
    grip.title = "Drag to rearrange";
    grip.setAttribute("aria-label", "Drag to rearrange this panel");
    h2.prepend(grip);
    attachDrag(grip, panel);
  }

  restore();

  // --- per-panel drag wiring -------------------------------------------------
  function attachDrag(grip, panel) {
    let startX = 0, startY = 0, grabDX = 0, grabDY = 0;
    let dragging = false, placeholder = null, pointerId = null;
    let rafId = 0, lastPx = 0, lastPy = 0; // latest pointer (for edge auto-scroll)

    grip.addEventListener("pointerdown", (e) => {
      if (e.button != null && e.button > 0) return; // primary button / touch / pen only
      pointerId = e.pointerId;
      const r = panel.getBoundingClientRect();
      startX = e.clientX; startY = e.clientY;
      grabDX = e.clientX - r.left; grabDY = e.clientY - r.top;
      grip.setPointerCapture(pointerId);
      grip.addEventListener("pointermove", onMove);
      grip.addEventListener("pointerup", onUp);
      grip.addEventListener("pointercancel", onUp);
      e.preventDefault(); // no text selection / native image drag
    });

    function onMove(e) {
      lastPx = e.clientX; lastPy = e.clientY; // record first (the auto-scroll loop reads these)
      if (!dragging) {
        if (Math.hypot(e.clientX - startX, e.clientY - startY) < THRESHOLD) return;
        startDrag();
      }
      movePanel();
      updateSlot(lastPx, lastPy);
    }

    // position:fixed → left/top are viewport coordinates, so the grabbed point
    // stays under the pointer (and stays put while the page auto-scrolls beneath it).
    function movePanel() {
      panel.style.left = lastPx - grabDX + "px";
      panel.style.top = lastPy - grabDY + "px";
    }

    // rAF loop: while the pointer is held near a viewport edge, keep scrolling and
    // re-evaluating the drop slot (pointermove alone wouldn't fire while the finger
    // is still). Stops as soon as the drag ends or the pointer leaves the edge.
    function autoScroll() {
      if (!dragging) return;
      // The LAYOUT viewport height in CSS pixels — the same coordinate space as the
      // pointer's clientY. (window.innerHeight is the wrong reference: under mobile
      // emulation / a pinch-zoomed visual viewport it differs from clientY's space,
      // so the bottom-edge test would never fire for a real finger position.)
      const vh = document.documentElement.clientHeight;
      let dy = 0;
      if (lastPy < EDGE) dy = -speed(EDGE - lastPy);
      else if (lastPy > vh - EDGE) dy = speed(lastPy - (vh - EDGE));
      if (dy) {
        const before = window.scrollY;
        window.scrollBy(0, dy);
        if (window.scrollY !== before) { movePanel(); updateSlot(lastPx, lastPy); }
      }
      rafId = requestAnimationFrame(autoScroll);
    }
    function speed(depth) { return Math.min(MAX_SCROLL, 3 + depth * 0.3); }

    function onUp() {
      if (dragging) endDrag();
      try { grip.releasePointerCapture(pointerId); } catch { /* already released */ }
      grip.removeEventListener("pointermove", onMove);
      grip.removeEventListener("pointerup", onUp);
      grip.removeEventListener("pointercancel", onUp);
    }

    function startDrag() {
      dragging = true;
      const r = panel.getBoundingClientRect();
      // A placeholder holds the panel's slot in the flow while it floats, so the
      // other panels keep their positions until the drop point is chosen.
      placeholder = document.createElement("div");
      placeholder.className = "panel-placeholder";
      placeholder.style.height = r.height + "px";
      if (panel.classList.contains("wide")) {
        placeholder.style.flexBasis = "100%"; // a full-row panel keeps a full-row slot
      } else {
        placeholder.style.flex = "0 0 " + r.width + "px";
        placeholder.style.width = r.width + "px";
      }
      container.insertBefore(placeholder, panel);
      // Lock the panel's box and lift it out of flow (CSS .dragging = position:fixed).
      panel.style.width = r.width + "px";
      panel.style.height = r.height + "px";
      panel.style.left = r.left + "px";
      panel.style.top = r.top + "px";
      panel.classList.add("dragging");
      document.body.classList.add("is-dragging-panel");
      rafId = requestAnimationFrame(autoScroll); // begin edge auto-scroll
    }

    // Move the placeholder to the slot nearest the pointer. 2-D nearest-center
    // (the layout wraps, so we can't reduce this to a 1-D before/after): pick the
    // in-flow panel whose center is closest, then drop before/after it by reading
    // order (row first, then column).
    function updateSlot(px, py) {
      let best = null, bestD = Infinity, after = false;
      for (const el of panels()) {
        if (el === panel) continue; // skip the floating panel itself
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const d = (px - cx) ** 2 + (py - cy) ** 2;
        if (d < bestD) {
          bestD = d; best = el;
          if (py < cy - r.height / 2) after = false;       // clearly above → before
          else if (py > cy + r.height / 2) after = true;   // clearly below → after
          else after = px > cx;                            // same row → left/right
        }
      }
      if (!best) return;
      container.insertBefore(placeholder, after ? best.nextSibling : best);
    }

    function endDrag() {
      dragging = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = 0; } // stop edge auto-scroll
      container.insertBefore(panel, placeholder); // land where the placeholder is
      placeholder.remove();
      placeholder = null;
      panel.classList.remove("dragging");
      document.body.classList.remove("is-dragging-panel");
      panel.style.left = panel.style.top = "";
      panel.style.width = panel.style.height = "";
      save();
    }
  }

  // --- order persistence -----------------------------------------------------
  function save() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(panels().map(idOf)));
    } catch { /* private mode / quota — order just won't persist */ }
  }

  function restore() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(storageKey) || "null"); } catch { /* ignore */ }
    if (!Array.isArray(saved) || !saved.length) return;
    const byId = new Map(panels().map((el) => [idOf(el), el]));
    // Apply the saved order first…
    for (const id of saved) {
      const el = byId.get(id);
      if (el) container.appendChild(el);
    }
    // …then append any panel NOT in the saved list — a panel added in a later phase
    // would otherwise silently vanish for anyone who already has a saved layout.
    for (const id of defaultOrder) {
      if (!saved.includes(id)) {
        const el = byId.get(id);
        if (el) container.appendChild(el);
      }
    }
  }

  function reset() {
    const byId = new Map(panels().map((el) => [idOf(el), el]));
    for (const id of defaultOrder) {
      const el = byId.get(id);
      if (el) container.appendChild(el);
    }
    try { localStorage.removeItem(storageKey); } catch { /* ignore */ }
  }

  return { reset, save };
}
