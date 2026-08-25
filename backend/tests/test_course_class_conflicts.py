"""Test luật mới của lớp học phần: trùng phòng/GV, mã -Nxx, vòng đời COMPLETED.

Lịch cố định mỗi lớp: cùng kỳ + thứ + khối giờ là "đụng" nhau (khối chiếm trọn
sáng/chiều/tối nên không cần so tiết giao nhau như JSON cũ).
"""

from app.models import Grade
from app.services.grade_service import recalculate_total


def _payload(course_id, **over):
    body = {
        "course_id": course_id,
        "term": 1,
        "year": 2026,
        "weekday": 2,
        "block": "morning",
        "room": "P101",
    }
    body.update(over)
    return body


# ---------- Tạo lớp: chặn trùng phòng / trùng lịch giảng viên ----------

def test_create_room_conflict_blocked(client, db, make_user, make_course, make_course_class):
    make_course_class(db, make_course(db), weekday=2, block="morning", room="P101", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post("/course-classes", json=_payload(other_course.id), headers=h)

    assert resp.status_code == 400
    assert "Phòng P101" in resp.json()["detail"]


def test_create_room_conflict_case_insensitive(client, db, make_user, make_course, make_course_class):
    """So khớp phòng không phân biệt hoa/thường ('p101' ≡ 'P101')."""
    make_course_class(db, make_course(db), weekday=2, block="morning", room="P101", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post("/course-classes", json=_payload(other_course.id, room=" p101 "), headers=h)

    assert resp.status_code == 400


def test_create_same_slot_different_room_ok(client, db, make_user, make_course, make_course_class):
    """Cùng thứ/khối nhưng khác phòng → hợp lệ (demo trùng lịch SV vẫn hoạt động)."""
    make_course_class(db, make_course(db), weekday=2, block="morning", room="P101", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post("/course-classes", json=_payload(other_course.id, room="P102"), headers=h)

    assert resp.status_code == 201
    assert resp.json()["code"].endswith("-N01")


def test_create_same_room_other_term_ok(client, db, make_user, make_course, make_course_class):
    """Phòng chỉ bị chiếm trong cùng kỳ — kỳ sau dùng lại thoải mái."""
    make_course_class(db, make_course(db), weekday=2, block="morning", room="P101", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post("/course-classes", json=_payload(other_course.id, year=2025), headers=h)

    assert resp.status_code == 201


def test_create_lecturer_conflict_blocked(client, db, make_user, make_course, make_course_class, make_lecturer):
    lect = make_lecturer(db)
    make_course_class(db, make_course(db), lecturer=lect, weekday=4, block="afternoon", room="P201", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post(
        "/course-classes",
        json=_payload(other_course.id, lecturer_id=lect.id, weekday=4, block="afternoon", room="P202"),
        headers=h,
    )

    assert resp.status_code == 400
    assert "Giảng viên" in resp.json()["detail"]


def test_create_lecturer_same_day_different_block_ok(client, db, make_user, make_course, make_course_class, make_lecturer):
    """GV dạy sáng rồi chiều cùng ngày là bình thường — không bị chặn."""
    lect = make_lecturer(db)
    make_course_class(db, make_course(db), lecturer=lect, weekday=4, block="morning", room="P201", year=2026, term=1)
    other_course = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.post(
        "/course-classes",
        json=_payload(other_course.id, lecturer_id=lect.id, weekday=4, block="afternoon", room="P201"),
        headers=h,
    )

    assert resp.status_code == 201


# ---------- Mã lớp -Nxx sinh theo thứ tự tạo ----------

def test_class_code_numbered_by_creation_order(client, db, make_user, make_course):
    c = make_course(db)
    h = make_user(db, role="training_office")

    r1 = client.post("/course-classes", json=_payload(c.id, room="R1"), headers=h)
    r2 = client.post("/course-classes", json=_payload(c.id, room="R2"), headers=h)

    assert r1.json()["code"] == f"{c.code}-N01"
    assert r2.json()["code"] == f"{c.code}-N02"


# ---------- Sửa lớp ----------

def test_patch_into_occupied_room_blocked(client, db, make_user, make_course, make_course_class):
    # Lớp khác đã chiếm P301 vào T5 sáng — đúng slot của target sau khi đổi phòng
    make_course_class(db, make_course(db), weekday=5, block="morning", room="P301", year=2026, term=1)
    target = make_course_class(db, make_course(db), weekday=5, block="morning", room="P302", year=2026, term=1)
    h = make_user(db, role="training_office")

    resp = client.patch(f"/course-classes/{target.id}", json={"room": "P301"}, headers=h)

    assert resp.status_code == 400
    assert "Phòng P301" in resp.json()["detail"]
    # Dời cả thứ + khối + phòng sang ô trống thì ok
    resp = client.patch(
        f"/course-classes/{target.id}",
        json={"weekday": 3, "block": "evening", "room": "P301"},
        headers=h,
    )
    assert resp.status_code == 200


def test_patch_status_completed_directly_blocked(client, db, make_user, make_course, make_course_class):
    """Chuyển COMPLETED phải đi qua /complete để được kiểm tra đủ điểm."""
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = client.patch(f"/course-classes/{cc.id}", json={"status": "completed"}, headers=h)

    assert resp.status_code == 400
    assert "/complete" in resp.json()["detail"]


# ---------- Vòng đời COMPLETED ----------

def test_complete_flow_requires_closed_and_full_grades(
    client, db, make_user, make_student, make_course, make_course_class, make_enrollment
):
    cc = make_course_class(db, make_course(db), status="open")
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc)  # chưa có điểm
    h = make_user(db, role="training_office")

    # OPEN → complete bị chặn: phải CLOSED trước
    resp = client.post(f"/course-classes/{cc.id}/complete", headers=h)
    assert resp.status_code == 400
    assert "CLOSED" in resp.json()["detail"]

    # Đóng đăng ký
    resp = client.patch(f"/course-classes/{cc.id}", json={"status": "closed"}, headers=h)
    assert resp.status_code == 200

    # CLOSED nhưng còn SV chưa có điểm → chặn
    resp = client.post(f"/course-classes/{cc.id}/complete", headers=h)
    assert resp.status_code == 400
    assert "chưa có điểm" in resp.json()["detail"]

    # Nhập đủ điểm → complete thành công
    grade = Grade(enrollment_id=enrollment.id, process_score=8.0, exam_score=7.0)
    recalculate_total(grade)
    db.add(grade)
    db.commit()

    resp = client.post(f"/course-classes/{cc.id}/complete", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    # COMPLETED → khóa hoàn toàn, PATCH gì cũng bị từ chối
    resp = client.patch(f"/course-classes/{cc.id}", json={"max_size": 10}, headers=h)
    assert resp.status_code == 400
    assert "COMPLETED" in resp.json()["detail"]

    # Sinh viên không thể đăng ký vào lớp completed (status != open)
    sh = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=sh)
    assert resp.status_code == 400


def test_complete_twice_rejected(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db), status="completed")
    h = make_user(db, role="training_office")

    resp = client.post(f"/course-classes/{cc.id}/complete", headers=h)

    assert resp.status_code == 400


# ---------- Kỳ hiện tại ----------

def test_current_term_is_latest_with_classes(client, db, make_user, make_course, make_course_class):
    make_course_class(db, make_course(db), year=2025, term=3)
    make_course_class(db, make_course(db), year=2026, term=1)
    h = make_user(db, role="student")

    resp = client.get("/course-classes/current-term", headers=h)

    assert resp.status_code == 200
    assert resp.json() == {"year": 2026, "term": 1}


def test_current_term_empty_db_returns_nulls(client, db, make_user):
    h = make_user(db, role="student")

    resp = client.get("/course-classes/current-term", headers=h)

    assert resp.status_code == 200
    assert resp.json() == {"year": None, "term": None}


def test_current_term_requires_auth(client, db):
    resp = client.get("/course-classes/current-term")
    assert resp.status_code == 401
