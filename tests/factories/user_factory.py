from faker import Faker
from uuid import UUID
from app.models.user import User
from app.models.enums import UserRole
from app.core.security import hash_password

fake = Faker("en_IN")


class UserFactory:
    @staticmethod
    def create(db, hospital_id: UUID, role: UserRole = UserRole.PATIENT, **kwargs) -> User:
        user = User(
            email=kwargs.get("email", fake.unique.email()),
            phone=kwargs.get("phone", fake.phone_number()[:20]),
            hashed_password=hash_password(kwargs.get("password", "Test@1234")),
            role=role,
            hospital_id=hospital_id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user