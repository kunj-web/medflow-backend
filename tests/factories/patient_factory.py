from uuid import UUID

from faker import Faker

from app.models.enums import BloodGroup, Gender, UserRole
from app.models.patient import Patient
from tests.factories.user_factory import UserFactory

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
            first_name=kwargs.get("first_name", fake.first_name()),
            last_name=kwargs.get("last_name", fake.last_name()),
            phone=kwargs.get("phone", fake.numerify("##########")),
            email=kwargs.get("email", fake.unique.email()),
            gender=kwargs.get("gender", Gender.MALE),
            blood_group=kwargs.get("blood_group", BloodGroup.O_POS),
            existing_conditions=kwargs.get("existing_conditions", None),
        )
        db.add(patient)
        db.flush()
        return patient
