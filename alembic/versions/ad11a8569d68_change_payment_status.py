"""change payment status

Revision ID: ad11a8569d68
Revises: e4fc40df6266
Create Date: 2026-06-13 07:36:51.636237

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad11a8569d68'
down_revision: Union[str, Sequence[str], None] = 'e4fc40df6266'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE paymentstatus RENAME VALUE 'failed' TO 'cancelled'")


def downgrade() -> None:
    op.execute("ALTER TYPE paymentstatus RENAME VALUE 'cancelled' TO 'failed'")
