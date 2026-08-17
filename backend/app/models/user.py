from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

ROLES = ("training_office", "lecturer", "advisor", "student")


class User(Base, TimestampMixin):
    """Tài khoản đăng nhập — liên kết với Student, Lecturer hoặc Advisor qua FK nullable."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Một Student/Lecturer/Advisor có tối đa 1 tài khoản (unique).
    # role "advisor" gắn với Advisor (bảng riêng, không còn là Lecturer).
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student.id"), unique=True, nullable=True
    )
    lecturer_id: Mapped[int | None] = mapped_column(
        ForeignKey("lecturer.id"), unique=True, nullable=True
    )
    advisor_id: Mapped[int | None] = mapped_column(
        ForeignKey("advisor.id"), unique=True, nullable=True
    )
