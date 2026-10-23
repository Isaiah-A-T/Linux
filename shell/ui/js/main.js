// Entry point: loads state, builds the frame and routes input to views.

import { get, post } from "./api.js";
import { h } from "./dom.js";
import { focus, focused, focusFirst, move, onFocus, setBase, topLayer } from "./focus.js";
import { lastDevice, onAction } from "./input.js";
import { closeAll } from "./layers.js";
import { isOpen, openKeyboard } from "./osk.js";
import { openQuickSettings } from "./quick.js";
import { applyTheme, pollJobs, refresh, state } from "./state.js";
import { renderTopbar } from "./topbar.js";
import * as home from "./views/home.js";
import * as library from "./views/library.js";
import * as store from "./views/store.js";
import * as app from "./views/app.js";
import * as settings from "./views/settings.js";
import * as login from "./views/login.js";

const VIEWS = { home, library, store, app, settings, login };
const viewRoot = document.getElementById("view");
const hintsEl = document.getElementById("hints");
const history = [];
let splashDone = false;

const ctx = {
  go: (name, params) => navigate(name, params),
  back: () => back(),
  ready() {
    if (!splashDone) {
      splashDone = true;
      document.getElementById("splash").classList.add("done");
    }
    paintHints();
  },
};

function current() {
  return history[history.length - 1];
}

function mount(entry, enterCls, leaving, leaveCls) {
  entry.view = VIEWS[entry.name].render(ctx, entry.params || {});
  entry.view.el.classList.add(enterCls);
  viewRoot.append(entry.view.el);
  if (leaving) {
    leaving.view.destroy?.();
    leaving.view.el.classList.add(leaveCls);
    setTimeout(() => leaving.view.el.remove(), 420);
  }
  requestAnimationFrame(() => {
    const f = focused();
    if (!f || !entry.view.el.contains(f)) {
      const auto = entry.view.el.querySelector(".f[data-autofocus]") || entry.view.el.querySelector(".f");
      if (auto) focus(auto);
    }
  });
  paintHints();
}

function navigate(name, params = {}) {
  closeAll();
  const prev = current();
  if (prev && prev.name === name && name !== "app") {
    // Same view with new params (e.g. Library > Accounts): replace it.
    history.pop();
    history.push({ name, params });
    mount(current(), "enter", prev, "leave");
    return;
  }
  if (prev) prev.focus = focused();
  history.push({ name, params });
  mount(current(), "enter", prev, "leave");
}

function back() {
  if (history.length <= 1) return;
  const leaving = history.pop();
  const entry = current();
  mount(entry, "enter-back", leaving, "leave-back");
}

function goHome() {
  closeAll();
  if (current()?.name === "home") return;
  const leaving = history.pop();
  history.length = 0;
  history.push({ name: "home" });
  mount(current(), "enter-back", leaving, "leave-back");
}

function paintHints() {
  const layer = topLayer();
  const hints = (layer && !layer.base && layer.hints) || current()?.view?.hints || [["A", "Select"], ["B", "Back"]];
  const left = state.info.mode === "greeter" ? [] : [["☰", "Quick settings"], ["⌂", "Home"]];
  hintsEl.replaceChildren(
    h("div.hints-left", left.map(([g, t]) => h("span.hint", h("span.glyph", {}, g), t))),
    ...hints.map(([g, t]) => h("span.hint", h(`span.glyph${g.length > 1 ? ".wide" : ""}`, {}, g), t)));
}
window.addEventListener("lumen:layers", paintHints);
window.addEventListener("lumen:go", (e) => navigate(e.detail.view, e.detail.params));

onAction((action, source) => {
  const layer = topLayer();
  const f = focused();
  if (layer?.onAction?.(action, f)) return;
  if (layer && !layer.base) {
    if (action === "back") {
      layer.onBack?.();
      return;
    }
  } else if (current()?.view?.onAction?.(action, f)) {
    return;
  }
  switch (action) {
    case "up": case "down": case "left": case "right":
      move(action);
      break;
    case "accept":
      if (f?.matches("input") && source === "gamepad" && !isOpen()) openKeyboard(f, { onDone: () => f._onSubmit?.() });
      else if (f?.matches("input")) f._onSubmit?.();
      else f?.click();
      break;
    case "submit":
      f?._onSubmit?.();
      break;
    case "back":
      back();
      break;
    case "home":
      if (state.info.mode !== "greeter") goHome();
      break;
    case "menu":
      if (state.info.mode !== "greeter" && (!layer || layer.base)) openQuickSettings();
      break;
  }
});

// Mouse: hovering moves focus (without scrolling), clicking works as usual.
document.addEventListener("mouseover", (e) => {
  if (lastDevice !== "mouse") return;
  const el = e.target.closest?.(".f");
  const layer = topLayer();
  if (el && layer && layer.root.contains(el) && el !== focused()) focus(el, { scroll: false });
});
document.addEventListener("focusin", (e) => {
  if (e.target.matches(".f") && e.target !== focused()) focus(e.target, { scroll: false });
});

onFocus(() => {});

// When a game takes over the screen the shell loses focus. Coming back means
// the game has closed (or you switched away), so lumend puts the power mode,
// frame rate cap and button layout back to normal.
let away = false;
window.addEventListener("blur", () => { away = true; });
window.addEventListener("focus", () => {
  if (!away || state.info.mode === "greeter") return;
  away = false;
  post("game-settings/restore").catch(() => {});
});

async function boot() {
  const params = new URLSearchParams(location.search);
  state.info = await get("info").catch(() => state.info);
  if (params.get("mode") === "greeter") state.info.mode = "greeter";
  state.settings = await get("settings").catch(() => null);
  applyTheme(state.settings);
  setBase(document.getElementById("app"));

  if (state.info.mode === "greeter") {
    document.getElementById("topbar").remove();
    history.push({ name: "login" });
    mount(current(), "enter");
    return;
  }

  state.me = await get("me");
  await refresh("quick", "quick");
  refresh("media", "media");
  renderTopbar(document.getElementById("topbar"), { go: (v) => navigate(v) });
  pollJobs();
  setInterval(() => refresh("quick", "quick"), 10000);
  setInterval(() => refresh("media", "media"), 8000);

  const start = params.get("view") || "home";
  if (start !== "home") history.push({ name: "home" });
  history.push({ name: start, params: Object.fromEntries(params) });
  mount(current(), "enter");
  if (start !== "home") history[0].view = null;
  // Fallback in case a view never reports ready (e.g. daemon error).
  setTimeout(ctx.ready, 2500);
  setTimeout(() => { if (!focused()) focusFirst(); }, 600);
}

boot();
