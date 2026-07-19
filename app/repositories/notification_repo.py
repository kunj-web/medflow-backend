from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification, UserDevice
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: Session):
        super().__init__(Notification, db)

    def get_user_notifications(
        self, user_id: UUID, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        query = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.deleted_at.is_(None),
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)

        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    def get_unread_count(self, user_id: UUID) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.deleted_at.is_(None),
            )
            .count()
        )

    def mark_all_read(self, user_id: UUID) -> int:
        updated = (
            self.db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.deleted_at.is_(None),
            )
            .update({"is_read": True})
        )
        self.db.flush()
        return updated

    def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification | None:
        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.deleted_at.is_(None),
            )
            .first()
        )
        if not notification:
            return None
        notification.is_read = True
        self.db.flush()
        return notification

    def get_user_devices(self, user_id: UUID) -> list[UserDevice]:
        return (
            self.db.query(UserDevice)
            .filter(
                UserDevice.user_id == user_id,
                UserDevice.is_active == True,
            )
            .all()
        )

    def upsert_device(self, user_id: UUID, fcm_token: str, device_info: str = None):
        existing = (
            self.db.query(UserDevice)
            .filter(UserDevice.fcm_token == fcm_token)
            .first()
        )
        if existing:
            existing.user_id = user_id
            existing.is_active = True
            self.db.flush()
            return existing

        device = UserDevice(
            user_id=user_id,
            fcm_token=fcm_token,
            device_info=device_info,
        )
        self.db.add(device)
        self.db.flush()
        return device
