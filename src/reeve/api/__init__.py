"""
HTTP REST API

FastAPI server for external systems to trigger pulses.
"""

from .server import create_app

__all__ = ["create_app"]
