from faker import Faker
from uuid import UUID
from app.models.patient import Patient
from app.models.enums import Gender, BloodGroup
from tests.factories.user_factory import UserFactory
from app.models.enums import UserRole

fake = Faker("en_IN")


class PatientFactory:
    @staticmethod
    def create(db, hospital_id: UUID, user_id: UUID = None, **kwargs) -> Patient:
        if not user_id:
            user = UserFactory.create(db, hospital_id, role=UserRole.PATIENT)
            user_id = user.id

        patient = Patient(
            user_id=user_id,
            hospital_id=hospital_id,
            name=kwargs.get("name", fake.name()),
            gender=kwargs.get("gender", Gender.MALE),
            blood_group=kwargs.get("blood_group", BloodGroup.O_POS),
            address=kwargs.get("address", fake.address()),
        )
        db.add(patient)
        db.flush()
        return patient