from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.dependencies.auth_dependency import get_current_user
from app.models import User
from app.schemas.auth import LoginResponse, UserInfo

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Đăng nhập không phân biệt hoa/thường (VD: dtcgv001 ≡ DTCGV001)
    user = db.scalar(
        select(User).where(func.lower(User.username) == form.username.strip().lower())
    )
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")
    return LoginResponse(
        access_token=create_access_token(user),
        user=UserInfo(
            id=user.id,
            username=user.username,
            role=user.role,
            student_id=user.student_id,
            lecturer_id=user.lecturer_id,
            advisor_id=user.advisor_id,
        ),
    )


@router.get("/me", response_model=UserInfo)
def me(user: dict = Depends(get_current_user)):
    return UserInfo(
        id=user["user_id"],
        username=user["username"],
        role=user["role"],
        student_id=user.get("student_id"),
        lecturer_id=user.get("lecturer_id"),
        advisor_id=user.get("advisor_id"),
    )
