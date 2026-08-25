"""Nghiệp vụ học phần: tiên quyết + chống chu kỳ, mã lớp, chống trùng phòng/GV."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, CourseClass, Prerequisite


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


def get_class_code(db: Session, cc: CourseClass) -> str:
    """Mã lớp học phần dạng CTDL-N01 — số nhóm = THỨ TỰ TẠO trong (môn, năm, kỳ).

    Không lưu cột: hệ thống không có xóa lớp nên thứ tự id ổn định vĩnh viễn,
    lớp tạo trước trong cùng kỳ luôn là N01, kế tiếp N02…
    """
    if cc.course is None:
        return f"Lớp#{cc.id}"
    sibling_ids = db.scalars(
        select(CourseClass.id)
        .where(
            CourseClass.course_id == cc.course_id,
            CourseClass.year == cc.year,
            CourseClass.term == cc.term,
        )
        .order_by(CourseClass.id)
    ).all()
    stt = sibling_ids.index(cc.id) + 1 if cc.id in sibling_ids else len(sibling_ids) + 1
    return f"{cc.course.code}-N{stt:02d}"


def ensure_no_schedule_conflicts(
    db: Session,
    *,
    year: int,
    term: int,
    weekday: int,
    block: str,
    room: str | None,
    lecturer_id: int | None,
    exclude_class_id: int | None = None,
) -> None:
    """Chặn trùng phòng và trùng lịch giảng viên khi admin tạo/sửa lớp học phần.

    Buổi học chiếm đúng 1 khối giờ chuẩn (sáng/chiều/tối) nên 2 lớp "đụng" nhau
    khi cùng kỳ + cùng thứ + cùng khối:
    - Trùng phòng: 2 lớp chung 1 phòng cùng lúc — so khớp không phân biệt hoa/thường.
    - Trùng lịch GV: 1 giảng viên bị xếp dạy 2 lớp chồng giờ.
    Lớp closed/completed vẫn chiếm phòng như thường (cùng kỳ thì lịch vẫn thật).
    """
    stmt = select(CourseClass).where(
        CourseClass.year == year,
        CourseClass.term == term,
        CourseClass.weekday == weekday,
        CourseClass.block == block,
    )
    if exclude_class_id is not None:
        stmt = stmt.where(CourseClass.id != exclude_class_id)
    for other in db.scalars(stmt).all():
        other_code = get_class_code(db, other)
        if (
            room and other.room
            and room.strip().casefold() == other.room.strip().casefold()
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Phòng {room} đã có lớp {other_code} học cùng thứ/khối giờ này "
                    f"(kỳ {term}/{year}) — chọn phòng hoặc khối giờ khác"
                ),
            )
        if lecturer_id is not None and other.lecturer_id == lecturer_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Giảng viên đã có lớp {other_code} dạy trùng thứ/khối giờ này "
                    f"(kỳ {term}/{year})"
                ),
            )
