# Architecture

Chitai is a parent-driven reading practice tool. The parent types text on a phone; the child reads it on a tablet. A laptop is used for library management between sessions. All three devices talk to a single FastAPI server over WebSockets (real-time session state) and REST (persistent data).

## The mental model

A **session** is one reading practice run. Inside a session, the parent adds **items** (words or sentences). Items are read one at a time, word by word, with the parent tapping to advance. Items can be queued ahead of time or submitted on the fly.

The session is the unit of real-time coordination. Everything outside a session (browsing the library, reviewing history) is plain HTTP against the REST API.

## How the pieces fit together

```
Phone (controller)          Tablet (display)         Laptop (admin)
      │                           │                        │
      │  wss /ws?role=controller  │  wss /ws?role=display  │  HTTP /api/*
      └───────────┬───────────────┘────────────────────────┘
                  │
          ┌───────▼─────────┐
          │   FastAPI app   │
          │                 │
          │  WebSocket hub  │  ← single endpoint, all roles
          │  REST routers   │  ← items, sessions, autocomplete, logs
          │  SessionState   │  ← in-memory, single source of truth
          │  GraceTimer     │  ← auto-ends idle sessions
          └───────┬─────────┘
                  │ SQLAlchemy
          ┌───────▼─────────┐
          │   SQLite DB     │  ← volume-mounted, survives restarts
          └─────────────────┘
```

- **Controller and display share the same WebSocket endpoint.** The `role` query parameter selects which HTML page is served, but at the protocol level all clients are equal — any client can send any message. Access control is in the UI, not the server.
- **SessionState is the single source of truth** for what is currently on screen. Every WebSocket message that changes it triggers a broadcast to all connected clients. A client that connects mid-session receives the current state immediately.
- **SQLite persists what matters for history.** What is ephemeral (current word index, syllables) and what is persisted (items, session timestamps, queue membership) is documented in [websocket-protocol.md](websocket-protocol.md).
- **All connections are TLS.** A self-signed certificate is generated on first container start. Clients connect via `wss://`.

## What lives where

| Concern                          | Where to look                                    |
|----------------------------------|--------------------------------------------------|
| Session state & lifecycle        | [websocket-protocol.md](websocket-protocol.md)  |
| Database schema & migrations     | [data-model.md](data-model.md)                   |
| Frontend conventions & gotchas   | [frontend.md](frontend.md)                       |
| Docker, CI/CD, env vars          | [deployment.md](deployment.md)                   |
| Roadmap & what's planned         | [roadmap.md](roadmap.md)                         |
