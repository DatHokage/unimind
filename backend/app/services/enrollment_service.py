"""Nghiệp vụ đăng ký học phần (mục 9.2 đặc tả).

Thứ tự kiểm tra: sĩ số → điều kiện tiên quyết → trùng lịch → đã đăng ký.
Chỉ coi là "qua môn" khi total_score >= PASS_THRESHOLD (mặc định 5.0).
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, CourseClass, Enrollment, Grade, Prerequisite
from app.services.course_service import get_class_code


def get_passed_course_ids(db: Session, student_id: int) -> set[int]:
    """Tập course_id mà sinh viên đã ĐẠT (total_score >= ngưỡng qua môn)."""
    rows = (
        db.query(Enrollment.course_class_id, Grade.total_score)
        .join(Grade, Grade.enrollment_id == Enrollment.id)
        .filter(Enrollment.student_id == student_id, Grade.total_score.is_not(None))
        .all()
    )
    class_ids = [cid for cid, total in rows if total >= settings.PASS_THRESHOLD]
    if not class_ids:
        return set()
    course_ids = db.scalars(
        select(CourseClass.course_id).where(CourseClass.id.in_(class_ids))
    ).all()
    return set(course_ids)


def count_enrollments(db: Session, course_class_id: int) -> int:
    return db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.course_class_id == course_class_id)
    ) or 0


def check_enrollment_eligibility(db: Session, student_id: int, course_class_id: int) -> tuple[bool, str]:
    course_class = db.get(CourseClass, course_class_id)
    if course_class is None:
        return False, "Không tìm thấy lớp học phần"
    if course_class.status != "open":
        return False, "Lớp học phần đã đóng đăng ký"

    # 1. Kiểm tra sĩ số
    if count_enrollments(db, course_class_id) >= course_class.max_size:
        return False, "Lớp đã đầy sĩ số"

    # 2. Kiểm tra điều kiện tiên quyết
    prereq_ids = db.scalars(
        select(Prerequisite.prerequisite_course_id).where(
            Prerequisite.course_id == course_class.course_id
        )
    ).all()
    if prereq_ids:
        passed = get_passed_course_ids(db, student_id)
        missing_ids = [pid for pid in prereq_ids if pid not in passed]
        if missing_ids:
            missing_codes = list(
                db.scalars(select(Course.code).where(Course.id.in_(missing_ids)))
            )
            return False, f"Còn thiếu điều kiện tiên quyết: {', '.join(missing_codes)}"

    # 3. Kiểm tra trùng lịch với các lớp đã đăng ký trong cùng kỳ.
    #    Buổi học chiếm đúng 1 khối giờ chuẩn (sáng/chiều/tối, không cắt giữa khối)
    #    nên trùng lịch ⇔ cùng kỳ + cùng thứ + cùng khối giờ.
    my_enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()
    for e in my_enrollments:
        other = e.course_class
        if other is None or other.id == course_class.id:
            continue
        same_slot = (
            other.year == course_class.year
            and other.term == course_class.term
            and other.weekday == course_class.weekday
            and other.block == course_class.block
        )
        if same_slot:
            return False, f"Trùng lịch với lớp {get_class_code(db, other)}"

    # 4. Kiểm tra đã đăng ký lớp này chưa
    duplicate = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student_id,
            Enrollment.course_class_id == course_class_id,
        )
    )
    if duplicate is not None:
        return False, "Đã đăng ký lớp học phần này rồi"

    return True, "Hợp lệ"


def create_enrollment(db: Session, student_id: int, course_class_id: int) -> Enrollment:
    # Khóa dòng lớp học phần đến khi commit (SELECT ... FOR UPDATE — mục 9.2):
    # 2 request cùng giành chỗ cuối phải xếp hàng tuần tự, request sau đếm được
    # sĩ số MỚI sau khi request trước commit → không bao giờ vượt max_size.
    # SQLite bỏ qua FOR UPDATE (khóa cả DB khi ghi nên test vẫn đúng ngữ nghĩa).
    db.execute(
        select(CourseClass).where(CourseClass.id == course_class_id).with_for_update()
    )

    ok, message = check_enrollment_eligibility(db, student_id, course_class_id)
    if not ok:
        db.rollback()  # nhả FOR UPDATE sớm, không giữ lock qua vòng đời request
        raise HTTPException(status_code=400, detail=message)

    enrollment = Enrollment(
        student_id=student_id,
        course_class_id=course_class_id,
        enrolled_at=datetime.now(timezone.utc),
        status="approved",
    )
    db.add(enrollment)
    try:
        db.commit()  # commit cũng nhả lock ở trên
    except IntegrityError:
        # 2 request CÙNG sinh viên đua nhau lọt qua pre-check → unique constraint
        # uq_enrollment_student_class chặn ở DB; trả lỗi nghiệp vụ thay vì 500.
        db.rollback()
        raise HTTPException(status_code=400, detail="Đã đăng ký lớp học phần này rồi")
    db.refresh(enrollment)
    return enrollment
