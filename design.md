/* Hallmark · pre-emit critique: P5 H5 E5 S5 R4 V5 */

# Mission Control Task Board Design System

Status: locked design source for the task board.
Source of truth: `site-public/tasks-floral-mock.html`
Production file: `site-public/tasks.html`
Public URL: https://site-public.vercel.app/tasks.html
Reference URL: https://mac-studio.tail8d1e3e.ts.net/floral-task-mock/tasks-floral-mock.html

This document captures the design DNA of the floral task board so future edits do not drift back into the older dark/cyber task-board style.

## Design Intent

The task board should feel like a soft, tactile daily notebook for research, email, and life operations. It is not a SaaS dashboard, not a cyber console, and not a generic kanban board.

The interface should be:
- warm, handmade, and floral
- compact enough for repeated phone use
- rich in texture, but still readable
- one-column and calm, with task cards as the main object
- playful only at interaction points, especially check completion

Avoid:
- dark cyber palettes
- black glass panels
- generic Tailwind dashboard cards
- large marketing-page hero sections
- nested cards inside cards
- replacing the floral notebook structure with a normal admin layout

## Canonical Page Structure

Current production order:

1. Top navigation with back button, sync pill, and small settings button
2. Compact floral hero card: `Mission Control · Task Board`, one-line `今日のタスク`, progress orb, short hold-note only
3. Segmented filter:
   - 全部
   - 自分
   - Bot
4. Section title and count
5. Categorized task list, grouped by headings parsed from Obsidian `Meta TODO.md`
6. Background switcher, below the task list so tasks appear immediately
7. Sticky bottom action bar

The page should stay mobile-first and centered on phones. Desktop should widen with the viewport:
- phone: one task/category column
- tablet/narrow desktop: one readable `~720px` column
- desktop: two category columns from `1040px`
- wide desktop: three category columns from `1360px`

Do not turn it into a dense admin dashboard. The wider layout is only for faster PC scanning: category panels should wrap into two or three calm columns while preserving the floral notebook feeling.

## Typography

Use the rounded Japanese UI stack from the current HTML:

```css
--font-ui: "Hiragino Maru Gothic ProN", "Hiragino Maru Gothic Pro", "Yu Gothic Rounded", "Tsukushi A Round Gothic", "Zen Maru Gothic", "M PLUS Rounded 1c", "Hiragino Sans", "Yu Gothic", "YuGothic", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
```

Keep type compact and dense:
- Hero title: large, rounded, high weight, but not a landing-page hero scale
- Task title: about `15px`, heavy weight, line-height around `1.45`
- Task titles render as one-line ellipsized rows in production for faster scanning
- Buttons: bold, rounded, symbol-friendly

Do not introduce serif display fonts, tech monospace branding, or oversized marketing typography.

## Color Tokens

The palette is warm paper plus vivid floral accents. Keep these tokens as the core system:

```css
--color-paper: #f4e4cf;
--color-paper-deep: #dec2a4;
--color-paper-warm: #ead3b4;
--color-cream: #fff8ec;
--color-cream-glass: rgba(255, 248, 236, 0.74);
--color-glass-bright: rgba(255, 255, 255, 0.68);
--color-petal: #d58c96;
--color-petal-deep: #b9536d;
--color-rose: #c92e58;
--color-coral: #e26b43;
--color-lavender: #b7a6df;
--color-violet: #8f7ac2;
--color-indigo: #444c9d;
--color-cobalt: #176eb7;
--color-leaf: #8dbd8b;
--color-leaf-deep: #5f946a;
--color-teal: #238c82;
--color-aqua: #31b8ad;
--color-mimosa: #f0c130;
--color-honey: #c7801f;
--color-rust: #9f4d35;
--color-plum: #8a3f85;
--color-sky: #9dc8df;
--color-ink: #46352b;
--color-ink-soft: #7c6659;
--color-line: rgba(120, 92, 72, 0.18);
--color-pattern: rgba(92, 67, 96, 0.15);
--color-blueberry: #2f459d;
--color-clay: #ad3f34;
--color-orchid: #9d3e87;
--color-citrine: #d59b17;
--color-emerald: #2f9c68;
--color-berry: #a92363;
--color-shadow: rgba(116, 79, 45, 0.18);
--color-white: rgba(255, 255, 255, 0.86);
```

