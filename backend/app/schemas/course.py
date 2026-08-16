from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    credits: int = Field(ge=1, le=20)
    counted_in_gpa: bool = True
    prerequisite_course_ids: list[int] = []


class CourseUpdate(BaseModel):
    name: str | None = None
    credits: int | None = Field(default=None, ge=1, le=20)
    counted_in_gpa: bool | None = None
    prerequisite_course_ids: list[int] | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    credits: int
    counted_in_gpa: bool = True
    prerequisites: list["CourseBrief"] = []


class CourseBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    credits: int


CourseOut.model_rebuild()
