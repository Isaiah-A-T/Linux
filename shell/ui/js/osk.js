// On-screen keyboard for controller users. Opens when a text field is
// activated with a controller. A types, X deletes, Y adds a space, Menu is
// Done, B closes.

import { h } from "./dom.js";
import { focus, pushLayer, popLayer } from "./focus.js";

const LAYOUTS = {
  abc: ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"],
  sym: ["1234567890", "@#$%&*-+=_", "!?\"'():;/", ".,~^<>|\\"],
};

let open = null;

export function isOpen() {
  return !!open;
}

export function openKeyboard(input, { onDone } = {}) {
  if (open) return;
  let mode = "abc";
  let shift = false;
  const preview = h("div.preview");
  const box = h("div.osk");
  const masked = input.type === "password";

  const show = () => {
    preview.textContent = masked ? "•".repeat(input.value.length) : input.value;
  };
  const type = (ch) => {
    input.value += ch;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    if (shift) { shift = false; render(); }
    show();
  };
  const del = () => {
    input.value = input.value.slice(0, -1);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    show();
  };
  const done = () => {
    close();
    onDone?.(input.value);
  };

  function render() {
    const rows = LAYOUTS[mode].map((row) =>
      h("div.krow", [...row].map((c) => {
        const ch = shift ? c.toUpperCase() : c;
        return h("button.key.f.ring", { onclick: () => type(ch) }, ch);
      })));
    rows.push(h("div.krow",
      h("button.key.wide.f.ring", { onclick: () => { shift = !shift; render(); } }, shift ? "⇧ ON" : "⇧"),
      h("button.key.wide.f.ring", { onclick: () => { mode = mode === "abc" ? "sym" : "abc"; render(); } }, mode === "abc" ? "#+=" : "abc"),
      h("button.key.space.f.ring", { onclick: () => type(" ") }, "space"),
      h("button.key.wide.f.ring", { onclick: del }, "⌫"),
      h("button.key.wide.accent.f.ring", { onclick: done }, "Done")));
    const keep = box.querySelector(".focused")?.textContent;
    box.replaceChildren(preview, ...rows);
    const again = [...box.querySelectorAll(".key")].find((k) => k.textContent.toLowerCase() === (keep || "").toLowerCase());
    if (again) focus(again, { scroll: false });
  }

  const layer = {
    root: box,
    onBack: () => close(),
    onAction: (a) => {
      if (a === "options") { del(); return true; }
      if (a === "search") { type(" "); return true; }
      if (a === "menu" || a === "submit") { done(); return true; }
      return false;
    },
    hints: [["A", "Type"], ["X", "Delete"], ["Y", "Space"], ["☰", "Done"]],
  };
  function close() {
    box.remove();
    open = null;
    popLayer(layer);
    window.dispatchEvent(new Event("lumen:layers"));
  }
  render();
  show();
  document.body.append(box);
  open = layer;
  pushLayer(layer);
  window.dispatchEvent(new Event("lumen:layers"));
}
