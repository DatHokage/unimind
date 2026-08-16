"""Seed dữ liệu demo — idempotent (bỏ qua nếu đã tồn tại).

Chạy:  python -m app.seed   (từ thư mục backend/)
"""

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.services.grade_service import recalculate_total
from app.models import (
    Course,
    CourseClass,
    Enrollment,
    Grade,
    HomeroomClass,
    Lecturer,
    Major,
    Prerequisite,
    Student,
    User,
)

PASSWORD = "password123"


def _get_or_create_user(db: Session, username: str, role: str, **fk) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user:
        return user
    user = User(username=username, password_hash=hash_password(PASSWORD), role=role, **fk)
    db.add(user)
    db.flush()
    print(f"  + tài khoản {username}/{PASSWORD} ({role})")
    return user


def _get_or_create(db: Session, model, where: dict, **fields):
    obj = db.scalar(select(model).filter_by(**where))
    if obj:
        return obj, False
    obj = model(**where, **fields)
    db.add(obj)
    db.flush()
    return obj, True


def _enroll_with_grade(
    db: Session,
    sv: Student,
    cc: CourseClass,
    process: float,
    exam: float,
    enrolled_at: datetime.datetime,
    updated_at: datetime.datetime,
) -> Enrollment:
    """Đăng ký + điểm (total/letter/score4 do recalculate_total tính) — bỏ qua nếu đã tồn tại."""
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == sv.id, Enrollment.course_class_id == cc.id
        )
    )
    if enrollment:
        return enrollment
    enrollment = Enrollment(
        student_id=sv.id,
        course_class_id=cc.id,
        enrolled_at=enrolled_at,
        status="approved",
    )
    db.add(enrollment)
    db.flush()
    grade = Grade(
        enrollment_id=enrollment.id,
        process_score=process,
        exam_score=exam,
        updated_at=updated_at,
    )
    recalculate_total(grade)  # total + letter_grade + score4 theo logic backend
    db.add(grade)
    return enrollment


