from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Lecturer
from app.schemas.lecturer import LecturerCreate, LecturerOut
from app.services.user_service import create_user_account

router = APIRouter(prefix="/lecturers", tags=["Giảng viên"])


@router.get("", response_model=list[LecturerOut])
def list_lecturers(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer")),
):
    return db.scalars(select(Lecturer).order_by(Lecturer.code)).all()


@router.post("", response_model=LecturerOut, status_code=201)
def create_lecturer(
    body: LecturerCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(Lecturer).where(Lecturer.code == body.code)):
        raise HTTPException(status_code=409, detail="Mã giảng viên đã tồn tại")
    lecturer = Lecturer(code=body.code, name=body.name, department=body.department)
    db.add(lecturer)
    db.flush()
    if body.account:
        create_user_account(
            db,
            body.account.username,
            body.account.password,
            body.account.role,
            lecturer_id=lecturer.id,
        )
    db.commit()
    db.refresh(lecturer)
    return lecturer
