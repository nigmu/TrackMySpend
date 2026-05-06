"""Entry point for the auth package.

This file exposes the Gmail auth router so the main FastAPI app can
import and mount auth routes in one line.
"""

from .routes import router

__all__ = ["router"]