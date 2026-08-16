import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)


class StudentCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    dob: datetime.date | None = None
    major_id: int | None = None
    class_id: int | None = None
    account: AccountCreate | None = None


class StudentUpdate(BaseModel):
    name: str | None = None
    dob: datetime.date | None = None
    major_id: int | None = None
    class_id: int | None = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    dob: datetime.date | None = None
    major_id: int | None = None
    class_id: int | None = None
    major_name: str | None = None
    class_name: str | None = None


class StudentPage(BaseModel):
    """Kết quả phân trang danh sách sinh viên (server-side pagination)."""

    data: list[StudentOut]
    page: int
    size: int
    totalElements: int
    totalPages: int
