# Roadmap

## Shipped

### v0.0 — Scaffolding

* Git repo, Docker dev/prod profiles, FastAPI skeleton, CI/CD pipeline (lint, type check, tests, container smoke test, deploy via Watchtower), basic static file serving.

### v0.1 — Core loop

* Parent types text → server syllabifies → tablet renders. Word-by-word highlight, parent taps to advance. Single item, no queue, no persistence. Unit tests for syllabification.

### v0.2 — Persistence

* SQLite via SQLAlchemy + Alembic. Items and sessions saved. Session history logged. Tests for DB operations.

### v0.3 — Queue & flow

- Queue: parent can prep multiple items ahead of the child
- Completed state: advancing past the last word completes the item; the full text stays visible without highlighting until the parent moves on
- Admin UI: items table with usage stats, sessions table with duration, delete with cascade, tab persistence via URL hash
- Autocomplete on controller text input (prefix match, language-filtered, debounced)
- REST API: list/get/delete items and sessions, autocomplete, frontend log relay
- WebSocket reliability: auto-reconnect with backoff, visibility-aware connection lifecycle, activity-based grace timer, configurable ping timeout
- Integration tests covering the full session flow end to end

### v0.4 — Illustrations

- Many-to-many relationship: items can have multiple illustrations, illustrations can attach to multiple items
- Import from URL or file upload (admin UI)
- Images processed to WebP format with configurable quality and max dimensions
- Convention-based file storage: `{uuid}.webp` and `{uuid}_thumb.webp` in `data/illustrations/`
- Random selection when item has multiple illustrations (ephemeral, not persisted)
- Two-panel tablet layout: text + illustration split 50/50, adapts to orientation
- Illustration fades in on item completion, fades out synchronized with text slide animation
- Pre-fetch for instant reveal
- Item creation form in admin UI (text + language dropdown)
- Unique constraint on `(text, language)` prevents duplicates

## Planned

### v0.5 — Starring & back-scroll

Star items during a session for later reuse. Back-scroll through session history on the tablet (parent-controlled). End-of-session review.

### v0.6 — Image search (laptop)

On-the-fly image search in the admin UI. Selected result downloaded and saved locally.

### v0.7 — Phone-friendly illustration workflow

Move image search and selection to the phone controller. UI optimized for quick mid-session selection.

### v0.8 — Settings

Wire the Settings table to the API and the frontend. Syllables on/off, dim controls. Persisted, editable from the parent interface.

### v1.0 — Multi-language

German and English syllabification via `pyphen`. Language selector per session. Documentation, README, license. Open-source release.

### Future

AI image generation with cost controls and confirmation before generating.
