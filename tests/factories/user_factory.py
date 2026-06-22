from uuid import UUID

from faker import Faker

from app.core.security import hash_password
from app.models.enums import AccountStatus, UserRole
from app.models.user import User

fake = Faker("en_IN")


class UserFactory:
    @staticmethod
    def create(
        db,
        hospital_id: UUID | None = None,
        role: UserRole = UserRole.PATIENT,
        **kwargs,
    ) -> User:
        # hospital_id remains accepted temporarily so older tests can migrate
        # incrementally; marketplace users are never hospital-scoped.
        user = User(
            email=kwargs.get("email", fake.unique.email()),
            phone=kwargs.get("phone", fake.phone_number()[:20]),
            hashed_password=hash_password(kwargs.get("password", "Test@1234")),
            role=role,
            status=kwargs.get("status", AccountStatus.ACTIVE),
            is_super_admin=kwargs.get("is_super_admin", False),
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user
