from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Course
from app.schemas.course import CourseBrief, CourseCreate, CourseOut
from app.services.course_service import attach_prerequisites

router = APIRouter(prefix="/courses", tags=["Học phần"])


def _course_out(db: Session, course: Course) -> CourseOut:
    return CourseOut(
        id=course.id,
        code=course.code,
        name=course.name,
        credits=course.credits,
        counted_in_gpa=course.counted_in_gpa,
        prerequisites=[CourseBrief.model_validate(p) for p in course.prerequisites],
    )


@router.get("", response_model=list[CourseOut])
def list_courses(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    courses = db.scalars(select(Course).order_by(Course.code)).all()
    return [_course_out(db, c) for c in courses]


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    body: CourseCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(Course).where(Course.code == body.code)):
        raise HTTPException(status_code=409, detail="Mã học phần đã tồn tại")
    course = Course(
        code=body.code,
        name=body.name,
        credits=body.credits,
        counted_in_gpa=body.counted_in_gpa,
    )
    db.add(course)
    db.flush()
    attach_prerequisites(db, course, body.prerequisite_course_ids)
    db.commit()
    db.refresh(course)
    return _course_out(db, course)
