"""Loguru logging initialization for shinebridge."""

import sys
from pathlib import Path
from loguru import logger


def setup_logging(level: str = "INFO", rotation: str = "10 MB", retention: str = "7 days") -> None:
    """Initialize Loguru with structured logging configuration.

    Removes default handler and adds new handlers for console and file output.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        rotation: File rotation size (e.g., "10 MB", "500 KB").
        retention: How long to keep rotated files (e.g., "7 days", "30d").
    """
    # Remove default handler
    logger.remove()

    # Console handler with colored output
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {name}:{function}:{line} - <cyan>{message}</cyan>",
        colorize=True,
    )

    # File handler with rotation and retention
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)

    logger.add(
        logs_dir / "shinebridge.log",
        level=level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
