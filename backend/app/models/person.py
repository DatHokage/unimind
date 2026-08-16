import datetime

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Major(Base):
    """Ngành học."""

    __tablename__ = "major"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    students: Mapped[list["Student"]] = relationship(back_populates="major")

    # Index hỗ trợ tìm kiếm trong danh sách ngành học (theo code có unique index sẵn)
    __table_args__ = (Index("ix_major_name", "name"),)


class Student(Base):
    """Sinh viên."""

    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dob: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    major_id: Mapped[int | None] = mapped_column(ForeignKey("major.id"), nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("homeroom_class.id"), nullable=True)

    major: Mapped["Major | None"] = relationship(back_populates="students")
    homeroom_class: Mapped["HomeroomClass | None"] = relationship(back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student")

    # Index hỗ trợ tìm kiếm + sắp xếp trong danh sách sinh viên (theo code có unique index sẵn)
    __table_args__ = (Index("ix_student_name", "name"),)


class Lecturer(Base):
    """Giảng viên — có thể vừa dạy lớp học phần, vừa làm cố vấn lớp hành chính."""

    __tablename__ = "lecturer"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)

    course_classes: Mapped[list["CourseClass"]] = relationship(back_populates="lecturer")
    advised_classes: Mapped[list["HomeroomClass"]] = relationship(back_populates="advisor")

    # Index hỗ trợ tìm kiếm trong danh sách giảng viên (theo code có unique index sẵn)
    __table_args__ = (Index("ix_lecturer_name", "name"),)
