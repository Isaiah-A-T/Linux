// PS5-style sign-in: "Who's playing?" with big avatars, then a password.

import { get, post } from "../api.js";
import { avatar, h, icon } from "../dom.js";
import { focus } from "../focus.js";
import { lastDevice } from "../input.js";
import { openKeyboard } from "../osk.js";
import { openPower } from "../quick.js";
import { setHero, state } from "../state.js";

export function render(ctx) {
  const clock = h("div.clock");
  const stage = h("div", { style: { display: "flex", flexDirection: "column", alignItems: "center" } });
  const el = h("div.view.login", clock, stage,
    h("div.login-foot",
      h("span", {}, "Lumen OS"),
      h("button.tb-btn.f.ring", { onclick: openPower }, icon("power"), "Power")));
  let users = [];
  let picked = null;

  const tick = () => { clock.textContent = new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); };
  tick();
  const timer = setInterval(tick, 5000);

  function pickScreen() {
    picked = null;
    stage.replaceChildren(
      h("h1", {}, "Who's playing?"),
      h("div.users", { "data-group": true }, users.map((u, i) => {
        const b = h("button.user.f", { style: { "--c": u.color, animationDelay: `${0.08 * i}s` }, onclick: () => passwordScreen(u) },
          avatar(u), h("span", {}, u.name));
        return b;
      })));
    const last = localStorage.getItem("lumen:lastUser");
    const btns = [...stage.querySelectorAll(".user")];
    focus(btns[Math.max(0, users.findIndex((u) => u.username === last))] || btns[0]);
  }

  function passwordScreen(u) {
    picked = u;
    const field = h("input.field.f.ring", { type: "password", placeholder: "Password", "data-autofocus": true });
    const err = h("div.err");
    const submit = async () => {
      try {
        await post("login", { username: u.username, secret: field.value });
        localStorage.setItem("lumen:lastUser", u.username);
        el.classList.add("signing");
        // greetd now starts the session and this greeter exits. In mock mode
        // there is no greetd, so continue into the shell ourselves.
        if (state.info.mock) setTimeout(() => { location.search = ""; }, 900);
      } catch (e) {
        err.textContent = e.message;
        field.value = "";
        box.classList.remove("shake");
        void box.offsetWidth;
        box.classList.add("shake");
      }
    };
    field._onSubmit = submit;
    const box = h("div.pw-box", { style: { "--c": u.color } },
      avatar(u), h("h2", {}, u.name), field, err,
      h("div", { style: { display: "flex", gap: ".8rem" } },
        h("button.btn.primary.f.ring", { onclick: submit }, "Sign in"),
        h("button.btn.f.ring", { onclick: pickScreen }, "Back")));
    stage.replaceChildren(box);
    focus(field);
    if (lastDevice === "gamepad") openKeyboard(field, { onDone: submit });
  }

  setHero(null);
  get("users").then((r) => {
    users = r.users;
    pickScreen();
    ctx.ready();
  });

  return {
    el,
    hints: [["A", "Select"], ["B", "Back"]],
    onAction(action) {
      if (action === "back" && picked) {
        pickScreen();
        return true;
      }
      return action === "back" || action === "home" || action === "menu";
    },
    destroy: () => clearInterval(timer),
  };
}
