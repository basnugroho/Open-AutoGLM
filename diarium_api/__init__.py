"""
Diarium Automation API Package
==============================

Modular REST API for automating Diarium app on Android.
"""

from .config import Config, LoginScreenElements
from .models import (
    StatusCode, HealthStatus, 
    ResponseMetadata, StandardResponse,
    LoginRequest, MFARequest, CheckoutRequest
)

__version__ = "2.1.0"
__all__ = [
    "Config", "LoginScreenElements",
    "StatusCode", "HealthStatus",
    "ResponseMetadata", "StandardResponse", 
    "LoginRequest", "MFARequest", "CheckoutRequest"
]
