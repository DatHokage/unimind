import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class HomeroomClass(Base):
    """Lớp hành chính — gắn 1 cố vấn (giảng viên) phụ trách."""

    __tablename__ = "homeroom_class"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    major_id: Mapped[int | None] = mapped_column(ForeignKey("major.id"), nullable=True)
    cohort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advisor_id: Mapped[int | None] = mapped_column(ForeignKey("lecturer.id"), nullable=True)

    major: Mapped["Major | None"] = relationship()
    advisor: Mapped["Lecturer | None"] = relationship(back_populates="advised_classes")
    students: Mapped[list["Student"]] = relationship(back_populates="homeroom_class")

    # Index hỗ trợ filter theo ngành/khóa trong danh sách lớp hành chính phân trang
    __table_args__ = (
        Index("ix_homeroom_class_major_id", "major_id"),
        Index("ix_homeroom_class_cohort", "cohort"),
    )


class Prerequisite(Base):
    """Điều kiện tiên quyết giữa 2 học phần (bảng trung gian M2M tự tham chiếu)."""

    __tablename__ = "prerequisite"

    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), primary_key=True)
    prerequisite_course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), primary_key=True)


class Course(Base):
    """Học phần."""

    __tablename__ = "course"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    # Học phần có được tính vào GPA tích lũy hay không (VD: GDTC có thể không tính)
    counted_in_gpa: Mapped[bool] = mapped_column(default=True, nullable=False)

    prerequisites: Mapped[list["Course"]] = relationship(
        secondary="prerequisite",
        primaryjoin="Course.id == Prerequisite.course_id",
        secondaryjoin="Course.id == Prerequisite.prerequisite_course_id",
    )
    course_classes: Mapped[list["CourseClass"]] = relationship(back_populates="course")

    # Index hỗ trợ tìm kiếm trong danh sách học phần (theo code có unique index sẵn)
    __table_args__ = (Index("ix_course_name", "name"),)


class CourseClass(Base):
    """Lớp học phần — 1 học phần mở nhiều lớp theo kỳ.

    schedule: JSON list các buổi học, mỗi buổi dạng
    {"weekday": 2..8, "start_period": int, "end_period": int, "room": str}
    """

    __tablename__ = "course_class"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("lecturer.id"), nullable=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..3
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_size: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    schedule: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open/closed

    course: Mapped["Course"] = relationship(back_populates="course_classes")
    lecturer: Mapped["Lecturer | None"] = relationship(back_populates="course_classes")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course_class")

    # Index hỗ trợ filter theo kỳ/năm trong danh sách lớp học phần phân trang
    __table_args__ = (
        Index("ix_course_class_term", "term"),
        Index("ix_course_class_year", "year"),
    )


class Enrollment(Base):
    """Đăng ký học phần của sinh viên."""

    __tablename__ = "enrollment"
    __table_args__ = (UniqueConstraint("student_id", "course_class_id", name="uq_enrollment_student_class"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    course_class_id: Mapped[int] = mapped_column(ForeignKey("course_class.id"), nullable=False)
    enrolled_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")

    student: Mapped["Student"] = relationship(back_populates="enrollments")
    course_class: Mapped["CourseClass"] = relationship(back_populates="enrollments")
    grade: Mapped["Grade | None"] = relationship(back_populates="enrollment", uselist=False)


class Grade(Base):
    """Điểm của 1 đăng ký — process do giảng viên nhập, exam do phòng đào tạo nhập."""

    __tablename__ = "grade"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollment.id"), unique=True, nullable=False
    )
    process_score: Mapped[float | None] = mapped_column(nullable=True)
    exam_score: Mapped[float | None] = mapped_column(nullable=True)
    total_score: Mapped[float | None] = mapped_column(nullable=True)  # backend tự tính
    # Backend tự quy đổi từ total_score mỗi khi tổng kết thay đổi — client không gửi
    letter_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)  # A/B/C/D/F
    score4: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0..4
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    enrollment: Mapped["Enrollment"] = relationship(back_populates="grade")
