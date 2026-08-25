import datetime

from pydantic import BaseModel

from app.schemas.course_class import SessionOverrideOut


class TermOption(BaseModel):
    """Một học kỳ có đăng ký — dùng để frontend dựng bộ chọn kỳ."""

    year: int
    term: int


class ScheduleClassOut(BaseModel):
    """Một lớp học phần trong thời khóa biểu của sinh viên.

    Lịch cố định: 1 buổi/tuần trong khối giờ chuẩn (morning=tiết 1–5,
    afternoon=6–10, evening=11–15), kéo dài `weeks` tuần.
    `session_overrides`: các buổi bị dời/nghỉ riêng lẻ (thường rỗng).
    """

    course_class_id: int
    class_code: str | None = None  # mã lớp CTDL-N01
    course_code: str | None = None
    course_name: str | None = None
    credits: int | None = None
    lecturer_name: str | None = None
    year: int
    term: int
    weekday: int | None = None
    block: str | None = None
    room: str | None = None
    start_period: int | None = None
    end_period: int | None = None
    weeks: int | None = None
    session_overrides: list[SessionOverrideOut] = []


class SessionEventOut(BaseModel):
    """Một buổi học đã quy đổi ra ngày cụ thể.

    Sinh từ slot cố định + start_date của kỳ, đã áp hiệu lực ghi đè từng buổi:
    status normal/moved/cancelled; moved có weekday/block/room là slot bù.
    `week` = tuần học của kỳ tính từ 1 (trùng seq vì mỗi lớp 1 buổi/tuần).
    """

    course_class_id: int
    class_code: str | None = None
    course_code: str | None = None
    course_name: str | None = None
    credits: int | None = None
    lecturer_name: str | None = None
    seq: int
    week: int
    date: datetime.date
    status: str
    weekday: int
    block: str
    room: str | None = None
    start_period: int
    end_period: int


class StudentScheduleOut(BaseModel):
    """Thời khóa biểu của 1 sinh viên trong 1 kỳ.

    `terms`: toàn bộ các kỳ có đăng ký (mới nhất trước) để đổi kỳ trên UI;
    `classes`: các lớp của kỳ đang xem (`year`, `term`) — lịch tuần điển hình;
    `sessions`: toàn bộ buổi học của kỳ đã quy đổi ra ngày cụ thể (dùng cho
    view theo tháng / theo tuần học) — rỗng nếu kỳ chưa có ngày bắt đầu.
    """

    student_id: int
    year: int | None = None
    term: int | None = None
    start_date: datetime.date | None = None
    terms: list[TermOption] = []
    classes: list[ScheduleClassOut] = []
    sessions: list[SessionEventOut] = []
