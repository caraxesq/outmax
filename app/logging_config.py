from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    info_handler = RotatingFileHandler(settings.log_dir / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(settings.log_dir / "error.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(info_handler)
    root.addHandler(error_handler)
    root.addHandler(console_handler)
