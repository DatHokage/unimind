"""quy doi diem chu he 4 + counted_in_gpa

Revision ID: 7c2f9a1d4e0b
Revises: 3f9a7c2b81d4
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2f9a1d4e0b'
down_revision: Union[str, Sequence[str], None] = '3f9a7c2b81d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _batch_alter(table: str):
    # batch mode để tương thích SQLite (dev) lẫn Postgres (prod)
    return op.batch_alter_table(table)


def upgrade() -> None:
    """Upgrade schema."""
    with _batch_alter("grade") as batch:
        batch.add_column(sa.Column("letter_grade", sa.String(length=2), nullable=True))
        batch.add_column(sa.Column("score4", sa.Integer(), nullable=True))
    with _batch_alter("course") as batch:
        batch.add_column(
            sa.Column("counted_in_gpa", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    # Backfill: quy đổi letter_grade/score4 cho các bản ghi đã có total_score,
    # theo đúng bảng quy đổi trong app.services.grade_service.convert_score10
    conn = op.get_bind()
    grades = conn.execute(sa.text("SELECT id, total_score FROM grade")).fetchall()
    for gid, total in grades:
        if total is None:
            continue
        if total >= 8.5:
            letter, score4 = "A", 4
        elif total >= 7.0:
            letter, score4 = "B", 3
        elif total >= 5.5:
            letter, score4 = "C", 2
        elif total >= 4.0:
            letter, score4 = "D", 1
        else:
            letter, score4 = "F", 0
        conn.execute(
            sa.text("UPDATE grade SET letter_grade = :l, score4 = :s WHERE id = :id"),
            {"l": letter, "s": score4, "id": gid},
        )


def downgrade() -> None:
    """Downgrade schema."""
    with _batch_alter("course") as batch:
        batch.drop_column("counted_in_gpa")
    with _batch_alter("grade") as batch:
        batch.drop_column("score4")
        batch.drop_column("letter_grade")
