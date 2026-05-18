from __future__ import annotations

import logging

from database.db import LOGS_DIR, ensure_runtime_dirs

LOG_PATH = LOGS_DIR / "campflow.log"


def _logger() -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger("campflow")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def log_info(message: str) -> None:
    _logger().info(message)


def log_warning(message: str) -> None:
    _logger().warning(message)


def log_error(message: str, exc: Exception | None = None) -> None:
    if exc is None:
        _logger().error(message)
    else:
        _logger().exception("%s : %s", message, exc)
