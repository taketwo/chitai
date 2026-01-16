"""FastAPI application with WebSocket endpoint."""

import logging

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from chitai.server.session import session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chitai")

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

    if role == "controller":
        await session.add_controller(websocket)
    elif role == "display":
        await session.add_display(websocket)
    else:
        logger.warning("Unknown role: %s", role)
        await websocket.close()
        return

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("Received from %s: %s", role, data)

            if role == "controller":
                await _handle_controller_message(data)

    except WebSocketDisconnect:
        logger.info("%s disconnected", role.capitalize())
    except (RuntimeError, ValueError) as e:
        logger.info("%s disconnected: %s", role.capitalize(), e)
    finally:
        session.remove_client(websocket)


async def _handle_controller_message(data: dict) -> None:
    """Handle messages from controller clients.

    Parameters
    ----------
    data : dict
        The message data

    """
    message_type = data.get("type")

    if message_type == "add_item":
        text = data.get("payload", {}).get("text")
        if text:
            await session.set_text(text)
        else:
            logger.warning("add_item message missing text")
    else:
        logger.warning("Unknown message type: %s", message_type)
