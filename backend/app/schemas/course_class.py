from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleSession(BaseModel):
    """Một buổi học: weekday 2..8 (2 = Thứ Hai ... 8 = Chủ Nhật), tiết inclusive."""

    weekday: int = Field(ge=2, le=8)
    start_period: int = Field(ge=1, le=15)
    end_period: int = Field(ge=1, le=15)
    room: str | None = None

    @model_validator(mode="after")
    def _check_period_range(self):
        if self.start_period > self.end_period:
            raise ValueError("start_period phải <= end_period")
        return self


class CourseClassCreate(BaseModel):
    course_id: int
    lecturer_id: int | None = None
    term: int = Field(ge=1, le=3)
    year: int = Field(ge=2000, le=2100)
    max_size: int = Field(ge=1, le=500, default=40)
    schedule: list[ScheduleSession] = []
    status: str = Field(default="open", pattern="^(open|closed)$")


class CourseClassUpdate(BaseModel):
    lecturer_id: int | None = None
    max_size: int | None = Field(default=None, ge=1, le=500)
    schedule: list[ScheduleSession] | None = None
    status: str | None = Field(default=None, pattern="^(open|closed)$")


class CourseClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    lecturer_id: int | None = None
    term: int
    year: int
    max_size: int
    schedule: list
    status: str
    course_code: str | None = None
    course_name: str | None = None
    credits: int | None = None
    lecturer_name: str | None = None
    enrolled_count: int = 0
    prerequisite_codes: list[str] = []


class CourseClassPage(BaseModel):
    """Kết quả phân trang danh sách lớp học phần (server-side pagination)."""

    data: list[CourseClassOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
