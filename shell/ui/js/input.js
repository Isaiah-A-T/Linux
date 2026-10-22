// Turns controller, keyboard and mouse input into shell actions.
//
// Actions: up down left right accept back menu search options tabprev
// tabnext home. Standard gamepad mapping (Xbox/PlayStation/Switch Pro all
// report it in Chromium): 0 A, 1 B, 2 X, 3 Y, 4 LB, 5 RB, 8 View, 9 Menu,
// 12-15 D-pad, 16 Guide.

const BUTTONS = {
  0: "accept", 1: "back", 2: "options", 3: "search", 4: "tabprev", 5: "tabnext",
  8: "options", 9: "menu", 12: "up", 13: "down", 14: "left", 15: "right", 16: "home",
};
const REPEATS = new Set(["up", "down", "left", "right", "tabprev", "tabnext"]);
const KEYS = {
  ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
  Enter: "accept", " ": "accept", Escape: "back", Backspace: "back",
  PageUp: "tabprev", PageDown: "tabnext", Home: "home", F1: "menu", Tab: null,
  "[": "tabprev", "]": "tabnext", "/": "search", ContextMenu: "options",
};

let handler = () => {};
export let lastDevice = "mouse";

export function onAction(fn) {
  handler = fn;
}

function emit(action, source) {
  lastDevice = source;
  document.body.classList.toggle("hide-cursor", source !== "mouse");
  handler(action, source);
}

// --- Keyboard ---------------------------------------------------------------

window.addEventListener("keydown", (e) => {
  const inInput = e.target.matches?.("input, textarea");
  let action = KEYS[e.key];
  if (inInput) {
    // Typing keys belong to the field; arrows leave it only at the edges.
    if (e.key === "Backspace" || e.key === " " || e.key === "/" || e.key === "[" || e.key === "]") return;
    if ((e.key === "ArrowLeft" && e.target.selectionStart > 0) ||
        (e.key === "ArrowRight" && e.target.selectionEnd < e.target.value.length)) return;
    if (e.key === "Enter") action = "submit";
  }
  if (action === undefined || action === null) return;
  e.preventDefault();
  emit(action, "keyboard");
});

// --- Mouse ------------------------------------------------------------------

window.addEventListener("mousemove", () => {
  if (lastDevice !== "mouse") {
    lastDevice = "mouse";
    document.body.classList.remove("hide-cursor");
  }
});

// --- Gamepad -----------------------------------------------------------------

const pads = new Map(); // index -> { pressed: Set, next: Map(action -> time) }
const FIRST_REPEAT = 380;
const REPEAT = 110;

function stickActions(gp) {
  const out = [];
  const [x = 0, y = 0] = gp.axes;
  const dead = 0.55;
  if (x < -dead) out.push("left");
  if (x > dead) out.push("right");
  if (y < -dead) out.push("up");
  if (y > dead) out.push("down");
  return out;
}

function poll(now) {
  for (const gp of navigator.getGamepads ? navigator.getGamepads() : []) {
    if (!gp) continue;
    let st = pads.get(gp.index);
    if (!st) pads.set(gp.index, (st = { held: new Map() }));
    const active = new Set(stickActions(gp));
    gp.buttons.forEach((b, i) => {
      if (b.pressed && BUTTONS[i]) active.add(BUTTONS[i]);
    });
    for (const action of active) {
      const next = st.held.get(action);
      if (next === undefined) {
        st.held.set(action, now + FIRST_REPEAT);
        emit(action, "gamepad");
      } else if (REPEATS.has(action) && now >= next) {
        st.held.set(action, now + REPEAT);
        emit(action, "gamepad");
      }
    }
    for (const action of [...st.held.keys()]) {
      if (!active.has(action)) st.held.delete(action);
    }
  }
  requestAnimationFrame(poll);
}

window.addEventListener("gamepadconnected", (e) => {
  window.dispatchEvent(new CustomEvent("lumen:pad", { detail: { id: e.gamepad.id, connected: true } }));
});
window.addEventListener("gamepaddisconnected", (e) => {
  pads.delete(e.gamepad.index);
  window.dispatchEvent(new CustomEvent("lumen:pad", { detail: { id: e.gamepad.id, connected: false } }));
});

requestAnimationFrame(poll);
