from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.enums import NotificationType
from app.schemas.validators.common import validate_non_empty_string


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

class NotificationResponse(BaseModel):
    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    body: str
    data: Optional[dict[str, Any]]     # arbitrary JSON payload (e.g. appointment_id)
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Device registration (FCM token upsert)
# ---------------------------------------------------------------------------

class DeviceRegisterRequest(BaseModel):
    fcm_token: str
    device_id: str                      # client-generated stable device identifier
    platform: str                       # "android" | "ios" | "web"

    @field_validator("fcm_token", "device_id")
    @classmethod
    def non_empty(cls, v: str) -> str:
        return validate_non_empty_string(v)

    @field_validator("platform")
    @classmethod
    def valid_platform(cls, v: str) -> str:
        allowed = {"android", "ios", "web"}
        if v.lower() not in allowed:
            raise ValueError(f"platform must be one of {allowed}")
        return v.lower()


class DeviceRegisterResponse(BaseModel):
    device_id: str
    platform: str
    registered: bool                    # True = new, False = updated existing token


# ---------------------------------------------------------------------------
# Unread count (lightweight poll endpoint)
# ---------------------------------------------------------------------------

class UnreadCountResponse(BaseModel):
    unread_count: int