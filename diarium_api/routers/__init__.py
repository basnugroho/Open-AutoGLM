"""
Routers Package
===============

Contains all FastAPI routers organized by functionality.
"""

from .device import router as device_router
from .auth import router as auth_router
from .actions import router as actions_router

__all__ = ["device_router", "auth_router", "actions_router"]
