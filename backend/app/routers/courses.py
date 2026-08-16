from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Course, CourseClass, Prerequisite
from app.schemas.course import CourseBrief, CourseCreate, CourseOut, CoursePage, CourseUpdate
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


def _get_course_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy học phần")
    return course


@router.get("", response_model=CoursePage)
def list_courses(
    search: str | None = None,
    counted_in_gpa: bool | None = None,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    """Danh sách học phần phân trang phía server — chỉ query đúng các bản ghi của trang hiện tại."""
    stmt = select(Course)
    if counted_in_gpa is not None:
        stmt = stmt.where(Course.counted_in_gpa == counted_in_gpa)
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(or_(Course.name.ilike(keyword), Course.code.ilike(keyword)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    courses = db.scalars(
        stmt.options(joinedload(Course.prerequisites))
        .order_by(Course.code, Course.id)
        .offset(page * size)
        .limit(size)
    ).unique().all()
    return CoursePage(
        data=[_course_out(db, c) for c in courses],
        page=page,
        size=size,
        totalElements=total,
        totalPages=(total + size - 1) // size,
    )


@router.get("/all", response_model=list[CourseOut])
def list_all_courses(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    """Toàn bộ học phần (không phân trang) — chỉ dùng cho dropdown/select của form."""
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


@router.put("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    body: CourseUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    course = _get_course_or_404(db, course_id)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field == "prerequisite_course_ids":
            continue
        setattr(course, field, value)
    if "prerequisite_course_ids" in data:
        # Gán lại toàn bộ danh sách tiên quyết (clear rồi attach, kèm chống chu kỳ)
        course.prerequisites.clear()
        db.flush()
        attach_prerequisites(db, course, data["prerequisite_course_ids"])
    db.commit()
    db.refresh(course)
    return _course_out(db, course)


@router.delete("/{course_id}", status_code=200)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa học phần — chặn nếu đã mở lớp học phần."""
    course = _get_course_or_404(db, course_id)
    class_count = db.scalar(
        select(func.count(CourseClass.id)).where(CourseClass.course_id == course_id)
    ) or 0
    if class_count:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: học phần đã có lớp học phần"
        )
    # Dọn các bản ghi tiên quyết liên quan (cả 2 chiều)
    db.query(Prerequisite).filter(
        (Prerequisite.course_id == course_id)
        | (Prerequisite.prerequisite_course_id == course_id)
    ).delete(synchronize_session=False)
    db.delete(course)
    db.commit()
    return {"detail": f"Đã xóa học phần {course.code}"}
