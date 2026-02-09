"""Integration tests for /api/logs endpoint."""

import pytest

from tests.integration.helpers import http_client


class TestLogsEndpoint:
    """Tests for /api/logs endpoint."""

    @pytest.mark.asyncio
    async def test_receive_frontend_log(self):
        """Test POST /api/logs accepts and acknowledges frontend log."""
        async with http_client() as client:
            response = await client.post(
                "/api/logs",
                json={
                    "level": "error",
                    "message": "Test error from frontend",
                    "args": [],
                },
            )

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_receive_frontend_log_all_levels(self):
        """Test POST /api/logs accepts all log levels."""
        async with http_client() as client:
            for level in ["log", "info", "warn", "error"]:
                response = await client.post(
                    "/api/logs",
                    json={
                        "level": level,
                        "message": f"Test {level} message",
                        "args": [],
                    },
                )

                assert response.status_code == 200
                assert response.json() == {"status": "ok"}
