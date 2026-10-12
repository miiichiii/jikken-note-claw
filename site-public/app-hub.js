/* Generic app directory only: no private data, model calls or trust in Telegram identity hints. */
(function (root) {
  "use strict";
  const configKey = "taskBoardSyncConfigV2";
  const setupKeys = ["sync-token", "task-board-sync-token"];
  const externalDestinations = new Set([
    "https://calendar.google.com/calendar/u/0/r",
    "https://miiichiii.github.io/research-fund-dashboard/"
  ]);

  function readStorage(win, kind) {
    try {
      const raw = win[kind].getItem(configKey);
      if (raw === null) return { available: true, present: false, config: {} };
      const config = JSON.parse(raw);
      return { available: true, present: true, config: config && typeof config === "object" && !Array.isArray(config) ? config : {} };
    } catch { return { available: false, present: false, config: {} }; }
  }

  function writeStorage(win, kind, config) {
    try { win[kind].setItem(configKey, JSON.stringify(config)); return true; }
    catch { return false; }
  }

  function bootstrap(win) {
    const params = new URLSearchParams(win.location.hash.replace(/^#/, ""));
    const hasSetup = setupKeys.some((key) => params.has(key));
    let token = setupKeys.map((key) => params.get(key)).find((value) => value && value.trim());
    // Remove only our setup parameters: SDK launch parameters must remain readable.
    setupKeys.forEach((key) => params.delete(key));
    if (hasSetup) {
      const rest = params.toString();
      win.history.replaceState(null, "", `${win.location.pathname}${win.location.search}${rest ? `#${rest}` : ""}`);
    }
    if (!token) return { fallbackToken: "", malformed: hasSetup };
    token = token.trim();
    if (token.length > 8192 || /[\u0000-\u0020\u007f\ufffd]/.test(token)) return { fallbackToken: "", malformed: true };
    const persistent = readStorage(win, "localStorage");
    const session = readStorage(win, "sessionStorage");
    // Preserve explicit persistent logout and every existing setting/auth field.
    const config = { ...(persistent.present ? persistent.config : session.config), token };
    const savedPersistent = writeStorage(win, "localStorage", config);
    writeStorage(win, "sessionStorage", config);
    // A session-only save still needs forwarding: taskboard persistence may be blocked.
    return { fallbackToken: savedPersistent ? "" : token, malformed: false };
  }

  function taskDestination(state) {
    return `tasks.html?miniapp=1${state.fallbackToken ? `#sync-token=${encodeURIComponent(state.fallbackToken)}` : ""}`;
  }

  function openExternal(win, url, event) {
    if (!externalDestinations.has(url)) return false;
    if (win.Telegram?.WebApp?.openLink) {
      try {
        win.Telegram.WebApp.openLink(url, { try_instant_view: false });
        event.preventDefault();
        return true;
      } catch { /* A real anchor remains usable when the SDK cannot open it. */ }
    }
    return false;
  }

  function init(win, doc) {
    const state = bootstrap(win);
    const task = doc.getElementById("taskApp");
    // Credentials stay in memory, never in a visible link or external URL.
    if (state.fallbackToken) task.addEventListener("click", (event) => {
      event.preventDefault();
      win.location.assign(taskDestination(state));
    });
    if (state.malformed) doc.getElementById("hubStatus").textContent = "タスクの接続設定を読み込めませんでした。元の起動ボタンから開き直してください。";
    doc.querySelectorAll("[data-external]").forEach((link) => {
      link.addEventListener("click", (event) => openExternal(win, link.href, event));
    });
    // Initialize after setup hash cleanup; official SDK reads its own launch params.
    const sdk = doc.createElement("script");
    sdk.src = "https://telegram.org/js/telegram-web-app.js";
    sdk.onload = () => { try { win.Telegram?.WebApp?.ready(); } catch { /* Links work without the SDK. */ } };
    doc.head.appendChild(sdk);
    return state;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { bootstrap, taskDestination, openExternal, init };
  else if (root.document) init(root, root.document);
})(typeof window !== "undefined" ? window : globalThis);
