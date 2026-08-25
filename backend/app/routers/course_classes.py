from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Course, CourseClass, CourseClassSession, Enrollment, Grade, Lecturer
from app.schemas.course_class import (
    CourseClassCreate,
    CourseClassOut,
    CourseClassPage,
    CourseClassUpdate,
    CurrentTermOut,
    SessionOverrideSet,
    SessionOverrideOut,
)
from app.schemas.enrollment import EnrollmentOut
from app.services.course_service import (
    ensure_no_schedule_conflicts,
    get_class_code,
    get_prerequisite_ids,
)

router = APIRouter(prefix="/course-classes", tags=["Lớp học phần"])


def _enrollment_out(db: Session, e: Enrollment) -> EnrollmentOut:
    cc = e.course_class
    return EnrollmentOut(
        id=e.id,
        student_id=e.student_id,
        student_code=e.student.code if e.student else None,
        student_name=e.student.name if e.student else None,
        course_class_id=e.course_class_id,
        course_code=cc.course.code if cc and cc.course else None,
        class_code=get_class_code(db, cc) if cc else None,
        course_name=cc.course.name if cc and cc.course else None,
        term=cc.term if cc else None,
        year=cc.year if cc else None,
        weekday=cc.weekday if cc else None,
        block=cc.block if cc else None,
        room=cc.room if cc else None,
        enrolled_at=e.enrolled_at,
        status=e.status,
    )


def _course_class_out(db: Session, cc: CourseClass) -> CourseClassOut:
    enrolled = db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.course_class_id == cc.id)
    ) or 0
    prereq_ids = get_prerequisite_ids(db, cc.course_id)
    prereq_codes = []
    if prereq_ids:
        prereq_codes = list(
            db.scalars(select(Course.code).where(Course.id.in_(prereq_ids)))
        )
    return CourseClassOut(
        id=cc.id,
        course_id=cc.course_id,
        lecturer_id=cc.lecturer_id,
        term=cc.term,
        year=cc.year,
        max_size=cc.max_size,
        status=cc.status,
        code=get_class_code(db, cc),
        # Lịch cố định cả khóa: 1 buổi/tuần trong khối giờ chuẩn
        weekday=cc.weekday,
        block=cc.block,
        room=cc.room,
        start_period=cc.start_period,
        end_period=cc.end_period,
        weeks=(cc.course.credits * 3) if cc.course else None,
        course_code=cc.course.code if cc.course else None,
        course_name=cc.course.name if cc.course else None,
        credits=cc.course.credits if cc.course else None,
        lecturer_name=cc.lecturer.name if cc.lecturer else None,
        enrolled_count=enrolled,
        prerequisite_codes=prereq_codes,
        session_overrides=[
            SessionOverrideOut.model_validate(o) for o in cc.session_overrides
        ],
    )


def _get_course_class_or_404(db: Session, course_class_id: int) -> CourseClass:
    cc = db.get(CourseClass, course_class_id)
    if cc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần")
    return cc


