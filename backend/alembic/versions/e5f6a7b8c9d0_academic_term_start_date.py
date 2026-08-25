"""academic_term: ngày bắt đầu học kỳ — gốc quy đổi lịch ra ngày cụ thể

Bảng mới hoàn toàn, không đụng dữ liệu hiện có. Lớp học phần chỉ lưu slot
tuần điển hình (thứ + khối); muốn vẽ TKB theo tháng / đánh số "Tuần 1..N"
thì phải biết tuần 1 của kỳ bắt đầu từ ngày nào.

Revision ID: e5f6a7b8c9d0
Revises: d9e4f1a6b7c3
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d9e4f1a6b7c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_term",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("term", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "term", name="uq_academic_term_year_term"),
    )


def downgrade() -> None:
    op.drop_table("academic_term")
