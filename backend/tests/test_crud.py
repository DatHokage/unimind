"""CRUD quản trị: update + delete cho Student/Lecturer/Major/HomeroomClass/Course,
chặn xóa khi có tham chiếu (409), và phòng đào tạo đăng ký hộ sinh viên."""


# ---------- Student ----------


def test_update_student_fields(client, db, make_user, make_student, make_homeroom, make_major):
    """PUT /students/{id} cập nhật từng phần và trả về dữ liệu mới."""
    s = make_student(db)
    hc = make_homeroom(db)
    major = make_major(db)
    h = make_user(db, role="training_office")

    resp = client.put(
        f"/students/{s.id}",
        json={"name": "Nguyễn Văn A", "major_id": major.id, "class_id": hc.id},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Nguyễn Văn A"
    assert body["major_id"] == major.id
    assert body["class_id"] == hc.id
    # Mã SV giữ nguyên khi không truyền
    assert body["code"] == s.code


def test_update_student_duplicate_code_409(client, db, make_user, make_student):
    """Đổi mã SV sang mã đã tồn tại → 409."""
    s1 = make_student(db, code="SV-A")
    s2 = make_student(db, code="SV-B")
    h = make_user(db, role="training_office")

    resp = client.put(f"/students/{s1.id}", json={"code": "SV-B"}, headers=h)
    assert resp.status_code == 409


def test_update_student_bad_fk_404(client, db, make_user, make_student):
    """class_id/major_id không tồn tại → 404."""
    s = make_student(db)
    h = make_user(db, role="training_office")

    resp = client.put(f"/students/{s.id}", json={"class_id": 9999}, headers=h)
    assert resp.status_code == 404
    resp = client.put(f"/students/{s.id}", json={"major_id": 9999}, headers=h)
    assert resp.status_code == 404


def test_delete_student_ok(client, db, make_user, make_student):
    """Sinh viên chưa có đăng ký → xóa được."""
    s = make_student(db)
    h = make_user(db, role="training_office")

    resp = client.delete(f"/students/{s.id}", headers=h)
    assert resp.status_code == 200

    resp = client.get("/students", params={"search": s.code}, headers=h)
    assert resp.json()["totalElements"] == 0


def test_delete_student_blocked_when_enrolled(client, db, make_user, make_student,
                                              make_course, make_course_class, make_enrollment):
    """Sinh viên đã có đăng ký học phần → 409, dữ liệu nguyên vẹn."""
    s = make_student(db)
    cc = make_course_class(db, make_course(db))
    make_enrollment(db, s, cc)
    h = make_user(db, role="training_office")

    resp = client.delete(f"/students/{s.id}", headers=h)
    assert resp.status_code == 409

    resp = client.get(f"/students/{s.id}", headers=h)
    assert resp.status_code == 200


def test_student_cannot_update_or_delete(client, db, make_user, make_student):
    """Sinh viên không được sửa/xóa hồ sơ người khác → 403."""
    s = make_student(db)
    other = make_student(db)
    h = make_user(db, role="student", student=s)

    assert client.put(f"/students/{other.id}", json={"name": "X"}, headers=h).status_code == 403
    assert client.delete(f"/students/{other.id}", headers=h).status_code == 403


# ---------- Lecturer ----------


def test_update_lecturer_ok(client, db, make_user, make_lecturer):
    l = make_lecturer(db)
    h = make_user(db, role="training_office")

    resp = client.put(
        f"/lecturers/{l.id}",
        json={"name": "Trần Thị B", "department": "Toán"},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Trần Thị B"
    assert body["department"] == "Toán"


def test_update_lecturer_duplicate_code_409(client, db, make_user, make_lecturer):
    l1 = make_lecturer(db, code="GV-X")
    l2 = make_lecturer(db, code="GV-Y")
    h = make_user(db, role="training_office")

    resp = client.put(f"/lecturers/{l1.id}", json={"code": "GV-Y"}, headers=h)
    assert resp.status_code == 409


def test_delete_lecturer_ok(client, db, make_user, make_lecturer):
    l = make_lecturer(db)
    h = make_user(db, role="training_office")

    assert client.delete(f"/lecturers/{l.id}", headers=h).status_code == 200
    assert all(x["id"] != l.id for x in client.get("/lecturers", headers=h).json())


def test_delete_lecturer_blocked_when_teaching(client, db, make_user, make_lecturer,
                                               make_course, make_course_class):
    l = make_lecturer(db)
    make_course_class(db, make_course(db), lecturer=l)
    h = make_user(db, role="training_office")

    resp = client.delete(f"/lecturers/{l.id}", headers=h)
    assert resp.status_code == 409


def test_delete_lecturer_blocked_when_advising(client, db, make_user, make_lecturer, make_homeroom):
    l = make_lecturer(db)
    make_homeroom(db, advisor=l)
    h = make_user(db, role="training_office")

    resp = client.delete(f"/lecturers/{l.id}", headers=h)
    assert resp.status_code == 409


# ---------- Major ----------


def test_update_major_ok(client, db, make_user, make_major):
    m = make_major(db)
    h = make_user(db, role="training_office")

    resp = client.put(f"/majors/{m.id}", json={"name": "Khoa học máy tính"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Khoa học máy tính"


def test_delete_major_ok(client, db, make_user, make_major):
    m = make_major(db)
    h = make_user(db, role="training_office")

    assert client.delete(f"/majors/{m.id}", headers=h).status_code == 200
    assert all(x["id"] != m.id for x in client.get("/majors", headers=h).json())


def test_delete_major_blocked_when_has_students(client, db, make_user, make_major, make_student):
    m = make_major(db)
    make_student(db, major=m)
    h = make_user(db, role="training_office")

    assert client.delete(f"/majors/{m.id}", headers=h).status_code == 409


def test_delete_major_blocked_when_has_homerooms(client, db, make_user, make_major, make_homeroom):
    """Lớp hành chính gắn ngành → không cho xóa ngành."""
    from app.models import HomeroomClass

    m = make_major(db)
    hc = make_homeroom(db)
    hc.major_id = m.id
    db.commit()
    h = make_user(db, role="training_office")

    assert client.delete(f"/majors/{m.id}", headers=h).status_code == 409


# ---------- HomeroomClass ----------


def test_update_homeroom_ok(client, db, make_user, make_homeroom, make_lecturer, make_major):
    hc = make_homeroom(db)
    advisor = make_lecturer(db)
    major = make_major(db)
    h = make_user(db, role="training_office")

    resp = client.put(
        f"/homeroom-classes/{hc.id}",
        json={"name": "CNTT9-K13", "advisor_id": advisor.id, "major_id": major.id},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "CNTT9-K13"
    assert body["advisor_id"] == advisor.id
    assert body["major_id"] == major.id


def test_update_homeroom_duplicate_name_409(client, db, make_user, make_homeroom):
    hc1 = make_homeroom(db)
    hc2 = make_homeroom(db)
    h = make_user(db, role="training_office")

    resp = client.put(f"/homeroom-classes/{hc1.id}", json={"name": hc2.name}, headers=h)
    assert resp.status_code == 409


def test_delete_homeroom_ok(client, db, make_user, make_homeroom):
    hc = make_homeroom(db)
    h = make_user(db, role="training_office")

    assert client.delete(f"/homeroom-classes/{hc.id}", headers=h).status_code == 200


def test_delete_homeroom_blocked_when_has_students(client, db, make_user, make_homeroom, make_student):
    hc = make_homeroom(db)
    make_student(db, homeroom=hc)
    h = make_user(db, role="training_office")

    resp = client.delete(f"/homeroom-classes/{hc.id}", headers=h)
    assert resp.status_code == 409


# ---------- Course ----------


def test_update_course_ok_with_prereq_replace(client, db, make_user, make_course):
    """Sửa thông tin + gán lại toàn bộ danh sách tiên quyết."""
    a = make_course(db)
    b = make_course(db)
    c = make_course(db)
    h = make_user(db, role="training_office")

    resp = client.put(
        f"/courses/{a.id}",
        json={"name": "Nhập môn lập trình", "credits": 4, "prerequisite_course_ids": [b.id]},
        headers=h,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Nhập môn lập trình"
    assert body["credits"] == 4
    assert [p["id"] for p in body["prerequisites"]] == [b.id]

    # Gán lại sang c → danh sách cũ bị thay thế hoàn toàn
    resp = client.put(f"/courses/{a.id}", json={"prerequisite_course_ids": [c.id]}, headers=h)
    assert [p["id"] for p in resp.json()["prerequisites"]] == [c.id]


def test_update_course_prereq_cycle_400(client, db, make_user, make_course):
    """A→B rồi bắt B→A tạo chu kỳ → 400."""
    a = make_course(db)
    b = make_course(db, prereqs=[a])
    h = make_user(db, role="training_office")

    resp = client.put(f"/courses/{a.id}", json={"prerequisite_course_ids": [b.id]}, headers=h)
    assert resp.status_code == 400


def test_delete_course_ok(client, db, make_user, make_course):
    c = make_course(db)
    h = make_user(db, role="training_office")

    assert client.delete(f"/courses/{c.id}", headers=h).status_code == 200
    assert all(x["id"] != c.id for x in client.get("/courses", headers=h).json())


def test_delete_course_blocked_when_has_classes(client, db, make_user, make_course, make_course_class):
    c = make_course(db)
    make_course_class(db, c)
    h = make_user(db, role="training_office")

    assert client.delete(f"/courses/{c.id}", headers=h).status_code == 409


# ---------- Phòng đào tạo đăng ký hộ ----------


def test_office_enrolls_student(client, db, make_user, make_student, make_course, make_course_class):
    """POST /enrollments kèm student_id bởi training_office → đăng ký hộ thành công."""
    s = make_student(db)
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = client.post(
        "/enrollments", json={"course_class_id": cc.id, "student_id": s.id}, headers=h
    )
    assert resp.status_code == 201
    assert resp.json()["student_id"] == s.id

    # Xuất hiện trong lịch sử đăng ký của sinh viên đó
    resp = client.get(f"/enrollments/student/{s.id}", headers=h)
    assert len(resp.json()) == 1


def test_office_enroll_missing_student_id_400(client, db, make_user, make_course, make_course_class):
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=h)
    assert resp.status_code == 400


def test_office_enroll_respects_capacity(client, db, make_user, make_student, make_course,
                                         make_course_class, make_enrollment):
    """Đăng ký hộ vẫn bị chặn khi lớp đầy sĩ số."""
    cc = make_course_class(db, make_course(db), max_size=1)
    make_enrollment(db, make_student(db), cc)
    s2 = make_student(db)
    h = make_user(db, role="training_office")

    resp = client.post(
        "/enrollments", json={"course_class_id": cc.id, "student_id": s2.id}, headers=h
    )
    assert resp.status_code == 400
    assert "sĩ số" in resp.json()["detail"]


def test_student_ignores_student_id_in_body(client, db, make_user, make_student,
                                            make_course, make_course_class):
    """Sinh viên truyền student_id người khác vẫn chỉ đăng ký cho chính mình."""
    s = make_student(db)
    other = make_student(db)
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="student", student=s)

    resp = client.post(
        "/enrollments", json={"course_class_id": cc.id, "student_id": other.id}, headers=h
    )
    assert resp.status_code == 201
    assert resp.json()["student_id"] == s.id


def test_lecturer_cannot_manage_records(client, db, make_user, make_lecturer, make_student):
    """Giảng viên không có quyền sửa/xóa hồ sơ quản trị → 403."""
    l = make_lecturer(db)
    s = make_student(db)
    h = make_user(db, role="lecturer", lecturer=l)

    assert client.put(f"/students/{s.id}", json={"name": "X"}, headers=h).status_code == 403
    assert client.delete(f"/students/{s.id}", headers=h).status_code == 403
    assert client.delete(f"/lecturers/{l.id}", headers=h).status_code == 403
