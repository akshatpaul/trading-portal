"""
utils/logger.py — Centralised logging configuration

Uses Python's built-in logging module.
Log format: [LEVEL] TIMESTAMP module — message

TODO (Step 2): Initialise and export a configured logger.
"""

import logging
import sys
from datetime import datetime


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger. Call once at application startup."""
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="[%(levelname)s] %(asctime)s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module name.

    Usage:
        from utils.logger import get_logger
        log = get_logger(__name__)
        log.info("System started")
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="[%(levelname)s] %(asctime)s %(name)s — %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
