"""Dựng payload cho AI từ DB — chỉ truy vấn dữ liệu của sinh viên được yêu cầu,
không bao giờ đưa dữ liệu sinh viên khác vào prompt (mục 7 đặc tả)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, CourseClass, Enrollment, Grade, Student
from app.services.course_service import get_prerequisite_ids
from app.services.enrollment_service import check_enrollment_eligibility, count_enrollments
from app.services.grade_service import compute_gpa, convert_score10, is_passed
from app.services.llm_service import LLMError, call_llm_json
from app.services.prompts import (
    build_class_overview_prompt,
    build_course_advice_prompt,
    build_study_summary_prompt,
)


def _plain(text: str) -> str:
    """Gỡ dấu **in đậm** model thỉnh thoảng tự thêm dù prompt đã cấm.

    Mọi panel hiển thị kết quả AI đều in văn bản thuần (không render markdown),
    nên chỉ cần bỏ cặp dấu ** — nội dung bên trong giữ nguyên.
    """
    return text.replace("**", "")


def _student_brief(db: Session, student: Student) -> dict:
    return {
        "code": student.code,
        "name": student.name,
        "major_name": student.major.name if student.major else None,
        "homeroom_class_name": student.homeroom_class.name if student.homeroom_class else None,
    }


def _grade_map(db: Session, student_id: int) -> dict[int, Grade]:
    """enrollment_id -> Grade (chỉ của sinh viên này)."""
    grades = db.scalars(
        select(Grade).join(Enrollment, Grade.enrollment_id == Enrollment.id).where(
            Enrollment.student_id == student_id
        )
    ).all()
    return {g.enrollment_id: g for g in grades}


def build_course_advice_payload(
    db: Session, student_id: int, target_year: int | None = None, target_term: int | None = None
) -> dict:
    student = db.get(Student, student_id)
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()
    grades = _grade_map(db, student_id)

    passed, taken_not_passed = [], []
    for e in enrollments:
        if e.course_class is None or e.course_class.course is None:
            continue
        course = e.course_class.course
        grade = grades.get(e.id)
        total = grade.total_score if grade else None
        entry = {"code": course.code, "name": course.name, "credits": course.credits}
        if total is not None and total >= settings.PASS_THRESHOLD:
            passed.append({**entry, "total_score": total})
        else:
            taken_not_passed.append({**entry, "total_score": total})

    # Các lớp đang mở (catalog chung — không chứa dữ liệu sinh viên nào)
    stmt = select(CourseClass).where(CourseClass.status == "open")
    if target_year is not None:
        stmt = stmt.where(CourseClass.year == target_year)
    if target_term is not None:
        stmt = stmt.where(CourseClass.term == target_term)
    open_classes = db.scalars(stmt.order_by(CourseClass.year, CourseClass.term)).all()

    open_payload = []
    for cc in open_classes:
        prereq_ids = get_prerequisite_ids(db, cc.course_id)
        prereq_codes = []
        if prereq_ids:
            prereq_codes = list(db.scalars(select(Course.code).where(Course.id.in_(prereq_ids))))
        eligible, note = check_enrollment_eligibility(db, student_id, cc.id)
        open_payload.append(
            {
                "class_id": cc.id,
                "course_code": cc.course.code,
                "course_name": cc.course.name,
                "credits": cc.course.credits,
                "year": cc.year,
                "term": cc.term,
                # Lịch cố định: 1 buổi/tuần, khối giờ chuẩn (morning/afternoon/evening)
                "time_slot": {
                    "weekday": cc.weekday,
                    "block": cc.block,
                    "room": cc.room,
                },
                "remaining_slots": max(cc.max_size - count_enrollments(db, cc.id), 0),
                "prerequisites": prereq_codes,
                "eligible": eligible,
                "eligibility_note": note,
            }
        )

    return {
        "student": _student_brief(db, student),
        "passed_courses": passed,
        "taken_not_passed": taken_not_passed,
        "open_course_classes": open_payload,
    }


def build_study_summary_payload(db: Session, student_id: int) -> dict:
    student = db.get(Student, student_id)
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.student_id == student_id)
    ).all()
    grades = _grade_map(db, student_id)

    terms: dict[tuple[int, int], dict] = {}
    low_score_courses = []
    for e in enrollments:
        if e.course_class is None or e.course_class.course is None:
            continue
        cc = e.course_class
        grade = grades.get(e.id)
        total = grade.total_score if grade else None
        key = (cc.year, cc.term)
        term = terms.setdefault(
            key, {"year": cc.year, "term": cc.term, "credits_registered": 0, "courses": []}
        )
        term["credits_registered"] += cc.course.credits
        term["courses"].append(
            {"code": cc.course.code, "name": cc.course.name, "total_score": total}
        )
        if total is not None:
            if total < settings.PASS_THRESHOLD:
                low_score_courses.append(
                    {"code": cc.course.code, "name": cc.course.name, "total_score": total}
                )

    term_list = []
    for term in sorted(terms.values(), key=lambda t: (t["year"], t["term"])):
        scored = [c["total_score"] for c in term["courses"] if c["total_score"] is not None]
        term["avg_total_score"] = round(sum(scored) / len(scored), 2) if scored else None
        term_list.append(term)

    gpa4, _, _, _ = compute_gpa(db, student_id)
    return {
        "student": _student_brief(db, student),
        "terms": term_list,
        "low_score_courses": low_score_courses,
        # GPA hệ 4 theo tín chỉ (chỉ HP tính vào GPA) — không lấy trung bình đơn giản
        "overall_gpa": gpa4,
    }


async def run_course_advice(
    db: Session, student_id: int, target_year: int | None, target_term: int | None
) -> tuple[dict, list[dict], bool]:
    """Trả về (ai_result, eligible_classes, fallback).

    ai_result = {overview, recommendations, warnings, suggestions, notes}.
    """
    payload = build_course_advice_payload(db, student_id, target_year, target_term)
    open_ids = {c["class_id"] for c in payload["open_course_classes"]}
    eligible = [c for c in payload["open_course_classes"] if c["eligible"]]

    empty = {"overview": None, "recommendations": [], "warnings": [],
             "suggestions": [], "notes": None}
    try:
        result = await call_llm_json(build_course_advice_prompt(payload))
    except LLMError:
        return empty, eligible, True

    recommendations = []
    for rec in result.get("recommended", []):
        cc_id = rec.get("course_class_id")
        # Validate: chỉ chấp nhận lớp thực sự đang mở — không tin output AI
        if isinstance(cc_id, int) and cc_id in open_ids:
            recommendations.append(
                {
                    "course_class_id": cc_id,
                    "course_code": _plain(str(rec.get("course_code", ""))),
                    "reason": _plain(str(rec.get("reason", ""))),
                }
            )
    return (
        {
            "overview": _plain(str(result["overview"])) if result.get("overview") else None,
            "recommendations": recommendations,
            "warnings": [_plain(str(w)) for w in result.get("warnings", [])],
            "suggestions": [_plain(str(s)) for s in result.get("suggestions", [])],
            "notes": _plain(str(result["notes"])) if result.get("notes") else None,
        },
        eligible,
        False,
    )


async def run_study_summary(db: Session, student_id: int) -> tuple[dict, bool]:
    """Trả về (ai_result, fallback); ai_result = {summary, warnings, suggestions}."""
    payload = build_study_summary_payload(db, student_id)
    try:
        result = await call_llm_json(build_study_summary_prompt(payload))
        return (
            {
                "summary": _plain(str(result.get("summary", ""))),
                "warnings": [_plain(str(w)) for w in result.get("warnings", [])],
                "suggestions": [_plain(str(s)) for s in result.get("suggestions", [])],
            },
            False,
        )
    except LLMError:
        return {"summary": None, "warnings": [], "suggestions": []}, True


# Ngưỡng cảnh báo rủi ro học vụ cho AI đánh giá lớp (GPA hệ 4 / số môn / điểm hệ 10).
RISK_GPA_HIGH = 2.0       # dưới ngưỡng này → nguy cơ cao
RISK_GPA_MEDIUM = 2.5     # dưới ngưỡng này → nguy cơ trung bình
RISK_FAILED_HIGH = 3      # từ số môn nợ này trở lên → nguy cơ cao
RISK_TREND_DROP = -1.0    # TB kỳ gần giảm quá ngưỡng so kỳ liền trước → nguy cơ trung bình
RISK_TREND_RISE = 1.0     # TB kỳ gần tăng quá ngưỡng so kỳ liền trước → tính là đi lên


def _class_score_rows(db: Session, homeroom_id: int) -> dict[int, list[tuple]]:
    """student_id -> [(year, term, total_score, credits, counted_in_gpa)] của cả lớp — 1 query."""
    rows = db.execute(
        select(
            Enrollment.student_id,
            CourseClass.year,
            CourseClass.term,
            Grade.total_score,
            Course.credits,
            Course.counted_in_gpa,
        )
        .join(Grade, Grade.enrollment_id == Enrollment.id)
        .join(CourseClass, CourseClass.id == Enrollment.course_class_id)
        .join(Course, Course.id == CourseClass.course_id)
        .where(
            Enrollment.student_id.in_(
                select(Student.id).where(Student.class_id == homeroom_id)
            )
        )
    ).all()
    by_student: dict[int, list[tuple]] = {}
    for sid, year, term, total, credits, counted in rows:
        by_student.setdefault(sid, []).append((year, term, total, credits, counted))
    return by_student


def _student_metrics(score_rows: list[tuple]) -> dict:
    """GPA/tín chỉ/nợ môn/xu hướng của 1 SV — đúng ngữ nghĩa compute_gpa
    (F vẫn tính vào GPA, HP counted_in_gpa=False loại khỏi GPA nhưng Đạt vẫn cộng tích lũy)."""
    weighted4 = weighted10 = 0.0
    credits = accumulated = failed = 0
    term_scores: dict[tuple[int, int], list[float]] = {}
    for _year, _term, total, n_credits, counted in score_rows:
        if total is None:
            continue
        letter, score4 = convert_score10(total)
        if is_passed(letter):
            accumulated += n_credits  # tích lũy: ngữ nghĩa compute_gpa (D vẫn cộng)
        if total < settings.PASS_THRESHOLD:
            # nợ môn: cùng ngưỡng 5.0 với trang thống kê & kiểm tra tiên quyết
            failed += 1
        term_scores.setdefault((_year, _term), []).append(total)
        if not counted:
            continue
        weighted4 += (score4 or 0) * n_credits
        weighted10 += total * n_credits
        credits += n_credits

    gpa4 = round(weighted4 / credits, 2) if credits else None
    gpa10 = round(weighted10 / credits, 2) if credits else None
    trend = None
    if len(term_scores) >= 2:
        avgs = [
            round(sum(v) / len(v), 2) for _, v in sorted(term_scores.items())
        ]
        trend = round(avgs[-1] - avgs[-2], 2)
    return {
        "gpa4": gpa4,
        "gpa10": gpa10,
        "accumulated_credits": accumulated,
        "failed_count": failed,
        "trend": trend,
    }


def _risk_level(m: dict) -> str | None:
    """Mức rủi ro học vụ theo rule server (không do AI quyết định)."""
    gpa4, failed, trend = m["gpa4"], m["failed_count"], m["trend"]
    if gpa4 is None:
        return None
    if gpa4 < RISK_GPA_HIGH or failed >= RISK_FAILED_HIGH:
        return "high"
    if gpa4 < RISK_GPA_MEDIUM or failed >= 1 or (trend is not None and trend <= RISK_TREND_DROP):
        return "medium"
    return "low"


async def run_class_overview(db: Session, homeroom_id: int) -> dict:
    """AI đánh giá TỔNG QUAN lớp hành chính cho cố vấn (điểm mạnh/điểm yếu/gợi ý).

    Bảo mật tối đa: payload gửi LLM chỉ là SỐ LIỆU TỔNG HỢP của cả lớp —
    không có dữ liệu riêng của bất kỳ sinh viên nào (kể cả mã giả), tất nhiên
    càng không tên/MSSV. AI chỉ diễn giải ở mức lớp; mọi con số hiển thị
    (stats) do server tự tính — không tin output AI.
    """
    students = db.scalars(
        select(Student).where(Student.class_id == homeroom_id).order_by(Student.id)
    ).all()
    by_student = _class_score_rows(db, homeroom_id)

    metrics = [_student_metrics(by_student.get(s.id, [])) for s in students]
    graded = [m for m in metrics if m["gpa4"] is not None]
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    for m in metrics:
        level = _risk_level(m)
        if level:
            risk_counts[level] += 1

    stats = {
        "class_size": len(students),
        "students_with_grades": len(graded),
        "students_without_grades": len(students) - len(graded),
        "avg_gpa4": (
            round(sum(m["gpa4"] for m in graded) / len(graded), 2) if graded else None
        ),
        "avg_gpa10": (
            round(sum(m["gpa10"] for m in graded) / len(graded), 2) if graded else None
        ),
        "risk_counts": risk_counts,
    }

    # Payload tổng hợp: đủ màu để nhận xét điểm mạnh/yếu nhưng không đếm xấu ai
    payload = {
        **stats,
        "highest_gpa4": max((m["gpa4"] for m in graded), default=None),
        "lowest_gpa4": min((m["gpa4"] for m in graded), default=None),
        "total_failed_courses": sum(m["failed_count"] for m in metrics),
        "students_with_failed_courses": sum(1 for m in metrics if m["failed_count"] > 0),
        "avg_accumulated_credits": (
            round(sum(m["accumulated_credits"] for m in graded) / len(graded), 1)
            if graded
            else None
        ),
        "students_declining": sum(
            1 for m in metrics if m["trend"] is not None and m["trend"] <= RISK_TREND_DROP
        ),
        "students_improving": sum(
            1 for m in metrics if m["trend"] is not None and m["trend"] >= RISK_TREND_RISE
        ),
    }

    try:
        result = await call_llm_json(build_class_overview_prompt(payload))
    except LLMError:
        return {
            "summary": None,
            "strengths": [],
            "weaknesses": [],
            "suggestions": [],
            "stats": stats,
            "fallback": True,
        }

    return {
        "summary": _plain(str(result.get("summary", ""))).strip() or None,
        "strengths": [_plain(str(x)) for x in result.get("strengths", [])],
        "weaknesses": [_plain(str(x)) for x in result.get("weaknesses", [])],
        "suggestions": [_plain(str(x)) for x in result.get("suggestions", [])],
        "stats": stats,
        "fallback": False,
    }
