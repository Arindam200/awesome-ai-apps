import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from utils.cors import DEFAULT_ALLOWED_ORIGINS, get_allowed_origins


def create_test_client(allowed_origins: list[str]) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_default_origins_support_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert get_allowed_origins() == list(DEFAULT_ALLOWED_ORIGINS)


def test_configured_origins_are_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        " https://app.example.com,https://admin.example.com, ",
    )

    assert get_allowed_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        get_allowed_origins("*")


def test_credentialed_preflight_allows_configured_origin() -> None:
    client = create_test_client(get_allowed_origins("https://app.example.com"))

    response = client.options(
        "/health",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_credentialed_preflight_rejects_unknown_origin() -> None:
    client = create_test_client(get_allowed_origins("https://app.example.com"))

    response = client.options(
        "/health",
        headers={
            "Origin": "https://malicious.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
