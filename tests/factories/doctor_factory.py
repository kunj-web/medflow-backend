from faker import Faker
from uuid import UUID
from datetime import time
from app.models.doctor import Doctor, DoctorSchedule
from app.models.enums import DayOfWeek
from tests.factories.user_factory import UserFactory
from app.models.enums import UserRole

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
            name=kwargs.get("name", f"Dr. {fake.name()}"),
            specialization=kwargs.get("specialization", fake.random_element(SPECIALIZATIONS)),
            consultation_fee=kwargs.get("consultation_fee", 500),
            avg_consultation_minutes=kwargs.get("avg_consultation_minutes", 15),
            is_available=kwargs.get("is_available", True),
        )
        db.add(doctor)
        db.flush()

        # Add a default Monday-Saturday schedule
        for day in [
            DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY,
            DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY,
        ]:
            schedule = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                slot_duration_minutes=15,
            )
            db.add(schedule)

        db.flush()
        return doctor