"""add full_name to users

Revision ID: 59820047400b
Revises: add_order_line_reference_price
Create Date: 2026-02-07 18:18:30.737366

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '59820047400b'
down_revision: Union[str, Sequence[str], None] = 'add_order_line_reference_price'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")

