from pydantic import BaseModel, ConfigDict, Field

from app.schemas.student import AccountCreate


class LecturerAccountCreate(AccountCreate):
    role: str = Field(default="lecturer", pattern="^(lecturer|advisor)$")


class LecturerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    department: str | None = None
    account: LecturerAccountCreate | None = None


class LecturerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    department: str | None = None
