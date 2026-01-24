"""REST API endpoint for frontend logging."""

import logging

from fastapi import APIRouter

from chitai.server.routers.schemas import LogMessage  # noqa: TC001

router = APIRouter(prefix="/api/logs", tags=["logs"])

logger = logging.getLogger(__name__)


@router.post("")
async def receive_frontend_log(log: LogMessage) -> dict[str, str]:
    """Receive frontend console logs and write to server log.

    This endpoint allows frontend JavaScript to transmit console logs to the
    backend, making it easier to debug client-side issues by consolidating
    all logs in one place.

    Parameters
    ----------
    log : LogMessage
        The frontend log message

    Returns
    -------
    dict[str, str]
        Success acknowledgment

    """
    full_message = f"[FRONTEND] {log.message}"
    if log.args:
        full_message += f" {log.args}"

    if log.level == "error":
        logger.error(full_message)
    elif log.level == "warn":
        logger.warning(full_message)
    elif log.level == "info":
        logger.info(full_message)
    else:
        logger.debug(full_message)

    return {"status": "ok"}
