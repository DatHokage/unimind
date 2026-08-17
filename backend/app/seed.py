"""Seed dữ liệu demo — idempotent (bỏ qua nếu đã tồn tại).

Chạy:  python -m app.seed             (từ thư mục backend/ — an toàn khi deploy)
       python -m app.seed --wipe      (XÓA SẠCH dữ liệu rồi nạp lại từ đầu)

Cấu trúc seed (đủ số lượng để demo phân trang/tìm kiếm trên web):
  - 1 admin (tài khoản DTCAD001 — role training_office, quản trị hệ thống)
  - 3 ngành · 6 giảng viên (DTCGV001..006) · 4 cố vấn (DTCCV001..004)
  - 4 lớp hành chính · 15 sinh viên (DTC001..DTC015) · 15 học phần
  - Tiên quyết: TH1 → CTDL → OOP · TH1 → CSDL
  - 2025-T1: TH1.A (đóng, có điểm 10 SV)
  - 2025-T2: CTDL.B / GDTC1.B / GT1.B (đóng, có điểm)
  - 2026-T1: 8 lớp đang mở (CTDL×2, CSDL max_size=2, OOP×2, GDTC1, GT2, AV1)
    phục vụ demo đăng ký; DTC003+DTC004 chiếm đủ chỗ CSDL.A, DTC004 học OOP.B.

Sinh viên demo chính (các dữ liệu khác được thiết kế để KHÔNG làm lệch số liệu):
  - DTC001 (student1): TH1 7.5 (B) → đăng ký được CTDL/CSDL
  - DTC002 (student2): TH1 4.0 (D nhưng < 5.0) → demo chặn tiên quyết
  - DTC003 (student3): TH1 6.0 (C) + đang học CSDL.A
  - DTC004 (student4): đủ 3 học kỳ → GPA 1.50 / 4.75, tích lũy 6 TC
    (GDTC1 đạt A nhưng không tính GPA — counted_in_gpa=False)

Mọi tài khoản dùng chung mật khẩu: password123.
"""

