from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

try:
    import resend
except ImportError:  # pragma: no cover - optional notification dependency
    resend = None

try:
    from firebase_admin import credentials, messaging
    from firebase_admin import get_app as firebase_get_app
    from firebase_admin import initialize_app as firebase_initialize_app
except ImportError:  # pragma: no cover - optional notification dependency
    credentials = None
    messaging = None
    firebase_get_app = None
    firebase_initialize_app = None
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import NotificationType, UserRole
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repo import NotificationRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Firebase initialisation — runs once at import time
# ---------------------------------------------------------------------------

def _init_firebase() -> None:
    """Initialize Firebase only if credentials file exists."""
    if credentials is None or firebase_get_app is None or firebase_initialize_app is None:
        logger.warning("firebase-admin is not installed. Push notifications disabled.")
        return

    if not os.path.exists(settings.firebase_credentials_path):
        logger.warning(
            "Firebase credentials not found (%s). Push notifications disabled.",
            settings.firebase_credentials_path,
        )
        return

    try:
        firebase_get_app()
    except ValueError:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        firebase_initialize_app(cred)

# _init_firebase()


# ---------------------------------------------------------------------------
# NotificationService
# ---------------------------------------------------------------------------

class NotificationService:
    """
    Handles all outbound notifications for MedFlow.

    Channels:
        - FCM push  (Firebase Cloud Messaging)
        - Email     (Resend)

    Public helpers called from AppointmentService:
        notify_appointment_booked(appointment, db)
        notify_appointment_cancelled(appointment, db)
        notify_appointment_reminder(appointment, db)   # call for 24h AND 1h
    """

    def __init__(self) -> None:
        if resend is not None:
            resend.api_key = settings.resend_api_key

    # -----------------------------------------------------------------------
    # Core — Push
    # -----------------------------------------------------------------------

    def send_push(
        self,
        user_id: UUID | str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        db: Session | None = None,
        hospital_id: str | None = None,
    ) -> None:
        """
        Send an FCM push notification to every registered device for user_id.

        - Fetches device tokens from UserDevice via NotificationRepository.
        - Persists the notification record to the DB if a session is provided.
        - Silently skips if the user has no registered devices.
        - Logs (never raises) on FCM errors so a push failure never breaks
          the calling service transaction.
        """
        if db is None:
            logger.warning("send_push called without db session — skipping DB write")
            return

        user_uuid = _coerce_uuid(user_id)
        self._persist_notification(
            db=db,
            user_id=user_uuid,
            notification_type=_notification_type_from_data(data),
            title=title,
            body=body,
            data=data,
        )

        notification_repo = NotificationRepository(db)
        devices = notification_repo.get_user_devices(user_uuid)

        if not devices:
            logger.debug("No registered devices for user %s — skipping push", user_id)
            return

        tokens = [d.fcm_token for d in devices if d.fcm_token]
        if not tokens:
            return

        if messaging is None:
            logger.warning("firebase-admin is not installed. Push notification skipped.")
            return

        # Send via FCM multicast
        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default")
                )
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)
            logger.info(
                "FCM multicast to user %s — success: %d, failure: %d",
                user_id,
                response.success_count,
                response.failure_count,
            )
            # Log individual failures for debugging
            for idx, result in enumerate(response.responses):
                if not result.success:
                    logger.warning(
                        "FCM token %s failed: %s",
                        tokens[idx],
                        result.exception,
                    )
        except Exception as exc:
            logger.error("FCM send_each_for_multicast failed for user %s: %s", user_id, exc)

    # -----------------------------------------------------------------------
    # Core — Email
    # -----------------------------------------------------------------------

    def send_email(self, to: str, subject: str, html: str) -> None:
        """
        Send a transactional email via Resend.

        Logs (never raises) on failure so an email error never breaks
        the calling service transaction.
        """
        try:
            if resend is None:
                logger.warning("resend is not installed. Email notification skipped.")
                return

            resend.Emails.send({
                "from": settings.email_from,
                "to": to,
                "subject": subject,
                "html": html,
            })
            logger.info("Email sent to %s — subject: %s", to, subject)
        except Exception as exc:
            logger.error("Resend email failed to %s: %s", to, exc)

    # -----------------------------------------------------------------------
    # Appointment helpers
    # -----------------------------------------------------------------------

    def notify_appointment_booked(self, appointment: Appointment, db: Session) -> None:
        """
        Notify patient and doctor when an appointment is successfully booked.
        Called from AppointmentService.book() after commit.
        """
        patient = appointment.patient
        doctor = appointment.doctor
        slot = _fmt_slot(appointment.slot_time)

        # --- Patient push ---
        self.send_push(
            user_id=str(patient.user_id),
            title="Appointment Confirmed",
            body=f"Your appointment with Dr. {doctor.last_name} is confirmed for {slot}.",
            data={
                "type": "appointment_booked",
                "category": "appointments",
                "appointment_id": str(appointment.id),
                "doctor_name": f"Dr. {doctor.first_name} {doctor.last_name}",
                "slot_time": appointment.slot_time.isoformat(),
                "token_number": str(appointment.token_number or ""),
                "href": f"/appointments#{appointment.id}",
            },
            db=db,
            hospital_id=(
                str(appointment.hospital_id) if appointment.hospital_id else None
            ),
        )

        # --- Patient email ---
        if patient.email:
            self.send_email(
                to=patient.email,
                subject="Your MedFlow Appointment is Confirmed",
                html=_render_booked_email(
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
                    slot=slot,
                    token=appointment.token_number,
                ),
            )

        # --- Doctor push ---
        self.send_push(
            user_id=str(doctor.user_id),
            title="New Appointment",
            body=f"New appointment booked: {patient.first_name} {patient.last_name} at {slot}.",
            data={
                "type": "appointment_booked",
                "category": "appointments",
                "appointment_id": str(appointment.id),
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "slot_time": appointment.slot_time.isoformat(),
                "token_number": str(appointment.token_number or ""),
                "href": f"/appointments#{appointment.id}",
            },
            db=db,
            hospital_id=(
                str(appointment.hospital_id) if appointment.hospital_id else None
            ),
        )
        db.commit()

    def notify_appointment_cancelled(
        self,
        appointment: Appointment,
        db: Session,
        cancellation_source: str | None = None,
    ) -> None:
        """
        Notify patient and doctor when an appointment is cancelled.
        Called from AppointmentService.cancel() after commit.
        """
        patient = appointment.patient
        doctor = appointment.doctor
        slot = _fmt_slot(appointment.slot_time)
        is_doctor_closure = cancellation_source == "doctor_date_closure"

        patient_title = (
            "Doctor closed availability for this date"
            if is_doctor_closure
            else "Appointment Cancelled"
        )
        patient_body = (
            f"Dr. {doctor.last_name} closed availability for {slot}. "
            "Your appointment has been cancelled."
            if is_doctor_closure
            else f"Your appointment with Dr. {doctor.last_name} on {slot} has been cancelled."
        )
        doctor_title = (
            "Date availability closed"
            if is_doctor_closure
            else "Appointment Cancelled"
        )
        doctor_body = (
            f"You closed availability for {slot}. Appointment with "
            f"{patient.first_name} {patient.last_name} was cancelled."
            if is_doctor_closure
            else f"Appointment with {patient.first_name} {patient.last_name} at {slot} was cancelled."
        )

        # --- Patient push ---
        self.send_push(
            user_id=str(patient.user_id),
            title=patient_title,
            body=patient_body,
            data={
                "type": "appointment_cancelled",
                "category": "appointments",
                "event": cancellation_source or "appointment_cancelled",
                "appointment_id": str(appointment.id),
                "doctor_name": f"Dr. {doctor.first_name} {doctor.last_name}",
                "slot_time": appointment.slot_time.isoformat(),
                "reason": appointment.cancellation_reason or "",
                "href": f"/appointments#{appointment.id}",
            },
            db=db,
            hospital_id=(
                str(appointment.hospital_id) if appointment.hospital_id else None
            ),
        )

        # --- Patient email ---
        if patient.email:
            self.send_email(
                to=patient.email,
                subject="Your MedFlow Appointment Has Been Cancelled",
                html=_render_cancelled_email(
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
                    slot=slot,
                ),
            )

        # --- Doctor push ---
        self.send_push(
            user_id=str(doctor.user_id),
            title=doctor_title,
            body=doctor_body,
            data={
                "type": "appointment_cancelled",
                "category": "appointments",
                "event": cancellation_source or "appointment_cancelled",
                "appointment_id": str(appointment.id),
                "patient_name": f"{patient.first_name} {patient.last_name}",
                "slot_time": appointment.slot_time.isoformat(),
                "reason": appointment.cancellation_reason or "",
                "href": f"/appointments#{appointment.id}",
            },
            db=db,
            hospital_id=(
                str(appointment.hospital_id) if appointment.hospital_id else None
            ),
        )
        db.commit()

    def notify_pending_doctor_review(
        self,
        doctor_name: str,
        doctor_email: str,
        db: Session,
    ) -> None:
        admins = (
            db.query(User)
            .filter(
                User.role == UserRole.WEBSITE_ADMIN,
                User.is_active == True,
                User.deleted_at.is_(None),
            )
            .all()
        )

        for admin in admins:
            self.send_push(
                user_id=admin.id,
                title="Doctor review pending",
                body=f"{doctor_name} signed up as a doctor and needs review.",
                data={
                    "type": "general",
                    "category": "admin",
                    "event": "pending_doctor_review",
                    "doctor_email": doctor_email,
                    "href": "/admin-review",
                },
                db=db,
            )
        db.commit()

    def notify_appointment_reminder(self, appointment: Appointment, db: Session, hours_before: int) -> None:
        """
        Send a reminder to the patient ahead of their appointment.

        Call this method twice from your scheduler:
            notify_appointment_reminder(appointment, db, hours_before=24)
            notify_appointment_reminder(appointment, db, hours_before=1)

        hours_before must be 24 or 1.
        """
        assert hours_before in (1, 24), "hours_before must be 1 or 24"

        patient = appointment.patient
        doctor = appointment.doctor
        slot = _fmt_slot(appointment.slot_time)

        if hours_before == 24:
            push_body = f"Reminder: appointment with Dr. {doctor.last_name} tomorrow at {slot}."
            email_subject = "Reminder: Your Appointment Tomorrow"
        else:
            push_body = f"Reminder: appointment with Dr. {doctor.last_name} in 1 hour at {slot}."
            email_subject = "Reminder: Your Appointment in 1 Hour"

        # --- Patient push ---
        self.send_push(
            user_id=str(patient.user_id),
            title="Appointment Reminder",
            body=push_body,
            data={
                "type": "appointment_reminder",
                "category": "appointments",
                "appointment_id": str(appointment.id),
                "hours_before": str(hours_before),
                "slot_time": appointment.slot_time.isoformat(),
                "href": f"/appointments#{appointment.id}",
            },
            db=db,
            hospital_id=(
                str(appointment.hospital_id) if appointment.hospital_id else None
            ),
        )

        # --- Patient email ---
        if patient.email:
            self.send_email(
                to=patient.email,
                subject=email_subject,
                html=_render_reminder_email(
                    patient_name=f"{patient.first_name} {patient.last_name}",
                    doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
                    slot=slot,
                    hours_before=hours_before,
                ),
            )
        db.commit()

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _persist_notification(
        self,
        db: Session,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        body: str,
        data: dict[str, Any] | None,
    ) -> None:
        """Write a Notification row. Errors are logged, never raised."""
        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                message=body,
                data=data or {},
            )
            db.add(notification)
            db.flush()  # not commit — caller owns the transaction
        except Exception as exc:
            logger.error("Failed to persist notification for user %s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

notification_service = NotificationService()


# ---------------------------------------------------------------------------
# Scheduling helpers (called by your task scheduler / cron)
# ---------------------------------------------------------------------------

def get_reminder_appointments_for_offset(
    db: Session,
    hours_before: int,
) -> list[Appointment]:
    """
    Return scheduled appointments whose slot_time falls within a 5-minute
    window starting exactly `hours_before` hours from now (naive UTC).

    Designed to be called by a cron job every 5 minutes:
        get_reminder_appointments_for_offset(db, 24)
        get_reminder_appointments_for_offset(db, 1)
    """
    from app.models.enums import AppointmentStatus

    now = datetime.utcnow()
    window_start = now + timedelta(hours=hours_before)
    window_end = window_start + timedelta(minutes=5)

    return (
        db.query(Appointment)
        .filter(
            Appointment.slot_time >= window_start,
            Appointment.slot_time < window_end,
            Appointment.status == AppointmentStatus.SCHEDULED,
            Appointment.deleted_at.is_(None),
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Email templates (minimal inline HTML — swap for Jinja2 later if needed)
# ---------------------------------------------------------------------------

def _fmt_slot(slot_time: datetime) -> str:
    """Format a naive UTC slot_time for display. e.g. 'Mon, 9 Jun 2025 at 10:30 AM'"""
    return f"{slot_time.strftime('%a,')} {slot_time.day} {slot_time.strftime('%b %Y at %I:%M %p')}"


def _coerce_uuid(value: UUID | str) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(value)


def _notification_type_from_data(data: dict[str, str] | None) -> NotificationType:
    if data and data.get("type"):
        try:
            return NotificationType(data["type"])
        except ValueError:
            logger.warning("Unknown notification type %s; using general", data["type"])
    return NotificationType.GENERAL


def _render_booked_email(
    patient_name: str,
    doctor_name: str,
    slot: str,
    token: int | None,
) -> str:
    token_line = f"<p>Your token number is <strong>#{token}</strong>.</p>" if token else ""
    return f"""
    <h2>Appointment Confirmed</h2>
    <p>Hi {patient_name},</p>
    <p>Your appointment with <strong>{doctor_name}</strong> has been confirmed.</p>
    <p><strong>Date & Time:</strong> {slot}</p>
    {token_line}
    <p>Please arrive 10 minutes early.</p>
    <p>— MedFlow</p>
    """


def _render_cancelled_email(
    patient_name: str,
    doctor_name: str,
    slot: str,
) -> str:
    return f"""
    <h2>Appointment Cancelled</h2>
    <p>Hi {patient_name},</p>
    <p>Your appointment with <strong>{doctor_name}</strong> scheduled for <strong>{slot}</strong>
    has been cancelled.</p>
    <p>Please book a new appointment at your convenience.</p>
    <p>— MedFlow</p>
    """


def _render_reminder_email(
    patient_name: str,
    doctor_name: str,
    slot: str,
    hours_before: int,
) -> str:
    when = "tomorrow" if hours_before == 24 else "in 1 hour"
    return f"""
    <h2>Appointment Reminder</h2>
    <p>Hi {patient_name},</p>
    <p>This is a reminder that you have an appointment with <strong>{doctor_name}</strong>
    <strong>{when}</strong> at <strong>{slot}</strong>.</p>
    <p>Please arrive 10 minutes early.</p>
    <p>— MedFlow</p>
    """
