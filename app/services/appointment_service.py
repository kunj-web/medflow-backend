from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, DayOfWeek, UserRole
from app.models.patient import Patient
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.doctor_repo import DoctorRepository
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule
from app.services.notification_service import notification_service


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
        self.doctor_repo = DoctorRepository(db)

    def book(self, data: AppointmentCreate, patient_user_id: UUID) -> Appointment:
        self._ensure_advance_booking(data.slot_time.date())

        patient = (
            self.db.query(Patient)
            .filter(
                Patient.user_id == patient_user_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )
        if not patient:
            raise LookupError("Patient profile not found")

        doctor = self.doctor_repo.get_public_by_id(data.doctor_id)
        if not doctor:
            raise LookupError("Doctor not found or unavailable")

        day_name = data.slot_time.strftime("%A").lower()
        schedule = self.doctor_repo.get_schedule_for_day(
            doctor.id, DayOfWeek(day_name)
        )
        if not schedule:
            raise ValueError(f"Doctor does not work on {day_name.capitalize()}")

        slot_time = data.slot_time.time()
        if slot_time < schedule.start_time or slot_time >= schedule.end_time:
            raise ValueError("Slot time is outside doctor's working hours")

        leave = self.doctor_repo.get_leave_for_date(doctor.id, data.slot_time.date())
        if leave and leave.is_approved:
            raise ValueError("Doctor is on approved leave on this date")

        if self.appointment_repo.get_slot_if_taken(doctor.id, data.slot_time):
            raise ValueError("This slot is already booked")

        day_appointments = self.appointment_repo.get_doctor_appointments_for_date(
            doctor.id, data.slot_time.date()
        )
        appointment = self.appointment_repo.create(
            {
                # Snapshot only; nullable for clinic doctors.
                "hospital_id": doctor.hospital_id,
                "patient_id": patient.id,
                "doctor_id": doctor.id,
                "slot_time": data.slot_time,
                "end_time": data.slot_time
                + timedelta(minutes=schedule.slot_duration_minutes),
                "type": data.type,
                "chief_complaint": data.chief_complaint,
                "token_number": len(day_appointments) + 1,
                "status": AppointmentStatus.SCHEDULED,
            }
        )
        self.db.commit()

        appointment = self.appointment_repo.get_by_id_with_relations(appointment.id)
        notification_service.notify_appointment_booked(appointment, self.db)
        return appointment

    def cancel(
        self,
        appointment_id: UUID,
        reason: str,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Appointment:
        appointment = self._get_mutable_by_actor(
            appointment_id, actor_user_id, actor_role
        )
        if appointment.status in (
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
        ):
            raise ValueError(
                f"Cannot cancel an appointment that is {appointment.status.value}"
            )

        self.appointment_repo.update(
            appointment,
            {
                "status": AppointmentStatus.CANCELLED,
                "cancellation_reason": reason,
            },
        )
        self.db.commit()
        appointment = self.appointment_repo.get_by_id_with_relations(appointment_id)
        notification_service.notify_appointment_cancelled(appointment, self.db)
        return appointment

    def reschedule(
        self,
        appointment_id: UUID,
        data: AppointmentReschedule,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Appointment:
        appointment = self._get_mutable_by_actor(
            appointment_id, actor_user_id, actor_role
        )
        if appointment.status == AppointmentStatus.COMPLETED:
            raise ValueError("Cannot reschedule a completed appointment")

        self._ensure_advance_booking(data.new_slot_time.date())

        schedule = self.doctor_repo.get_schedule_for_day(
            appointment.doctor_id,
            DayOfWeek(data.new_slot_time.strftime("%A").lower()),
        )
        if not schedule:
            raise ValueError("Doctor does not work on the selected day")
        new_time = data.new_slot_time.time()
        if new_time < schedule.start_time or new_time >= schedule.end_time:
            raise ValueError("Slot time is outside doctor's working hours")

        existing = self.appointment_repo.get_slot_if_taken(
            appointment.doctor_id, data.new_slot_time
        )
        if existing and existing.id != appointment_id:
            raise ValueError("New slot is already booked")

        self.appointment_repo.update(
            appointment,
            {
                "slot_time": data.new_slot_time,
                "end_time": data.new_slot_time
                + timedelta(minutes=schedule.slot_duration_minutes),
                "status": AppointmentStatus.SCHEDULED,
            },
        )
        self.db.commit()
        return self.appointment_repo.get_by_id_with_relations(appointment_id)

    def _get_mutable_by_actor(
        self, appointment_id: UUID, actor_user_id: UUID, actor_role: str
    ) -> Appointment:
        appointment = self.appointment_repo.get_by_id(appointment_id)
        if not appointment:
            raise LookupError("Appointment not found")

        if actor_role == UserRole.WEBSITE_ADMIN.value:
            return appointment
        if actor_role != UserRole.PATIENT.value:
            raise PermissionError("Access denied")

        owns_appointment = (
            self.db.query(Patient.id)
            .filter(
                Patient.id == appointment.patient_id,
                Patient.user_id == actor_user_id,
                Patient.deleted_at.is_(None),
            )
            .first()
        )
        if not owns_appointment:
            raise PermissionError("Access denied")
        return appointment

    @staticmethod
    def _ensure_advance_booking(slot_date: date) -> None:
        if slot_date <= date.today():
            raise ValueError("Appointments must be booked at least one day in advance")
