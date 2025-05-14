"""add strategy columns

Revision ID: add_strategy_columns
Revises: 
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_strategy_columns'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 添加策略相关字段
    op.add_column('trade_history', sa.Column('strategy', sa.String(20), nullable=True))
    op.add_column('trade_history', sa.Column('strategy_params', sa.String(255), nullable=True))

def downgrade():
    # 删除策略相关字段
    op.drop_column('trade_history', 'strategy_params')
    op.drop_column('trade_history', 'strategy') 