Do not collapse this into one beige theme. The page needs rose, blue, teal, yellow, green, and plum accents so the floral textile feeling survives.

## Surface And Glass

Use rounded, tactile, liquid-glass surfaces:

```css
--radius-shell: 34px;
--radius-card: 28px;
--radius-button: 999px;
--shadow-raised: 0 18px 34px var(--color-shadow), inset 0 1px 0 var(--color-white);
--shadow-liquid: 0 17px 30px rgba(79, 48, 34, 0.2), 0 5px 12px rgba(255, 255, 255, 0.24), inset 0 2px 0 rgba(255, 255, 255, 0.78), inset 0 -12px 20px rgba(83, 48, 31, 0.14);
--shadow-liquid-pressed: inset 0 8px 16px rgba(83, 48, 31, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.54);
--shadow-pressed: inset 0 7px 14px rgba(109, 72, 42, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.45);
--blur-glass: blur(22px) saturate(1.35);
```

Liquid glass applies to whole task cards, not only buttons. Cards should have depth, inner highlight, and light translucency.

## Background System

The user explicitly wants background mood switching. Preserve the four-mode switcher and local preference storage.
The switcher should not appear before tasks. Keep it below the task list or otherwise out of the first task-scanning area.

Current background assets:
- `assets/generated-dark-paisley.webp`
- `assets/generated-scattered-petals.webp`
- `assets/generated-branch-forest.webp`
- `assets/slow-mixed-paint-generated.webp`

Do not put a milky white wash over the selected background image. Avoid page-wide pseudo overlays for the app shell; the bitmap texture itself should show without a pale membrane effect.

Modes:
- `paisley`: dense pattern, vivid and strongest
- `petals`: light scattered floral
- `leaves`: green branch/forest mood
- `paint`: painterly mixed tail, current default

Store the selected mode in:

```js
localStorage.setItem("taskBoardBackgroundChoiceV2", selected);
```

Default background should be `paint` unless the user asks otherwise.

## Task Cards

Task cards are the main UI object. Preserve:
- one task per rounded liquid-glass card
- check button on the left
- full task title on the right with wrapping, especially in the 2/3-column PC layout
- category grouping from Meta TODO headings
- responsive PC layout with category panels in two or three columns when the window is wide enough
- done tasks sorted after unfinished tasks
- category-like color variation through `nth-of-type` styling so only task cards are counted, not category headings
- category panels must stay highly translucent on desktop; use only very low-opacity glass (`~0.1` cream/white layers) so they organize tasks without becoming a white backing card that hides the selected background behind completed tasks
- visible but restrained color on unfinished cards, using rose, teal, blue, and honey tints so uncompleted tasks do not read as plain beige
- unfinished cards should feel like small ceramic plates: raised rim, glazed shine, shallow concave center, and tactile shadow. The center must read as recessed, not inflated: use a subtle upper inner shadow and lower inner highlight, plus the `::after` inner rim. Do this with layered gradients and inset shadows rather than making the whole card an opaque white slab.

Do not show implementation/meta tags (`#id`, `@assignee`, `Priority`, status chips, source IDs, or sync explanations) in the visible card list. Those can exist in `tasks.json` for internal logic but should not clutter the public UI.

Done state:
- use `.task-card.is-done`
- reduce opacity to around `0.58`
- keep the surface translucent enough that the selected background texture is visibly present through completed cards
- no strikethrough
- task title becomes white-ish gray:

```css
.task-card.is-done .task-name {
  color: rgba(226, 222, 216, 0.9);
  text-shadow: 0 2px 7px rgba(22, 15, 24, 0.46);
  text-decoration: none;
}
```

