from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, get_target_student, require_role
from app.models import Enrollment, Grade, Student
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.services.enrollment_service import create_enrollment

router = APIRouter(prefix="/enrollments", tags=["Đăng ký học phần"])


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
        schedule=cc.schedule or [] if cc else [],
        enrolled_at=e.enrolled_at,
        status=e.status,
    )


@router.post("", response_model=EnrollmentOut, status_code=201)
def enroll(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("student")),
):
    """Sinh viên tự đăng ký; server validate sĩ số + tiên quyết + trùng lịch."""
    student_id = user["student_id"]
    if student_id is None or db.get(Student, student_id) is None:
        raise HTTPException(status_code=403, detail="Tài khoản chưa gắn hồ sơ sinh viên")
    enrollment = create_enrollment(db, student_id, body.course_class_id)
    return _enrollment_out(enrollment)


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
    return [_enrollment_out(e) for e in enrollments]
