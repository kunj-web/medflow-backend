from datetime import time
from uuid import UUID

from faker import Faker

from app.models.doctor import Doctor, DoctorSchedule
from app.models.enums import DayOfWeek, Gender, UserRole, WorkType
from tests.factories.user_factory import UserFactory

fake = Faker("en_IN")

SPECIALIZATIONS = [
    "General Physician", "Cardiologist", "Dermatologist",
    "Pediatrician", "Orthopedic", "Neurologist",
]


class DoctorFactory:
    @staticmethod
    def create(db, hospital_id: UUID, user_id: UUID = None, **kwargs) -> Doctor:
        if not user_id:
            user = UserFactory.create(db, hospital_id, role=UserRole.DOCTOR)
            user_id = user.id

        doctor = Doctor(
            user_id=user_id,
            hospital_id=hospital_id,
            first_name=kwargs.get("first_name", fake.first_name()),
            last_name=kwargs.get("last_name", fake.last_name()),
            gender=kwargs.get("gender", Gender.MALE),
            phone=kwargs.get("phone", fake.numerify("##########")),
            email=kwargs.get("email", fake.unique.email()),
            registration_number=kwargs.get("registration_number", fake.unique.numerify("REG#####")),
            specialization=kwargs.get("specialization", fake.random_element(SPECIALIZATIONS)),
            qualification=kwargs.get("qualification", "MBBS"),
            consultation_fee=kwargs.get("consultation_fee", 500),
            experience_years=kwargs.get("experience_years", 5),
            is_active=kwargs.get("is_active", True),
            work_type=kwargs.get("work_type", WorkType.HOSPITAL),
        )
        db.add(doctor)
        db.flush()

        # Default Monday–Saturday schedule 09:00–17:00
        for day in [
            DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
            DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY,
        ]:
            db.add(DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                slot_duration_minutes=10,
            ))

        db.flush()
        return doctor
