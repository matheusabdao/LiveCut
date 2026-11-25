"""Logging setup shared by the GUI, the CLI and the provisioner."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import app_paths

LOGGER_NAME = "livecut"
_LOG_FILE = "livecut.log"
_configured = False


def setup_logging(level: int = logging.INFO, console: bool = True) -> logging.Logger:
    """Configure the ``livecut`` logger once and return it."""
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        logs = app_paths.logs_dir()
        logs.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            logs / _LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Logging must never take the app down.
        pass

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _configured = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_file_path():
    return app_paths.logs_dir() / _LOG_FILE
