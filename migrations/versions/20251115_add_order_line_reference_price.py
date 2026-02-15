"""add order_lines.reference_price_cents

Revision ID: add_order_line_reference_price
Revises: add_orders_created_at_idx
Create Date: 2025-11-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_order_line_reference_price'
down_revision = 'add_orders_created_at_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'order_lines' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('order_lines')}
    if 'reference_price_cents' in columns:
        return
    op.add_column(
        'order_lines',
        sa.Column('reference_price_cents', sa.Integer(), nullable=False, server_default='0')
    )
    op.execute("UPDATE order_lines SET reference_price_cents = unit_price_cents")
    if bind.dialect.name != "sqlite":
        op.alter_column('order_lines', 'reference_price_cents', server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'order_lines' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('order_lines')}
    if 'reference_price_cents' not in columns:
        return
    op.drop_column('order_lines', 'reference_price_cents')
