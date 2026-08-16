from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import get_current_user, get_target_student, require_role
from app.models import Enrollment
from app.schemas.grade import GpaOut, GradeOut, ScoreUpdate, StudentGradeOut
from app.services.grade_service import (
    compute_gpa,
    convert_score10,
    is_passed,
    update_exam_score,
    update_process_score,
)

router = APIRouter(prefix="/grades", tags=["Điểm"])


def _get_enrollment_or_404(db: Session, enrollment_id: int) -> Enrollment:
    enrollment = db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký")
    return enrollment


def _grade_out(grade) -> dict:
    """Grade + điểm chữ/hệ 4/kết quả — lấy từ DB, fallback quy đổi khi DB chưa backfill."""
    if grade is None:
        return {}
    letter, score4 = grade.letter_grade, grade.score4
    if grade.total_score is not None and letter is None:
        letter, score4 = convert_score10(grade.total_score)
    return {
        "id": grade.id,
        "enrollment_id": grade.enrollment_id,
        "process_score": grade.process_score,
        "exam_score": grade.exam_score,
        "total_score": grade.total_score,
        "letter_grade": letter,
        "score4": score4,
        "passed": is_passed(letter),
        "updated_at": grade.updated_at,
    }


@router.put("/{enrollment_id}/process", response_model=GradeOut)
def set_process_score(
    enrollment_id: int,
    body: ScoreUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("lecturer")),
):
    """Nhập điểm quá trình — CHỈ giảng viên đang dạy lớp học phần đó."""
    enrollment = _get_enrollment_or_404(db, enrollment_id)
    course_class = enrollment.course_class
    if course_class is None or course_class.lecturer_id != user["lecturer_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
    grade = update_process_score(db, enrollment_id, body.score, user["user_id"])
    return _grade_out(grade)


@router.put("/{enrollment_id}/exam", response_model=GradeOut)
def set_exam_score(
    enrollment_id: int,
    body: ScoreUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Nhập điểm thi — CHỈ phòng đào tạo, kể cả giảng viên dạy lớp cũng không được."""
    _get_enrollment_or_404(db, enrollment_id)
    grade = update_exam_score(db, enrollment_id, body.score, user["user_id"])
    return _grade_out(grade)


@router.get("/student/{student_id}", response_model=list[StudentGradeOut])
def get_student_grades(
    student_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Bảng điểm của 1 sinh viên — chính SV, advisor phụ trách, lecturer liên quan, training_office."""
    get_target_student(db, user, student_id, allow_lecturer=True)
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()
    rows = []
    for e in enrollments:
        cc = e.course_class
        if cc is None or cc.course is None:
            continue
        grade = e.grade
        total = grade.total_score if grade else None
        letter = grade.letter_grade if grade else None
        score4 = grade.score4 if grade else None
        if total is not None and letter is None:
            letter, score4 = convert_score10(total)
        if total is None:
            status = "chưa có điểm"
        elif letter != "F":
            status = "đạt"
        else:
            status = "không đạt"
        rows.append(
            StudentGradeOut(
                enrollment_id=e.id,
                course_code=cc.course.code,
                course_name=cc.course.name,
                credits=cc.course.credits,
                counted_in_gpa=cc.course.counted_in_gpa,
                term=cc.term,
                year=cc.year,
                process_score=grade.process_score if grade else None,
                exam_score=grade.exam_score if grade else None,
                total_score=total,
                letter_grade=letter,
                score4=score4,
                status=status,
            )
        )
    rows.sort(key=lambda r: (r.year, r.term, r.course_code))
    return rows


@router.get("/student/{student_id}/gpa", response_model=GpaOut)
def get_student_gpa(
    student_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """GPA tích lũy hệ 4 + hệ 10 theo tín chỉ — backend tính, chỉ gồm HP counted_in_gpa."""
    get_target_student(db, user, student_id, allow_lecturer=True)
    gpa4, gpa10, credits, accumulated_credits = compute_gpa(db, student_id)
    return GpaOut(
        gpa4=gpa4,
        gpa10=gpa10,
        credits=credits,
        accumulated_credits=accumulated_credits,
    )
