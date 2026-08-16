from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Major
from app.schemas.major import MajorCreate, MajorOut

router = APIRouter(prefix="/majors", tags=["Ngành học"])


@router.get("", response_model=list[MajorOut])
def list_majors(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor", "lecturer", "student")),
):
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
