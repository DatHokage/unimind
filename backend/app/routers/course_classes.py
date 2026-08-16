from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Course, CourseClass, Enrollment, Lecturer
from app.schemas.course_class import (
    CourseClassCreate,
    CourseClassOut,
    CourseClassPage,
    CourseClassUpdate,
)
from app.schemas.enrollment import EnrollmentOut
from app.services.course_service import get_prerequisite_ids

router = APIRouter(prefix="/course-classes", tags=["Lớp học phần"])


def _enrollment_out(e: Enrollment) -> EnrollmentOut:
    cc = e.course_class
    return EnrollmentOut(
        id=e.id,
        student_id=e.student_id,
        student_code=e.student.code if e.student else None,
        student_name=e.student.name if e.student else None,
        course_class_id=e.course_class_id,
        course_code=cc.course.code if cc and cc.course else None,
        course_name=cc.course.name if cc and cc.course else None,
        term=cc.term if cc else None,
        year=cc.year if cc else None,
        schedule=cc.schedule if cc else [],
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
        schedule=cc.schedule or [],
        status=cc.status,
        course_code=cc.course.code if cc.course else None,
        course_name=cc.course.name if cc.course else None,
        credits=cc.course.credits if cc.course else None,
        lecturer_name=cc.lecturer.name if cc.lecturer else None,
        enrolled_count=enrolled,
        prerequisite_codes=prereq_codes,
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
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
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
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
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
    user: dict = Depends(require_role("lecturer", "advisor")),
):
    """Các lớp học phần giảng viên đang đăng nhập phụ trách (advisor cũng là giảng viên)."""
    classes = db.scalars(
        select(CourseClass)
        .where(CourseClass.lecturer_id == user["lecturer_id"])
        .order_by(CourseClass.year.desc(), CourseClass.term.desc(), CourseClass.id)
    ).all()
    return [_course_class_out(db, cc) for cc in classes]


@router.get("/{course_class_id}", response_model=CourseClassOut)
def get_course_class(
    course_class_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    return _course_class_out(db, _get_course_class_or_404(db, course_class_id))


@router.get("/{course_class_id}/enrollments", response_model=list[EnrollmentOut])
def list_class_enrollments(
    course_class_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "lecturer", "advisor")),
):
    """Danh sách đăng ký trong 1 lớp — giảng viên chỉ xem lớp mình dạy."""
    cc = _get_course_class_or_404(db, course_class_id)
    if user["role"] in ("lecturer", "advisor") and cc.lecturer_id != user["lecturer_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.course_class_id == course_class_id)
    ).all()
    return [_enrollment_out(e) for e in enrollments]


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
    cc = CourseClass(
        course_id=body.course_id,
        lecturer_id=body.lecturer_id,
        term=body.term,
        year=body.year,
        max_size=body.max_size,
        schedule=[s.model_dump() for s in body.schedule],
        status=body.status,
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
    data = body.model_dump(exclude_unset=True)
    if "lecturer_id" in data and data["lecturer_id"] is not None:
        if db.get(Lecturer, data["lecturer_id"]) is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên")
    for field, value in data.items():
        setattr(cc, field, value)
    db.commit()
    db.refresh(cc)
    return _course_class_out(db, cc)
