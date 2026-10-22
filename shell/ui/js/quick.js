// Left side of the top bar: Quick Settings, the account menu and power.
// Quick Settings is the only place for Wi-Fi, Bluetooth, sound, brightness
// and airplane mode.

import { post } from "./api.js";
import { avatar, h, icon } from "./dom.js";
import { focused } from "./focus.js";
import { confirmSheet, openBlade, openSheet, toast } from "./layers.js";
import { openKeyboard } from "./osk.js";
import { lastDevice } from "./input.js";
import { changed, refresh, state } from "./state.js";

function wifiLabel(q) {
  if (!q.wifi.enabled) return "Off";
  const net = q.wifi.networks.find((n) => n.connected);
  return net ? net.ssid : "Not connected";
}

function btLabel(q) {
  if (!q.bluetooth.enabled) return "Off";
  const n = q.bluetooth.devices.filter((d) => d.connected).length;
  return n ? `${n} connected` : "On";
}

function slider(label, ic, value, onSet) {
  const el = h("div.slider.f.ring", { "data-slider": true },
    icon(ic),
    h("div.track", h("div.fill", { style: { width: `${value}%` } }), h("div.knob", { style: { left: `${value}%` } })),
    h("div.val", {}, `${value}`));
  el._value = value;
  el._set = (v) => {
    v = Math.max(0, Math.min(100, Math.round(v)));
    el._value = v;
    el.querySelector(".fill").style.width = `${v}%`;
    el.querySelector(".knob").style.left = `${v}%`;
    el.querySelector(".val").textContent = v;
    clearTimeout(el._t);
    el._t = setTimeout(() => onSet(v), 120);
  };
  el.setAttribute("aria-label", label);
  el.querySelector(".track").addEventListener("click", (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    el._set(((e.clientX - r.left) / r.width) * 100);
  });
  return el;
}

export function openQuickSettings() {
  let page = "main";
  let busy = "";
  let error = "";

  const act = async (fn) => {
    error = "";
    try {
      state.quick = { ...state.quick, ...(await fn()) };
    } catch (e) {
      error = e.message;
    }
    busy = "";
    changed("quick");
    blade.render();
  };

  const pages = {
    main() {
      const q = state.quick;
      const muted = q.audio.muted;
      return [
        h("h2", {}, "Quick settings"),
        h("div.body.page-in",
          h("div.qs-grid",
            h(`button.qs-tile.f.ring${q.wifi.enabled ? ".on" : ""}`, { "data-autofocus": true, onclick: () => go("wifi") },
              h("div.top", icon(q.wifi.enabled ? "wifi" : "wifiOff"), h("span.more", icon("chevron"))),
              h("div", h("b", {}, "Wi-Fi"), h("small", {}, wifiLabel(q)))),
            h(`button.qs-tile.f.ring${q.bluetooth.enabled ? ".on" : ""}`, { onclick: () => go("bt") },
              h("div.top", icon("bt"), h("span.more", icon("chevron"))),
              h("div", h("b", {}, "Bluetooth"), h("small", {}, btLabel(q)))),
            h(`button.qs-tile.f.ring${q.airplane ? ".on" : ""}`, {
              onclick: () => act(() => post("airplane", { enabled: !q.airplane })),
            }, h("div.top", icon("plane")), h("div", h("b", {}, "Airplane mode"), h("small", {}, q.airplane ? "On" : "Off"))),
            h(`button.qs-tile.f.ring${!muted ? ".on" : ""}`, {
              onclick: () => act(async () => ({ audio: await post("audio", { muted: !muted }) })),
            }, h("div.top", icon(muted ? "mute" : "vol")), h("div", h("b", {}, "Sound"), h("small", {}, muted ? "Muted" : "On")))),
          slider("Volume", muted ? "mute" : "vol", q.audio.volume, (v) =>
            post("audio", { volume: v }).then((a) => { state.quick.audio = a; changed("quick"); })),
          q.brightness.available ? slider("Brightness", "sun", q.brightness.level, (v) =>
            post("brightness", { level: v }).then((b) => { state.quick.brightness = b; })) : null,
          q.battery.present ? h("div.item",
            icon(q.battery.charging ? "bolt" : "battery"),
            h("div.grow", h("b", {}, `Battery ${q.battery.level}%`),
              h("small", {}, q.battery.charging ? "Charging" : "On battery"))) : null,
          h("div.err", {}, error)),
      ];
    },

    wifi() {
      const w = state.quick.wifi;
      return [
        header("Wi-Fi"),
        h("div.body.page-in",
          toggleItem("Wi-Fi", w.enabled, () => act(async () => ({ wifi: await post("wifi", { enabled: !w.enabled }) }))),
          w.enabled ? h("div.section-label", {}, "Networks") : null,
          w.enabled ? h("div.list", w.networks.map((n) =>
            h("button.item.f.ring", { onclick: () => joinNetwork(n) },
              icon("wifi"),
              h("div.grow", h("b", {}, n.ssid), h("small", {}, n.connected ? "Connected" : n.secure ? "Secured" : "Open")),
              n.secure ? icon("lock") : null,
              n.connected ? h("span.tag", {}, "✓") : null))) : null,
          w.enabled ? h("button.item.f.ring", { onclick: () => { busy = "scan"; blade.render(); act(async () => ({ wifi: await post("wifi/scan") })); } },
            busy === "scan" ? h("span.spin") : icon("restart"), h("div.grow", h("b", {}, "Scan again"))) : null,
          h("div.err", {}, error)),
      ];
    },

    bt() {
      const b = state.quick.bluetooth;
      return [
        header("Bluetooth"),
        h("div.body.page-in",
          toggleItem("Bluetooth", b.enabled, () => act(async () => ({ bluetooth: await post("bluetooth", { enabled: !b.enabled }) }))),
          b.enabled ? h("div.section-label", {}, "Devices") : null,
          b.enabled ? h("div.list", b.devices.map((d) =>
            h("button.item.f.ring", {
              onclick: () => {
                busy = d.address;
                blade.render();
                act(async () => ({ bluetooth: await post(d.connected ? "bluetooth/disconnect" : "bluetooth/connect", { address: d.address }) }));
              },
            },
              icon(/controller|gamepad|pad/i.test(d.name) ? "pad" : "bt"),
              h("div.grow", h("b", {}, d.name), h("small", {}, d.connected ? "Connected" : d.paired ? "Paired" : "Tap to pair")),
              busy === d.address ? h("span.spin") : d.connected ? h("span.tag", {}, "✓") : null))) : null,
          b.enabled ? h("button.item.f.ring", {
            onclick: () => { busy = "scan"; blade.render(); act(async () => ({ bluetooth: await post("bluetooth/scan") })); },
          }, busy === "scan" ? h("span.spin") : icon("search"),
            h("div.grow", h("b", {}, "Pair a new device"), h("small", {}, "Put the device in pairing mode first"))) : null,
          h("div.err", {}, error)),
      ];
    },
  };

  function header(title) {
    return h("h2", {}, h("button.back.f.ring", { onclick: () => go("main") }, icon("back")), title);
  }

  function toggleItem(label, on, onclick) {
    return h("button.item.f.ring", { "data-autofocus": true, onclick },
      h("div.grow", h("b", {}, label), h("small", {}, on ? "On" : "Off")),
      h("span", { class: "btn" + (on ? " primary" : ""), style: { height: "2.2rem", padding: "0 1rem" } }, on ? "On" : "Off"));
  }

  function go(p) {
    page = p;
    error = "";
    blade.render();
  }

  function joinNetwork(n) {
    if (n.connected) {
      confirmSheet({ title: `Disconnect from ${n.ssid}?`, ok: "Disconnect" }).then((yes) => {
        if (yes) act(async () => ({ wifi: await post("wifi/disconnect", { ssid: n.ssid }) }));
      });
      return;
    }
    if (!n.secure) {
      act(async () => ({ wifi: await post("wifi/connect", { ssid: n.ssid }) }));
      return;
    }
    const field = h("input.field.f.ring", { type: "password", placeholder: "Password", "data-autofocus": true });
    const submit = () => {
      sheet.close();
      busy = n.ssid;
      act(async () => ({ wifi: await post("wifi/connect", { ssid: n.ssid, password: field.value }) }))
        .then(() => !error && toast(`Connected to ${n.ssid}`, icon("wifi")));
    };
    field._onSubmit = submit;
    const sheet = openSheet(({ close }) => [
      h("h3", {}, n.ssid),
      h("p", {}, "Enter the network password."),
      field,
      h("div.actions",
        h("button.btn.primary.f.ring", { onclick: submit }, "Connect"),
        h("button.btn.f.ring", { onclick: close }, "Cancel")),
    ]);
    if (lastDevice === "gamepad") openKeyboard(field, { onDone: submit });
  }

  const blade = openBlade("left", () => pages[page](), {
    onAction(action) {
      const el = focused();
      if (el?.dataset.slider !== undefined && (action === "left" || action === "right")) {
        el._set(el._value + (action === "left" ? -5 : 5));
        return true;
      }
      if (action === "back" && page !== "main") {
        go("main");
        return true;
      }
      return false;
    },
    hints: [["A", "Select"], ["B", "Back"], ["◀▶", "Adjust"]],
  });
  refresh("quick", "quick").then(() => blade.render());
  return blade;
}

