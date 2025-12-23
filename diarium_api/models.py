"""
Pydantic Models Module
======================

Contains all request/response models and enums.
"""

from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# ============================================================================
# ENUMS
# ============================================================================

class StatusCode(str, Enum):
    """Standard status codes for API responses"""
    SUCCESS = "success"
    ERROR = "error"
    LOGGED_IN = "logged_in"
    NOT_LOGGED_IN = "not_logged_in"
    MFA_REQUIRED = "mfa_required"
    LOGIN_FAILED = "login_failed"
    CHECKED_IN = "checked_in"
    CHECKOUT_SUCCESS = "checkout_success"
    CHECKOUT_NOT_AVAILABLE = "checkout_not_available"
    CHECKOUT_ALREADY_DONE = "checkout_already_done"
    DEVICE_NOT_FOUND = "device_not_found"


class HealthStatus(str, Enum):
    """Health status options for check-in/checkout"""
    SEHAT = "Sehat"
    KURANG_FIT = "Kurang Fit"
    SAKIT = "Sakit"


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ResponseMetadata(BaseModel):
    """Metadata included in all API responses"""
    hit_time: str
    result_time: str
    duration_seconds: float
    device_id: Optional[str] = None


class StandardResponse(BaseModel):
    """
    Standard response format for all endpoints.
    
    Example:
        {
            "success": true,
            "status": "logged_in",
            "message": "Login successful",
            "data": {"username": "John"},
            "metadata": {...}
        }
    """
    success: bool
    status: str
    message: str
    data: Optional[dict] = None
    metadata: ResponseMetadata


# ============================================================================
# REQUEST MODELS
# ============================================================================

class LoginRequest(BaseModel):
    """Request model for login endpoints"""
    nik: str = Field(..., description="NIK TelkomGroup")
    password: str = Field(..., description="Password SSO")


class MFARequest(BaseModel):
    """Request model for MFA submission"""
    mfa_code: str = Field(..., description="Kode MFA 6 digit")


class CheckoutRequest(BaseModel):
    """Request model for checkout"""
    health_status: HealthStatus = Field(default=HealthStatus.SEHAT, description="Status kesehatan")
    complete_activities: bool = Field(default=True, description="Selesaikan semua aktivitas In Progress")


class CheckInRequest(BaseModel):
    """Request model for check-in"""
    health_status: HealthStatus = Field(default=HealthStatus.SEHAT, description="Status kesehatan")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_response(
    success: bool,
    status: str,
    message: str,
    data: Optional[dict],
    hit_time: datetime,
    device_id: Optional[str] = None
) -> StandardResponse:
    """
    Create standardized API response with metadata.
    
    Args:
        success: Whether operation succeeded
        status: Status code (from StatusCode enum)
        message: Human-readable message
        data: Optional response data
        hit_time: Request timestamp
        device_id: Connected device ID
    
    Returns:
        StandardResponse object
    """
    result_time = datetime.now()
    duration = (result_time - hit_time).total_seconds()
    
    return StandardResponse(
        success=success,
        status=status,
        message=message,
        data=data,
        metadata=ResponseMetadata(
            hit_time=hit_time.isoformat(),
            result_time=result_time.isoformat(),
            duration_seconds=round(duration, 2),
            device_id=device_id
        )
    )
