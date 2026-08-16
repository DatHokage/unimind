from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Enrollment, HomeroomClass, Student, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> dict:
    """Giải mã JWT và trả về claims dict; kèm kiểm tra user vẫn tồn tại trong DB."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_error
    user = db.get(User, payload.get("user_id"))
    if user is None:
        raise credentials_error
    return payload


def require_role(*allowed_roles: str):
    """Dependency factory: chỉ cho phép các role được liệt kê."""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
        return user

    return checker


def get_target_student(
    db: Session, user: dict, student_id: int, allow_lecturer: bool = False
) -> Student:
    """Kiểm tra quyền truy cập hồ sơ/điểm của MỘT sinh viên cụ thể (mục 7 đặc tả).

    - student: chỉ chính mình
    - advisor: sinh viên thuộc HomeroomClass mình phụ trách
    - lecturer (allow_lecturer=True): đang dạy ít nhất 1 CourseClass mà SV có Enrollment
    - training_office: toàn quyền
    """
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên")

    role = user["role"]
    if role == "training_office":
        return student

    if role == "student":
        if user["student_id"] != student_id:
            raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
        return student

    if role == "advisor":
        if student.class_id is None:
            raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
        homeroom = db.get(HomeroomClass, student.class_id)
        if homeroom is None or homeroom.advisor_id != user["lecturer_id"]:
            raise HTTPException(status_code=403, detail="Không phải sinh viên bạn phụ trách")
        return student

    if role == "lecturer" and allow_lecturer:
        teaches = (
            db.query(Enrollment.id)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.course_class.has(lecturer_id=user["lecturer_id"]),
            )
            .first()
        )
        if teaches is None:
            raise HTTPException(
                status_code=403, detail="Sinh viên không thuộc lớp bạn phụ trách"
            )
        return student

    raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")


def assert_advisor_owns_homeroom(db: Session, user: dict, homeroom_id: int) -> HomeroomClass:
    """Cố vấn chỉ được thao tác trên lớp hành chính mình phụ trách."""
    homeroom = db.get(HomeroomClass, homeroom_id)
    if homeroom is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp hành chính")
    if user["role"] != "training_office" and homeroom.advisor_id != user["lecturer_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
    return homeroom
