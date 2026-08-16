from typing import Any

from pydantic import BaseModel


class CourseAdviceRequest(BaseModel):
    student_id: int
    target_year: int | None = None
    target_term: int | None = None


class CourseAdviceRecommendation(BaseModel):
    course_class_id: int
    course_code: str
    reason: str


class CourseAdviceResponse(BaseModel):
    # overview/warnings/suggestions: phần phân tích chuyên sâu của AI
    # (prompt yêu cầu viết chi tiết, có dẫn chứng — xem app/services/prompts.py)
    overview: str | None = None
    recommendations: list[CourseAdviceRecommendation] = []
    warnings: list[str] = []
    suggestions: list[str] = []
    notes: str | None = None
    eligible_classes: list[dict] = []  # du lieu server-side tinh san
    fallback: bool = False  # True = LLM loi/khong co key, chi tra du lieu server-side


class StudySummaryRequest(BaseModel):
    student_id: int


class StudySummaryResponse(BaseModel):
    summary: str | None = None
    warnings: list[str] = []
    suggestions: list[str] = []
    stats: dict = {}  # du lieu server-side tinh san
    fallback: bool = False


class RegulationChatRequest(BaseModel):
    question: str
    session_id: str = "default"  # định danh phiên chat (giữ ngữ cảnh hỏi-đáp)
    # Model được chọn từ dropdown trên web; bỏ trống = model mặc định theo .env.
    # Model được chọn gọi lỗi vẫn tự fallback sang model miễn phí khác.
    provider: str = ""  # "openrouter" | "gemini"
    model: str = ""     # ví dụ "nvidia/nemotron-3-super-120b-a12b:free"


class RegulationSource(BaseModel):
    # Khớp với format_sources() trong src/rag/chain.py.
    # phan/chuong/muc/dieu/khoan để Any vì pipeline trả int hoặc str tùy tài liệu.
    phan: Any = ""
    chuong: Any = ""
    chuong_con: Any = ""
    muc: Any = ""
    trich: Any = ""
    dieu: Any = ""
    ten_dieu: str = ""
    khoan: Any = ""
    so_trang: int = 0
    nguon: str = ""
    text: str = ""


class RegulationChatResponse(BaseModel):
    answer: str
    sources: list[RegulationSource] = []
    provider: str = ""
    model: str = ""


class RegulationModelItem(BaseModel):
    provider: str
    model: str
    label: str = ""


class RegulationModelListResponse(BaseModel):
    models: list[RegulationModelItem] = []
    default: RegulationModelItem | None = None
