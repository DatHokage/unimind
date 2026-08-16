from app.models import Grade


def _setup(client, db, factories):
    """Lớp học do GV1 dạy, sinh viên đã đăng ký; trả về (headers các vai trò, enrollment_id)."""
    make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment = factories
    lecturer = make_lecturer(db)
    other_lecturer = make_lecturer(db)
    office_headers = make_user(db, role="training_office")
    lecturer_headers = make_user(db, role="lecturer", lecturer=lecturer)
    other_lecturer_headers = make_user(db, role="lecturer", lecturer=other_lecturer)
    student = make_student(db)
    student_headers = make_user(db, role="student", student=student)
    cc = make_course_class(db, make_course(db), lecturer=lecturer)
    enrollment = make_enrollment(db, student, cc)
    return {
        "office": office_headers,
        "lecturer": lecturer_headers,
        "other_lecturer": other_lecturer_headers,
        "student": student_headers,
        "enrollment_id": enrollment.id,
    }


def test_lecturer_cannot_set_exam_score(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(
        f"/grades/{s['enrollment_id']}/exam", json={"score": 9}, headers=s["lecturer"]
    )
    assert resp.status_code == 403


def test_office_cannot_set_process_score(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(
        f"/grades/{s['enrollment_id']}/process", json={"score": 9}, headers=s["office"]
    )
    assert resp.status_code == 403


def test_non_teaching_lecturer_cannot_set_process_score(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(
        f"/grades/{s['enrollment_id']}/process", json={"score": 9}, headers=s["other_lecturer"]
    )
    assert resp.status_code == 403


def test_teaching_lecturer_sets_process_score(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(
        f"/grades/{s['enrollment_id']}/process", json={"score": 8}, headers=s["lecturer"]
    )
    assert resp.status_code == 200
    grade = db.query(Grade).filter(Grade.enrollment_id == s["enrollment_id"]).first()
    assert grade.process_score == 8
    assert grade.total_score is None  # chưa có exam


def test_office_sets_exam_score_and_total_recalculated(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    client.put(f"/grades/{s['enrollment_id']}/process", json={"score": 8}, headers=s["lecturer"])
    resp = client.put(f"/grades/{s['enrollment_id']}/exam", json={"score": 6}, headers=s["office"])
    assert resp.status_code == 200
    grade = db.query(Grade).filter(Grade.enrollment_id == s["enrollment_id"]).first()
    assert grade.exam_score == 6
    assert grade.total_score == 7.0  # (8+6)/2


def test_invalid_score_rejected(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    for bad in (11, -1):
        resp = client.put(
            f"/grades/{s['enrollment_id']}/process", json={"score": bad}, headers=s["lecturer"]
        )
        assert resp.status_code == 422


def test_student_cannot_set_any_score(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(
        f"/grades/{s['enrollment_id']}/process", json={"score": 10}, headers=s["student"]
    )
    assert resp.status_code == 403
    resp = client.put(
        f"/grades/{s['enrollment_id']}/exam", json={"score": 10}, headers=s["student"]
    )
    assert resp.status_code == 403


# ---------- Quy đổi điểm chữ / hệ 4 ----------


def test_convert_score10_boundaries():
    """Bảng quy đổi: 8.5→A/4, 7.0→B/3, 5.5→C/2, 4.0→D/1, dưới 4.0→F/0."""
    from app.services.grade_service import convert_score10

    cases = [
        (10, "A", 4), (8.5, "A", 4), (8.49, "B", 3),
        (7.0, "B", 3), (6.99, "C", 2), (5.5, "C", 2),
        (5.49, "D", 1), (4.0, "D", 1), (3.99, "F", 0), (0, "F", 0),
    ]
    for total, letter, score4 in cases:
        assert convert_score10(total) == (letter, score4), total
    assert convert_score10(None) == (None, None)


def test_letter_and_score4_updated_with_total(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    """Nhập điểm → total_score thay đổi → letter_grade/score4 tự quy đổi theo."""
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    client.put(f"/grades/{s['enrollment_id']}/process", json={"score": 8}, headers=s["lecturer"])
    resp = client.put(f"/grades/{s['enrollment_id']}/exam", json={"score": 6}, headers=s["office"])
    body = resp.json()
    # 7.0 → B / 3 / Đạt
    assert body["total_score"] == 7.0
    assert body["letter_grade"] == "B"
    assert body["score4"] == 3
    assert body["passed"] is True

    grade = db.query(Grade).filter(Grade.enrollment_id == s["enrollment_id"]).first()
    assert (grade.letter_grade, grade.score4) == ("B", 3)

    # Đổi điểm thi → quy đổi cập nhật lại (8+10)/2 = 9.0 → A / 4
    resp = client.put(f"/grades/{s['enrollment_id']}/exam", json={"score": 10}, headers=s["office"])
    assert resp.json()["letter_grade"] == "A"
    assert resp.json()["score4"] == 4


def test_letter_cleared_when_total_incomplete(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    """Chưa đủ 2 điểm thành phần → chưa quy đổi (None, kể cả ở API bảng điểm)."""
    s = _setup(client, db, (make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment))
    resp = client.put(f"/grades/{s['enrollment_id']}/process", json={"score": 9}, headers=s["lecturer"])
    assert resp.json()["letter_grade"] is None
    assert resp.json()["score4"] is None
    assert resp.json()["passed"] is None


def test_student_grades_api_returns_conversion_fields(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    """GET /grades/student/{id} trả letter_grade, score4, status do backend quyết định."""
    student = make_student(db)
    other = make_student(db)
    cc_pass = make_course_class(db, make_course(db), year=2025, term=1)
    cc_fail = make_course_class(db, make_course(db), year=2025, term=1)
    make_enrollment(db, student, cc_pass, process=8, exam=9)   # 8.5 → A → đạt
    make_enrollment(db, student, cc_fail, process=4, exam=3)   # 3.5 → F → không đạt
    h = make_user(db, role="student", student=student)

    resp = client.get(f"/grades/student/{student.id}", headers=h)
    assert resp.status_code == 200
    rows = {r["course_code"]: r for r in resp.json()}
    assert len(rows) == 2
    passed_row, failed_row = rows[cc_pass.course.code], rows[cc_fail.course.code]
    assert passed_row["letter_grade"] == "A" and passed_row["score4"] == 4
    assert passed_row["status"] == "đạt"
    assert failed_row["letter_grade"] == "F" and failed_row["score4"] == 0
    assert failed_row["status"] == "không đạt"

    # Sinh viên khác không xem được bảng điểm của nhau
    h_other = make_user(db, role="student", student=other)
    assert client.get(f"/grades/student/{student.id}", headers=h_other).status_code == 403


def test_gpa_weighted_by_credits_excludes_non_gpa_courses(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    """GPA = SUM(score4 × credits)/SUM(credits); bỏ qua HP counted_in_gpa=False; F vẫn tính 0 điểm."""
    student = make_student(db)
    # HP1: 2TC, 8.5 → A/4 → 8đ ; HP2: 3TC, 6.5 → C/2 → 6đ ; HP3: 3TC, 3.0 → F/0 → 0đ
    cc1 = make_course_class(db, make_course(db, credits=2), year=2025, term=1)
    cc2 = make_course_class(db, make_course(db, credits=3), year=2025, term=1)
    cc3 = make_course_class(db, make_course(db, credits=3), year=2025, term=1)
    # HP4: 1TC, không tính vào GPA, điểm tuyệt đối → không được kéo GPA lên
    cc4 = make_course_class(db, make_course(db, credits=1, counted_in_gpa=False), year=2025, term=1)
    make_enrollment(db, student, cc1, process=8, exam=9)    # 8.5
    make_enrollment(db, student, cc2, process=7, exam=6)    # 6.5
    make_enrollment(db, student, cc3, process=3, exam=3)    # 3.0
    make_enrollment(db, student, cc4, process=10, exam=10)  # 10 nhưng bị loại

    h = make_user(db, role="student", student=student)
    resp = client.get(f"/grades/student/{student.id}/gpa", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["gpa4"] == round((4 * 2 + 2 * 3 + 0 * 3) / (2 + 3 + 3), 2)  # 14/8 = 1.75
    assert body["gpa10"] == round((8.5 * 2 + 6.5 * 3 + 3.0 * 3) / (2 + 3 + 3), 2)  # 45.5/8 = 5.69
    assert body["credits"] == 8  # không tính 1 TC của HP4; F vẫn tính
    assert body["accumulated_credits"] == 6  # Đạt: HP1(2TC)+HP2(3TC)+HP4(1TC, không tính GPA vẫn tích lũy); HP3 bị F loại


def test_gpa_not_simple_average(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    """GPA phải trọng số theo tín chỉ — không phải trung bình cộng của score4."""
    student = make_student(db)
    cc_small = make_course_class(db, make_course(db, credits=1), year=2025, term=1)
    cc_big = make_course_class(db, make_course(db, credits=4), year=2025, term=1)
    make_enrollment(db, student, cc_small, process=10, exam=10)  # A/4
    make_enrollment(db, student, cc_big, process=6, exam=6)      # 6.0 → C/2
    h = make_user(db, role="student", student=student)

    gpa4 = client.get(f"/grades/student/{student.id}/gpa", headers=h).json()["gpa4"]
    assert gpa4 == round((4 * 1 + 2 * 4) / 5, 2)  # 12/5 = 2.4 ≠ (4+2)/2 = 3.0


def test_gpa_empty_and_permission(client, db, make_user, make_student):
    s1 = make_student(db)
    s2 = make_student(db)
    h = make_user(db, role="student", student=s1)
    body = client.get(f"/grades/student/{s1.id}/gpa", headers=h).json()
    assert body == {"gpa4": None, "gpa10": None, "credits": 0, "accumulated_credits": 0}
    # Không xem GPA của người khác
    assert client.get(f"/grades/student/{s2.id}/gpa", headers=h).status_code == 403
