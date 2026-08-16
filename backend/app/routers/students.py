from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, require_role
from app.models import Enrollment, HomeroomClass, Major, Student
from app.schemas.student import StudentCreate, StudentOut, StudentPage, StudentUpdate
from app.services.user_service import create_user_account

router = APIRouter(prefix="/students", tags=["Sinh viên"])


def _student_out(db: Session, student: Student) -> StudentOut:
    return StudentOut(
        id=student.id,
        code=student.code,
        name=student.name,
        dob=student.dob,
        major_id=student.major_id,
        class_id=student.class_id,
        major_name=student.major.name if student.major else None,
        class_name=student.homeroom_class.name if student.homeroom_class else None,
    )


@router.get("", response_model=StudentPage)
def list_students(
    class_id: int | None = None,
    major_id: int | None = None,
    search: str | None = None,
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer")),
):
    """Danh sách sinh viên phân trang phía server — chỉ query đúng các bản ghi của trang hiện tại."""
    stmt = select(Student)
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    if major_id is not None:
        stmt = stmt.where(Student.major_id == major_id)
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(or_(Student.name.ilike(keyword), Student.code.ilike(keyword)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    students = (
        db.scalars(stmt.order_by(Student.code).offset(page * size).limit(size)).all()
    )
    return StudentPage(
        data=[_student_out(db, s) for s in students],
        page=page,
        size=size,
        totalElements=total,
        totalPages=(total + size - 1) // size,
    )


@router.post("", response_model=StudentOut, status_code=201)
def create_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(Student).where(Student.code == body.code)):
        raise HTTPException(status_code=409, detail="Mã sinh viên đã tồn tại")
    student = Student(
        code=body.code,
        name=body.name,
        dob=body.dob,
        major_id=body.major_id,
        class_id=body.class_id,
    )
    db.add(student)
    db.flush()
    if body.account:
        create_user_account(db, body.account.username, body.account.password, "student", student_id=student.id)
    db.commit()
    db.refresh(student)
    return _student_out(db, student)


@router.get("/{student_id}", response_model=StudentOut)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # training_office xem ai cũng được; student chỉ xem chính mình
    if user["role"] == "student" and user["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
    if user["role"] not in ("training_office", "student"):
        raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên")
    return _student_out(db, student)


@router.put("/{student_id}", response_model=StudentOut)
def update_student(
    student_id: int,
    body: StudentUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên")
    data = body.model_dump(exclude_unset=True)
    if "code" in data and data["code"] != student.code:
        if db.scalar(select(Student).where(Student.code == data["code"], Student.id != student_id)):
            raise HTTPException(status_code=409, detail="Mã sinh viên đã tồn tại")
    if data.get("major_id") is not None and db.get(Major, data["major_id"]) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ngành học")
    if data.get("class_id") is not None and db.get(HomeroomClass, data["class_id"]) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp hành chính")
    for field, value in data.items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return _student_out(db, student)


@router.delete("/{student_id}", status_code=200)
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa sinh viên — chặn nếu đã có đăng ký học phần (bảo toàn dữ liệu điểm)."""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên")
    has_enrollment = db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.student_id == student_id)
    ) or 0
    if has_enrollment:
        raise HTTPException(
            status_code=409,
            detail="Không thể xóa: sinh viên đã có đăng ký học phần",
        )
    db.delete(student)
    db.commit()
    return {"detail": f"Đã xóa sinh viên {student.code}"}
