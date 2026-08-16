"""Nghiệp vụ học phần: quản lý điều kiện tiên quyết + chống chu kỳ."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, Prerequisite


def get_prerequisite_ids(db: Session, course_id: int) -> list[int]:
    rows = db.scalars(
        select(Prerequisite.prerequisite_course_id).where(Prerequisite.course_id == course_id)
    ).all()
    return list(rows)


def check_prerequisite_cycle(db: Session, course_id: int, prerequisite_ids: list[int]) -> None:
    """Chặn tạo chu kỳ tiên quyết (ví dụ A→B→A) bằng DFS từ mỗi prerequisite.

    Nếu đi theo chuỗi tiên quyết mà quay lại được course_id thì là chu kỳ.
    """
    for start in prerequisite_ids:
        if start == course_id:
            raise HTTPException(status_code=400, detail="Điều kiện tiên quyết tạo thành chu kỳ")
        visited = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current == course_id:
                raise HTTPException(
                    status_code=400, detail="Điều kiện tiên quyết tạo thành chu kỳ"
                )
            if current in visited:
                continue
            visited.add(current)
            stack.extend(get_prerequisite_ids(db, current))


def attach_prerequisites(db: Session, course: Course, prerequisite_ids: list[int]) -> None:
    seen = set()
    for pid in prerequisite_ids:
        if pid == course.id or pid in seen:
            continue
        if db.get(Course, pid) is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy học phần tiên quyết {pid}")
        seen.add(pid)
    check_prerequisite_cycle(db, course.id, list(seen))
    for pid in seen:
        db.add(Prerequisite(course_id=course.id, prerequisite_course_id=pid))
