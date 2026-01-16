"""FastAPI application with WebSocket endpoint."""

import logging

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chitai")

app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Minimal WebSocket endpoint for v0.0 testing."""
    await websocket.accept()
    logger.info("WebSocket connected")

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received: %s", data)
            await websocket.send_json({"echo": data})
    except (RuntimeError, ValueError) as e:
        logger.info("WebSocket disconnected: %s", e)
