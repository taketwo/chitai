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

## Alpine.js conventions

- **Do not use `x-init` to call `init()`.** Alpine automatically invokes an `init()` method if one is present on the `x-data` object. Adding `x-init="init()"` causes a double invocation.
- All three pages use the `x-data="appName()"` pattern — a plain function that returns the component object. `init()` is the setup entry point within that object.
- `$refs` are used sparingly: the status indicator element and the controller's current-word element (for dynamic font-size adjustment).

## Display animations

When a new item starts (transition from completed/empty to word index 0), the display animates a slide: old text slides out, new text slides in from the opposite side. The slide direction adapts to the viewport — vertical on landscape (tablet), horizontal on portrait. The animation is driven by CSS transitions and coordinated by Alpine state (`slideState`). An `animationId` counter guards against stale animations if a new item arrives before the previous transition finishes.

The highlight (yellow background on the current word) is applied *after* the slide-in settles, so the child sees the new text arrive before attention is drawn to word one.
