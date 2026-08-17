from pydantic import BaseModel, ConfigDict, Field

from app.schemas.student import AccountCreate


class LecturerAccountCreate(AccountCreate):
    # Giảng viên không kiêm cố vấn — cố vấn là hồ sơ riêng (bảng advisor)
    role: str = Field(default="lecturer", pattern="^lecturer$")


class LecturerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    department: str | None = None
    account: LecturerAccountCreate | None = None


class LecturerUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = None
    department: str | None = None


class LecturerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department: str | None = None


class LecturerPage(BaseModel):
    """Kết quả phân trang danh sách giảng viên (server-side pagination)."""

    data: list[LecturerOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
