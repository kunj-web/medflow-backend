"""sync_marketplace_schema

Revision ID: 7d4f9c2a1b8e
Revises: 33eafb6280f4
Create Date: 2026-06-26 22:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "7d4f9c2a1b8e"
down_revision: str | None = "33eafb6280f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


account_status_enum = postgresql.ENUM(
    "PENDING",
    "ACTIVE",
    "REJECTED",
    name="accountstatus",
)
work_type_enum = postgresql.ENUM(
    "HOSPITAL",
    "CLINIC",
    name="worktype",
)


def upgrade() -> None:
    bind = op.get_bind()
    account_status_enum.create(bind, checkfirst=True)
    work_type_enum.create(bind, checkfirst=True)

    # Existing databases may still have the old ADMIN enum value only.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'WEBSITE_ADMIN'")
    op.execute("UPDATE users SET role = 'WEBSITE_ADMIN' WHERE role = 'ADMIN'")

    op.add_column("users", sa.Column("status", account_status_enum, nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute("UPDATE users SET status = 'ACTIVE' WHERE status IS NULL")
    op.alter_column("users", "status", nullable=False)
    op.alter_column("users", "is_super_admin", server_default=None)

    op.drop_constraint("users_hospital_id_fkey", "users", type_="foreignkey")
    op.drop_index("ix_user_email_hospital", table_name="users")
    op.drop_index("ix_user_phone_hospital", table_name="users")
    op.drop_index("ix_users_hospital_id", table_name="users")
    op.drop_column("users", "hospital_id")
    op.create_index("ix_user_email", "users", ["email"], unique=True)
    op.create_index("ix_user_phone", "users", ["phone"])
    op.create_index("ix_user_status", "users", ["status"])

    op.drop_constraint("patients_hospital_id_fkey", "patients", type_="foreignkey")
    op.drop_index("ix_patient_hospital", table_name="patients")
    op.drop_index("ix_patients_hospital_id", table_name="patients")
    op.drop_column("patients", "hospital_id")

    op.add_column("hospitals", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("hospitals", sa.Column("state", sa.String(length=100), nullable=True))

    op.add_column(
        "doctors",
        sa.Column(
            "work_type",
            work_type_enum,
            nullable=False,
            server_default="HOSPITAL",
        ),
    )
    op.add_column("doctors", sa.Column("clinic_name", sa.String(length=255), nullable=True))
    op.add_column("doctors", sa.Column("clinic_city", sa.String(length=100), nullable=True))
    op.add_column("doctors", sa.Column("clinic_address", sa.Text(), nullable=True))
    op.add_column(
        "doctors",
        sa.Column("pending_hospital_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "doctors",
        sa.Column("pending_hospital_city", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "doctors",
        sa.Column("pending_hospital_state", sa.String(length=100), nullable=True),
    )
    op.alter_column("doctors", "work_type", server_default=None)
    op.alter_column("doctors", "hospital_id", nullable=True)
    op.drop_constraint("doctors_hospital_id_fkey", "doctors", type_="foreignkey")
    op.create_foreign_key(
        "doctors_hospital_id_fkey",
        "doctors",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("ix_doctor_hospital_specialization", table_name="doctors")
    op.create_index("ix_doctor_hospital", "doctors", ["hospital_id"])
    op.create_index("ix_doctor_specialization", "doctors", ["specialization"])

    op.alter_column("appointments", "hospital_id", nullable=True)
    op.drop_constraint(
        "appointments_hospital_id_fkey",
        "appointments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "appointments_hospital_id_fkey",
        "appointments",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("ix_appointment_hospital_slot", table_name="appointments")
    op.create_index("ix_appointment_hospital", "appointments", ["hospital_id"])

    op.alter_column("invoices", "hospital_id", nullable=True)
    op.drop_constraint("invoices_hospital_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_hospital_id_fkey",
        "invoices",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("ix_invoice_hospital_status", table_name="invoices")
    op.create_index("ix_invoice_hospital", "invoices", ["hospital_id"])
    op.create_index("ix_invoice_status", "invoices", ["status"])


def downgrade() -> None:
    op.drop_index("ix_invoice_status", table_name="invoices")
    op.drop_index("ix_invoice_hospital", table_name="invoices")
    op.create_index(
        "ix_invoice_hospital_status",
        "invoices",
        ["hospital_id", "status"],
    )
    op.drop_constraint("invoices_hospital_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_hospital_id_fkey",
        "invoices",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("invoices", "hospital_id", nullable=False)

    op.drop_index("ix_appointment_hospital", table_name="appointments")
    op.create_index(
        "ix_appointment_hospital_slot",
        "appointments",
        ["hospital_id", "slot_time"],
    )
    op.drop_constraint(
        "appointments_hospital_id_fkey",
        "appointments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "appointments_hospital_id_fkey",
        "appointments",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("appointments", "hospital_id", nullable=False)

    op.drop_index("ix_doctor_specialization", table_name="doctors")
    op.drop_index("ix_doctor_hospital", table_name="doctors")
    op.create_index(
        "ix_doctor_hospital_specialization",
        "doctors",
        ["hospital_id", "specialization"],
    )
    op.drop_constraint("doctors_hospital_id_fkey", "doctors", type_="foreignkey")
    op.create_foreign_key(
        "doctors_hospital_id_fkey",
        "doctors",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("doctors", "hospital_id", nullable=False)
    op.drop_column("doctors", "pending_hospital_state")
    op.drop_column("doctors", "pending_hospital_city")
    op.drop_column("doctors", "pending_hospital_name")
    op.drop_column("doctors", "clinic_address")
    op.drop_column("doctors", "clinic_city")
    op.drop_column("doctors", "clinic_name")
    op.drop_column("doctors", "work_type")

    op.drop_column("hospitals", "state")
    op.drop_column("hospitals", "city")

    op.add_column("patients", sa.Column("hospital_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "patients_hospital_id_fkey",
        "patients",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_patients_hospital_id", "patients", ["hospital_id"])
    op.create_index("ix_patient_hospital", "patients", ["hospital_id"])

    op.drop_index("ix_user_status", table_name="users")
    op.drop_index("ix_user_phone", table_name="users")
    op.drop_index("ix_user_email", table_name="users")
    op.add_column("users", sa.Column("hospital_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "users_hospital_id_fkey",
        "users",
        "hospitals",
        ["hospital_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_users_hospital_id", "users", ["hospital_id"])
    op.create_index("ix_user_phone_hospital", "users", ["phone", "hospital_id"])
    op.create_index(
        "ix_user_email_hospital",
        "users",
        ["email", "hospital_id"],
        unique=True,
    )
    op.drop_column("users", "is_super_admin")
    op.drop_column("users", "status")

    work_type_enum.drop(op.get_bind(), checkfirst=True)
    account_status_enum.drop(op.get_bind(), checkfirst=True)