import datetime
from argparse import ArgumentParser

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base
from app.models import (
    Advisor,
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
from app.services.grade_service import recalculate_total

PASSWORD = "password123"

# ---------- Danh mục dữ liệu (thêm/bớt tại đây, seed tự chạy theo) ----------

MAJORS = [
    ("CNTT", "Công nghệ thông tin"),
    ("ATTT", "An toàn thông tin"),
    ("KHMT", "Khoa học máy tính"),
]

LECTURERS = [
    # (mã, tên, khoa, tài khoản hoặc None) — tài khoản đăng nhập = mã giảng viên (DTCGV00x)
    ("DTCGV001", "Nguyễn Văn An", "CNTT", "DTCGV001"),
    ("DTCGV002", "Trần Thị Bình", "CNTT", "DTCGV002"),
    ("DTCGV003", "Lê Minh Châu", "CNTT", None),
    ("DTCGV004", "Phạm Quốc Dũng", "Toán", None),
    ("DTCGV005", "Hoàng Hải Hà", "Ngoại ngữ", None),
    ("DTCGV006", "Vũ Thanh Tùng", "Giáo dục thể chất", None),
]

ADVISORS = [
    # (mã, tên, tài khoản) — cố vấn học tập là hồ sơ RIÊNG (bảng advisor),
    # không phải giảng viên; tài khoản = mã, role "advisor"
    ("DTCCV001", "Ngô Thị Lan", "DTCCV001"),
    ("DTCCV002", "Đinh Công Sơn", "DTCCV002"),
    ("DTCCV003", "Bùi Thị Huế", "DTCCV003"),
    ("DTCCV004", "Hồ Anh Tuấn", "DTCCV004"),  # không phụ trách lớp nào — demo /mine rỗng
]

HOMEROOMS = [
    # (tên lớp, mã ngành, khóa, mã cố vấn) — DTCCV001 phụ trách 2 lớp (demo /mine = 2)
    ("CNTT1-K12", "CNTT", 2023, "DTCCV001"),
    ("CNTT2-K12", "CNTT", 2023, "DTCCV001"),
    ("CNTT1-K11", "CNTT", 2022, "DTCCV002"),
    ("ATTT1-K12", "ATTT", 2023, "DTCCV003"),
]

STUDENTS = [
    # (mã, tên, tài khoản, tên lớp hành chính, ngày sinh) — tài khoản = mã sinh viên
    ("DTC001", "Phạm Văn Nhất", "DTC001", "CNTT1-K12", datetime.date(2005, 3, 15)),
    ("DTC002", "Lê Thị Nhị", "DTC002", "CNTT1-K12", datetime.date(2005, 7, 22)),
    ("DTC003", "Hoàng Văn Tam", "DTC003", "CNTT1-K12", datetime.date(2005, 11, 8)),
    ("DTC004", "Đỗ Thị Tư", "DTC004", "CNTT2-K12", datetime.date(2005, 1, 30)),
    ("DTC005", "Vũ Thị Năm", "DTC005", "CNTT2-K12", datetime.date(2005, 5, 12)),
    ("DTC006", "Đặng Văn Sáu", "DTC006", "CNTT2-K12", datetime.date(2004, 9, 3)),
    ("DTC007", "Bùi Thị Bảy", "DTC007", "CNTT1-K11", datetime.date(2004, 12, 25)),
    ("DTC008", "Ngô Văn Tám", "DTC008", "CNTT1-K11", datetime.date(2005, 4, 18)),
    ("DTC009", "Đinh Thị Chín", "DTC009", "CNTT1-K11", datetime.date(2005, 8, 6)),
    ("DTC010", "Hồ Văn Mười", "DTC010", "ATTT1-K12", datetime.date(2004, 10, 14)),
    ("DTC011", "Dương Thị Mười Một", "DTC011", "ATTT1-K12", datetime.date(2004, 6, 28)),
    ("DTC012", "Trịnh Văn Mười Hai", "DTC012", "CNTT1-K12", datetime.date(2005, 2, 11)),
    ("DTC013", "Phan Thị Mười Ba", "DTC013", "CNTT2-K12", datetime.date(2005, 6, 9)),
    ("DTC014", "Lý Văn Mười Bốn", "DTC014", "CNTT1-K11", datetime.date(2004, 8, 21)),
    ("DTC015", "Trần Thị Mười Lăm", "DTC015", "ATTT1-K12", datetime.date(2004, 4, 2)),
]

COURSES = [
    # (mã, tên, tín chỉ, tính vào GPA)
    ("TH1", "Tin học cơ sở", 2, True),
    ("GDTC1", "Giáo dục thể chất 1", 1, False),
    ("GT1", "Giải tích 1", 3, True),
    ("CTDL", "Cấu trúc dữ liệu", 3, True),
    ("OOP", "Lập trình hướng đối tượng", 3, True),
    ("CSDL", "Cơ sở dữ liệu", 3, True),
    ("KTLT", "Kỹ thuật lập trình", 3, True),
    ("MANG", "Mạng máy tính", 3, True),
    ("HDT", "Hệ điều hành", 3, True),
    ("PTPM", "Phát triển phần mềm", 3, True),
    ("TTNT", "Trí tuệ nhân tạo", 3, True),
    ("BMT", "Bảo mật thông tin", 3, True),
    ("LAPWEB", "Lập trình web", 3, True),
    ("GT2", "Giải tích 2", 3, True),
    ("AV1", "Tiếng Anh chuyên ngành 1", 2, True),
]

PREREQUISITES = [
    ("CTDL", "TH1"),
    ("OOP", "CTDL"),
    ("CSDL", "TH1"),
]


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


def _get_or_create_class(
    db: Session, course: Course, lecturer: Lecturer, sched: dict, max_size: int,
    year: int = 2026, term: int = 1,
) -> CourseClass:
    """Lớp học phần định danh bằng (học phần, kỳ, PHÒNG) — cùng 1 học phần mở
    nhiều lớp trong 1 kỳ (CTDL.A/CTDL.B...) nên không thể chỉ khóa theo kỳ."""
    for cc in db.scalars(
        select(CourseClass).filter_by(course_id=course.id, year=year, term=term)
    ).all():
        if any(s.get("room") == sched["room"] for s in (cc.schedule or [])):
            return cc
    cc = CourseClass(
        course_id=course.id, lecturer_id=lecturer.id, year=year, term=term,
        max_size=max_size, status="open", schedule=[sched],
    )
    db.add(cc)
    db.flush()
    return cc


def _approve(db: Session, sv: Student, cc: CourseClass, enrolled_at: datetime.datetime) -> None:
    """Đăng ký không điểm (lớp đang học) — bỏ qua nếu đã tồn tại."""
    exists = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == sv.id, Enrollment.course_class_id == cc.id
        )
    )
    if exists:
        return
    db.add(Enrollment(
        student_id=sv.id, course_class_id=cc.id,
        enrolled_at=enrolled_at, status="approved",
    ))


