from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.schemas.admin_user import AdminPasswordReset, AdminUserCreate, AdminUserResponse


class AdminUserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_admins(self) -> list[AdminUserResponse]:
        users = (
            self.db.query(User)
            .filter(
                User.role == UserRole.WEBSITE_ADMIN,
                User.deleted_at.is_(None),
            )
            .order_by(User.created_at.desc())
            .all()
        )
        return [self._to_response(user) for user in users]

    def create_admin(self, data: AdminUserCreate) -> AdminUserResponse:
        existing = (
            self.db.query(User)
            .filter(User.email == str(data.email), User.deleted_at.is_(None))
            .first()
        )
        if existing:
            raise ValueError("Email already registered")

        user = User(
            email=str(data.email),
            phone=data.phone,
            hashed_password=hash_password(data.password),
            role=UserRole.WEBSITE_ADMIN,
            status=AccountStatus.ACTIVE,
            is_active=True,
            is_verified=True,
            is_super_admin=False,
        )
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ValueError("Email already registered") from exc

        self.db.refresh(user)
        return self._to_response(user)

    def deactivate_admin(self, admin_id: UUID) -> AdminUserResponse:
        user = self._get_admin_or_404(admin_id)
        self._ensure_not_super_admin(user, "Super admin cannot be deactivated")
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return self._to_response(user)

    def reactivate_admin(self, admin_id: UUID) -> AdminUserResponse:
        user = self._get_admin_or_404(admin_id)
        self._ensure_not_super_admin(user, "Super admin cannot be reactivated here")
        user.is_active = True
        user.status = AccountStatus.ACTIVE
        self.db.commit()
        self.db.refresh(user)
        return self._to_response(user)

    def reset_admin_password(
        self, admin_id: UUID, data: AdminPasswordReset
    ) -> AdminUserResponse:
        user = self._get_admin_or_404(admin_id)
        self._ensure_not_super_admin(user, "Super admin password cannot be reset here")
        user.hashed_password = hash_password(data.password)
        self.db.commit()
        self.db.refresh(user)
        return self._to_response(user)

    def _get_admin_or_404(self, admin_id: UUID) -> User:
        user = (
            self.db.query(User)
            .filter(
                User.id == admin_id,
                User.role == UserRole.WEBSITE_ADMIN,
                User.deleted_at.is_(None),
            )
            .first()
        )
        if not user:
            raise LookupError("Admin not found")
        return user

    @staticmethod
    def _ensure_not_super_admin(user: User, message: str) -> None:
        if user.is_super_admin:
            raise ValueError(message)

    @staticmethod
    def _to_response(user: User) -> AdminUserResponse:
        return AdminUserResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            status=user.status.value,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_super_admin=user.is_super_admin,
            created_at=user.created_at,
        )