Do not restore black text, heavy deletion lines, or old dark-card completion styling.

## Interaction Rules

Check completion behavior:
- Delay visual status change by `100ms`
- Keep the tiny pause; it makes the tap feel intentional
- When a task is checked done locally, keep it in its current unfinished-list position for 1 hour before releasing it into the completed section. This prevents tapped tasks from jumping out of view while the user is still scanning.
- Do not call full `renderTasks()` before the sparkle finishes when marking a task done. First update the existing card to `.is-done`, fire `sparkle(card)`, refresh counters, then re-render after `sparkleDurationMs`. Immediate re-render removes the DOM node and hides the burst.
- Trigger petal sparkle only when marking a task done
- Keep reduced-motion support

Canonical constants:

```js
const localStateKey = "taskBoardLocalStateV2";
const backgroundKey = "taskBoardBackgroundChoiceV2";
const toggleDelayMs = 100;
const doneHoldMs = 60 * 60 * 1000;
const sparkleDurationMs = 1280;
```

Petal sparkle:
- `.petal-burst` contains 10 spans
- Animation name: `petal-pop`
- Use varied petal colors from the token palette
- Do not replace this with confetti emoji or a generic animation library

## Data Rules

Obsidian `Meta TODO.md` is the upstream task source. The public board must not be edited by hand as an independent source of truth.

Generate the public JSON with:

```bash
python3 scripts/meta_todo_task_board_agent.py
```

The lower-level generator remains `scripts/meta_todo_to_tasks_json.py`, but normal operation should use the dedicated MetaTODO Task Board Agent so privacy checks, commit/push, Vercel deploy, and public verification all happen together.

Production `tasks.html` must read the generated static task data from:

```js
fetch("tasks.json", { cache: "no-store" })
```

Do not make the public static page depend on `/api/task-board/tasks` unless that endpoint is actually implemented and verified. A previous regression came from pointing the page at a missing API.

Permanent task changes belong upstream in:

```text
/Users/michito/Library/Mobile Documents/iCloud~md~obsidian/Documents/Hamada_Obsidian/Meta TODO.md
```

Then regenerate and publish:

```text
site-public/tasks.json
```

Local browser checking is temporary UI state only. Agent-side permanent updates must edit `Meta TODO.md`, run the MetaTODO Task Board Agent, and let it regenerate `tasks.json`, commit, push, deploy, and verify.

The normal production UI should not show a long sync memo before or after the task list. If debugging text is temporarily needed, it may say that the board reads `tasks.json` generated from Obsidian `Meta TODO`, but operational notes should stay out of the normal task-scanning flow.

## Responsive Rules

Verify these widths after visual edits:
- 320px
- 375px
- 414px
- 768px

Required behavior:
- no horizontal scroll
- shell remains mobile-first and centered
- task text wraps inside cards
- background options become one-column on narrow phones
- segmented buttons stay readable and do not force horizontal scrolling
- sticky bottom action bar remains inside viewport

## Implementation Guardrails

Before changing the task board UI, read this file and inspect:

```text
site-public/tasks-floral-mock.html
site-public/tasks.html
site-public/tasks.json
```

The best design reference is `tasks-floral-mock.html`. Production `tasks.html` should preserve that design while adding real task loading.

After edits:

1. Parse inline JavaScript.
2. Take a mobile screenshot at 375px.
3. Compare production/local page against the design reference if anything looks off.
4. Commit and push.
5. Manually deploy Vercel if auto-deploy is canceled.
6. Verify the production hash or screenshot before reporting done.

## Known Regression To Avoid

Do not repeat the partial-transfer mistake:

- `tasks-floral-mock.html` had the best design.
- `tasks.html` previously became a partial hybrid with old layout remnants.
- The user noticed that most of the previous work was missing.

When asked to apply the best design, move the complete design system over first, then carefully reapply production data behavior. Do not rebuild from memory.
