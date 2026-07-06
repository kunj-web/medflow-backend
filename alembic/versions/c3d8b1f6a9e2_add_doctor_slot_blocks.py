"""add_doctor_slot_blocks

Revision ID: c3d8b1f6a9e2
Revises: a1c9e7d2f4b6
Create Date: 2026-07-06 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c3d8b1f6a9e2"
down_revision: str | None = "a1c9e7d2f4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "doctor_slot_blocks",
        sa.Column("doctor_id", sa.UUID(), nullable=False),
        sa.Column("block_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_slot_block_doctor_date",
        "doctor_slot_blocks",
        ["doctor_id", "block_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_slot_block_doctor_date", table_name="doctor_slot_blocks")
    op.drop_table("doctor_slot_blocks")
