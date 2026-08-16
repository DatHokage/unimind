"""index ho tro tim kiem/loc cac trang quan ly admin

Revision ID: a1b2c3d4e5f6
Revises: 7c2f9a1d4e0b
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7c2f9a1d4e0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Hỗ trợ tìm kiếm theo họ tên trong danh sách giảng viên/ngành/học phần phân trang
    # (cột code đã có unique index từ schema gốc)
    op.create_index('ix_lecturer_name', 'lecturer', ['name'], unique=False)
    op.create_index('ix_major_name', 'major', ['name'], unique=False)
    op.create_index('ix_course_name', 'course', ['name'], unique=False)
    # Hỗ trợ filter theo ngành/khóa (lớp hành chính) và kỳ/năm (lớp học phần)
    op.create_index('ix_homeroom_class_major_id', 'homeroom_class', ['major_id'], unique=False)
    op.create_index('ix_homeroom_class_cohort', 'homeroom_class', ['cohort'], unique=False)
    op.create_index('ix_course_class_term', 'course_class', ['term'], unique=False)
    op.create_index('ix_course_class_year', 'course_class', ['year'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_course_class_year', table_name='course_class')
    op.drop_index('ix_course_class_term', table_name='course_class')
    op.drop_index('ix_homeroom_class_cohort', table_name='homeroom_class')
    op.drop_index('ix_homeroom_class_major_id', table_name='homeroom_class')
    op.drop_index('ix_course_name', table_name='course')
    op.drop_index('ix_major_name', table_name='major')
    op.drop_index('ix_lecturer_name', table_name='lecturer')
