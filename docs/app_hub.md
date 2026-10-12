# Telegram application launcher

`site-public/apps.html` is a generic, static three-link directory. It contains no private task, calendar or research-fund data and makes no model or private-data API calls.

- **タスク** opens `tasks.html?miniapp=1` on the same origin; the compact task header links back to the directory.
- **予定** opens the actual Google Calendar web application in an external browser.
- **研究費** opens the existing research-fund dashboard in an external browser.
- Calendar/research-fund require their own existing Google authentication where applicable. They never receive task sync credentials. The mock `calendar.html` is deliberately excluded.

## Owner setup and credential handling

An owner-only setup button may point at `apps.html#sync-token=…`. Only `sync-token` and the legacy `task-board-sync-token` setup key are consumed. They are removed via history replacement before loading the official Telegram SDK. Other Telegram launch hash parameters remain available for SDK initialization.

The generic menu URL remains plain `apps.html`. Setup updates only the `token` field in existing same-origin `taskBoardSyncConfigV2`, preserving other settings/credential fields. Authenticated task writes still use the existing API and HMAC/Google authorization: this launcher grants no new permissions.

Denied storage falls back to RAM. A setup token is forwarded only on actual task navigation to the fixed same-origin task route, then consumed there. Task-to-launcher navigation similarly forwards only RAM-only task credentials to `apps.html` using a fragment; regular persistent-storage navigation has no credential fragment. No token is written into link markup, external URLs, displayed text or logs. Fragment credentials are not sent in HTTP requests; the launcher explicitly uses `no-referrer`.

The narrow task-side change adds RAM fallback for auth/in-flight display state and exception guards around filter/background preferences. Ordinary persistent precedence and explicit logout remain unchanged. With all storage denied, closing/reloading a plain menu loses RAM setup; reopen the original owner setup button. Pending RAM-only display state is also not durable across document navigation; backend request ownership is unchanged.

## Telegram SDK

Official source checked 2026-10-12: <https://core.telegram.org/bots/webapps#initializing-mini-apps> and <https://core.telegram.org/bots/webapps#webapp>.

- The official `telegram-web-app.js` creates `window.Telegram.WebApp`.
- `ready()` informs Telegram that the essential UI is ready and hides its loading placeholder.
- `openLink(url[, options])` opens an external browser without closing the Mini App and must be called in response to a user interaction.

The SDK is inserted into `<head>` immediately after setup cleanup (a deliberate ordering choice to keep setup credentials out of the launch hash before SDK initialization), then `ready()` is called on load. `openLink` is used only from clicks on the two exact external allowlisted URLs, with `try_instant_view: false`. If SDK loading/opening fails, normal `_blank` anchors with `noopener noreferrer` remain usable. Telegram launch version/platform parameters are preserved. `initDataUnsafe` is not used as authentication.

## Verification and delivery ownership

Run:

```sh
node --test tests/test_app_hub.cjs tests/test_task_board_frontend.cjs tests/test_task_board_reverse_sync_api.cjs
node --check site-public/app-hub.js
git diff --check
```

The implementation child verified unit/fixture behavior and inline task-script syntax without changing any real task. Parent owns 320/375/414/768px browser review, deployment, owner-only Telegram setup/menu updates, and actual-device verification. No native Telegram-device launch has been claimed by the child.
