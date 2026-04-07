"""
Centralized logging configuration for VEGA AI Assistant.

Provides a consistent logger with both console and file output.
Call get_logger(__name__) from any module to get a child logger.
"""

import logging
import sys
from pathlib import Path


_INITIALIZED = False
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root 'vega' logger with console and file handlers.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    # Ensure logs directory exists
    _LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger("vega")
    root_logger.setLevel(numeric_level)

    # Formatter
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(_LOG_DIR / "vega.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # File always captures everything
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)

    root_logger.info("Logging initialized at %s level.", level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger under the 'vega' namespace.

    Args:
        name: Usually __name__ of the calling module.

    Returns:
        A configured logging.Logger instance.
    """
    return logging.getLogger(f"vega.{name}")
