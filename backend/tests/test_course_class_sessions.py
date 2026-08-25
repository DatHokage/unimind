


"""Ghi đè TỪNG buổi học (dời/nghỉ) — luật seq, xung đột slot bù, vòng đời."""

from app.models import Grade
from app.services.grade_service import recalculate_total


def _put(client, h, cc_id, seq, **body):
    return client.put(f"/course-classes/{cc_id}/sessions/{seq}", json=body, headers=h)


# ---------- Dời buổi ----------

def test_move_session_ok_and_visible_in_out(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))  # 3 TC → 9 buổi
    h = make_user(db, role="training_office")

    resp = _put(client, h, cc.id, 3, action="moved", weekday=6, block="afternoon", room="P999")

    assert resp.status_code == 200
    ovs = resp.json()["session_overrides"]
    assert len(ovs) == 1
    assert ovs[0] == {"seq": 3, "action": "moved", "weekday": 6, "block": "afternoon", "room": "P999"}


def test_move_session_out_of_range_blocked(client, db, make_user, make_course, make_course_class):
    """3 tín chỉ = 9 buổi — buổi 10 không tồn tại."""
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = _put(client, h, cc.id, 10, action="moved", weekday=6, block="afternoon")

    assert resp.status_code == 400
    assert "1..9" in resp.json()["detail"]


def test_move_session_requires_full_slot(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = _put(client, h, cc.id, 2, action="moved", weekday=6)

    assert resp.status_code == 400
    assert "thứ + khối" in resp.json()["detail"]


def test_move_session_into_occupied_room_blocked(client, db, make_user, make_course, make_course_class):
    """Slot bù đụng phòng của lớp khác cùng kỳ → chặn (giống mở lớp thường)."""
    make_course_class(db, make_course(db), weekday=5, block="morning", room="P301")
    target = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = _put(client, h, target.id, 1, action="moved", weekday=5, block="morning", room="P301")

    assert resp.status_code == 400
    assert "Phòng P301" in resp.json()["detail"]
    # Slot trống thì dời thoải mái
    resp = _put(client, h, target.id, 1, action="moved", weekday=5, block="afternoon", room="P301")
    assert resp.status_code == 200


def test_overwrite_same_session_replaces_override(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    _put(client, h, cc.id, 4, action="moved", weekday=6, block="afternoon")
    resp = _put(client, h, cc.id, 4, action="cancelled")

    assert resp.status_code == 200
    ovs = resp.json()["session_overrides"]
    # Vẫn đúng 1 dòng cho buổi 4 — đã chuyển sang cancelled, slot bù bị xóa sạch
    assert len(ovs) == 1
    assert ovs[0] == {"seq": 4, "action": "cancelled", "weekday": None, "block": None, "room": None}


# ---------- Nghĩ buổi + bỏ ghi đè ----------

def test_cancelled_session_has_no_makeup_slot(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = _put(client, h, cc.id, 7, action="cancelled")

    assert resp.status_code == 200
    ov = resp.json()["session_overrides"][0]
    assert ov["action"] == "cancelled"
    assert ov["weekday"] is None and ov["block"] is None


def test_delete_override_restores_regular_schedule(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    _put(client, h, cc.id, 2, action="cancelled")
    resp = client.delete(f"/course-classes/{cc.id}/sessions/2", headers=h)

    assert resp.status_code == 200
    assert resp.json()["session_overrides"] == []
    # Xóa buổi không có ghi đè → vẫn 200 (idempotent)
    resp = client.delete(f"/course-classes/{cc.id}/sessions/2", headers=h)
    assert resp.status_code == 200


# ---------- Vòng đời + phân quyền ----------

def test_completed_class_rejects_session_edits(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db), status="open")
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc)
    grade = Grade(enrollment_id=enrollment.id, process_score=8.0, exam_score=7.0)
    recalculate_total(grade)
    db.add(grade)
    db.commit()
    h = make_user(db, role="training_office")
    client.patch(f"/course-classes/{cc.id}", json={"status": "closed"}, headers=h)
    client.post(f"/course-classes/{cc.id}/complete", headers=h)

    resp = _put(client, h, cc.id, 1, action="cancelled")
    assert resp.status_code == 400
    assert "COMPLETED" in resp.json()["detail"]

    resp = client.delete(f"/course-classes/{cc.id}/sessions/1", headers=h)
    assert resp.status_code == 400


def test_student_cannot_edit_sessions(client, db, make_user, make_student, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    sh = make_user(db, role="student", student=make_student(db))

    resp = _put(client, sh, cc.id, 1, action="cancelled")
    assert resp.status_code == 403
    resp = client.delete(f"/course-classes/{cc.id}/sessions/1", headers=sh)
    assert resp.status_code == 403


# ---------- Đọc qua các luồng khác ----------

def test_schedule_includes_session_overrides(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    student = make_student(db)
    make_enrollment(db, student, cc)
    h = make_user(db, role="training_office")
    _put(client, h, cc.id, 5, action="moved", weekday=8, block="morning", room="P888")
    sh = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", headers=sh)

    assert resp.status_code == 200
    cls = resp.json()["classes"][0]
    assert cls["class_code"].endswith("-N01")
    assert cls["session_overrides"] == [
        {"seq": 5, "action": "moved", "weekday": 8, "block": "morning", "room": "P888"}
    ]
