// Spatial focus engine shared by controller, keyboard and mouse.
//
// Anything with class "f" can take focus. Only elements inside the top layer
// (the open blade or dialog, else the base screen) are candidates. Moving picks
// the nearest element in the pressed direction. A container marked
// data-group remembers its last focused child, so going down to the dock and
// back up returns to the same tile.

const layers = [];
let current = null;
const listeners = new Set();

export function onFocus(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function topLayer() {
  return layers.length ? layers[layers.length - 1] : null;
}

export function pushLayer(layer) {
  // layer: { root, onBack?, onAction?, restore? }
  layer.restore = current;
  layers.push(layer);
  const first = layer.root.querySelector(".f[data-autofocus]") || candidates(layer.root)[0];
  if (first) focus(first);
}

export function popLayer(layer) {
  const i = layers.indexOf(layer);
  if (i < 0) return;
  layers.splice(i, 1);
  if (layer.restore && layer.restore.isConnected) focus(layer.restore);
  else focusFirst();
}

export function setBase(root) {
  layers.length = 0;
  layers.push({ root, base: true });
}

function visible(el) {
  if (el.disabled || el.closest("[inert]")) return false;
  const r = el.getBoundingClientRect();
  return r.width > 0 && r.height > 0;
}

export function candidates(root = topLayer()?.root) {
  if (!root) return [];
  return [...root.querySelectorAll(".f")].filter(visible);
}

export function focused() {
  return current && current.isConnected ? current : null;
}

export function focus(el, { scroll = true } = {}) {
  if (!el) return;
  if (current && current !== el) current.classList.remove("focused");
  current = el;
  el.classList.add("focused");
  const group = el.closest("[data-group]");
  if (group) group._last = el;
  if (el.matches("input")) el.focus({ preventScroll: true });
  else if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  if (scroll) el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
  for (const fn of listeners) fn(el);
}

export function focusFirst() {
  const layer = topLayer();
  if (!layer) return;
  const preferred = layer.root.querySelector(".f[data-autofocus]");
  focus(preferred && visible(preferred) ? preferred : candidates()[0]);
}

const DIRS = {
  left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1],
};

export function move(dir) {
  const from = focused();
  const all = candidates();
  if (!from || !all.includes(from)) {
    focusFirst();
    return true;
  }
  const [dx, dy] = DIRS[dir];
  const a = from.getBoundingClientRect();
  const ax = a.left + a.width / 2;
  const ay = a.top + a.height / 2;
  let best = null;
  let bestScore = Infinity;
  for (const el of all) {
    if (el === from) continue;
    const b = el.getBoundingClientRect();
    const bx = b.left + b.width / 2;
    const by = b.top + b.height / 2;
    // Distance along the pressed direction, measured edge to edge so big and
    // small tiles in one row still line up.
    const primary = dx
      ? (dx > 0 ? b.left - a.right : a.left - b.right)
      : (dy > 0 ? b.top - a.bottom : a.top - b.bottom);
    const centerPrimary = dx ? (bx - ax) * dx : (by - ay) * dy;
    if (centerPrimary <= 1 || primary < -Math.min(a.width, a.height) / 2) continue;
    const overlap = dx
      ? Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)
      : Math.min(a.right, b.right) - Math.max(a.left, b.left);
    const secondary = dx ? Math.abs(by - ay) : Math.abs(bx - ax);
    const score = Math.max(primary, 0) + secondary * (overlap > 0 ? 0.3 : 2.5);
    if (score < bestScore) {
      bestScore = score;
      best = el;
    }
  }
  if (!best) return false;
  const group = best.closest("[data-group]");
  if (group && group !== from.closest("[data-group]") && group._last && group._last.isConnected && all.includes(group._last)) {
    best = group._last;
  }
  focus(best);
  return true;
}
