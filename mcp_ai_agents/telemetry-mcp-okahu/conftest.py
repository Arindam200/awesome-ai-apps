"""
Pytest configuration - Suppress local output

All debugging MUST happen via Okahu MCP traces.
No local logs, warnings, or debug info available.
"""

import logging
import warnings

# Suppress all warnings
warnings.filterwarnings("ignore")

# Disable all logging output
logging.disable(logging.CRITICAL)


def pytest_configure(config):
    """Suppress pytest warnings and noise."""
    config.addinivalue_line("filterwarnings", "ignore::DeprecationWarning")
    config.addinivalue_line("filterwarnings", "ignore::UserWarning")
    config.addinivalue_line("filterwarnings", "ignore::PendingDeprecationWarning")
    # Suppress tracebacks - force agent to use Okahu MCP traces
    config.option.tbstyle = "no"
