from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import HomeroomClass, Major, Student
from app.schemas.major import MajorCreate, MajorOut, MajorPage, MajorUpdate

router = APIRouter(prefix="/majors", tags=["Ngành học"])


def _get_major_or_404(db: Session, major_id: int) -> Major:
    major = db.get(Major, major_id)
    if major is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ngành học")
    return major


@router.get("", response_model=MajorPage)
def list_majors(
    search: str | None = None,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    """Danh sách ngành học phân trang phía server — chỉ query đúng các bản ghi của trang hiện tại."""
    stmt = select(Major)
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(or_(Major.name.ilike(keyword), Major.code.ilike(keyword)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    majors = db.scalars(stmt.order_by(Major.code).offset(page * size).limit(size)).all()
    return MajorPage(
        data=majors,
        page=page,
        size=size,
        totalElements=total,
        totalPages=(total + size - 1) // size,
    )


@router.get("/all", response_model=list[MajorOut])
def list_all_majors(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
    """Toàn bộ ngành học (không phân trang) — chỉ dùng cho dropdown/select của form."""
    return db.scalars(select(Major).order_by(Major.code)).all()


@router.post("", response_model=MajorOut, status_code=201)
def create_major(
    body: MajorCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(Major).where(Major.code == body.code)):
        raise HTTPException(status_code=409, detail="Mã ngành đã tồn tại")
    major = Major(code=body.code, name=body.name)
    db.add(major)
    db.commit()
    db.refresh(major)
    return major


@router.put("/{major_id}", response_model=MajorOut)
def update_major(
    major_id: int,
    body: MajorUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    major = _get_major_or_404(db, major_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(major, field, value)
    db.commit()
    db.refresh(major)
    return major


@router.delete("/{major_id}", status_code=200)
def delete_major(
    major_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa ngành — chặn nếu còn sinh viên hoặc lớp hành chính thuộc ngành."""
    major = _get_major_or_404(db, major_id)
    student_count = db.scalar(
        select(func.count(Student.id)).where(Student.major_id == major_id)
    ) or 0
    if student_count:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: ngành vẫn còn sinh viên"
        )
    homeroom_count = db.scalar(
        select(func.count(HomeroomClass.id)).where(HomeroomClass.major_id == major_id)
    ) or 0
    if homeroom_count:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: ngành vẫn còn lớp hành chính"
        )
    db.delete(major)
    db.commit()
    return {"detail": f"Đã xóa ngành {major.code}"}