@router.get("", response_model=CourseClassPage)
def list_course_classes(
    search: str | None = None,
    term: int | None = None,
    year: int | None = None,
    status: str | None = None,
    course_id: int | None = None,
    lecturer_id: int | None = None,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer", "student")),
):
    """Danh sách lớp học phần phân trang phía server — chỉ query đúng các bản ghi của trang hiện tại."""
    stmt = select(CourseClass)
    if term is not None:
        stmt = stmt.where(CourseClass.term == term)
    if year is not None:
        stmt = stmt.where(CourseClass.year == year)
    if status is not None:
        stmt = stmt.where(CourseClass.status == status)
    if course_id is not None:
        stmt = stmt.where(CourseClass.course_id == course_id)
    if lecturer_id is not None:
        stmt = stmt.where(CourseClass.lecturer_id == lecturer_id)
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.join(Course, CourseClass.course_id == Course.id).join(
            Lecturer, CourseClass.lecturer_id == Lecturer.id, isouter=True
        ).where(
            or_(
                Course.code.ilike(keyword),
                Course.name.ilike(keyword),
                Lecturer.name.ilike(keyword),
                Lecturer.code.ilike(keyword),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    classes = db.scalars(
        stmt.order_by(CourseClass.year, CourseClass.term, CourseClass.id)
        .offset(page * size)
        .limit(size)
    ).all()
    return CourseClassPage(
        data=[_course_class_out(db, cc) for cc in classes],
        page=page,
        size=size,
        totalElements=total,
        totalPages=(total + size - 1) // size,
    )


@router.get("/all", response_model=list[CourseClassOut])
def list_all_course_classes(
    term: int | None = None,
    year: int | None = None,
    status: str | None = None,
    course_id: int | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer", "student")),
):
    """Toàn bộ lớp học phần (không phân trang) — chỉ dùng cho dropdown/select và trang đăng ký."""
    stmt = select(CourseClass)
    if term is not None:
        stmt = stmt.where(CourseClass.term == term)
    if year is not None:
        stmt = stmt.where(CourseClass.year == year)
    if status is not None:
        stmt = stmt.where(CourseClass.status == status)
    if course_id is not None:
        stmt = stmt.where(CourseClass.course_id == course_id)
    classes = db.scalars(stmt.order_by(CourseClass.year, CourseClass.term, CourseClass.id)).all()
    return [_course_class_out(db, cc) for cc in classes]


@router.get("/mine", response_model=list[CourseClassOut])
def my_course_classes(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("lecturer")),
):
    """Các lớp học phần giảng viên đang đăng nhập phụ trách (cố vấn không giảng dạy)."""
    classes = db.scalars(
        select(CourseClass)
        .where(CourseClass.lecturer_id == user["lecturer_id"])
        .order_by(CourseClass.year.desc(), CourseClass.term.desc(), CourseClass.id)
    ).all()
    return [_course_class_out(db, cc) for cc in classes]


@router.get("/current-term", response_model=CurrentTermOut)
def get_current_term(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer", "student")),
):
    """Kỳ hiện tại = kỳ MỚI NHẤT đang có lớp học phần (max year → max term).

    Admin mở lớp kỳ mới thì "kỳ hiện tại" tự trượt sang kỳ đó — không cần cấu
    hình. Đặt route này TRƯỚC /{course_class_id} để không bị nuốt vào path param.
    """
    latest = db.scalar(
        select(CourseClass)
        .order_by(CourseClass.year.desc(), CourseClass.term.desc())
        .limit(1)
    )
    return CurrentTermOut(
        year=latest.year if latest else None,
        term=latest.term if latest else None,
    )


@router.get("/{course_class_id}", response_model=CourseClassOut)
def get_course_class(
    course_class_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer", "student")),
):
    return _course_class_out(db, _get_course_class_or_404(db, course_class_id))


@router.get("/{course_class_id}/enrollments", response_model=list[EnrollmentOut])
def list_class_enrollments(
    course_class_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer")),
):
    """Danh sách đăng ký trong 1 lớp — giảng viên chỉ xem lớp mình dạy."""
    cc = _get_course_class_or_404(db, course_class_id)
    if user["role"] == "lecturer" and cc.lecturer_id != user["lecturer_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.course_class_id == course_class_id)
    ).all()
    return [_enrollment_out(db, e) for e in enrollments]


@router.post("", response_model=CourseClassOut, status_code=201)
def create_course_class(
    body: CourseClassCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.get(Course, body.course_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học phần")
    if body.lecturer_id is not None and db.get(Lecturer, body.lecturer_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên")
    # Chặn trùng phòng / trùng lịch giảng viên ngay khi mở lớp
    ensure_no_schedule_conflicts(
        db,
        year=body.year,
        term=body.term,
        weekday=body.weekday,
        block=body.block,
        room=body.room,
        lecturer_id=body.lecturer_id,
    )
    cc = CourseClass(
        course_id=body.course_id,
        lecturer_id=body.lecturer_id,
        term=body.term,
        year=body.year,
        max_size=body.max_size,
        status=body.status,
        weekday=body.weekday,
        block=body.block,
        room=body.room,
    )
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return _course_class_out(db, cc)


@router.patch("/{course_class_id}", response_model=CourseClassOut)
def update_course_class(
    course_class_id: int,
    body: CourseClassUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    cc = _get_course_class_or_404(db, course_class_id)
    if cc.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Lớp đã COMPLETED — chỉ tra cứu, không chỉnh sửa",
        )
    data = body.model_dump(exclude_unset=True)
    if data.get("status") == "completed":
        # Phải qua endpoint /complete để được kiểm tra "đủ điểm" trước khi khóa lớp
        raise HTTPException(
            status_code=400,
            detail="Không thể chuyển COMPLETED trực tiếp — dùng POST /course-classes/{id}/complete",
        )
    if "lecturer_id" in data and data["lecturer_id"] is not None:
        if db.get(Lecturer, data["lecturer_id"]) is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên")
    # Kiểm tra xung đột trên BỘ GIÁ TRỊ SAU KHI SỬA (PATCH có thể đổi từng phần),
    # trừ chính lớp đang sửa khỏi danh sách so sánh
    ensure_no_schedule_conflicts(
        db,
        year=cc.year,
        term=cc.term,
        weekday=data.get("weekday", cc.weekday),
        block=data.get("block", cc.block),
        room=data.get("room", cc.room),
        lecturer_id=data.get("lecturer_id", cc.lecturer_id),
        exclude_class_id=cc.id,
    )
    for field, value in data.items():
        setattr(cc, field, value)
    db.commit()
    db.refresh(cc)
    return _course_class_out(db, cc)


@router.post("/{course_class_id}/complete", response_model=CourseClassOut)
def complete_course_class(
    course_class_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Chuyển lớp sang COMPLETED — khóa vĩnh viễn, chỉ tra cứu.

    Điều kiện: lớp đã đóng đăng ký (closed) và 100% sinh viên trong lớp đã có điểm.
    Dữ liệu được giữ lại phục vụ tra cứu + lịch sử học tập — KHÔNG có xóa lớp.
    """
    cc = _get_course_class_or_404(db, course_class_id)
    if cc.status == "completed":
        raise HTTPException(status_code=400, detail="Lớp đã ở trạng thái COMPLETED")
    if cc.status != "closed":
        raise HTTPException(
            status_code=400,
            detail="Chỉ chuyển COMPLETED từ CLOSED — hãy đóng đăng ký lớp trước",
        )
    total = db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.course_class_id == cc.id)
    ) or 0
    graded = db.scalar(
        select(func.count(Enrollment.id))
        .join(Grade, Grade.enrollment_id == Enrollment.id)
        .where(Enrollment.course_class_id == cc.id, Grade.total_score.is_not(None))
    ) or 0
    if graded < total:
        raise HTTPException(
            status_code=400,
            detail=f"Chưa đủ điều kiện: còn {total - graded}/{total} sinh viên chưa có điểm",
        )
    cc.status = "completed"
    db.commit()
    db.refresh(cc)
    return _course_class_out(db, cc)


def _set_session_override(db: Session, cc: CourseClass, seq: int, body: SessionOverrideSet) -> None:
    """Ghi đè lịch 1 buổi: dời (moved — cần slot bù, check xung đột) hoặc nghỉ."""
    if cc.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Lớp đã COMPLETED — chỉ tra cứu, không chỉnh sửa",
        )
    weeks = (cc.course.credits * 3) if cc.course else 0
    if not 1 <= seq <= weeks:
        raise HTTPException(
            status_code=400,
            detail=f"Buổi phải nằm trong khoảng 1..{weeks} (số buổi của lớp)",
        )
    if body.action == "moved":
        if body.weekday is None or body.block is None:
            raise HTTPException(
                status_code=400,
                detail="Dời buổi cần đủ thứ + khối giờ học bù",
            )
        # Slot bù không được đụng phòng/giảng viên của lớp khác trong cùng kỳ
        ensure_no_schedule_conflicts(
            db,
            year=cc.year,
            term=cc.term,
            weekday=body.weekday,
            block=body.block,
            room=body.room,
            lecturer_id=cc.lecturer_id,
            exclude_class_id=cc.id,
        )

    ov = db.scalar(
        select(CourseClassSession).where(
            CourseClassSession.course_class_id == cc.id,
            CourseClassSession.seq == seq,
        )
    )
    if ov is None:
        ov = CourseClassSession(course_class_id=cc.id, seq=seq)
        db.add(ov)
    moved = body.action == "moved"
    ov.action = body.action
    ov.weekday = body.weekday if moved else None
    ov.block = body.block if moved else None
    ov.room = body.room if moved else None
    db.commit()


@router.put("/{course_class_id}/sessions/{seq}", response_model=CourseClassOut)
def set_session_override(
    course_class_id: int,
    seq: int,
    body: SessionOverrideSet,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Dời/nghỉ TỪNG buổi riêng lẻ (lễ, sự kiện, GV bận) — các buổi khác giữ lịch thường.

    `seq` = buổi thứ mấy tính từ 1 đến credits×3. Gọi lại trên cùng buổi là ghi đè mới.
    """
    cc = _get_course_class_or_404(db, course_class_id)
    _set_session_override(db, cc, seq, body)
    db.refresh(cc)
    return _course_class_out(db, cc)


@router.delete("/{course_class_id}/sessions/{seq}", response_model=CourseClassOut)
def clear_session_override(
    course_class_id: int,
    seq: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa ghi đè — buổi trở lại lịch cố định của lớp."""
    cc = _get_course_class_or_404(db, course_class_id)
    if cc.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Lớp đã COMPLETED — chỉ tra cứu, không chỉnh sửa",
        )
    ov = db.scalar(
        select(CourseClassSession).where(
            CourseClassSession.course_class_id == cc.id,
            CourseClassSession.seq == seq,
        )
    )
    if ov is not None:
        db.delete(ov)
        db.commit()
    db.refresh(cc)
    return _course_class_out(db, cc)
