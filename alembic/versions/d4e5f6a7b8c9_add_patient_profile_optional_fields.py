"""add_patient_profile_optional_fields

Revision ID: d4e5f6a7b8c9
Revises: c3d8b1f6a9e2
Create Date: 2026-07-08 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d8b1f6a9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("patients", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("state", sa.String(length=100), nullable=True))
    op.add_column("patients", sa.Column("height", sa.Float(), nullable=True))
    op.add_column("patients", sa.Column("weight", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("patients", "weight")
    op.drop_column("patients", "height")
    op.drop_column("patients", "state")
    op.drop_column("patients", "city")
