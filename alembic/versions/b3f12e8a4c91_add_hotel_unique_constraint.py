"""add hotel unique constraint

Revision ID: b3f12e8a4c91
Revises: ad11a8569d68
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b3f12e8a4c91'
down_revision: Union[str, Sequence[str], None] = 'ad11a8569d68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_hotel_name_location",
        "hotels",
        ["name", "country", "city", "address"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_hotel_name_location", "hotels", type_="unique")
