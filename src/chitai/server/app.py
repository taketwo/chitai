"""FastAPI application with WebSocket endpoint."""

import logging

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from chitai.server.session import SessionState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chitai")

app.state.session = SessionState()

app.mount("/web", StaticFiles(directory="web", html=True), name="web")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    role: str = Query(..., description="Client role: 'controller' or 'display'"),
) -> None:
    """WebSocket endpoint for controller and display clients.

    Parameters
    ----------
    websocket : WebSocket
        The WebSocket connection
    role : str
        Client role: 'controller' or 'display'

    """
    await websocket.accept()
    session = websocket.app.state.session

    if role not in ("controller", "display"):
        logger.warning("Unknown role: %s", role)
        await websocket.close()
        return

    await session.add_client(websocket, role)

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received from %s: %s", role, data)
            await _handle_message(websocket, data)

    except WebSocketDisconnect:
        logger.info("%s disconnected", role.capitalize())
    except (RuntimeError, ValueError) as e:
        logger.info("%s disconnected: %s", role.capitalize(), e)
    finally:
        session.remove_client(websocket)


async def _handle_message(websocket: WebSocket, data: dict) -> None:
    """Handle messages from any client.

    Parameters
    ----------
    websocket : WebSocket
        The client's WebSocket connection
    data : dict
        The message data

    """
    session = websocket.app.state.session
    message_type = data.get("type")

    if message_type == "add_item":
        text = data.get("payload", {}).get("text")
        if text:
            await session.set_text(text)
        else:
            logger.warning("add_item message missing text")
    elif message_type == "advance_word":
        delta = data.get("payload", {}).get("delta", 1)
        await session.advance_word(delta)
    else:
        logger.warning("Unknown message type: %s", message_type)
