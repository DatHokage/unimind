from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

ROLES = ("training_office", "lecturer", "advisor", "student")


class User(Base, TimestampMixin):
    """Tài khoản đăng nhập — liên kết với Student hoặc Lecturer qua FK nullable."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Một Student/Lecturer có tối đa 1 tài khoản (unique); advisor là Lecturer có role "advisor"
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("student.id"), unique=True, nullable=True
    )
    lecturer_id: Mapped[int | None] = mapped_column(
        ForeignKey("lecturer.id"), unique=True, nullable=True
    )
