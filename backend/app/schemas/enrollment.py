import datetime

from pydantic import BaseModel, ConfigDict


class EnrollmentCreate(BaseModel):
    course_class_id: int


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    student_code: str | None = None
    student_name: str | None = None
    course_class_id: int
    course_code: str | None = None
    course_name: str | None = None
    term: int | None = None
    year: int | None = None
    schedule: list = []
    enrolled_at: datetime.datetime
    status: str
