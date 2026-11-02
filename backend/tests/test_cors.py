import re

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import cors_options

EXTENSION_ID = "abcdefghijklmnopabcdefghijklmnop"
OTHER_EXTENSION = "chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba"


def allowed(extension_id: str, origin: str) -> bool:
    return re.fullmatch(cors_options(extension_id)["allow_origin_regex"], origin) is not None


@pytest.mark.parametrize(
    "origin",
    [f"chrome-extension://{EXTENSION_ID}", "http://localhost:8000", "http://127.0.0.1:5173"],
)
def test_configured_extension_and_localhost_are_allowed(origin: str) -> None:
    assert allowed(EXTENSION_ID, origin)


@pytest.mark.parametrize(
    "origin",
    [
        OTHER_EXTENSION,
        "https://es.wallapop.com",
        "https://evil.example.com",
        "http://localhost.evil.example.com",
        f"chrome-extension://{EXTENSION_ID}.evil.example.com",
    ],
)
def test_other_origins_are_rejected(origin: str) -> None:
    assert not allowed(EXTENSION_ID, origin)


def test_any_extension_is_allowed_only_without_configured_id() -> None:
    assert allowed("", OTHER_EXTENSION)
    assert not allowed("", "https://evil.example.com")


def preflight(origin: str) -> tuple[int, dict[str, str]]:
    app = FastAPI()
    app.add_middleware(CORSMiddleware, **cors_options(EXTENSION_ID))

    @app.post("/analyze")
    def analyze() -> dict[str, str]:
        return {}

    response = TestClient(app).options(
        "/analyze",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            # Chrome adds this when a page or extension calls localhost (Private Network Access).
            "Access-Control-Request-Private-Network": "true",
        },
    )
    return response.status_code, dict(response.headers)


def test_preflight_from_the_extension_to_localhost_is_accepted() -> None:
    status, headers = preflight(f"chrome-extension://{EXTENSION_ID}")

    assert status == 200
    assert headers["access-control-allow-origin"] == f"chrome-extension://{EXTENSION_ID}"
    assert headers["access-control-allow-private-network"] == "true"


def test_preflight_from_a_website_is_rejected() -> None:
    status, headers = preflight("https://es.wallapop.com")

    assert status == 400
    assert "access-control-allow-origin" not in headers
