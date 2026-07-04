import os
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.enums import AccountStatus, UserRole
from app.models.user import User
from app.schemas.validators.password import validate_password_strength


DEFAULT_DEV_EMAIL = "admin@medflow.dev"
LEGACY_DEFAULT_DEV_EMAIL = "admin@medflow.local"
DEFAULT_DEV_PASSWORD = "Admin@12345"


def get_seed_values() -> tuple[str, str, str | None, bool]:
    email = (
        os.getenv("SUPER_ADMIN_EMAIL")
        or os.getenv("ADMIN_EMAIL")
        or DEFAULT_DEV_EMAIL
    )
    password = os.getenv("SUPER_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    used_default_password = False

    if not password:
        if settings.app_env.lower() == "production":
            raise RuntimeError(
                "Set SUPER_ADMIN_PASSWORD before seeding a production admin."
            )
        password = DEFAULT_DEV_PASSWORD
        used_default_password = True

    validate_password_strength(password)
    phone = os.getenv("SUPER_ADMIN_PHONE") or os.getenv("ADMIN_PHONE")
    return email.strip().lower(), password, phone, used_default_password


def main() -> None:
    email, password, phone, used_default_password = get_seed_values()
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == email).first()
        if not user and email == DEFAULT_DEV_EMAIL:
            user = db.query(User).filter(User.email == LEGACY_DEFAULT_DEV_EMAIL).first()

        if user:
            user.email = email
            user.hashed_password = hash_password(password)
            user.phone = phone or user.phone
            user.role = UserRole.WEBSITE_ADMIN
            user.status = AccountStatus.ACTIVE
            user.is_super_admin = True
            user.is_active = True
            user.is_verified = True
            user.deleted_at = None
            action = "Updated"
        else:
            user = User(
                email=email,
                phone=phone,
                hashed_password=hash_password(password),
                role=UserRole.WEBSITE_ADMIN,
                status=AccountStatus.ACTIVE,
                is_super_admin=True,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            action = "Created"

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError("Could not seed super admin due to a database conflict.") from exc
    finally:
        db.close()

    print(f"{action} super admin: {email}")
    if used_default_password:
        print(f"Development password: {DEFAULT_DEV_PASSWORD}")


if __name__ == "__main__":
    main()
