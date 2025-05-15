"""添加 position_type 列到 trade_history 表

Revision ID: add_position_type
Revises: 
Create Date: 2024-03-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_position_type'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 添加 position_type 列
    op.add_column('trade_history', sa.Column('position_type', sa.String(10), nullable=True))
    
    # 更新现有记录
    op.execute("""
        UPDATE trade_history 
        SET position_type = CASE 
            WHEN side = 'BUY' THEN 'LONG'
            WHEN side = 'SELL' THEN 'SHORT'
            ELSE 'UNKNOWN'
        END
    """)
    
    # 将列设置为非空
    op.alter_column('trade_history', 'position_type',
                    existing_type=sa.String(10),
                    nullable=False)

def downgrade():
    # 删除 position_type 列
    op.drop_column('trade_history', 'position_type') 