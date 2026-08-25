import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

# Khối giờ chuẩn: mỗi buổi học nằm gọn trong ĐÚNG 1 khối 5 tiết, không cắt giữa khối
# (sáng/chiều/tối). start/end period của buổi học suy ra từ block, không lưu riêng.
TIME_BLOCKS = {
    "morning": (1, 5),      # Sáng: tiết 1–5
    "afternoon": (6, 10),   # Chiều: tiết 6–10
    "evening": (11, 15),    # Tối: tiết 11–15
}


class HomeroomClass(Base):
    """Lớp hành chính — gắn 1 cố vấn học tập phụ trách."""

    __tablename__ = "homeroom_class"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    major_id: Mapped[int | None] = mapped_column(ForeignKey("major.id"), nullable=True)
    cohort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    advisor_id: Mapped[int | None] = mapped_column(ForeignKey("advisor.id"), nullable=True)

    major: Mapped["Major | None"] = relationship()
    advisor: Mapped["Advisor | None"] = relationship(back_populates="advised_classes")
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

    Lịch học CỐ ĐỊNH suốt khóa: mỗi tuần 1 buổi, kéo dài (credits × 3) tuần
    (1 tín chỉ = 15 tiết = 3 buổi × 5 tiết), cùng 1 phòng.
    Mã lớp KHÔNG lưu cột — sinh theo thứ tự tạo trong (môn, năm, kỳ):
    lớp tạo trước = N01, kế tiếp = N02… (xem course_service.get_class_code).
    Vòng đời: open → closed (đóng đăng ký) → completed (hết kỳ, đủ điểm, read-only).
    """

    __tablename__ = "course_class"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    lecturer_id: Mapped[int | None] = mapped_column(ForeignKey("lecturer.id"), nullable=True)
    term: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..3
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    max_size: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    # open: đang đăng ký · closed: đóng đăng ký (vẫn sửa lịch/nhập điểm)
    # completed: hết kỳ + đủ điểm — KHÓA hoàn toàn, chỉ tra cứu
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")

    # --- Lịch học cố định cả khóa ---
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)   # 2..8 (2 = Thứ Hai)
    block: Mapped[str] = mapped_column(String(10), nullable=False)  # morning/afternoon/evening
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)

    course: Mapped["Course"] = relationship(back_populates="course_classes")
    lecturer: Mapped["Lecturer | None"] = relationship(back_populates="course_classes")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course_class")
    session_overrides: Mapped[list["CourseClassSession"]] = relationship(
        back_populates="course_class",
        order_by="CourseClassSession.seq",
        cascade="all, delete-orphan",
    )

    # Index hỗ trợ filter theo kỳ/năm trong danh sách lớp học phần phân trang
    __table_args__ = (
        Index("ix_course_class_term", "term"),
        Index("ix_course_class_year", "year"),
    )

    @property
    def start_period(self) -> int:
        """Tiết bắt đầu của buổi học tuần — suy ra từ khối giờ, không lưu riêng."""
        return TIME_BLOCKS[self.block][0]

    @property
    def end_period(self) -> int:
        return TIME_BLOCKS[self.block][1]


class AcademicTerm(Base):
    """Học kỳ + ngày bắt đầu — gốc quy đổi mọi buổi học ra ngày cụ thể.

    Lớp học phần chỉ lưu slot tuần điển hình (thứ + khối); muốn vẽ lịch theo
    tháng hay đánh số "Tuần 1..N" thì phải có mốc thời gian. start_date nên là
    Thứ 2 của tuần 1 — service tính ngày buổi học tự căn về Thứ 2 của tuần
    chứa start_date nên nhập lệch thứ cũng không sai.
    """

    __tablename__ = "academic_term"
    __table_args__ = (UniqueConstraint("year", "term", name="uq_academic_term_year_term"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..3
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)


class CourseClassSession(Base):
    """Ghi đè lịch cho TỪNG buổi của lớp — trường hợp đặc biệt (lễ, sự kiện, GV bận).

    Buổi bình thường sinh từ slot cố định của lớp (mỗi tuần 1 buổi); chỉ những
    buổi có dòng ở đây mới khác thường: dời sang thứ/khối/phòng khác (moved)
    hoặc nghỉ hẳn (cancelled). Lớp không có dòng nào = lịch đều suốt khóa.
    """

    __tablename__ = "course_class_session"
    __table_args__ = (
        UniqueConstraint("course_class_id", "seq", name="uq_session_class_seq"),
        Index("ix_course_class_session_class", "course_class_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_class_id: Mapped[int] = mapped_column(ForeignKey("course_class.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # buổi thứ mấy, tính từ 1
    # moved: học bù vào weekday/block/room · cancelled: nghỉ, không có slot bù
    action: Mapped[str] = mapped_column(String(10), nullable=False)  # moved/cancelled
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 2..8 khi moved
    block: Mapped[str | None] = mapped_column(String(10), nullable=True)  # khi moved
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)

    course_class: Mapped["CourseClass"] = relationship(back_populates="session_overrides")


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
