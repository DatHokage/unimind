from pydantic import BaseModel, ConfigDict, Field


class CourseClassCreate(BaseModel):
    """Tạo lớp học phần — lịch cố định suốt khóa: 1 buổi/tuần × (credits×3) tuần, 1 phòng.

    Buổi học nằm gọn trong 1 khối giờ chuẩn (morning=tiết 1–5, afternoon=6–10,
    evening=11–15), không cắt giữa khối. Mã lớp (CTDL-N01…) sinh tự theo thứ tự
    tạo trong kỳ — không cần truyền.
    """

    course_id: int
    lecturer_id: int | None = None
    term: int = Field(ge=1, le=3)
    year: int = Field(ge=2000, le=2100)
    max_size: int = Field(ge=1, le=500, default=40)
    status: str = Field(default="open", pattern="^(open|closed|completed)$")
    weekday: int = Field(ge=2, le=8)  # 2 = Thứ Hai … 8 = Chủ Nhật
    block: str = Field(pattern="^(morning|afternoon|evening)$")
    room: str | None = Field(default=None, max_length=50)


class CourseClassUpdate(BaseModel):
    lecturer_id: int | None = None
    max_size: int | None = Field(default=None, ge=1, le=500)
    status: str | None = Field(default=None, pattern="^(open|closed|completed)$")
    weekday: int | None = Field(default=None, ge=2, le=8)
    block: str | None = Field(default=None, pattern="^(morning|afternoon|evening)$")
    room: str | None = Field(default=None, max_length=50)


class SessionOverrideSet(BaseModel):
    """Ghi đè 1 buổi học: dời sang slot khác (moved) hoặc nghỉ (cancelled).

    moved bắt buộc có weekday + block; cancelled bỏ trống phần slot bù.
    """

    action: str = Field(pattern="^(moved|cancelled)$")
    weekday: int | None = Field(default=None, ge=2, le=8)
    block: str | None = Field(default=None, pattern="^(morning|afternoon|evening)$")
    room: str | None = Field(default=None, max_length=50)


class SessionOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int  # buổi thứ mấy, tính từ 1
    action: str  # moved/cancelled
    weekday: int | None = None
    block: str | None = None
    room: str | None = None


class CourseClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    lecturer_id: int | None = None
    term: int
    year: int
    max_size: int
    status: str
    # Mã lớp CTDL-N01 (sinh theo thứ tự tạo trong kỳ)
    code: str | None = None
    # Lịch cố định cả khóa
    weekday: int
    block: str
    room: str | None = None
    start_period: int
    end_period: int
    weeks: int | None = None  # số tuần = credits × 3
    course_code: str | None = None
    course_name: str | None = None
    credits: int | None = None
    lecturer_name: str | None = None
    enrolled_count: int = 0
    prerequisite_codes: list[str] = []
    # Buổi bị dời/nghỉ (thường rỗng — chỉ có khi phòng đào tạo ghi đè)
    session_overrides: list[SessionOverrideOut] = []


class CurrentTermOut(BaseModel):
    """Kỳ hiện tại của hệ thống = kỳ mới nhất đang có lớp học phần."""

    year: int | None = None
    term: int | None = None


class CourseClassPage(BaseModel):
    """Kết quả phân trang danh sách lớp học phần (server-side pagination)."""

    data: list[CourseClassOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
