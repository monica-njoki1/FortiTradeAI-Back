"""add client order id to trades

Revision ID: 1a6f96c247be
Revises: bf108252e3a0
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa


revision = "1a6f96c247be"
down_revision = "bf108252e3a0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("trades") as batch_op:
        batch_op.add_column(sa.Column("binance_client_order_id", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint("uq_trades_binance_client_order_id", ["binance_client_order_id"])


def downgrade():
    with op.batch_alter_table("trades") as batch_op:
        batch_op.drop_constraint("uq_trades_binance_client_order_id", type_="unique")
        batch_op.drop_column("binance_client_order_id")
