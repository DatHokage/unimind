from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import (
    assert_advisor_owns_homeroom,
    get_current_user,
    require_role,
)
from app.models import HomeroomClass, Lecturer, Major, Student
from app.schemas.homeroom_class import (
    HomeroomClassCreate,
    HomeroomClassOut,
    HomeroomClassUpdate,
)
from app.schemas.student import StudentOut

router = APIRouter(prefix="/homeroom-classes", tags=["Lớp hành chính"])


def _homeroom_out(db: Session, hc: HomeroomClass) -> HomeroomClassOut:
    count = db.scalar(select(func.count(Student.id)).where(Student.class_id == hc.id))
    return HomeroomClassOut(
        id=hc.id,
        name=hc.name,
        major_id=hc.major_id,
        major_name=hc.major.name if hc.major else None,
        cohort=hc.cohort,
        advisor_id=hc.advisor_id,
        advisor_name=hc.advisor.name if hc.advisor else None,
        student_count=count or 0,
    )


@router.get("", response_model=list[HomeroomClassOut])
def list_homeroom_classes(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    hcs = db.scalars(select(HomeroomClass).order_by(HomeroomClass.name)).all()
    return [_homeroom_out(db, hc) for hc in hcs]


@router.get("/mine", response_model=list[HomeroomClassOut])
def my_homeroom_classes(
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("advisor", "lecturer")),
):
    """Cố vấn liệt kê các lớp hành chính mình phụ trách."""
    hcs = db.scalars(
        select(HomeroomClass)
        .where(HomeroomClass.advisor_id == user["lecturer_id"])
        .order_by(HomeroomClass.name)
    ).all()
    return [_homeroom_out(db, hc) for hc in hcs]


@router.post("", response_model=HomeroomClassOut, status_code=201)
def create_homeroom_class(
    body: HomeroomClassCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    if db.scalar(select(HomeroomClass).where(HomeroomClass.name == body.name)):
        raise HTTPException(status_code=409, detail="Tên lớp hành chính đã tồn tại")
    if body.advisor_id is not None and db.get(Lecturer, body.advisor_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên cố vấn")
    if body.major_id is not None and db.get(Major, body.major_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ngành học")
    hc = HomeroomClass(
        name=body.name, major_id=body.major_id, cohort=body.cohort, advisor_id=body.advisor_id
    )
    db.add(hc)
    db.commit()
    db.refresh(hc)
    return _homeroom_out(db, hc)


@router.put("/{homeroom_id}", response_model=HomeroomClassOut)
def update_homeroom_class(
    homeroom_id: int,
    body: HomeroomClassUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    hc = db.get(HomeroomClass, homeroom_id)
    if hc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp hành chính")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != hc.name:
        if db.scalar(
            select(HomeroomClass).where(
                HomeroomClass.name == data["name"], HomeroomClass.id != homeroom_id
            )
        ):
            raise HTTPException(status_code=409, detail="Tên lớp hành chính đã tồn tại")
    if data.get("advisor_id") is not None and db.get(Lecturer, data["advisor_id"]) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy giảng viên cố vấn")
    if data.get("major_id") is not None and db.get(Major, data["major_id"]) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ngành học")
    for field, value in data.items():
        setattr(hc, field, value)
    db.commit()
    db.refresh(hc)
    return _homeroom_out(db, hc)


@router.delete("/{homeroom_id}", status_code=200)
def delete_homeroom_class(
    homeroom_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office")),
):
    """Xóa lớp hành chính — chặn nếu lớp vẫn còn sinh viên."""
    hc = db.get(HomeroomClass, homeroom_id)
    if hc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp hành chính")
    student_count = db.scalar(
        select(func.count(Student.id)).where(Student.class_id == homeroom_id)
    ) or 0
    if student_count:
        raise HTTPException(
            status_code=409, detail="Không thể xóa: lớp vẫn còn sinh viên"
        )
    db.delete(hc)
    db.commit()
    return {"detail": f"Đã xóa lớp hành chính {hc.name}"}


@router.get("/{homeroom_id}/students", response_model=list[StudentOut])
def list_homeroom_students(
    homeroom_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("training_office", "advisor")),
):
    """Danh sách sinh viên trong lớp hành chính — advisor chỉ xem lớp mình phụ trách."""
    assert_advisor_owns_homeroom(db, user, homeroom_id)
    students = db.scalars(
        select(Student).where(Student.class_id == homeroom_id).order_by(Student.code)
    ).all()
    return [
        StudentOut(
            id=s.id,
            code=s.code,
            name=s.name,
            dob=s.dob,
            major_id=s.major_id,
            class_id=s.class_id,
            major_name=s.major.name if s.major else None,
            class_name=s.homeroom_class.name if s.homeroom_class else None,
        )
        for s in students
    ]