export function openAccount() {
  openBlade("left", ({ close }) => [
    h("div", { style: { display: "flex", alignItems: "center", gap: "1.2rem", marginBottom: "2rem" } },
      avatar(state.me, ""),
      h("div", h("h2", { style: { margin: 0 } }, state.me.name), h("small", { style: { color: "var(--muted)" } }, `@${state.me.username}`))),
    h("div.body.list",
      h("button.item.f.ring", { "data-autofocus": true, onclick: () => { close(); window.dispatchEvent(new CustomEvent("lumen:go", { detail: { view: "library", params: { tab: "accounts" } } })); } },
        icon("link"), h("div.grow", h("b", {}, "Game accounts"), h("small", {}, "Steam, Epic Games, GOG"))),
      h("button.item.f.ring", {
        onclick: async () => {
          if (await confirmSheet({ title: "Switch user?", text: "Your games keep running only until you sign out.", ok: "Sign out" })) {
            await post("power", { action: "signout" });
            if (state.info.mock) location.search = "?mode=greeter";
          }
        },
      }, icon("logout"), h("div.grow", h("b", {}, "Switch user"), h("small", {}, "Sign out and go back to the user picker")))),
  ]);
}

export function openPower() {
  const run = async (action, label) => {
    toast(label, icon("power"));
    await post("power", { action }).catch((e) => toast(e.message));
  };
  openSheet(({ close }) => [
    h("h3", {}, "Power"),
    h("div.list", { style: { marginTop: "1rem" } },
      h("button.item.f.ring", { "data-autofocus": true, onclick: () => { close(); run("suspend", "Going to sleep"); } },
        icon("moon"), h("div.grow", h("b", {}, "Sleep"), h("small", {}, "Pick up where you left off"))),
      h("button.item.f.ring", { onclick: () => { close(); run("reboot", "Restarting"); } },
        icon("restart"), h("div.grow", h("b", {}, "Restart"))),
      h("button.item.f.ring", { onclick: () => { close(); run("poweroff", "Shutting down"); } },
        icon("power"), h("div.grow", h("b", {}, "Turn off")))),
  ]);
}
