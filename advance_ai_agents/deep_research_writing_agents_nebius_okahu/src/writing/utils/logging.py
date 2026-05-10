"""Unified logging configuration."""

import logging

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with the standard format."""

    logging.basicConfig(level=level, format=LOG_FORMAT)
