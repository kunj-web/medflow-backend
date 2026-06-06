from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus, DayOfWeek, NotificationType
from app.repositories.appointment_repo import AppointmentRepository
from app.repositories.doctor_repo import DoctorRepository
from app.repositories.notification_repo import NotificationRepository
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule


class AppointmentService:
    def __init__(self, db: Session):
        self.db = db
        self.appointment_repo = AppointmentRepository(db)
        self.doctor_repo = DoctorRepository(db)
        self.notification_repo = NotificationRepository(db)

    def book(
        self,
        data: AppointmentCreate,
        hospital_id: UUID,
        patient_id: UUID,
        user_id: UUID,
    ) -> Appointment:
        # 1. Check doctor exists in this hospital
        doctor = self.doctor_repo.get_by_id(data.doctor_id)
        if not doctor or str(doctor.hospital_id) != str(hospital_id):
            raise ValueError("Doctor not found in this hospital")

        if not doctor.is_available:
            raise ValueError("Doctor is not available for bookings")

        # 2. Check doctor works on this day
        day_name = data.slot_time.strftime("%A").lower()
        day_of_week = DayOfWeek(day_name)
        schedule = self.doctor_repo.get_schedule_for_day(doctor.id, day_of_week)
        if not schedule:
            raise ValueError(f"Doctor does not work on {day_name.capitalize()}")

        # 3. Check slot is within working hours
        slot_time = data.slot_time.time()
        if slot_time < schedule.start_time or slot_time >= schedule.end_time:
            raise ValueError("Slot time is outside doctor's working hours")

        # 4. Check doctor is not on leave
        leave = self.doctor_repo.get_leave_for_date(doctor.id, data.slot_time.date())
        if leave and leave.is_approved:
            raise ValueError("Doctor is on approved leave on this date")

        # 5. Check for double booking
        existing = self.appointment_repo.get_slot_if_taken(doctor.id, data.slot_time)
        if existing:
            raise ValueError("This slot is already booked")

        # 6. Calculate token number for the day
        day_appointments = self.appointment_repo.get_doctor_appointments_for_date(
            doctor.id, data.slot_time.date()
        )
        token_number = len(day_appointments) + 1

        # 7. Create appointment
        end_time = data.slot_time + timedelta(minutes=doctor.avg_consultation_minutes)
        appointment = self.appointment_repo.create({
            "hospital_id": hospital_id,
            "patient_id": patient_id,
            "doctor_id": doctor.id,
            "slot_time": data.slot_time,
            "end_time": end_time,
            "type": data.type,
            "chief_complaint": data.chief_complaint,
            "token_number": token_number,
            "status": AppointmentStatus.SCHEDULED,
        })

        # 8. Create notification (same transaction)
        self.notification_repo.create({
            "user_id": user_id,
            "appointment_id": appointment.id,
            "type": NotificationType.APPOINTMENT_BOOKED,
            "title": "Appointment Confirmed",
            "message": f"Your appointment with Dr. {doctor.name} is scheduled for {data.slot_time.strftime('%d %b %Y at %I:%M %p')}",
            "data": {"appointment_id": str(appointment.id)},
        })

        self.db.commit()

        # Return with relations loaded
        return self.appointment_repo.get_by_id_with_relations(appointment.id)

    def cancel(
        self,
        appointment_id: UUID,
        hospital_id: UUID,
        reason: str,
        cancelled_by_user_id: UUID,
    ) -> Appointment:
        appointment = self.appointment_repo.get_by_id(appointment_id)

        if not appointment:
            raise ValueError("Appointment not found")

        if str(appointment.hospital_id) != str(hospital_id):
            raise ValueError("Appointment not found in this hospital")

        if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
            raise ValueError(f"Cannot cancel an appointment that is {appointment.status.value}")

        self.appointment_repo.update(appointment, {
            "status": AppointmentStatus.CANCELLED,
            "cancellation_reason": reason,
        })

        # Notify patient
        self.notification_repo.create({
            "user_id": cancelled_by_user_id,
            "appointment_id": appointment.id,
            "type": NotificationType.APPOINTMENT_CANCELLED,
            "title": "Appointment Cancelled",
            "message": f"Your appointment has been cancelled. Reason: {reason}",
            "data": {"appointment_id": str(appointment.id)},
        })

        self.db.commit()
        return self.appointment_repo.get_by_id_with_relations(appointment_id)

    def reschedule(
        self,
        appointment_id: UUID,
        hospital_id: UUID,
        data: AppointmentReschedule,
        user_id: UUID,
    ) -> Appointment:
        appointment = self.appointment_repo.get_by_id(appointment_id)

        if not appointment:
            raise ValueError("Appointment not found")

        if str(appointment.hospital_id) != str(hospital_id):
            raise ValueError("Appointment not found in this hospital")

        if appointment.status == AppointmentStatus.COMPLETED:
            raise ValueError("Cannot reschedule a completed appointment")

        # Check new slot availability
        existing = self.appointment_repo.get_slot_if_taken(
            appointment.doctor_id, data.new_slot_time
        )
        if existing and existing.id != appointment_id:
            raise ValueError("New slot is already booked")

        self.appointment_repo.update(appointment, {
            "slot_time": data.new_slot_time,
            "status": AppointmentStatus.SCHEDULED,
        })

        self.notification_repo.create({
            "user_id": user_id,
            "appointment_id": appointment.id,
            "type": NotificationType.APPOINTMENT_RESCHEDULED,
            "title": "Appointment Rescheduled",
            "message": f"Your appointment has been rescheduled to {data.new_slot_time.strftime('%d %b %Y at %I:%M %p')}",
            "data": {"appointment_id": str(appointment.id)},
        })

        self.db.commit()
        return self.appointment_repo.get_by_id_with_relations(appointment_id)
