// Blades (side panels), sheets (dialogs), toasts and hints.

import { h } from "./dom.js";
import { candidates, focus, focused, popLayer, pushLayer } from "./focus.js";

// After a re-render, keep focus inside the layer (the old element is gone).
function refocus(root) {
  const f = focused();
  if (f && root.contains(f)) return;
  const pick = root.querySelector(".f[data-autofocus]") || candidates(root)[0];
  if (pick && stack.length && stack[stack.length - 1].el === root) focus(pick, { scroll: false });
}

const stack = [];

export function openBlade(side, build, opts = {}) {
  const scrim = h("div.scrim", { onclick: () => close() });
  const blade = h(`div.blade.${side}`);
  const layer = { root: blade, onBack: () => close(), hints: opts.hints, onAction: opts.onAction };
  const api = { el: blade, close, layer, render };
  function render() {
    blade.replaceChildren(...[].concat(build(api)));
    refocus(blade);
  }
  function close() {
    const i = stack.indexOf(api);
    if (i < 0) return;
    stack.splice(i, 1);
    blade.classList.add("out");
    scrim.classList.add("out");
    setTimeout(() => { blade.remove(); scrim.remove(); }, 300);
    popLayer(layer);
    opts.onClose?.();
    window.dispatchEvent(new Event("lumen:layers"));
  }
  render();
  document.body.append(scrim, blade);
  stack.push(api);
  pushLayer(layer);
  window.dispatchEvent(new Event("lumen:layers"));
  return api;
}

export function openSheet(build, opts = {}) {
  const scrim = h("div.scrim", { onclick: () => close() });
  const sheet = h(`div.sheet${opts.cls ? "." + opts.cls : ""}`);
  const layer = { root: sheet, onBack: () => close(), hints: opts.hints, onAction: opts.onAction };
  const api = { el: sheet, close, layer, render };
  function render() {
    sheet.replaceChildren(...[].concat(build(api)));
    refocus(sheet);
  }
  function close() {
    const i = stack.indexOf(api);
    if (i < 0) return;
    stack.splice(i, 1);
    sheet.classList.add("out");
    scrim.classList.add("out");
    setTimeout(() => { sheet.remove(); scrim.remove(); }, 250);
    popLayer(layer);
    opts.onClose?.();
    window.dispatchEvent(new Event("lumen:layers"));
  }
  render();
  document.body.append(scrim, sheet);
  stack.push(api);
  pushLayer(layer);
  window.dispatchEvent(new Event("lumen:layers"));
  return api;
}

export function closeAll() {
  while (stack.length) stack[stack.length - 1].close();
}

export function confirmSheet({ title, text, ok = "OK", danger = false }) {
  return new Promise((resolve) => {
    let answered = false;
    const s = openSheet(({ close }) => [
      h("h3", {}, title),
      text ? h("p", {}, text) : null,
      h("div.actions",
        h(`button.btn.f.ring${danger ? ".danger" : ".primary"}`, {
          "data-autofocus": true,
          onclick: () => { answered = true; close(); resolve(true); },
        }, ok),
        h("button.btn.f.ring", { onclick: () => close() }, "Cancel")),
    ], { onClose: () => { if (!answered) resolve(false); } });
    return s;
  });
}

export function toast(text, iconEl) {
  const el = h("div.toast", iconEl, h("span", {}, text));
  document.body.append(el);
  setTimeout(() => el.classList.add("out"), 2600);
  setTimeout(() => el.remove(), 3000);
}
