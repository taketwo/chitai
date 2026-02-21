# Frontend

Three UIs, all served as static files by FastAPI. No build step, no bundler. Each page loads its own JS plus shared modules from `web/`.

## The three pages

| Page | URL path | Role | Framework |
|------|----------|------|-----------|
| Controller | `/web/controller/` | Parent (phone) | Alpine.js |
| Display | `/web/display/` | Child (tablet) | Alpine.js |
| Admin | `/web/admin/` | Parent (laptop) | Alpine.js |

Controller and display connect to the WebSocket on load and stay connected for the lifetime of the page. Admin does not use WebSockets — it talks to the REST API only.

## Shared modules

**`websocket.js` — `ChitaiWebSocket`**

The shared WebSocket client. Important behaviors that are non-obvious:

- **Visibility-aware lifecycle.** When the page is hidden (e.g. tablet goes to background), the connection is closed proactively. Mobile browsers throttle background tabs and kill pong responses, which causes noisy server-side keepalive timeouts. On visibility restore the connection is reopened immediately, bypassing the exponential backoff.
- **Exponential backoff on disconnect.** Starts at 1 s, caps at 30 s. Resets to 1 s on successful reconnect.
- **Connection status indicator.** An optional DOM element is managed automatically — a red triangle appears in the top-right corner after a 1 s grace period if the connection has not (re)established. Disappears on connect.
- **Initial state on connect.** The server sends the current state immediately after the WebSocket is accepted. The client does not need to request it.

**`debug.js`**

Intercepts `console.log/info/warn/error` and forwards each call to `POST /api/logs`. This lets all frontend logs appear in the server log stream (prefixed `[FRONTEND]`), which is useful when debugging via `just docker-logs -f`. Load it before any other script on every page.

**`styles.css`**

Shared CSS custom properties and button styles. Controller and display layout styles live here. Admin has its own `admin/admin.css` for table and tab styles.

**`icons.svg`**

SVG sprite. Icons are referenced via `<use href="/web/icons.svg#name">`.

## Controller view switching

The controller has a bottom navigation bar that switches between Queue and Library views. The active view is driven by URL hash (`#library`; queue is the default when hash is empty). A `hashchange` listener syncs the view on browser back/forward. The library view's state (search text, filter pills, results) persists in the Alpine component when switching away and back — no re-fetch needed.

The admin UI also uses URL hash for tab persistence, but with a different mechanism (`loadTabFromHash`). Both follow the same principle: hash is the source of truth, UI reacts to hash changes.

## Alpine.js conventions

- **Do not use `x-init` to call `init()`.** Alpine automatically invokes an `init()` method if one is present on the `x-data` object. Adding `x-init="init()"` causes a double invocation.
- All three pages use the `x-data="appName()"` pattern — a plain function that returns the component object. `init()` is the setup entry point within that object.
- `$refs` are used sparingly: the status indicator element and the controller's current-word element (for dynamic font-size adjustment).

## Display layout and animations

The display uses a two-panel layout: text on one side, illustration on the other. The panels split 50/50 and adapt to orientation — landscape (side-by-side) vs portrait (stacked). This is handled via CSS Grid with `grid-template-columns` and `grid-template-rows` set dynamically based on an `orientation` data property that updates on window resize.

The text panel is a flex container that centers the `#textDisplay` element (max-width 900px), so word highlights fit the content width rather than stretching to fill the full panel.

**Slide animation:** When a new item starts (transition from completed/empty to word index 0), the text slides out and in from opposite sides. The slide direction adapts to viewport orientation. The illustration fades out simultaneously with the text slide-out, then the new illustration is pre-fetched (via `new Image()`) during the off-screen transition.

**Illustration reveal:** When the item completes (`current_word_index` becomes `null`), the illustration fades in via opacity transition. The image is centered in its panel with `object-fit: contain`.

The highlight (yellow background on the current word) is applied *after* the slide-in settles, so the child sees the new text arrive before attention is drawn to word one. An `animationId` counter guards against stale animations if a new item arrives before the previous transition finishes.

**Placeholder:** A centered spinner (🌀) overlays the entire screen when no session is active. It fades in/out via opacity transition and is positioned independently of the panel layout (`position: absolute` covering the full `.app-wrapper`).
