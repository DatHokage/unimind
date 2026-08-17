from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import require_role
from app.models import Advisor, HomeroomClass
from app.schemas.advisor import AdvisorCreate, AdvisorOut, AdvisorPage, AdvisorUpdate
from app.services.user_service import create_user_account

router = APIRouter(prefix="/advisors", tags=["Cố vấn học tập"])


def _advisor_out(db: Session, advisor: Advisor) -> AdvisorOut:
    return AdvisorOut(
        id=advisor.id,
        code=advisor.code,
        name=advisor.name,
    )


@router.get("", response_model=AdvisorPage)
def list_advisors(
    search: str | None = None,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Danh sách cố vấn học tập phân trang phía server — chỉ phòng đào tạo quản lý."""
    stmt = select(Advisor)
    if search:
        keyword = f"%{search.strip()}%"
        stmt = stmt.where(
            func.lower(Advisor.name).like(func.lower(keyword))
            | func.lower(Advisor.code).like(func.lower(keyword))
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    advisors = (
        db.scalars(stmt.order_by(Advisor.code).offset(page * size).limit(size)).all()
    )
    return AdvisorPage(
        data=[_advisor_out(db, a) for a in advisors],
        page=page,
        size=size,
        totalElements=total,
        totalPages=(total + size - 1) // size,
    )


@router.get("/all", response_model=list[AdvisorOut])
def list_all_advisors(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Toàn bộ cố vấn (không phân trang) — phục vụ dropdown chọn cố vấn cho lớp hành chính."""
    advisors = db.scalars(select(Advisor).order_by(Advisor.code)).all()
    return [_advisor_out(db, a) for a in advisors]


@router.post("", response_model=AdvisorOut, status_code=201)
def create_advisor(
    body: AdvisorCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(Advisor).where(Advisor.code == body.code)):
        raise HTTPException(status_code=409, detail="Mã cố vấn đã tồn tại")
    advisor = Advisor(
        code=body.code,
        name=body.name,
    )
    db.add(advisor)
    db.flush()
    if body.account:
        create_user_account(
            db, body.account.username, body.account.password, "advisor", advisor_id=advisor.id
        )
    db.commit()
    db.refresh(advisor)
    return _advisor_out(db, advisor)


@router.get("/{advisor_id}", response_model=AdvisorOut)
def get_advisor(
    advisor_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor")),
):
    advisor = db.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cố vấn")
    # Cố vấn chỉ xem được hồ sơ của chính mình
    if user["role"] == "advisor" and user.get("advisor_id") != advisor_id:
        raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
    return _advisor_out(db, advisor)


@router.put("/{advisor_id}", response_model=AdvisorOut)
def update_advisor(
    advisor_id: int,
    body: AdvisorUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    advisor = db.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cố vấn")
    data = body.model_dump(exclude_unset=True)
    if "code" in data and data["code"] != advisor.code:
        if db.scalar(select(Advisor).where(Advisor.code == data["code"], Advisor.id != advisor_id)):
            raise HTTPException(status_code=409, detail="Mã cố vấn đã tồn tại")
    for field, value in data.items():
        setattr(advisor, field, value)
    db.commit()
    db.refresh(advisor)
    return _advisor_out(db, advisor)


@router.delete("/{advisor_id}", status_code=200)
def delete_advisor(
    advisor_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa cố vấn — chặn nếu còn được gán phụ trách lớp hành chính."""
    advisor = db.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy cố vấn")
    assigned = db.scalar(
        select(func.count(HomeroomClass.id)).where(HomeroomClass.advisor_id == advisor_id)
    ) or 0
    if assigned:
        raise HTTPException(
            status_code=409,
            detail="Không thể xóa: cố vấn đang phụ trách lớp hành chính",
        )
    db.delete(advisor)
    db.commit()
    return {"detail": f"Đã xóa cố vấn {advisor.code}"}
