"""Docker healthcheck script for Chitai application."""

import http
import ssl
import sys
import urllib.error
import urllib.request

HEALTH_CHECK_TIMEOUT = 3


def main() -> None:
    """Check if the application is healthy by hitting the /health endpoint."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(
            "https://localhost:8000/health",
            timeout=HEALTH_CHECK_TIMEOUT,
            context=ssl_context,
        ) as response:
            if response.status != http.HTTPStatus.OK:
                sys.exit(1)
    except OSError, urllib.error.URLError:
        sys.exit(1)


if __name__ == "__main__":
    main()
