"""add orders.created_at index

Revision ID: add_orders_created_at_idx
Revises: 77a2db3f8970
Create Date: 2025-11-10
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'add_orders_created_at_idx'
down_revision = '77a2db3f8970'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_orders_created_at', 'orders', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_orders_created_at', table_name='orders')

