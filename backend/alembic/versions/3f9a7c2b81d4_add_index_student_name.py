"""index student.name

Revision ID: 3f9a7c2b81d4
Revises: bcd0ce4e455e
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f9a7c2b81d4'
down_revision: Union[str, Sequence[str], None] = 'bcd0ce4e455e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Hỗ trợ tìm kiếm theo họ tên trong danh sách sinh viên phân trang
    # (cột code đã có unique index từ schema gốc)
    op.create_index('ix_student_name', 'student', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_student_name', table_name='student')
