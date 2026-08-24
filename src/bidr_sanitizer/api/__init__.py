"""Versioned HTTP application adapter for BIDR Sanitizer."""

from bidr_sanitizer.api.app import create_app
from bidr_sanitizer.api.config import WebAPISettings

__all__ = [
    "WebAPISettings",
    "create_app",
]
