from pydantic import BaseModel


class TermOption(BaseModel):
    """Một học kỳ có đăng ký — dùng để frontend dựng bộ chọn kỳ."""

    year: int
    term: int


class ScheduleClassOut(BaseModel):
    """Một lớp học phần trong thời khóa biểu của sinh viên."""

    course_class_id: int
    course_code: str | None = None
    course_name: str | None = None
    credits: int | None = None
    lecturer_name: str | None = None
    year: int
    term: int
    schedule: list = []


class StudentScheduleOut(BaseModel):
    """Thời khóa biểu của 1 sinh viên trong 1 kỳ.

    `terms`: toàn bộ các kỳ có đăng ký (mới nhất trước) để đổi kỳ trên UI;
    `classes`: các lớp của kỳ đang xem (`year`, `term`).
    """

    student_id: int
    year: int | None = None
    term: int | None = None
    terms: list[TermOption] = []
    classes: list[ScheduleClassOut] = []
