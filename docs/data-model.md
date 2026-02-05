# Data model

The ORM models live in `src/chitai/db/models.py`. Migrations are managed by Alembic (`alembic/versions/`). This document covers the design decisions and the things that
are not obvious from reading the models directly.

## What exists now

Four tables: `items`, `sessions`, `session_items`, `settings`.

**Item** is the reusable unit of content — a word, phrase, or sentence in a specific language. Items are created on the fly during sessions (deduplicated by `(text,
language)`) and persist across sessions. The composite index on `(text, language)` serves the autocomplete prefix query.

**Session** is one reading practice run. It records start/end timestamps and the language. A session with `ended_at = NULL` is either still active or was abandoned (server restarted mid-session — sessions do not survive restarts).

**SessionItem** is the join between a session and an item, with timestamps that track the item's lifecycle within that session. `displayed_at` is NULL for items that are still in the queue and have not yet been shown. `completed_at` is NULL for items that were displayed but never explicitly advanced past. See [websocket-protocol.md](websocket-protocol.md) for the full lifecycle.

**Settings** is a single-row table (id is always 1) with display preferences. These are persisted but not yet wired to the API or the frontend — the display currently reads
defaults from client-side state. This will change in v0.8.

## What does not exist yet

These fields are planned but not implemented. Do not add them to the model without a migration:

- `items.illustration_path` — local path to an attached image (v0.4)
- `items.starred` — flagged for reuse (v0.5)
- `items.syllables_override` — manual syllabification correction per item (v1.0)

## Cascade rules

Deleting an **Item** cascade-deletes its **SessionItem** rows (the item disappears from all session histories). Deleting a **Session** cascade-deletes its **SessionItem** rows but leaves the **Item** rows intact — items are reusable across sessions.

## Migrations

Run `just db-upgrade` to apply pending migrations. Create a new one with `just db-create-migration "description"`. The migration history is linear; there are no branches. Alembic runs automatically in the container entrypoint before the server starts.
