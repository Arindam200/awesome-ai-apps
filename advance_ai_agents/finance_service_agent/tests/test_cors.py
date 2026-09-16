import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.cors import get_allowed_origins


def test_defaults_to_localhost_when_unset(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert get_allowed_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_parses_comma_separated_configured_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", " https://app.example.com ,https://admin.example.com"
    )

    assert get_allowed_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_rejects_wildcard_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    assert get_allowed_origins() == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_drops_wildcard_but_keeps_explicit_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,*")

    assert get_allowed_origins() == ["https://app.example.com"]
