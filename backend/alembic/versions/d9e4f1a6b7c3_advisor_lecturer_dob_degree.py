"""advisor, lecturer: thêm ngày sinh (dob); lecturer thêm học vị (degree)

Hồ sơ nhân sự trước đây chỉ có mã/tên (+khoa với giảng viên). Cố vấn học tập
không giảng dạy nên không cần học vị — cột degree chỉ nằm trên bảng lecturer.

Revision ID: d9e4f1a6b7c3
Revises: b7c2d9e4f1a6
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e4f1a6b7c3"
down_revision: Union[str, Sequence[str], None] = "b7c2d9e4f1a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("advisor", sa.Column("dob", sa.Date(), nullable=True))
    op.add_column("lecturer", sa.Column("dob", sa.Date(), nullable=True))
    op.add_column("lecturer", sa.Column("degree", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("lecturer", "degree")
    op.drop_column("lecturer", "dob")
    op.drop_column("advisor", "dob")
