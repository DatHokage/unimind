"""course_class_session: ghi đè lịch TỪNG buổi (dời/nghỉ trường hợp đặc biệt)

Bảng mới hoàn toàn — không đụng dữ liệu hiện có. Buổi bình thường sinh từ slot
cố định của lớp; dòng trong bảng này chỉ tồn tại khi buổi đó cần dời (moved,
kèm thứ/khối/phòng học bù) hoặc nghỉ hẳn (cancelled).

Revision ID: b7c2d9e4f1a6
Revises: e8f3a1c2d4b5
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c2d9e4f1a6"
down_revision: Union[str, Sequence[str], None] = "e8f3a1c2d4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "course_class_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_class_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("block", sa.String(length=10), nullable=True),
        sa.Column("room", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["course_class_id"], ["course_class.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_class_id", "seq", name="uq_session_class_seq"),
    )
    op.create_index(
        "ix_course_class_session_class", "course_class_session", ["course_class_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_course_class_session_class", table_name="course_class_session")
    op.drop_table("course_class_session")
