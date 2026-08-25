import datetime

from pydantic import BaseModel, ConfigDict


class EnrollmentCreate(BaseModel):
    course_class_id: int
    # Chỉ training_office được truyền (đăng ký hộ); sinh viên tự đăng ký thì bỏ qua
    student_id: int | None = None


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    course_class_id: int
    course_code: str | None = None
    class_code: str | None = None  # mã lớp học phần CTDL-N01
    course_name: str | None = None
    term: int | None = None
    year: int | None = None
    # Lịch cố định của lớp (1 buổi/tuần trong 1 khối giờ)
    weekday: int | None = None
    block: str | None = None
    room: str | None = None
    enrolled_at: datetime.datetime
    status: str
