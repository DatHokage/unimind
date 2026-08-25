"""Quy đổi lịch cố định thành các buổi học có ngày cụ thể.

Lớp học phần chỉ lưu slot tuần điển hình (thứ + khối + phòng); mọi view cần
ngày thật — TKB theo tháng, danh sách "Tuần 1..N", highlight hôm nay, xuất
ICS về sau — đều đi qua hàm mở rộng ở đây để có MỘT nguồn sự thật duy nhất.
"""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcademicTerm, CourseClass
from app.models.academic import TIME_BLOCKS

# Hệ thứ Việt Nam: 2 = Thứ Hai … 8 = Chủ Nhật (Python weekday(): 0 = Monday)
VN_MONDAY = 2


def monday_of_week(d: datetime.date) -> datetime.date:
    """Thứ 2 của tuần chứa d — start_date nhập lệch thứ vẫn chia tuần đúng."""
    return d - datetime.timedelta(days=d.weekday())


def term_start_date(db: Session, year: int, term: int) -> datetime.date | None:
    """Ngày bắt đầu kỳ (year, term) — None nếu PĐT chưa nhập."""
    at = db.scalar(
        select(AcademicTerm).where(AcademicTerm.year == year, AcademicTerm.term == term)
    )
    return at.start_date if at else None


def expand_class_sessions(
    cc: CourseClass, start_date: datetime.date
) -> list[dict]:
    """Sinh toàn bộ buổi học của 1 lớp: (credits × 3) buổi, mỗi tuần 1 buổi.

    Buổi seq nằm ở tuần seq: Thứ 2 tuần đó = Thứ 2 của tuần chứa start_date
    dịch forward (seq − 1) tuần; ngày học = Thứ Hai + (thứ học − 2) ngày.
    Ghi đè từng buổi được áp tại chỗ:
    - moved: dời sang weekday/block khác (vẫn trong tuần seq), room bù nếu có;
    - cancelled: giữ nguyên ngày gốc nhưng đánh dấu nghỉ.
    Trả về list dict thô — router tự ghép thông tin lớp thành SessionEventOut.
    """
    weeks = cc.course.credits * 3 if cc.course else 0
    overrides = {o.seq: o for o in (cc.session_overrides or [])}
    week1_monday = monday_of_week(start_date)

    events = []
    for seq in range(1, weeks + 1):
        monday = week1_monday + datetime.timedelta(days=(seq - 1) * 7)
        ov = overrides.get(seq)
        if ov is not None and ov.action == "moved":
            status = "moved"
            wd = ov.weekday or cc.weekday
            block = ov.block or cc.block
            room = ov.room or cc.room
        elif ov is not None and ov.action == "cancelled":
            status = "cancelled"
            wd, block, room = cc.weekday, cc.block, cc.room
        else:
            status = "normal"
            wd, block, room = cc.weekday, cc.block, cc.room
        start_period, end_period = TIME_BLOCKS[block]
        events.append(
            {
                "seq": seq,
                "week": seq,
                "date": monday + datetime.timedelta(days=wd - VN_MONDAY),
                "status": status,
                "weekday": wd,
                "block": block,
                "room": room,
                "start_period": start_period,
                "end_period": end_period,
            }
        )
    return events
