from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Course, CourseClass, Enrollment, Grade, HomeroomClass, Major, Student
from app.schemas.stats import AcademicResultRow, PopularCourseRow

router = APIRouter(prefix="/stats", tags=["Thống kê"])


@router.get("/academic-results", response_model=list[AcademicResultRow])
def academic_results(
    class_id: int | None = None,
    cohort: int | None = None,
    year: int | None = None,
    term: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor")),
):
    """Thống kê kết quả học tập theo lớp hành chính.

    Advisor chỉ được xem lớp mình phụ trách; không truyền class_id thì mặc định
    lấy toàn bộ lớp của advisor đó.
    """
    advisor_class_ids: list[int] | None = None
    if user["role"] == "advisor":
        advisor_class_ids = list(
            db.scalars(
                select(HomeroomClass.id).where(
                    HomeroomClass.advisor_id == user["lecturer_id"]
                )
            )
        )
        if class_id is not None and class_id not in advisor_class_ids:
            raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")

    stmt = (
        select(
            HomeroomClass.id,
            HomeroomClass.name,
            HomeroomClass.cohort,
            Major.name,
            func.count(func.distinct(Student.id)).label("student_count"),
            func.count(Grade.id).label("graded_count"),
            func.avg(Grade.total_score).label("avg_score"),
            func.sum(case((Grade.total_score >= settings.PASS_THRESHOLD, 1), else_=0)).label(
                "passed_count"
            ),
        )
        .join(Student, Student.class_id == HomeroomClass.id)
        .outerjoin(Enrollment, Enrollment.student_id == Student.id)
        .outerjoin(CourseClass, CourseClass.id == Enrollment.course_class_id)
        .outerjoin(Grade, Grade.enrollment_id == Enrollment.id)
        .outerjoin(Major, Major.id == HomeroomClass.major_id)
    )
    if class_id is not None:
        stmt = stmt.where(HomeroomClass.id == class_id)
    elif advisor_class_ids is not None:
        stmt = stmt.where(HomeroomClass.id.in_(advisor_class_ids))
    if cohort is not None:
        stmt = stmt.where(HomeroomClass.cohort == cohort)
    if year is not None:
        stmt = stmt.where(CourseClass.year == year)
    if term is not None:
        stmt = stmt.where(CourseClass.term == term)
    stmt = stmt.group_by(HomeroomClass.id, HomeroomClass.name, HomeroomClass.cohort, Major.name)

    rows = []
    for (
        hc_id,
        hc_name,
        hc_cohort,
        major_name,
        student_count,
        graded_count,
        avg_score,
        passed_count,
    ) in db.execute(stmt):
        rows.append(
            AcademicResultRow(
                class_id=hc_id,
                class_name=hc_name,
                cohort=hc_cohort,
                major_name=major_name,
                student_count=student_count or 0,
                graded_count=graded_count or 0,
                avg_score=round(float(avg_score), 2) if avg_score is not None else None,
                pass_rate=round(passed_count / graded_count, 4)
                if graded_count
                else None,
            )
        )
    return rows


@router.get("/popular-courses", response_model=list[PopularCourseRow])
def popular_courses(
    limit: int = 10,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Học phần có nhiều sinh viên đăng ký nhất."""
    rows = db.execute(
        select(
            Course.code,
            Course.name,
            Course.credits,
            func.count(Enrollment.id).label("enrollment_count"),
        )
        .join(CourseClass, CourseClass.course_id == Course.id)
        .join(Enrollment, Enrollment.course_class_id == CourseClass.id)
        .group_by(Course.id, Course.code, Course.name, Course.credits)
        .order_by(func.count(Enrollment.id).desc())
        .limit(limit)
    )
    return [
        PopularCourseRow(
            course_code=code,
            course_name=name,
            credits=credits,
            enrollment_count=count,
        )
        for code, name, credits, count in rows
    ]
