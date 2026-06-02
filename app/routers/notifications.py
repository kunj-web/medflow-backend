from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import get_db, CurrentUser
from app.repositories.notification_repo import NotificationRepository

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/me")
def get_my_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: CurrentUser = None,
):
    repo = NotificationRepository(db)
    notifications = repo.get_user_notifications(
        user_id=UUID(current_user["user_id"]),
        unread_only=unread_only,
        limit=limit,
    )
    unread_count = repo.get_unread_count(UUID(current_user["user_id"]))
    return {"data": notifications, "unread_count": unread_count}


@router.post("/me/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: CurrentUser = None,
):
    repo = NotificationRepository(db)
    count = repo.mark_all_read(UUID(current_user["user_id"]))
    db.commit()
    return {"marked_read": count}


@router.post("/device/register")
def register_device(
    fcm_token: str,
    device_info: str = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = None,
):
    """Frontend registers FCM token after user logs in."""
    repo = NotificationRepository(db)
    repo.upsert_device(
        user_id=UUID(current_user["user_id"]),
        fcm_token=fcm_token,
        device_info=device_info,
    )
    db.commit()
    return {"registered": True}