import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.student import AccountCreate


class AdvisorAccountCreate(AccountCreate):
    # Tài khoản tạo kèm hồ sơ cố vấn luôn có role "advisor"
    role: str = Field(default="advisor", pattern="^advisor$")


class AdvisorCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    dob: datetime.date | None = None
    account: AdvisorAccountCreate | None = None


class AdvisorUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = None
    dob: datetime.date | None = None


class AdvisorClassOut(BaseModel):
    """Một lớp hành chính cố vấn đang phụ trách — rút gọn để hiển thị trong danh sách."""

    id: int
    name: str
    cohort: int | None = None
    major_name: str | None = None


class AdvisorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    dob: datetime.date | None = None
    # Các lớp hành chính cố vấn đang quản lý
    classes: list[AdvisorClassOut] = []


class AdvisorPage(BaseModel):
    """Kết quả phân trang danh sách cố vấn học tập (server-side pagination)."""

    data: list[AdvisorOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