def _utc(y: int, m: int, d: int) -> datetime.datetime:
    return datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)


def seed(db: Session) -> None:
    # --- Ngành ---
    majors = {}
    for code, name in MAJORS:
        majors[code], _ = _get_or_create(db, Major, {"code": code}, name=name)

    # --- Giảng viên ---
    lecturers = {}
    for code, name, department, username in LECTURERS:
        gv, _ = _get_or_create(db, Lecturer, {"code": code}, name=name, department=department)
        lecturers[code] = gv
        # Tài khoản giảng viên = MÃ (DTCGV00x): DB cũ còn tài khoản dạng khác
        # (lecturer1…) thì đổi tên theo mã thay vì tạo thêm — tránh đụng unique lecturer_id
        old = db.scalar(select(User).where(User.lecturer_id == gv.id, User.username != code))
        if old:
            print(f"  ~ đổi tên tài khoản {old.username} → {code}")
            old.username = code
            db.flush()
        if username:
            _get_or_create_user(db, username, "lecturer", lecturer_id=gv.id)

    # --- Cố vấn học tập (bảng advisor riêng, KHÔNG phải giảng viên) ---
    # Dọn vết tích cũ: DB seed trước bản tách advisor còn lưu cố vấn trong bảng
    # lecturer (mã DTCCV*) và trỏ users.lecturer_id — xóa hàng lecturer cũ trước
    # (đã được migration chuyển sang advisor; seed chưa bao giờ gán lớp học phần
    # cho cố vấn nên không ảnh hưởng dữ liệu dạy/học).
    for gv in db.scalars(select(Lecturer).where(Lecturer.code.like("DTCCV%"))).all():
        for u in db.scalars(select(User).where(User.lecturer_id == gv.id)).all():
            u.lecturer_id = None
        db.delete(gv)
    db.flush()

    advisors = {}
    for code, name, username in ADVISORS:
        cv, _ = _get_or_create(db, Advisor, {"code": code}, name=name)
        advisors[code] = cv
        # Đổi tài khoản cũ (advisor1…) sang mã — cùng logic với giảng viên
        old = db.scalar(select(User).where(User.advisor_id == cv.id, User.username != username))
        if old:
            print(f"  ~ đổi tên tài khoản {old.username} → {username}")
            old.username = username
            db.flush()
        _get_or_create_user(db, username, "advisor", advisor_id=cv.id)

    # --- Phòng đào tạo + admin (admin = quản trị hệ thống, dùng role training_office) ---
    _get_or_create_user(db, "ptdt", "training_office")
    _get_or_create_user(db, "DTCAD001", "training_office")

    # --- Lớp hành chính ---
    homerooms = {}
    for name, major_code, cohort, advisor_code in HOMEROOMS:
        hc, _ = _get_or_create(
            db, HomeroomClass, {"name": name},
            major_id=majors[major_code].id, cohort=cohort,
            advisor_id=advisors[advisor_code].id,
        )
        homerooms[name] = hc

    # --- Sinh viên ---
    students = {}
    for code, name, username, hc_name, dob in STUDENTS:
        sv, _ = _get_or_create(
            db, Student, {"code": code},
            name=name, dob=dob,
            major_id=majors["CNTT" if hc_name.startswith(("CNTT",)) else "ATTT"].id,
            class_id=homerooms[hc_name].id,
        )
        # Tài khoản sinh viên = MÃ (DTC00x): DB cũ còn tài khoản dạng khác
        # (student1…) thì đổi tên theo mã thay vì tạo thêm — tránh đụng unique student_id
        old = db.scalar(select(User).where(User.student_id == sv.id, User.username != username))
        if old:
            print(f"  ~ đổi tên tài khoản {old.username} → {username}")
            old.username = username
            db.flush()
        _get_or_create_user(db, username, "student", student_id=sv.id)
        students[code] = sv

    # --- Học phần + tiên quyết ---
    courses = {}
    for code, name, credits, counted in COURSES:
        c, _ = _get_or_create(
            db, Course, {"code": code},
            name=name, credits=credits, counted_in_gpa=counted,
        )
        if code == "GDTC1" and c.counted_in_gpa:  # DB seed cũ để True — ép về False
            c.counted_in_gpa = False
        courses[code] = c

    for code, prereq_code in PREREQUISITES:
        exists = db.scalar(
            select(Prerequisite).filter_by(
                course_id=courses[code].id,
                prerequisite_course_id=courses[prereq_code].id,
            )
        )
        if not exists:
            db.add(Prerequisite(
                course_id=courses[code].id,
                prerequisite_course_id=courses[prereq_code].id,
            ))

    # --- Kỳ 2025-T1 (đóng, đã có điểm) — TH1.A do DTCGV001 dạy ---
    th1_a, _ = _get_or_create(
        db, CourseClass, {"course_id": courses["TH1"].id, "year": 2025, "term": 1},
        lecturer_id=lecturers["DTCGV001"].id, max_size=40, status="closed",
        schedule=[{"weekday": 2, "start_period": 1, "end_period": 3, "room": "A101"}],
    )
    # Điểm TH1.A: DTC001/DTC003/DTC004 đạt (≥5.0 → đủ tiên quyết CTDL/CSDL);
    # DTC002 chỉ 4.0 (điểm chữ D nhưng < ngưỡng qua môn 5.0) → demo chặn tiên quyết
    grades_th1 = {
        "DTC001": (8.0, 7.0),   # 7.5 → B
        "DTC002": (5.0, 3.0),   # 4.0 → D (< 5.0 → chưa qua môn)
        "DTC003": (6.0, 6.0),   # 6.0 → C
        "DTC004": (7.0, 7.0),   # 7.0 → B
        "DTC005": (7.5, 7.5),   # 7.5 → B
        "DTC006": (6.5, 5.5),   # 6.0 → C
        "DTC007": (5.0, 6.0),   # 5.5 → C
        "DTC008": (7.0, 6.0),   # 6.5 → C
        "DTC009": (8.0, 7.0),   # 7.5 → B
        "DTC010": (8.5, 7.5),   # 8.0 → B
    }
    for code, (process, exam) in grades_th1.items():
        _enroll_with_grade(
            db, students[code], th1_a, process, exam,
            enrolled_at=_utc(2025, 1, 5), updated_at=_utc(2025, 6, 1),
        )

    # --- Kỳ 2025-T2 (đóng, đã có điểm) — dữ liệu GPA cho DTC004 + vài SV khác ---
    ctdl_b, _ = _get_or_create(
        db, CourseClass, {"course_id": courses["CTDL"].id, "year": 2025, "term": 2},
        lecturer_id=lecturers["DTCGV001"].id, max_size=40, status="closed",
        schedule=[{"weekday": 3, "start_period": 1, "end_period": 3, "room": "B204"}],
    )
    gdtc1_b, _ = _get_or_create(
        db, CourseClass, {"course_id": courses["GDTC1"].id, "year": 2025, "term": 2},
        lecturer_id=lecturers["DTCGV006"].id, max_size=30, status="closed",
        schedule=[{"weekday": 5, "start_period": 7, "end_period": 9, "room": "Sân vận động"}],
    )
    gt1_b, _ = _get_or_create(
        db, CourseClass, {"course_id": courses["GT1"].id, "year": 2025, "term": 2},
        lecturer_id=lecturers["DTCGV004"].id, max_size=40, status="closed",
        schedule=[{"weekday": 6, "start_period": 1, "end_period": 3, "room": "A102"}],
    )
    # DTC004 kỳ 2025-T2: 1 môn đạt C, 1 môn đạt A nhưng KHÔNG tính GPA (GDTC1),
    # 1 môn trượt F → GPA 1.50 / 4.75, tích lũy 6 TC (đúng smoke_student4.py)
    _enroll_with_grade(db, students["DTC004"], ctdl_b, 6.0, 5.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    _enroll_with_grade(db, students["DTC004"], gdtc1_b, 9.0, 9.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    _enroll_with_grade(db, students["DTC004"], gt1_b, 3.0, 2.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    # DTC005 / DTC006 học thêm kỳ 2025-T2 cho dữ liệu đa dạng
    _enroll_with_grade(db, students["DTC005"], gdtc1_b, 8.0, 8.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    _enroll_with_grade(db, students["DTC005"], gt1_b, 7.0, 6.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    _enroll_with_grade(db, students["DTC006"], gdtc1_b, 6.0, 6.0,
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))
    _enroll_with_grade(db, students["DTC006"], gt1_b, 4.0, 3.0,   # 3.5 → F
                       enrolled_at=_utc(2025, 7, 5), updated_at=_utc(2025, 12, 1))

    # --- Kỳ 2026-T1 (đang mở — phục vụ demo đăng ký học phần) ---
    # Định danh mỗi lớp bằng (mã học phần, phòng) — phòng duy nhất trong kỳ
    open_classes = [
        # (mã HP, mã GV, lịch học, max_size, chú thích demo)
        ("CTDL", "DTCGV001", {"weekday": 3, "start_period": 4, "end_period": 6, "room": "B201"}, 40,
         "CTDL.A — lớp chính cho demo đăng ký"),
        ("CTDL", "DTCGV002", {"weekday": 6, "start_period": 7, "end_period": 9, "room": "B206"}, 40,
         "CTDL.B — lớp song song"),
        ("CSDL", "DTCGV003", {"weekday": 4, "start_period": 1, "end_period": 3, "room": "B202"}, 2,
         "CSDL.A — max_size=2, seed chiếm đủ chỗ → demo 'lớp đã đầy'"),
        ("OOP", "DTCGV001", {"weekday": 3, "start_period": 4, "end_period": 6, "room": "B203"}, 40,
         "OOP.A — trùng lịch CTDL.A → demo 'trùng lịch' + chưa đạt tiên quyết"),
        ("OOP", "DTCGV002", {"weekday": 6, "start_period": 1, "end_period": 3, "room": "B205"}, 40,
         "OOP.B — DTC004 đang học"),
        ("GDTC1", "DTCGV006", {"weekday": 5, "start_period": 7, "end_period": 9, "room": "Sân vận động"}, 30,
         "GDTC1.A — không tiên quyết"),
        ("GT2", "DTCGV004", {"weekday": 7, "start_period": 1, "end_period": 3, "room": "A201"}, 40,
         "GT2.A — không tiên quyết"),
        ("AV1", "DTCGV005", {"weekday": 4, "start_period": 7, "end_period": 9, "room": "C101"}, 35,
         "AV1.A — không tiên quyết"),
    ]
    cc_by_room = {}
    for course_code, gv_code, sched, max_size, _note in open_classes:
        cc = _get_or_create_class(
            db, courses[course_code], lecturers[gv_code], sched, max_size,
        )
        cc_by_room[(course_code, sched["room"])] = cc

    # Đăng ký sẵn kỳ 2026-T1: DTC003+DTC004 lấp đầy CSDL.A; DTC004 học OOP.B;
    # khối còn lại rải vào các lớp không tiên quyết (lịch không xung đột)
    enroll_2026 = [
        ("DTC003", [("CSDL", "B202")]),
        ("DTC004", [("CSDL", "B202"), ("OOP", "B205")]),
        ("DTC005", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC006", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC007", [("CTDL", "B201"), ("GDTC1", "Sân vận động"), ("GT2", "A201")]),
        ("DTC008", [("CTDL", "B201"), ("GDTC1", "Sân vận động"), ("AV1", "C101")]),
        ("DTC009", [("CTDL", "B206"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC010", [("CTDL", "B206"), ("GDTC1", "Sân vận động"), ("GT2", "A201")]),
        ("DTC011", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC012", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC013", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC014", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
        ("DTC015", [("GDTC1", "Sân vận động"), ("GT2", "A201"), ("AV1", "C101")]),
    ]
    for code, picks in enroll_2026:
        for key in picks:
            _approve(db, students[code], cc_by_room[key], _utc(2026, 1, 5))

    db.commit()
    print("Seed hoàn tất.")
    print("\nTài khoản demo — tên đăng nhập = MÃ, mật khẩu chung: password123,")
    print("đăng nhập KHÔNG phân biệt hoa/thường (dtc001 ≡ DTC001):")
    print("  DTCAD001  — Admin / quản trị hệ thống")
    print("  ptdt      — Phòng đào tạo")
    print("  DTCGV001 — GV Nguyễn Văn An (dạy TH1.A, CTDL.B; 2026-T1: CTDL.A, OOP.A)")
    print("  DTCGV002 — GV Trần Thị Bình (2026-T1: CTDL.B, OOP.B)")
    print("  DTCCV001 — Cố vấn Ngô Thị Lan (phụ trách CNTT1-K12 + CNTT2-K12)")
    print("  DTCCV002 — Cố vấn Đinh Công Sơn (CNTT1-K11)")
    print("  DTCCV003 — Cố vấn Bùi Thị Huế (ATTT1-K12)")
    print("  DTCCV004 — Cố vấn Hồ Anh Tuấn (chưa phụ trách lớp — demo /mine rỗng)")
    print("  DTC001   — SV Phạm Văn Nhất (đạt TH1 7.5 → đăng ký được CTDL/CSDL)")
    print("  DTC002   — SV Lê Thị Nhị (TH1 4.0 → demo chặn tiên quyết)")
    print("  DTC003   — SV Hoàng Văn Tam (đạt TH1 6.0, đang học CSDL.A)")
    print("  DTC004   — SV Đỗ Thị Tư (CNTT2-K12) — đủ dữ liệu demo:")
    print("             3 học kỳ, 6 đăng ký: môn đạt B/C, môn trượt F,")
    print("             môn đang học, HP không tính GPA (GDTC1) → GPA 1.50/4.75")
    print("  DTC005..DTC015 — dữ liệu phân trang/tìm kiếm")


def wipe() -> None:
    """XÓA TOÀN BỘ dữ liệu hiện có — chỉ dùng local/demo (--wipe)."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    print("Đã XÓA sạch dữ liệu cũ.")


def main():
    # Console Windows mặc định cp1252 — ép UTF-8 để in tiếng Việt không lỗi
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = ArgumentParser(description="Nạp dữ liệu demo")
    parser.add_argument(
        "--wipe", action="store_true",
        help="Xóa sạch dữ liệu hiện có trước khi seed (chỉ dùng local/demo)",
    )
    args = parser.parse_args()

    if args.wipe:
        wipe()

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
