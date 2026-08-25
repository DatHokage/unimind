from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, get_target_student
from app.models import Enrollment
from app.schemas.course_class import SessionOverrideOut
from app.schemas.schedule import (
    ScheduleClassOut,
    SessionEventOut,
    StudentScheduleOut,
    TermOption,
)
from app.services.course_service import get_class_code
from app.services.schedule_service import expand_class_sessions, term_start_date

router = APIRouter(prefix="/schedule", tags=["Thời khóa biểu"])


def _class_out(db: Session, e: Enrollment) -> ScheduleClassOut:
    cc = e.course_class
    return ScheduleClassOut(
        course_class_id=cc.id if cc else 0,
        class_code=get_class_code(db, cc) if cc else None,
        course_code=cc.course.code if cc and cc.course else None,
        course_name=cc.course.name if cc and cc.course else None,
        credits=cc.course.credits if cc and cc.course else None,
        lecturer_name=cc.lecturer.name if cc and cc.lecturer else None,
        year=cc.year if cc else 0,
        term=cc.term if cc else 0,
        weekday=cc.weekday if cc else None,
        block=cc.block if cc else None,
        room=cc.room if cc else None,
        start_period=cc.start_period if cc else None,
        end_period=cc.end_period if cc else None,
        weeks=(cc.course.credits * 3) if cc and cc.course else None,
        session_overrides=[
            SessionOverrideOut.model_validate(o) for o in (cc.session_overrides or [])
        ],
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

    selected_enrollments = [
        e
        for e in enrollments
        if e.course_class is not None
        and e.course_class.year == sel_year
        and e.course_class.term == sel_term
    ]
    # Sắp xếp theo thứ tự buổi học trong tuần (thứ → khối giờ) để UI dễ đọc
    selected_enrollments.sort(
        key=lambda e: (e.course_class.weekday, e.course_class.start_period)
    )
    classes = [_class_out(db, e) for e in selected_enrollments]

    # Toàn bộ buổi học của kỳ quy đổi ra ngày cụ thể — view theo tháng/tuần học.
    # Kỳ chưa có ngày bắt đầu (chưa nhập academic_term) → trả rỗng, UI tự ẩn view.
    start_date = term_start_date(db, sel_year, sel_term) if sel_year is not None else None
    sessions: list[SessionEventOut] = []
    if start_date is not None:
        for e in selected_enrollments:
            cc = e.course_class
            info = dict(
                course_class_id=cc.id,
                class_code=get_class_code(db, cc),
                course_code=cc.course.code if cc.course else None,
                course_name=cc.course.name if cc.course else None,
                credits=cc.course.credits if cc.course else None,
                lecturer_name=cc.lecturer.name if cc.lecturer else None,
            )
            for ev in expand_class_sessions(cc, start_date):
                sessions.append(SessionEventOut(**info, **ev))
        sessions.sort(key=lambda s: (s.date, s.start_period))

    return StudentScheduleOut(
        student_id=student_id,
        year=sel_year,
        term=sel_term,
        start_date=start_date,
        terms=[TermOption(year=y, term=t) for y, t in term_keys],
        classes=classes,
        sessions=sessions,
    )
