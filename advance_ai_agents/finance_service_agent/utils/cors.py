import os

DEV_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def get_allowed_origins() -> list[str]:
    """Resolve the CORS allow-list from CORS_ALLOWED_ORIGINS.

    Credentialed requests (allow_credentials=True) cannot safely be paired
    with a wildcard origin: a browser will refuse to honor "*" in that case,
    but a misconfigured server still accepts requests from any origin,
    enabling CSRF against authenticated users. "*" entries are therefore
    dropped instead of forwarded to CORSMiddleware.

    An unset or wildcard-only configuration fails closed (no cross-origin
    credentialed access) rather than defaulting to a permissive origin list,
    so a forgotten env var in production can't silently open this up. Set
    ENABLE_DEV_CORS_ORIGINS=1 to opt into the default frontend dev server
    origins for local development.
    """
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in raw.split(",")
        if origin.strip() and origin.strip() != "*"
    ]

    if origins:
        return origins

    if os.getenv("ENABLE_DEV_CORS_ORIGINS", "").strip().lower() in ("1", "true", "yes"):
        return DEV_ORIGINS

    return []
