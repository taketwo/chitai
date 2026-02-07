# Data model

The ORM models live in `src/chitai/db/models.py`. Migrations are managed by Alembic (`alembic/versions/`). This document covers the design decisions and the things that
are not obvious from reading the models directly.

## What exists now

Six tables: `items`, `sessions`, `session_items`, `settings`, `illustrations`, `item_illustrations`.

**Item** is the reusable unit of content — a word, phrase, or sentence in a specific language. Items are created on the fly during sessions (deduplicated by `(text, language)`) and persist across sessions. The composite index on `(text, language)` serves the autocomplete prefix query.

**Session** is one reading practice run. It records start/end timestamps and the language. A session with `ended_at = NULL` is either still active or was abandoned (server restarted mid-session — sessions do not survive restarts).

**SessionItem** is the join between a session and an item, with timestamps that track the item's lifecycle within that session. `displayed_at` is NULL for items that are still in the queue and have not yet been shown. `completed_at` is NULL for items that were displayed but never explicitly advanced past. See [websocket-protocol.md](websocket-protocol.md) for the full lifecycle.

**Settings** is a single-row table (id is always 1) with display preferences. These are persisted but not yet wired to the API or the frontend — the display currently reads defaults from client-side state. This will change in v0.8.

**Illustration** represents an image imported from URL or file upload. Files are stored on disk as `{id}.webp` and `{id}_thumb.webp` in `data/illustrations/`. The table records metadata (dimensions, file size, optional source URL) but not the filenames — those are derived by convention from the UUID. Images are processed to WebP format with configurable quality and max dimensions.

**ItemIllustration** is the many-to-many join between items and illustrations. An item can have multiple illustrations (one is randomly selected per display), and an illustration can be attached to multiple items. The composite index on `(item_id, illustration_id)` enforces uniqueness and serves the lookup queries.

## What does not exist yet

These fields are planned but not implemented. Do not add them to the model without a migration:

- `items.starred` — flagged for reuse (v0.5)
- `items.syllables_override` — manual syllabification correction per item (v1.0)

## Cascade rules

Deleting an **Item** cascade-deletes its **SessionItem** and **ItemIllustration** rows (the item disappears from session histories and loses illustration links, but illustrations remain for other items). Deleting a **Session** cascade-deletes its **SessionItem** rows but leaves the **Item** rows intact — items are reusable across sessions.

Deleting an **Illustration** cascade-deletes its **ItemIllustration** rows and removes the corresponding files from disk (`{id}.webp` and `{id}_thumb.webp`). Items lose the association but remain intact.

## Migrations

Run `just db-upgrade` to apply pending migrations. Create a new one with `just db-create-migration "description"`. The migration history is linear; there are no branches. Alembic runs automatically in the container entrypoint before the server starts.
