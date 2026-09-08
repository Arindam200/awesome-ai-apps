"""Put this project directory on sys.path so the tests can import ``debate``."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
