"""backfill_default_doctor_schedules

Revision ID: a1c9e7d2f4b6
Revises: 7d4f9c2a1b8e
Create Date: 2026-07-05 00:00:00.000000

"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "a1c9e7d2f4b6"
down_revision: str | None = "7d4f9c2a1b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_DAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT d.id AS doctor_id, ds.day_of_week AS existing_day
            FROM doctors d
            JOIN users u ON u.id = d.user_id
            LEFT JOIN doctor_schedules ds
                ON ds.doctor_id = d.id
                AND ds.deleted_at IS NULL
            WHERE d.deleted_at IS NULL
                AND u.deleted_at IS NULL
                AND u.status = 'ACTIVE'
                AND d.is_active IS TRUE
            """
        )
    ).fetchall()

    existing_by_doctor = {}
    for doctor_id, existing_day in rows:
        existing_by_doctor.setdefault(doctor_id, set())
        if existing_day is not None:
            existing_by_doctor[doctor_id].add(existing_day)

    for doctor_id, existing_days in existing_by_doctor.items():
        for day in DEFAULT_DAYS:
            if day in existing_days:
                continue
            bind.execute(
                sa.text(
                    """
                    INSERT INTO doctor_schedules (
                        id,
                        doctor_id,
                        day_of_week,
                        start_time,
                        end_time,
                        slot_duration_minutes,
                        is_active
                    )
                    VALUES (
                        :id,
                        :doctor_id,
                        :day_of_week,
                        '09:00',
                        '17:00',
                        10,
                        TRUE
                    )
                    """
                ),
                {
                    "id": uuid4(),
                    "doctor_id": doctor_id,
                    "day_of_week": day,
                },
            )


def downgrade() -> None:
    pass
