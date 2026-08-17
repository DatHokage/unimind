import datetime
import os

# Test: không khởi động thread warm-up RAG (tránh mở ChromaDB + gọi API Voyage/LLM)
os.environ["RAG_WARMUP"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Advisor, Base, Course, CourseClass, Enrollment, Grade, HomeroomClass, Lecturer, Major, Student, User
from app.services.grade_service import recalculate_total


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(db_engine):
    TestingSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Xóa sạch dữ liệu giữa các test — factory commit thật, phải rollback/dọn thủ công
        with db_engine.connect() as conn:
            trans = conn.begin()
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
            trans.commit()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- Factories (expose as pytest fixtures) ----------

_counter = {"n": 0}


def _next() -> int:
    _counter["n"] += 1
    return _counter["n"]


def _make_user(db, role="student", username=None, password="password123",
               student=None, lecturer=None, advisor=None) -> dict:
    """Tạo User và trả về dict headers Authorization.

    Cố vấn học tập là hồ sơ riêng (bảng advisor) — KHÔNG phải lecturer có role advisor.
    """
    n = _next()
    user = User(
        username=username or f"user{n}",
        password_hash=hash_password(password),
        role=role,
        student_id=student.id if student else None,
        lecturer_id=lecturer.id if lecturer else None,
        advisor_id=advisor.id if advisor else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def _make_major(db, code=None) -> Major:
    n = _next()
    major = Major(code=code or f"M{n}", name=f"Ngành {n}")
    db.add(major)
    db.commit()
    db.refresh(major)
    return major


def _make_lecturer(db, code=None) -> Lecturer:
    n = _next()
    lecturer = Lecturer(code=code or f"GV{n:03d}", name=f"Giảng viên {n}", department="CNTT")
    db.add(lecturer)
    db.commit()
    db.refresh(lecturer)
    return lecturer


def _make_advisor(db, code=None) -> Advisor:
    """Cố vấn học tập — hồ sơ riêng (bảng advisor), không thuộc bảng lecturer."""
    n = _next()
    advisor = Advisor(code=code or f"CV{n:03d}", name=f"Cố vấn {n}")
    db.add(advisor)
    db.commit()
    db.refresh(advisor)
    return advisor


def _make_homeroom(db, advisor=None, cohort=2023) -> HomeroomClass:
    n = _next()
    hc = HomeroomClass(name=f"Lớp-{n}", cohort=cohort, advisor_id=advisor.id if advisor else None)
    db.add(hc)
    db.commit()
    db.refresh(hc)
    return hc


def _make_student(db, homeroom=None, major=None, code=None) -> Student:
    n = _next()
    student = Student(
        code=code or f"SV{n:03d}",
        name=f"Sinh viên {n}",
        dob=datetime.date(2004, 1, 1),
        major_id=major.id if major else None,
        class_id=homeroom.id if homeroom else None,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def _make_course(db, code=None, prereqs: list[Course] | None = None, credits=3,
                 counted_in_gpa=True) -> Course:
    n = _next()
    course = Course(code=code or f"C{n}", name=f"Học phần {n}", credits=credits,
                    counted_in_gpa=counted_in_gpa)
    db.add(course)
    db.commit()
    db.refresh(course)
    for p in prereqs or []:
        from app.models import Prerequisite

        db.add(Prerequisite(course_id=course.id, prerequisite_course_id=p.id))
    db.commit()
    return course


def _make_course_class(db, course, lecturer=None, schedule=None, max_size=40,
                       year=2026, term=1, status="open") -> CourseClass:
    cc = CourseClass(
        course_id=course.id,
        lecturer_id=lecturer.id if lecturer else None,
        term=term,
        year=year,
        max_size=max_size,
        schedule=schedule if schedule is not None else [
            {"weekday": 2, "start_period": 1, "end_period": 3, "room": "A1"}
        ],
        status=status,
    )
    db.add(cc)
    db.commit()
    db.refresh(cc)
    return cc


def _make_enrollment(db, student, course_class, process=None, exam=None) -> Enrollment:
    e = Enrollment(
        student_id=student.id,
        course_class_id=course_class.id,
        enrolled_at=datetime.datetime.now(datetime.timezone.utc),
        status="approved",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    if process is not None or exam is not None:
        grade = Grade(enrollment_id=e.id, process_score=process, exam_score=exam)
        recalculate_total(grade)  # total + letter_grade + score4 theo đúng logic backend
        db.add(grade)
        db.commit()
    return e


# ---------- pytest fixtures wrapping factories ----------

@pytest.fixture()
def make_user():
    return _make_user


@pytest.fixture()
def make_major():
    return _make_major


@pytest.fixture()
def make_lecturer():
    return _make_lecturer


@pytest.fixture()
def make_advisor():
    return _make_advisor


@pytest.fixture()
def make_homeroom():
    return _make_homeroom


@pytest.fixture()
def make_student():
    return _make_student


@pytest.fixture()
def make_course():
    return _make_course


@pytest.fixture()
def make_course_class():
    return _make_course_class


@pytest.fixture()
def make_enrollment():
    return _make_enrollment
