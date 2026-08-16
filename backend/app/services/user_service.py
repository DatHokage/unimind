from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User


def create_user_account(
    db: Session,
    username: str,
    password: str,
    role: str,
    student_id: int | None = None,
    lecturer_id: int | None = None,
) -> User:
    """Tạo tài khoản đăng nhập kèm theo hồ sơ Student/Lecturer."""
    exists = db.scalar(select(User).where(User.username == username))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Tên đăng nhập đã tồn tại")
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        student_id=student_id,
        lecturer_id=lecturer_id,
    )
    db.add(user)
    return user
