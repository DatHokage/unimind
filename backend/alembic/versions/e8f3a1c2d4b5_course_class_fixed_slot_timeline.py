"""course_class: lịch cố định (weekday/block/room) + dồn timeline mới

Chuyển đổi một lần cho domain mới:
- Thêm cột ``weekday`` / ``block`` / ``room``; dữ liệu lấy từ buổi đầu tiên trong
  JSON ``schedule`` cũ, khối giờ suy ra từ tiết bắt đầu (1–5 sáng, 6–10 chiều,
  11–15 tối). Mỗi lớp học 1 buổi/tuần cố định trong cùng phòng suốt khóa.
- Dồn timeline: 2025-T1 → 2025-T2, 2025-T2 → 2025-T3 (CASE chạy một phát để hai
  nhóm không đè nhau); mọi lớp ngoài kỳ mới nhất chuyển COMPLETED — chỉ tra cứu,
  chặn đăng ký/chỉnh sửa.
- Lớp OOP kỳ hiện tại dạy trùng thứ/khối với CTDL (cùng DTCGV001) → chuyển sang
  DTCGV003 đúng như seed mới, tránh vi phạm luật chặn trùng lịch giảng viên.
- Drop cột ``schedule`` (không còn ai dùng).

Downgrade tái lập cột ``schedule`` từ các cột cố định (1 buổi) nhưng KHÔNG hoàn
tác timeline — muốn về nguyên trạng hãy khôi phục từ bảng backup
``course_class_backup_202608`` do bước đầu tiên của upgrade tạo ra.

Revision ID: e8f3a1c2d4b5
Revises: c9d8e7f6a5b4
Create Date: 2026-08-23
"""

from typing import Sequence, Union
import json

import sqlalchemy as sa
from alembic import op

revision: str = "e8f3a1c2d4b5"
down_revision: Union[str, Sequence[str], None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKUP_TABLE = "course_class_backup_202608"


def _block_from_start(start_period) -> str | None:
    """Khối giờ chuẩn từ tiết bắt đầu: 1–5 sáng, 6–10 chiều, 11–15 tối."""
    try:
        p = int(start_period)
    except (TypeError, ValueError):
        return None
    if 1 <= p <= 5:
        return "morning"
    if 6 <= p <= 10:
        return "afternoon"
    if 11 <= p <= 15:
        return "evening"
    return None


def _parse_schedule(raw):
    """Cột JSON trả list/dict sẵn trên Postgres nhưng là chuỗi trên SQLite."""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = [raw]
    return raw or []


def upgrade() -> None:
    conn = op.get_bind()

    # 0) Backup nguyên trạng — điểm khôi phục nếu cần
    op.execute(f"CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} AS SELECT * FROM course_class")

    # 1) Cột mới + index năm/kỳ (chỉ thêm khi thiếu — DB có thể đã được tạo sẵn)
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns("course_class")}
    indexes = {i["name"] for i in insp.get_indexes("course_class")}
    if "weekday" not in cols:
        op.add_column("course_class", sa.Column("weekday", sa.Integer(), nullable=True))
    if "block" not in cols:
        op.add_column("course_class", sa.Column("block", sa.String(length=10), nullable=True))
    if "room" not in cols:
        op.add_column("course_class", sa.Column("room", sa.String(length=50), nullable=True))
    if "ix_course_class_year" not in indexes:
        op.create_index("ix_course_class_year", "course_class", ["year"])
    if "ix_course_class_term" not in indexes:
        op.create_index("ix_course_class_term", "course_class", ["term"])

    # 2) schedule JSON → cột cố định (buổi đầu tiên của lớp)
    rows = conn.execute(sa.text("SELECT id, schedule FROM course_class")).fetchall()
    for row_id, sched in rows:
        first = next(
            (s for s in _parse_schedule(sched) if s.get("weekday") is not None), None
        )
        if first is None:
            continue  # dữ liệu lạ — giữ NULL, ràng buộc NOT NULL ở bước 4 sẽ báo
        conn.execute(
            sa.text("UPDATE course_class SET weekday = :w, block = :b, room = :r WHERE id = :i"),
            {
                "i": row_id,
                "w": int(first["weekday"]),
                "b": _block_from_start(first.get("start_period")),
                "r": first.get("room"),
            },
        )

    # 3) Dồn timeline + lưu trữ lịch sử
    #    a) Kỳ legacy: T1 → T2 (TH1), T2 → T3 (CTDL/GDTC1/GT1) — CASE một phát
    #       để nhóm vừa chuyển không bị nhóm sau bắt lại
    conn.execute(
        sa.text(
            "UPDATE course_class SET term = CASE WHEN term = 1 THEN 2 ELSE 3 END "
            "WHERE year = 2025 AND term IN (1, 2)"
        )
    )
    #    b) Mọi lớp ngoài kỳ mới nhất → COMPLETED (khóa vĩnh viễn, chỉ tra cứu)
    conn.execute(
        sa.text(
            "UPDATE course_class SET status = 'completed' "
            "WHERE (year * 10 + term) < (SELECT MAX(year * 10 + term) FROM course_class)"
        )
    )

    # 4) Ràng buộc NOT NULL sau khi dữ liệu đã đầy đủ
    #    (SQLite không ALTER được trực tiếp — dùng batch recreate bảng)
    with op.batch_alter_table("course_class") as batch:
        batch.alter_column("weekday", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("block", existing_type=sa.String(length=10), nullable=False)

    # 5) Sửa xung đột giảng viên ở kỳ hiện tại: OOP thứ 3 sáng do DTCGV001 dạy
    #    trùng slot với CTDL-N01 → chuyển sang DTCGV003 như seed mới
    lect = conn.execute(
        sa.text("SELECT id FROM lecturer WHERE code = 'DTCGV003'")
    ).first()
    if lect is not None:
        conn.execute(
            sa.text(
                "UPDATE course_class SET lecturer_id = :lid "
                "WHERE course_id IN (SELECT id FROM course WHERE code = 'OOP') "
                "AND weekday = 3 AND block = 'morning' "
                "AND (year * 10 + term) = (SELECT MAX(year * 10 + term) FROM course_class)"
            ),
            {"lid": lect.id},
        )

    # 6) Bỏ cột JSON cũ
    op.drop_column("course_class", "schedule")


def downgrade() -> None:
    """Tái lập cột ``schedule`` từ các cột cố định (timeline KHÔNG hoàn tác)."""
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    op.add_column("course_class", sa.Column("schedule", sa.JSON(), nullable=True))

    rows = conn.execute(
        sa.text("SELECT id, weekday, block, room FROM course_class")
    ).fetchall()
    blocks = {"morning": (1, 5), "afternoon": (6, 10), "evening": (11, 15)}
    for row_id, weekday, block, room in rows:
        start, end = blocks.get(block, (1, 5))
        payload = json.dumps([{"weekday": weekday, "start_period": start, "end_period": end, "room": room}])
        sql = (
            "UPDATE course_class SET schedule = :s WHERE id = :i"
            if is_sqlite
            else "UPDATE course_class SET schedule = CAST(:s AS JSON) WHERE id = :i"
        )
        conn.execute(sa.text(sql), {"s": payload, "i": row_id})

    with op.batch_alter_table("course_class") as batch:
        batch.alter_column("schedule", existing_type=sa.JSON(), nullable=False)
    op.drop_column("course_class", "room")
    op.drop_column("course_class", "block")
    op.drop_column("course_class", "weekday")
    op.drop_index("ix_course_class_term", table_name="course_class")
    op.drop_index("ix_course_class_year", table_name="course_class")
