"""Dựng payload cho AI từ DB — chỉ truy vấn dữ liệu của sinh viên được yêu cầu,
không bao giờ đưa dữ liệu sinh viên khác vào prompt (mục 7 đặc tả)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Course, CourseClass, Enrollment, Grade, HomeroomClass, Student
from app.services.course_service import get_prerequisite_ids
from app.services.enrollment_service import check_enrollment_eligibility, count_enrollments
from app.services.grade_service import compute_gpa
from app.services.llm_service import LLMError, call_llm_json
from app.services.prompts import build_course_advice_prompt, build_study_summary_prompt


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
                "schedule": cc.schedule or [],
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
                    "course_code": str(rec.get("course_code", "")),
                    "reason": str(rec.get("reason", "")),
                }
            )
    return (
        {
            "overview": str(result["overview"]) if result.get("overview") else None,
            "recommendations": recommendations,
            "warnings": [str(w) for w in result.get("warnings", [])],
            "suggestions": [str(s) for s in result.get("suggestions", [])],
            "notes": str(result["notes"]) if result.get("notes") else None,
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
                "summary": str(result.get("summary", "")),
                "warnings": [str(w) for w in result.get("warnings", [])],
                "suggestions": [str(s) for s in result.get("suggestions", [])],
            },
            False,
        )
    except LLMError:
        return {"summary": None, "warnings": [], "suggestions": []}, True
