# Task Board Remote Reverse Sync

Public browsers never touch `Meta TODO.md` directly. The remote write path is:

1. `site-public/tasks.html`
2. `site-public/api/task-board-reverse-sync/*` on Vercel
3. GitHub issue queue in `miiichiii/jikken-note-claw`
4. `scripts/task_board_reverse_sync_queue_worker.py` on the Mac Studio
5. `scripts/task_board_reverse_sync.py`
6. `scripts/meta_todo_task_board_agent.py`
7. refreshed `site-public/tasks.json` and Vercel deploy

## Secrets

Do not commit secrets. Runtime configuration is:

- Vercel `TASK_BOARD_SYNC_CLIENT_TOKEN`
- Vercel `TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN`
- optional Vercel `TASK_BOARD_GOOGLE_CLIENT_ID`
- optional Vercel `TASK_BOARD_GOOGLE_ALLOWED_EMAILS`
- optional Vercel `TASK_BOARD_GOOGLE_ALLOWED_DOMAINS`
- optional Vercel `TASK_BOARD_SYNC_QUEUE_REPO`
- optional local `TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN`

The browser never sends the raw sync token as a bearer token. It keeps the token only in `sessionStorage` and sends short-lived HMAC-signed requests.

The Mac worker also works with existing `gh auth token` if no local env token is set.

Google login mode is optional and can replace manual token entry for normal browser use. In that mode:

- the browser gets a Google ID token from Google Identity Services
- Vercel verifies the ID token against the configured web client id
- reverse sync is allowed only for explicitly allowed email addresses or domains
- the legacy signed-token path stays available as a fallback until migration is complete

## Vercel setup

Project root is `site-public/`.

Required env vars:

```bash
vercel env add TASK_BOARD_SYNC_QUEUE_GITHUB_TOKEN production
```

Legacy token mode also needs:

```bash
vercel env add TASK_BOARD_SYNC_CLIENT_TOKEN production
```

Optional:

```bash
vercel env add TASK_BOARD_GOOGLE_CLIENT_ID production
vercel env add TASK_BOARD_GOOGLE_ALLOWED_EMAILS production
vercel env add TASK_BOARD_GOOGLE_ALLOWED_DOMAINS production
vercel env add TASK_BOARD_SYNC_QUEUE_REPO production
```

After env changes, redeploy the `site-public` project.

## Google login setup

No Firebase is required for this task-board flow. Use a standard Google Cloud OAuth web client:

1. In Google Cloud Console, create or reuse an OAuth 2.0 Client ID of type `Web application`.
2. Add `https://site-public.vercel.app` to Authorized JavaScript origins.
3. Put the resulting client id into Vercel as `TASK_BOARD_GOOGLE_CLIENT_ID`.
4. Restrict who can write by setting one of:
   - `TASK_BOARD_GOOGLE_ALLOWED_EMAILS` as a comma-separated allowlist
   - `TASK_BOARD_GOOGLE_ALLOWED_DOMAINS` as a comma-separated domain allowlist
5. Redeploy the Vercel project.

Recommended migration:

1. Keep `TASK_BOARD_SYNC_CLIENT_TOKEN` in place temporarily.
2. Add the Google env vars above.
3. Open `tasks.html` and confirm the Google sign-in card appears.
4. Verify a checkbox update succeeds without entering the sync token.
5. Only after the new flow is stable, decide whether the legacy token shortcut is still needed.

## Mac worker

Template plist:

- `ops/launchd/ai.openclaw.task-board-reverse-sync-queue-worker.plist`

Install:

```bash
mkdir -p ~/Library/LaunchAgents ~/.openclaw/logs
cp ops/launchd/ai.openclaw.task-board-reverse-sync-queue-worker.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/ai.openclaw.task-board-reverse-sync-queue-worker.plist 2>/dev/null || true
launchctl load ~/Library/LaunchAgents/ai.openclaw.task-board-reverse-sync-queue-worker.plist
```

Smoke test once without launchd:

```bash
python3 scripts/task_board_reverse_sync_queue_worker.py
```

## iPhone use

Recommended first-time setup:

```bash
python3 /Users/michito/Documents/clawd/scripts/send_task_board_link.py \
  --target 8446959779 \
  --with-token \
  --button
```

- `--with-token` is DM-only. It reads the local token from `~/.openclaw/state/task_board_remote_sync_client_token.txt`
- the setup link carries the token only in the URL fragment (`#sync-token=...`), so the browser can store it in `sessionStorage` without sending it to Vercel
- default `タスク` shortcuts can keep using the plain URL without re-sending the token every time
- once Google login is configured, the Google button on `tasks.html` should be the primary path; token links become fallback only

Manual iPhone flow:

1. Open the one-time setup link from Telegram DM, or open `https://site-public.vercel.app/tasks.html`
2. If the page still shows `逆同期未設定 ⌘で初回設定`, tap `⌘`
3. Paste the reverse-sync token from your Telegram DM only if needed
4. Tap a task checkbox
5. Wait for `同期中` → `同期済み` or `正本更新済み / 公開待ち`

If the request becomes stale because the task changed elsewhere, the card shows `競合で停止`.
