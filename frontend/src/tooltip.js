// A single, body-mounted, viewport-clamped tooltip layer.
//
// Why a singleton instead of the per-element CSS `::after` pseudo-tooltips it
// replaces: the panels are draggable and reflow responsively (layout.js), so a
// panel — and its help "?" glyphs and dotted-underline ".tip" tokens — can land
// anywhere, including hard against the left or right viewport edge. A statically
// anchored CSS tooltip (open-right / open-left `.help-left` / open-up `.tip-up`)
// clips off whichever edge it grows toward once its panel is near that edge, and
// CSS alone cannot detect a viewport collision. Worse, a `::after` pseudo-element
// can't be measured with getBoundingClientRect, so its far edge can't be clamped.
//
// The fix: one real <div> appended to <body> (position:fixed → never clipped by a
// panel's overflow/transform), shown on hover/focus of any [data-tip] element via
// event delegation, and positioned by JS with viewport clamping on both axes —
// flipped above the trigger when it would overflow the bottom (this absorbs the
// old `.tip-up` status-line case for free), and clamped horizontally so it always
// stays on-screen. The horizontal clamp (not just a left/right side-flip) is the
// crux: a mid-panel glyph on a 390px phone clips BOTH ways at a 250px width, so a
// side-flip alone can't keep it on-screen — only clamping can.

const MARGIN = 8; // minimum gap from any viewport edge
const GAP = 7; // gap between the trigger and the tooltip (matches the old 7px)

export function initTooltips(root = document) {
  const tip = document.createElement("div");
  tip.className = "tooltip-layer";
  tip.setAttribute("role", "tooltip");
  tip.setAttribute("aria-hidden", "true");
  document.body.appendChild(tip);

  let current = null; // the trigger whose tooltip is currently shown

  function show(el) {
    const text = el.getAttribute("data-tip");
    if (!text) return;
    current = el;
    // textContent, not innerHTML: the attribute is already HTML-decoded on read
    // (so `&amp;` / `&lt;` / `&quot;` come back as literals), exactly as the old
    // `content: attr(data-tip)` rendered them — and it can't inject markup.
    tip.textContent = text;
    tip.classList.add("show");
    tip.setAttribute("aria-hidden", "false");
    position(el);
  }

  function hide() {
    if (!current) return;
    current = null;
    tip.classList.remove("show");
    tip.setAttribute("aria-hidden", "true");
  }

  function position(el) {
    const r = el.getBoundingClientRect();
    // documentElement.clientWidth/Height share getBoundingClientRect's coordinate
    // space (the layout viewport, scrollbar excluded) — the right space to clamp
    // in, including under mobile emulation where window.innerWidth differs.
    const vw = document.documentElement.clientWidth;
    const vh = document.documentElement.clientHeight;

    // Cap the height to the viewport (in the same units as the clamp below, so the
    // two can never disagree) BEFORE measuring — a few tooltips carry ~2000-char
    // pedagogy and would otherwise be taller than the screen. Then measure: with
    // visibility:hidden the box still has layout, and positioning is synchronous
    // (set before paint) so the tooltip never flashes at a stale spot.
    tip.style.maxHeight = `${vh - 2 * MARGIN}px`;
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;

    // Vertical: below the trigger; flip above if it would overflow the bottom and
    // there's room up top (covers the status line, which sits low in its panel);
    // if it fits neither way (tip nearly as tall as the viewport), pin it so it
    // stays fully on-screen — the max-height above guarantees room exists.
    let top = r.bottom + GAP;
    if (top + th > vh - MARGIN) {
      const above = r.top - GAP - th;
      top = above >= MARGIN ? above : Math.max(MARGIN, vh - th - MARGIN);
    }

    // Horizontal: left-align to the trigger, then clamp into the viewport so the
    // tooltip stays fully on-screen no matter where the panel was dragged.
    let left = r.left;
    const maxLeft = vw - tw - MARGIN;
    if (left > maxLeft) left = maxLeft;
    if (left < MARGIN) left = MARGIN;

    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  }

  // mouseover/mouseout bubble (mouseenter/mouseleave do not), so one delegated
  // pair covers every trigger — including JS-rendered ones added later (the
  // controls readout rows). The tooltip layer is pointer-events:none, so it never
  // intercepts clicks (the legend click-to-toggle keeps working).
  root.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el) {
      if (el !== current) show(el);
    } else if (current) {
      hide();
    }
  });
  // mouseover fires for every in-document move (and hides above when leaving a
  // trigger onto non-trigger content), but not when the pointer leaves the window
  // entirely — relatedTarget === null catches that.
  root.addEventListener("mouseout", (e) => {
    if (current && e.relatedTarget === null) hide();
  });

  // Keyboard / assistive tech: the triggers are tabbable (tabindex=0); focusin
  // and focusout bubble, so the same delegation shows the tooltip on focus.
  root.addEventListener("focusin", (e) => {
    const el = e.target.closest("[data-tip]");
    if (el) show(el);
  });
  root.addEventListener("focusout", () => hide());

  // A fixed tooltip would float detached from a trigger that scrolls or reflows;
  // hide it rather than chase the moving trigger.
  window.addEventListener("scroll", () => hide(), true);
  window.addEventListener("resize", () => hide());

  return { hide };
}
