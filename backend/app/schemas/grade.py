import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScoreUpdate(BaseModel):
    """Body nhập điểm — KHÔNG có trường total_score/letter/score4: backend tự tính."""

    score: float = Field(ge=0, le=10)


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    enrollment_id: int
    process_score: float | None = None
    exam_score: float | None = None
    total_score: float | None = None
    letter_grade: str | None = None  # A/B/C/D/F — backend quy đổi
    score4: int | None = None  # điểm hệ 4 (0..4)
    passed: bool | None = None  # Đạt/Không đạt — backend quyết định
    updated_at: datetime.datetime | None = None


class StudentGradeOut(BaseModel):
    """Một dòng trong bảng điểm sinh viên."""

    enrollment_id: int
    course_code: str
    course_name: str
    credits: int
    counted_in_gpa: bool = True
    term: int
    year: int
    process_score: float | None = None
    exam_score: float | None = None
    total_score: float | None = None
    letter_grade: str | None = None
    score4: int | None = None
    status: str  # "chưa có điểm" / "đạt" / "không đạt" — backend quyết định


class GpaOut(BaseModel):
    """GPA tích lũy theo tín chỉ — backend tính, không lấy trung bình đơn giản."""

    gpa4: float | None = None
    gpa10: float | None = None
    credits: int = 0  # tín chỉ đã tính vào GPA (có điểm, counted_in_gpa; F vẫn tính)
    accumulated_credits: int = 0  # tín chỉ TÍCH LŨY — mọi môn Đạt, kể cả HP không tính GPA
