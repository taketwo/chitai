# WebSocket protocol & session lifecycle

All real-time coordination happens over a single WebSocket endpoint at `/ws`. Message shapes are defined as Pydantic models in `src/chitai/server/websocket/protocol.py`. This document covers the *behavioral* contract — the rules that aren't obvious from reading the message definitions alone.

## Connection

```
wss://<host>/ws?role=controller|display
```

`role` selects the UI served by the static-file mount. At the protocol level it is informational only; any connected client can send any message type.

On connect, the server sends the full current state. This is how reconnecting clients (and new clients joining a session already in progress) get in sync without any handshake.

## The state message

The server pushes state after every mutation. Shape (see `StatePayload` in `protocol.py` for the exact Pydantic model):

```json
{
  "type": "state",
  "payload": {
    "session_id": "uuid | null",
    "language": "ru | de | en | null",
    "words": ["..."],
    "syllables": [["..."]],
    "current_word_index": 0,
    "illustration_id": "uuid | null",
    "queue": [{ "session_item_id": "uuid", "text": "..." }]
  }
}
```

## The two meanings of `current_word_index: null`

This is the most important behavioral detail in the protocol. `null` means two different things depending on context:

| `words` is empty | `current_word_index` | Meaning                                      |
|------------------|----------------------|----------------------------------------------|
| yes              | null                 | No item is loaded. Session may or may not be active. |
| no               | null                 | The current item is **completed**. Words are still present so the display can show the full text without highlighting. |

The completed state is a **one-way door**: you cannot navigate backward out of it with `advance_word`. The only way forward is `next_item` (if the queue is non-empty) or adding a new item.

## Item lifecycle within a session

An item moves through these states. The transitions that touch the database are marked.

```
add_item
    │
    ▼
┌─────────┐   (no current item)   ┌───────────┐
│ queued  │ ─────────────────────►│ displayed │  ← displayed_at written to DB
└────┬────┘                       └─────┬─────┘
     │                                  │
     │  next_item                       │  advance_word past last word
     │  (current item completed first)  ▼
     │                           ┌───────────┐
     └──────────────────────────►│ completed │  ← completed_at written to DB
                                 └───────────┘
```

- **Queued → Displayed** happens immediately (without going through the queue) if nothing is currently displayed when `add_item` arrives.
- **Displayed → Completed** via `next_item` writes `completed_at` on the *current* item, then pops the queue. It does *not* require the item to have been read word by word first — the parent can skip ahead.
- **Ending a session does not auto-complete items.** Incomplete items remain as a record of what was displayed or queued but not finished.

## Grace timer

The grace timer prevents sessions from lingering forever if all clients disconnect.

It is **activity-based, not disconnect-based.** Every incoming WebSocket message (from any client) refreshes the countdown while a session is active. The timer is stopped entirely when there is no active session. If it expires without being refreshed, the session is ended the same way `end_session` would end it (timestamp written, state reset, broadcast pushed).

The countdown duration is `CHITAI_GRACE_PERIOD_SECONDS` (default 3600). See `src/chitai/server/grace_timer.py` for the implementation.

## What is persisted vs. ephemeral

This is the cross-cutting concern that's hardest to reconstruct from code alone, because the reads and writes are spread across `handlers.py`, `session.py`, and `models.py`.

| Runtime field            | Persisted?                     | Where in DB                        |
|--------------------------|--------------------------------|------------------------------------|
| session_id               | Yes, on `start_session`        | `sessions.id`                      |
| current_session_item_id  | Yes, on display                | `session_items.displayed_at`       |
| queue membership         | Yes, on `add_item`             | `session_items` with `displayed_at = NULL` |
| illustration_id          | Yes, on display                | `session_items.illustration_id`    |
| current_word_index       | Never                          | Ephemeral                          |
| words                    | Never (derived from item text) | Ephemeral                          |
| syllables                | Never (computed on broadcast)  | Ephemeral                          |

`syllables` is a computed property on `SessionState` — it calls `syllabify()` on `words` every time it is accessed. Nothing syllabification-related is stored.

`illustration_id` is randomly selected from the item's linked illustrations when the item is displayed. If an item has multiple illustrations, one is chosen via `random.choice()`. The selection is written to `session_items.illustration_id` so that session history preserves which illustration was shown. Queued items have `illustration_id = NULL` until they are displayed.
