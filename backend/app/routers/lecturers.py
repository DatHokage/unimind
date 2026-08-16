from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import CourseClass, HomeroomClass, Lecturer
from app.schemas.lecturer import LecturerCreate, LecturerOut, LecturerUpdate
from app.services.user_service import create_user_account

router = APIRouter(prefix="/lecturers", tags=["Giảng viên"])


def _get_lecturer_or_404(db: Session, lecturer_id: int) -> Lecturer:
    lecturer = db.get(Lecturer, lecturer_id)
    if lecturer is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên")
    return lecturer


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


@router.put("/{lecturer_id}", response_model=LecturerOut)
def update_lecturer(
    lecturer_id: int,
    body: LecturerUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    lecturer = _get_lecturer_or_404(db, lecturer_id)
    data = body.model_dump(exclude_unset=True)
    if "code" in data and data["code"] != lecturer.code:
        if db.scalar(select(Lecturer).where(Lecturer.code == data["code"], Lecturer.id != lecturer_id)):
            raise HTTPException(status_code=409, detail="Mã giảng viên đã tồn tại")
    for field, value in data.items():
        setattr(lecturer, field, value)
    db.commit()
    db.refresh(lecturer)
    return lecturer


@router.delete("/{lecturer_id}", status_code=200)
def delete_lecturer(
    lecturer_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa giảng viên — chặn nếu đang dạy lớp học phần hoặc cố vấn lớp hành chính."""
    lecturer = _get_lecturer_or_404(db, lecturer_id)
    has_class = db.scalar(
        select(func.count(CourseClass.id)).where(CourseClass.lecturer_id == lecturer_id)
    ) or 0
    if has_class:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: giảng viên đang phụ trách lớp học phần"
        )
    has_homeroom = db.scalar(
        select(func.count(HomeroomClass.id)).where(HomeroomClass.advisor_id == lecturer_id)
    ) or 0
    if has_homeroom:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: giảng viên đang cố vấn lớp hành chính"
        )
    db.delete(lecturer)
    db.commit()
    return {"detail": f"Đã xóa giảng viên {lecturer.code}"}
