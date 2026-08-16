from pydantic import BaseModel, ConfigDict, Field


class HomeroomClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    major_id: int | None = None
    cohort: int | None = None
    advisor_id: int | None = None


class HomeroomClassUpdate(BaseModel):
    name: str | None = None
    major_id: int | None = None
    cohort: int | None = None
    advisor_id: int | None = None


class HomeroomClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    major_id: int | None = None
    major_name: str | None = None
    cohort: int | None = None
    advisor_id: int | None = None
    advisor_name: str | None = None
    student_count: int | None = None
