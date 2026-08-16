"""Nghiệp vụ đăng ký học phần (mục 9.2 đặc tả).

Thứ tự kiểm tra: sĩ số → điều kiện tiên quyết → trùng lịch → đã đăng ký.
Chỉ coi là "qua môn" khi total_score >= PASS_THRESHOLD (mặc định 5.0).
"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, CourseClass, Enrollment, Grade, Prerequisite


def sessions_overlap(a: dict, b: dict) -> bool:
    """Hai buổi học trùng nhau nếu cùng thứ và khoảng tiết (inclusive) giao nhau."""
    return (
        a.get("weekday") == b.get("weekday")
        and a.get("start_period", 0) <= b.get("end_period", 0)
        and b.get("start_period", 0) <= a.get("end_period", 0)
    )


def schedule_conflicts(s1: list[dict], s2: list[dict]) -> bool:
    return any(sessions_overlap(a, b) for a in s1 for b in s2)


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

    # 3. Kiểm tra trùng lịch với các lớp đã đăng ký trong cùng kỳ
    my_enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()
    for e in my_enrollments:
        other = e.course_class
        if other is None or other.id == course_class.id:
            continue
        if other.year == course_class.year and other.term == course_class.term:
            if schedule_conflicts(course_class.schedule or [], other.schedule or []):
                return False, f"Trùng lịch với lớp {other.course.code if other.course else other.id}"

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
    ok, message = check_enrollment_eligibility(db, student_id, course_class_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    enrollment = Enrollment(
        student_id=student_id,
        course_class_id=course_class_id,
        enrolled_at=datetime.now(timezone.utc),
        status="approved",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment
