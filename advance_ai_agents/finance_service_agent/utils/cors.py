import os

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def get_allowed_origins(value: str | None = None) -> list[str]:
    """Return explicit origins that may make credentialed CORS requests."""
    configured_origins = os.getenv("CORS_ALLOWED_ORIGINS") if value is None else value
    origins = [
        origin.strip()
        for origin in (configured_origins or "").split(",")
        if origin.strip()
    ]

    if "*" in origins:
        raise ValueError(
            "CORS_ALLOWED_ORIGINS cannot contain '*' when credentials are enabled"
        )

    return origins or list(DEFAULT_ALLOWED_ORIGINS)
