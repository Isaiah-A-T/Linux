// The top bar. Left is "you": account, Quick Settings status, Settings.
// Right is "fun": music, album, themes, notifications and the clock.

import { avatar, h, icon } from "./dom.js";
import { openMusic, openAlbum, openThemes, openNotifications } from "./fun.js";
import { openAccount, openQuickSettings } from "./quick.js";
import { state, subscribe } from "./state.js";

export function renderTopbar(root, { go }) {
  const status = h("button.tb-btn.tb-status.f.ring", { onclick: openQuickSettings, "aria-label": "Quick settings" });
  const now = h("span.tb-now");
  const bellBadge = h("span.badge", { style: { display: "none" } });
  const clock = h("div.tb-clock");

  const left = h("div.tb-side", { "data-group": true },
    h("button.tb-btn.tb-user.f.ring", { onclick: openAccount }, avatar(state.me), state.me.name),
    status,
    h("button.tb-btn.f.ring", { onclick: () => go("settings"), "aria-label": "Settings" }, icon("gear")));
  const right = h("div.tb-side", { "data-group": true },
    h("button.tb-btn.f.ring", { onclick: openMusic, "aria-label": "Music" }, icon("music"), now),
    h("button.tb-btn.f.ring", { onclick: openAlbum, "aria-label": "Album" }, icon("image")),
    h("button.tb-btn.f.ring", { onclick: openThemes, "aria-label": "Themes" }, icon("palette")),
    h("button.tb-btn.f.ring", { onclick: openNotifications, "aria-label": "Notifications" }, icon("bell"), bellBadge),
    h("div.tb-sep"),
    clock);
  root.replaceChildren(left, right);

  function paintStatus() {
    const q = state.quick;
    if (!q) return;
    const wifiOn = q.wifi.enabled && q.wifi.networks.some((n) => n.connected);
    const btOn = q.bluetooth.enabled;
    const parts = [
      icon(wifiOn ? "wifi" : "wifiOff", wifiOn ? "" : "off"),
      icon("bt", btOn ? "" : "off"),
      icon(q.audio.muted ? "mute" : "vol"),
    ];
    if (q.battery.present) {
      parts.push(icon(q.battery.charging ? "bolt" : "battery"), h("span.pct", {}, `${q.battery.level}%`));
    }
    status.replaceChildren(...parts);
  }

  function paintMedia() {
    const m = state.media;
    now.replaceChildren();
    if (m?.available && m.playing) now.append(h("b", {}, m.title), ` · ${m.artist}`);
  }

  function paintJobs() {
    const running = (state.jobs || []).filter((j) => j.state === "running").length;
    bellBadge.style.display = running ? "grid" : "none";
    bellBadge.textContent = running;
  }

  function tick() {
    const d = new Date();
    clock.textContent = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }

  subscribe((key) => {
    if (key === "quick") paintStatus();
    if (key === "media") paintMedia();
    if (key === "jobs") paintJobs();
  });
  paintStatus();
  paintMedia();
  paintJobs();
  tick();
  setInterval(tick, 5000);
}
