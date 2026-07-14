import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class FunASRSettings:
    funasr_base_url: str
    funasr_model: str
    funasr_api_key: str | None
    funasr_timeout_seconds: float


@dataclass(frozen=True)
class NebiusSettings:
    nebius_api_key: str | None
    nebius_base_url: str
    nebius_model: str
    nebius_timeout_seconds: float


@dataclass(frozen=True)
class Settings(FunASRSettings, NebiusSettings):
    pass


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    if environ is None:
        load_dotenv()
        return os.environ
    return environ


def load_funasr_settings(
    environ: Mapping[str, str] | None = None,
) -> FunASRSettings:
    environ = _environment(environ)
    return FunASRSettings(
        funasr_base_url=_validated_url(
            "FUNASR_BASE_URL",
            environ.get("FUNASR_BASE_URL", "http://127.0.0.1:8000/v1"),
        ),
        funasr_model=_required("FUNASR_MODEL", environ.get("FUNASR_MODEL", "sensevoice")),
        funasr_api_key=_optional(environ.get("FUNASR_API_KEY")),
        funasr_timeout_seconds=_positive_seconds(
            "FUNASR_TIMEOUT_SECONDS",
            environ.get("FUNASR_TIMEOUT_SECONDS", "120"),
        ),
    )


def load_nebius_settings(
    environ: Mapping[str, str] | None = None,
) -> NebiusSettings:
    environ = _environment(environ)
    return NebiusSettings(
        nebius_api_key=_optional(environ.get("NEBIUS_API_KEY")),
        nebius_base_url=_validated_url(
            "NEBIUS_BASE_URL",
            environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"),
        ),
        nebius_model=_required(
            "NEBIUS_MODEL",
            environ.get("NEBIUS_MODEL", "Qwen/Qwen3-235B-A22B"),
        ),
        nebius_timeout_seconds=_positive_seconds(
            "NEBIUS_TIMEOUT_SECONDS",
            environ.get("NEBIUS_TIMEOUT_SECONDS", "60"),
        ),
    )


def load_nebius_api_key(environ: Mapping[str, str] | None = None) -> str | None:
    return _optional(_environment(environ).get("NEBIUS_API_KEY"))


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    environ = _environment(environ)
    funasr = load_funasr_settings(environ)
    nebius = load_nebius_settings(environ)
    return Settings(**funasr.__dict__, **nebius.__dict__)


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _required(name: str, value: str | None) -> str:
    cleaned = _optional(value)
    if cleaned is None:
        raise ValueError(f"{name} must not be empty.")
    return cleaned


def _positive_seconds(name: str, value: str | None) -> float:
    try:
        seconds = float(_required(name, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number greater than zero.") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"{name} must be a finite number greater than zero.")
    return seconds


def _validated_url(name: str, value: str | None) -> str:
    url = _required(name, value)
    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError as exc:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL.") from exc

    unsafe_authority = (
        parsed.username is not None
        or parsed.password is not None
        or any(character.isspace() for character in parsed.netloc)
    )
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or unsafe_authority:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL without credentials.")
    if parsed.query or parsed.fragment:
        raise ValueError(f"{name} must not contain a query string or fragment.")
    return url.rstrip("/")
