"""Pytest configuration for the Monocle eval suite.

- Autoloads `.env` from the vendored temporal-tx-agent so OKAHU_API_KEY
  and OPENAI_API_KEY don't have to be re-exported by hand.
- The `monocle_trace_asserter` fixture comes from `monocle_test_tools`'
  pytest plugin, which is auto-registered when the package is installed.
"""

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional
    load_dotenv = None

_APP_ENV = Path(__file__).resolve().parent.parent / "temporal-tx-agent" / ".env"
if load_dotenv and _APP_ENV.exists():
    load_dotenv(_APP_ENV)
