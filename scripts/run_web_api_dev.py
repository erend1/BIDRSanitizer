"""Run the loopback-only review API for local web-client development."""

from __future__ import annotations

import os

import uvicorn

from bidr_sanitizer.api import WebAPISettings, create_app


HOST = "127.0.0.1"
PORT = 8765
TOKEN_ENVIRONMENT_VARIABLE = "BIDR_DEV_API_TOKEN"


def main() -> None:
    token = os.environ.get(TOKEN_ENVIRONMENT_VARIABLE)
    if token is None:
        raise SystemExit(
            f"Set {TOKEN_ENVIRONMENT_VARIABLE} to a fresh per-launch token first."
        )
    print(token)
    app = create_app(
        settings=WebAPISettings(
            api_token=token,
            allowed_hosts=(HOST, "localhost"),
            allowed_origins=(
                "http://127.0.0.1:4173",
                "http://localhost:4173",
            ),
        )
    )
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
