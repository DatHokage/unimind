"""Nghiệp vụ điểm (mục 9.3 đặc tả).

total_score = (process_score + exam_score) / 2, backend tự tính lại mỗi khi
1 trong 2 điểm thành phần được cập nhật. Client không bao giờ gửi total_score.

Quy đổi điểm chữ / hệ 4 (mục 6.8 đặc tả): backend là nơi duy nhất quyết định
kết quả học phần — frontend chỉ hiển thị giá trị backend trả về.

    [8.5, 10] → A / 4 · [7.0, 8.5) → B / 3 · [5.5, 7.0) → C / 2
    [4.0, 5.5) → D / 1 · dưới 4.0 → F / 0
    Kết quả: F → Không đạt; các chữ khác → Đạt.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CourseClass, Enrollment, Grade

# (ngưỡng dưới, điểm chữ, điểm hệ 4) — xét từ cao xuống thấp, dưới 4.0 là F/0.
GRADE_SCALE: tuple[tuple[float, str, int], ...] = (
    (8.5, "A", 4),
    (7.0, "B", 3),
    (5.5, "C", 2),
    (4.0, "D", 1),
)


def convert_score10(total_score: float | None) -> tuple[str | None, int | None]:
    """Quy đổi điểm TBC hệ 10 sang (điểm chữ, điểm hệ 4). Chưa có điểm → (None, None)."""
    if total_score is None:
        return None, None
    for threshold, letter, score4 in GRADE_SCALE:
        if total_score >= threshold:
            return letter, score4
    return "F", 0


def is_passed(letter_grade: str | None) -> bool | None:
    """Đạt/Không đạt theo điểm chữ; None khi chưa có điểm."""
    if letter_grade is None:
        return None
    return letter_grade != "F"


def compute_gpa(db: Session, student_id: int) -> tuple[float | None, float | None, int, int]:
    """GPA tích lũy theo tín chỉ: SUM(score × credits) / SUM(credits).

    GPA (hệ 4 + hệ 10) chỉ tính học phần có counted_in_gpa=True và đã có total_score.
    Trả về (gpa4, gpa10, credits, accumulated_credits):
    - credits: tín chỉ đã tính vào GPA (F vẫn tính — theo quy chế tín chỉ).
    - accumulated_credits: tín chỉ TÍCH LŨY — mọi môn đã có điểm và Đạt,
      KỂ CẢ HP không tính GPA (VD: GDTC đạt vẫn cộng tín chỉ tích lũy).
    Các giá trị điểm = None khi chưa có điểm nào tính vào GPA.
    """
    rows = db.execute(
        select(Grade.total_score, Course.credits, Course.counted_in_gpa)
        .join(Enrollment, Enrollment.id == Grade.enrollment_id)
        .join(CourseClass, CourseClass.id == Enrollment.course_class_id)
        .join(Course, Course.id == CourseClass.course_id)
        .where(Enrollment.student_id == student_id)
    ).all()
    weighted4 = 0.0
    weighted10 = 0.0
    credits = 0
    accumulated = 0
    for total, n_credits, counted in rows:
        if total is None:
            continue
        letter, score4 = convert_score10(total)
        if is_passed(letter):
            accumulated += n_credits  # tích lũy: mọi môn Đạt, kể cả HP không tính GPA
        if not counted:
            continue  # GPA bỏ qua HP counted_in_gpa=False
        weighted4 += (score4 or 0) * n_credits
        weighted10 += total * n_credits
        credits += n_credits
    if not credits:
        return None, None, 0, accumulated
    return round(weighted4 / credits, 2), round(weighted10 / credits, 2), credits, accumulated


def recalculate_total(grade: Grade) -> None:
    if grade.process_score is not None and grade.exam_score is not None:
        grade.total_score = round((grade.process_score + grade.exam_score) / 2, 2)
    else:
        grade.total_score = None
    # Quy đổi điểm chữ + hệ 4 mỗi khi total_score thay đổi (kể cả khi bị xóa về None)
    grade.letter_grade, grade.score4 = convert_score10(grade.total_score)


def get_or_create_grade(db: Session, enrollment_id: int) -> Grade:
    grade = db.query(Grade).filter(Grade.enrollment_id == enrollment_id).first()
    if grade is None:
        grade = Grade(enrollment_id=enrollment_id)
        db.add(grade)
        db.flush()
    return grade


def update_process_score(db: Session, enrollment_id: int, score: float, updater_id: int) -> Grade:
    grade = get_or_create_grade(db, enrollment_id)
    grade.process_score = score
    grade.updated_by = updater_id
    grade.updated_at = datetime.now(timezone.utc)
    recalculate_total(grade)
    db.commit()
    db.refresh(grade)
    return grade


def update_exam_score(db: Session, enrollment_id: int, score: float, updater_id: int) -> Grade:
    grade = get_or_create_grade(db, enrollment_id)
    grade.exam_score = score
    grade.updated_by = updater_id
    grade.updated_at = datetime.now(timezone.utc)
    recalculate_total(grade)
    db.commit()
    db.refresh(grade)
    return grade
