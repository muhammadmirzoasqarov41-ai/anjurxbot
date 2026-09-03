"""
Professional logging configuration for the bot.

Sets up a consistent logger used across all modules.
Sensitive values (tokens, keys) must never be passed to logger calls.
"""

import logging
import os
import sys
from typing import Optional


def setup_logger(
    name: str = "anjurxbot",
    level: int = logging.INFO,
    fmt: Optional[str] = None,
) -> logging.Logger:
    """
    Create and configure a logger instance.

    Args:
        name:  Logger name (visible in log output).
        level: Minimum log level (default INFO).
        fmt:   Optional custom format string.

    Returns:
        Configured :class:`logging.Logger`.
    """
    if fmt is None:
        fmt = "[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s"

    formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if setup_logger is called more than once
    if not logger.handlers:
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False

    return logger


# Module-level default logger — import this in other modules:
#   from app.utils.logger import logger
_configured_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logger: logging.Logger = setup_logger(level=_configured_level)
