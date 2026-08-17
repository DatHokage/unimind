from pydantic import BaseModel, ConfigDict, Field

from app.schemas.student import AccountCreate


class AdvisorAccountCreate(AccountCreate):
    # Tài khoản tạo kèm hồ sơ cố vấn luôn có role "advisor"
    role: str = Field(default="advisor", pattern="^advisor$")


class AdvisorCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    account: AdvisorAccountCreate | None = None


class AdvisorUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = None


class AdvisorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class AdvisorPage(BaseModel):
    """Kết quả phân trang danh sách cố vấn học tập (server-side pagination)."""

    data: list[AdvisorOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
