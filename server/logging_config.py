"""Markaziy log sozlamasi.

Loglar bir vaqtning o'zida konsolga va `logs/app.log` fayliga yoziladi
(fayl aylanma — RotatingFileHandler).
"""
import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import LOGS_DIR

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Windows konsoli sukut bo'yicha cp1252 — arab/kirill matni chop etilsa
    # UnicodeEncodeError beradi. Konsolni UTF-8 ga o'tkazamiz.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOGS_DIR / "app.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Uvicorn loglari ham shu handlerlardan foydalansin
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    _CONFIGURED = True
    logging.getLogger("euyhtr").info("Log tizimi sozlandi -> %s", LOGS_DIR / "app.log")
