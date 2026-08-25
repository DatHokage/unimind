from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, get_target_student, require_role
from app.models import Enrollment, Student
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.services.course_service import get_class_code
from app.services.enrollment_service import create_enrollment

router = APIRouter(prefix="/enrollments", tags=["Đăng ký học phần"])


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


@router.post("", response_model=EnrollmentOut, status_code=201)
def enroll(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("student", "training_office")),
):
    """Sinh viên tự đăng ký, hoặc phòng đào tạo đăng ký hộ (truyền student_id).

    Server validate sĩ số + tiên quyết + trùng lịch trong cả 2 trường hợp.
    """
    if user["role"] == "training_office":
        if body.student_id is None:
            raise HTTPException(
                status_code=400, detail="Thiếu student_id khi đăng ký hộ sinh viên"
            )
        if db.get(Student, body.student_id) is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên")
        student_id = body.student_id
    else:
        student_id = user["student_id"]
        if student_id is None or db.get(Student, student_id) is None:
            raise HTTPException(status_code=403, detail="Tài khoản chưa gắn hồ sơ sinh viên")
    enrollment = create_enrollment(db, student_id, body.course_class_id)
    return _enrollment_out(db, enrollment)


@router.delete("/{enrollment_id}", status_code=200)
def cancel_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("student", "training_office")),
):
    """Hủy đăng ký — chỉ khi chưa có điểm; chính sinh viên hoặc phòng đào tạo."""
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký")
    if user["role"] == "student" and enrollment.student_id != user["student_id"]:
        raise HTTPException(status_code=403, detail="Không phải đăng ký của bạn")
    grade = enrollment.grade
    if grade is not None and (grade.process_score is not None or grade.exam_score is not None):
        raise HTTPException(status_code=409, detail="Không thể hủy: đăng ký đã có điểm")
    db.delete(enrollment)
    if grade is not None:
        db.delete(grade)
    db.commit()
    return {"detail": "Đã hủy đăng ký"}


@router.get("/student/{student_id}", response_model=list[EnrollmentOut])
def list_student_enrollments(
    student_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Lịch sử đăng ký của 1 sinh viên — chính SV, advisor phụ trách, training_office."""
    get_target_student(db, user, student_id)
    enrollments = db.scalars(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.enrolled_at.desc())
    ).all()
    return [_enrollment_out(db, e) for e in enrollments]
