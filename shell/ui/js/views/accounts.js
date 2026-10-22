// Connecting Steam, Epic Games and GOG.

import { post } from "../api.js";
import { h, icon } from "../dom.js";
import { confirmSheet, openSheet, toast } from "../layers.js";

export function openAccountSheet(account, onChange) {
  if (account.connected) {
    confirmSheet({
      title: `${account.name}`,
      text: `Signed in as ${account.user || "you"}. Disconnecting removes its games from your library. Installed games stay on disk.`,
      ok: "Disconnect", danger: true,
    }).then(async (yes) => {
      if (!yes) return;
      const { accounts } = await post("accounts/disconnect", { launcher: account.id });
      onChange(accounts);
    });
    return;
  }
  if (!account.available) {
    toast(`${account.name} support isn't installed on this system.`, icon("info"));
    return;
  }

  let error = "";
  let busy = false;
  const login = account.login || {};
  const isSteam = login.type === "steam";
  const field = h("input.field.f.ring", {
    placeholder: isSteam ? "Steam Web API key (optional)" : "Paste or type the code",
  });

  const submit = async () => {
    busy = true;
    error = "";
    sheet.render();
    try {
      const payload = { launcher: account.id };
      payload[isSteam ? "api_key" : "code"] = field.value;
      const { accounts } = await post("accounts/connect", payload);
      onChange(accounts);
      sheet.close();
      toast(isSteam ? "Steam is opening. Sign in there." : `${account.name} connected`, icon("check"));
    } catch (e) {
      error = e.message;
      busy = false;
      sheet.render();
    }
  };
  field._onSubmit = submit;

  const sheet = openSheet(({ close }) => [
    h("h3", {}, `Connect ${account.name}`),
    h("p", {}, login.help),
    isSteam
      ? h("p", {}, "Optional: add a Steam Web API key to also see games you own but haven't installed. Get one at steamcommunity.com/dev/apikey.")
      : h("button.btn.f.ring", { "data-autofocus": true, onclick: () => post("open-url", { url: login.url }) },
        icon("link"), `Open ${account.name} sign-in`),
    h("div", { style: { marginTop: "1.2rem" } }, field),
    h("div.err", {}, error),
    h("div.actions",
      h("button.btn.primary.f.ring", { onclick: submit, disabled: busy, "data-autofocus": isSteam || null },
        busy ? h("span.spin") : null, isSteam ? "Open Steam" : "Connect"),
      h("button.btn.f.ring", { onclick: close }, "Cancel")),
  ]);
}
