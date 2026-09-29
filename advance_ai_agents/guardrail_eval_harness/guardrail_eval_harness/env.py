import os

_ENV_DEFAULTS = {
    "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
    "DEEPEVAL_DISABLE_DOTENV": "1",
    "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1",
    "DEEPEVAL_UPDATE_WARNING_OPT_IN": "0",
    "DEEPEVAL_FILE_SYSTEM": "READ_ONLY",
    "DEEPEVAL_NO_INSPECT_PROMPT": "1",
    "CONFIDENT_TRACING_ENABLED": "NO",
    "CONFIDENT_TRACE_FLUSH": "0",
    "CONFIDENT_TRACE_INTERNAL": "0",
    "CONFIDENT_OPEN_BROWSER": "0",
    "ENABLE_DEEPEVAL_CACHE": "0",
    "IGNORE_DEEPEVAL_ERRORS": "0",
    "SKIP_DEEPEVAL_MISSING_PARAMS": "0",
    "OPENAI_AGENTS_DISABLE_TRACING": "1",
}

_UNSET_KEYS = ("CONFIDENT_API_KEY",)


def apply_offline_environment() -> None:
    """Force documented offline settings for DeepEval and the Agents SDK.

    Must run before importing deepeval so telemetry backends are never
    configured. Values set here always win over ambient environment so a
    developer shell cannot silently re-enable cloud reporting.
    """
    for name, value in _ENV_DEFAULTS.items():
        os.environ[name] = value
    for name in _UNSET_KEYS:
        os.environ.pop(name, None)
