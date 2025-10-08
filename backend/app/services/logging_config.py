"""
Optimized logging configuration for faster startup
"""

import logging

from app.core.config import settings


def configure_logging():
    """Configure logging with minimal startup overhead"""
    # Only configure if not already configured
    if logging.getLogger().handlers:
        return

    level = logging.DEBUG if settings.debug else logging.INFO

    # Use a simpler format for better performance
    format_str = "%(levelname)s - %(name)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        force=True,  # Override any existing configuration
    )

    # Reduce verbosity of noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai.models").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
