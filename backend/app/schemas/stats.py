from pydantic import BaseModel


class AcademicResultRow(BaseModel):
    class_id: int
    class_name: str
    cohort: int | None = None
    major_name: str | None = None
    student_count: int
    graded_count: int
    avg_score: float | None = None
    pass_rate: float | None = None  # ty le total_score >= nguong qua mon


class PopularCourseRow(BaseModel):
    course_code: str
    course_name: str
    credits: int
    enrollment_count: int