def seed(db: Session) -> None:
    # --- Ngành ---
    major, _ = _get_or_create(db, Major, {"code": "CNTT"}, name="Công nghệ thông tin")

    # --- Giảng viên + tài khoản ---
    gv_an, _ = _get_or_create(
        db, Lecturer, {"code": "GV001"}, name="Nguyễn Văn An", department="CNTT"
    )
    _get_or_create_user(db, "advisor1", "advisor", lecturer_id=gv_an.id)

    gv_binh, _ = _get_or_create(
        db, Lecturer, {"code": "GV002"}, name="Trần Thị Bình", department="CNTT"
    )
    _get_or_create_user(db, "lecturer1", "lecturer", lecturer_id=gv_binh.id)

    # --- Phòng đào tạo ---
    _get_or_create_user(db, "ptdt", "training_office")

    # --- Lớp hành chính (advisor1 phụ trách cả 2 lớp) ---
    hc1, _ = _get_or_create(
        db, HomeroomClass, {"name": "CNTT1-K12"}, major_id=major.id, cohort=2023, advisor_id=gv_an.id
    )
    hc2, _ = _get_or_create(
        db, HomeroomClass, {"name": "CNTT2-K12"}, major_id=major.id, cohort=2023, advisor_id=gv_an.id
    )

    # --- Sinh viên ---
    students = {}
    student_data = [
        ("SV001", "Phạm Văn Nhất", "student1", hc1),
        ("SV002", "Lê Thị Nhị", "student2", hc1),
        ("SV003", "Hoàng Văn Tam", "student3", hc1),
        ("SV004", "Đỗ Thị Tư", "student4", hc2),
    ]
    for code, name, username, hc in student_data:
        sv, _ = _get_or_create(
            db, Student, {"code": code},
            name=name,
            dob=datetime.date(2005, 3, 15),
            major_id=major.id,
            class_id=hc.id,
        )
        _get_or_create_user(db, username, "student", student_id=sv.id)
        students[code] = sv

    # --- Học phần: TH1 → CTDL → OOP; TH1 → CSDL; GDTC1 + GT1 (không tiên quyết) ---
    th1, _ = _get_or_create(db, Course, {"code": "TH1"}, name="Tin học cơ sở", credits=2)
    gdtc1, _ = _get_or_create(
        db, Course, {"code": "GDTC1"}, name="Giáo dục thể chất 1", credits=1,
        counted_in_gpa=False,  # HP không tính vào GPA tích lũy
    )
    if gdtc1.counted_in_gpa:  # DB seed cũ để True — ép về False theo nghiệp vụ demo
        gdtc1.counted_in_gpa = False
    gt1, _ = _get_or_create(
        db, Course, {"code": "GT1"}, name="Giải tích 1", credits=3,
    )
    ctdl, _ = _get_or_create(db, Course, {"code": "CTDL"}, name="Cấu trúc dữ liệu", credits=3)
    oop, _ = _get_or_create(db, Course, {"code": "OOP"}, name="Lập trình hướng đối tượng", credits=3)
    csdl, _ = _get_or_create(db, Course, {"code": "CSDL"}, name="Cơ sở dữ liệu", credits=3)

    for course, prereq in ((ctdl, th1), (oop, ctdl), (csdl, th1)):
        exists = db.scalar(
            select(Prerequisite).filter_by(course_id=course.id, prerequisite_course_id=prereq.id)
        )
        if not exists:
            db.add(Prerequisite(course_id=course.id, prerequisite_course_id=prereq.id))

    # --- Lớp học phần kỳ 2025-T1 (đã kết thúc, có điểm) ---
    th1_a, _ = _get_or_create(
        db, CourseClass, {"course_id": th1.id, "year": 2025, "term": 1},
        lecturer_id=gv_binh.id, max_size=40, status="closed",
        schedule=[{"weekday": 2, "start_period": 1, "end_period": 3, "room": "A101"}],
    )

    # Điểm TH1.A: SV001 đạt 7.5, SV002 trượt 4.0, SV003 đạt 6.0, SV004 đạt 7.0
    grades_2025 = {
        "SV001": (8.0, 7.0),   # total 7.5 → đủ tiên quyết học CTDL/CSDL
        "SV002": (5.0, 3.0),   # total 4.0 → trượt, demo chặn tiên quyết
        "SV003": (6.0, 6.0),   # total 6.0
        "SV004": (7.0, 7.0),   # total 7.0
    }
    for code, (process, exam) in grades_2025.items():
        _enroll_with_grade(
            db, students[code], th1_a, process, exam,
            enrolled_at=datetime.datetime(2025, 1, 5, tzinfo=datetime.timezone.utc),
            updated_at=datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc),
        )

    # --- Lớp học phần kỳ 2025-T2 (đã kết thúc, có điểm) — dữ liệu demo cho SV004 ---
    ctdl_b, _ = _get_or_create(
        db, CourseClass, {"course_id": ctdl.id, "year": 2025, "term": 2},
        lecturer_id=gv_binh.id, max_size=40, status="closed",
        schedule=[{"weekday": 3, "start_period": 1, "end_period": 3, "room": "B204"}],
    )
    gdtc1_b, _ = _get_or_create(
        db, CourseClass, {"course_id": gdtc1.id, "year": 2025, "term": 2},
        lecturer_id=gv_binh.id, max_size=30, status="closed",
        schedule=[{"weekday": 5, "start_period": 7, "end_period": 9, "room": "Sân"}],
    )
    gt1_b, _ = _get_or_create(
        db, CourseClass, {"course_id": gt1.id, "year": 2025, "term": 2},
        lecturer_id=gv_binh.id, max_size=40, status="closed",
        schedule=[{"weekday": 6, "start_period": 1, "end_period": 3, "room": "A102"}],
    )

    # SV004 kỳ 2025-T2: 1 môn đạt C (tích lũy), 1 môn đạt A nhưng không tính GPA,
    # 1 môn trượt F (tính vào GPA nhưng KHÔNG cộng tín chỉ tích lũy)
    _enroll_with_grade(
        db, students["SV004"], ctdl_b, 6.0, 5.0,     # total 5.5 → C/2 → Đạt
        enrolled_at=datetime.datetime(2025, 7, 5, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc),
    )
    _enroll_with_grade(
        db, students["SV004"], gdtc1_b, 9.0, 9.0,    # total 9.0 → A/4 → Đạt (không tính GPA)
        enrolled_at=datetime.datetime(2025, 7, 5, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc),
    )
    _enroll_with_grade(
        db, students["SV004"], gt1_b, 3.0, 2.0,      # total 2.5 → F/0 → KHÔNG đạt
        enrolled_at=datetime.datetime(2025, 7, 5, tzinfo=datetime.timezone.utc),
        updated_at=datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc),
    )

    # --- Lớp học phần kỳ 2026-T1 (đang mở cho demo đăng ký) ---
    open_classes = [
        # (course, lịch, max_size) — chú thích demo
        (ctdl, [{"weekday": 3, "start_period": 4, "end_period": 6, "room": "B201"}], 40),
        (csdl, [{"weekday": 4, "start_period": 1, "end_period": 3, "room": "B202"}], 2),   # demo đầy sĩ số
        (oop, [{"weekday": 3, "start_period": 4, "end_period": 6, "room": "B203"}], 40),    # demo trùng lịch với CTDL.A
        (gdtc1, [{"weekday": 5, "start_period": 7, "end_period": 9, "room": "Sân"}], 30),
    ]
    for course, schedule, max_size in open_classes:
        cc, _ = _get_or_create(
            db, CourseClass, {"course_id": course.id, "year": 2026, "term": 1},
            lecturer_id=gv_binh.id, max_size=max_size, status="open", schedule=schedule,
        )
        if course is csdl:
            # Demo đầy sĩ số: SV003 + SV004 chiếm đủ 2 chỗ của CSDL.A (max_size=2)
            for code in ("SV003", "SV004"):
                exists = db.scalar(
                    select(Enrollment).where(
                        Enrollment.student_id == students[code].id,
                        Enrollment.course_class_id == cc.id,
                    )
                )
                if not exists:
                    db.add(Enrollment(
                        student_id=students[code].id, course_class_id=cc.id,
                        enrolled_at=datetime.datetime(2026, 1, 5, tzinfo=datetime.timezone.utc),
                        status="approved",
                    ))

    # --- OOP.B kỳ 2026-T1 (đang mở) — SV004 học tiếp sau khi đạt CTDL 2025-T2.
    # Lịch thứ 6 để không trùng CSDL.A (thứ 4) của SV004; nhận diện bằng phòng B205.
    oop_b = next(
        (
            c
            for c in db.scalars(
                select(CourseClass).filter_by(course_id=oop.id, year=2026, term=1)
            ).all()
            if any(s.get("room") == "B205" for s in (c.schedule or []))
        ),
        None,
    )
    if oop_b is None:
        oop_b = CourseClass(
            course_id=oop.id, lecturer_id=gv_binh.id, year=2026, term=1,
            max_size=40, status="open",
            schedule=[{"weekday": 6, "start_period": 1, "end_period": 3, "room": "B205"}],
        )
        db.add(oop_b)
        db.flush()
    if not db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == students["SV004"].id,
            Enrollment.course_class_id == oop_b.id,
        )
    ):
        db.add(Enrollment(
            student_id=students["SV004"].id, course_class_id=oop_b.id,
            enrolled_at=datetime.datetime(2026, 1, 6, tzinfo=datetime.timezone.utc),
            status="approved",
        ))

    db.commit()
    print("Seed hoàn tất.")
    print("\nTài khoản demo (mật khẩu chung: password123):")
    print("  ptdt      — Phòng đào tạo")
    print("  lecturer1 — Giảng viên Trần Thị Bình")
    print("  advisor1  — Cố vấn Nguyễn Văn An (phụ trách CNTT1-K12, CNTT2-K12)")
    print("  student1  — SV001 Phạm Văn Nhất (đã đạt TH1)")
    print("  student2  — SV002 Lê Thị Nhị (trượt TH1 → demo chặn tiên quyết)")
    print("  student3  — SV003 Hoàng Văn Tam")
    print("  student4  — SV004 Đỗ Thị Tư (lớp CNTT2-K12) — đủ dữ liệu demo:")
    print("              3 học kỳ, 6 đăng ký: môn đạt B/C, môn trượt F,")
    print("              môn chưa có điểm, HP không tính GPA (GDTC1)")


def main():
    # Console Windows mặc định cp1252 — ép UTF-8 để in tiếng Việt không lỗi
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
