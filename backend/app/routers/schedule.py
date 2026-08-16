from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, get_target_student
from app.models import Enrollment
from app.schemas.schedule import ScheduleClassOut, StudentScheduleOut, TermOption

router = APIRouter(prefix="/schedule", tags=["Thời khóa biểu"])


def _class_out(e: Enrollment) -> ScheduleClassOut:
    cc = e.course_class
    return ScheduleClassOut(
        course_class_id=cc.id if cc else 0,
        course_code=cc.course.code if cc and cc.course else None,
        course_name=cc.course.name if cc and cc.course else None,
        credits=cc.course.credits if cc and cc.course else None,
        lecturer_name=cc.lecturer.name if cc and cc.lecturer else None,
        year=cc.year if cc else 0,
        term=cc.term if cc else 0,
        schedule=cc.schedule or [] if cc else [],
    )


@router.get("/student/{student_id}", response_model=StudentScheduleOut)
def get_student_schedule(
    student_id: int,
    year: int | None = None,
    term: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Thời khóa biểu của 1 sinh viên — chính SV, advisor phụ trách, training_office.

    Không truyền year/term → trả về kỳ mới nhất có đăng ký.
    `terms` luôn trả đủ các kỳ có đăng ký (mới nhất trước) để UI dựng bộ chọn kỳ.
    """
    get_target_student(db, user, student_id)

    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()

    # Gom các kỳ có đăng ký (mới nhất trước) — key (year, term)
    term_keys: list[tuple[int, int]] = []
    for e in enrollments:
        cc = e.course_class
        if cc is None:
            continue
        key = (cc.year, cc.term)
        if key not in term_keys:
            term_keys.append(key)
    term_keys.sort(reverse=True)

    if year is not None or term is not None:
        # Chọn kỳ tường minh: nếu không tồn tại kỳ này trong danh sách đăng ký → 404
        selected = (year, term) if year is not None and term is not None else None
        if selected is None:
            selected = next(
                ((y, t) for y, t in term_keys if (year is None or y == year) and (term is None or t == term)),
                None,
            )
        if selected not in term_keys:
            raise HTTPException(status_code=404, detail="Kỳ học này không có đăng ký nào")
        sel_year, sel_term = selected
    else:
        if not term_keys:
            sel_year = sel_term = None
        else:
            sel_year, sel_term = term_keys[0]

    classes = [
        _class_out(e)
        for e in enrollments
        if e.course_class is not None
        and e.course_class.year == sel_year
        and e.course_class.term == sel_term
    ]
    # Sắp xếp theo thứ tự buổi học trong tuần để UI dễ đọc
    classes.sort(key=lambda c: (
        min((s.get("weekday", 9), s.get("start_period", 99)) for s in c.schedule)
        if c.schedule else (9, 99)
    ))

    return StudentScheduleOut(
        student_id=student_id,
        year=sel_year,
        term=sel_term,
        terms=[TermOption(year=y, term=t) for y, t in term_keys],
        classes=classes,
    )
