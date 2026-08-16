def test_schedule_defaults_to_latest_term(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c_old = make_course(db, code="HP_CU")
    c_new = make_course(db, code="HP_MOI")
    cc_old = make_course_class(db, c_old, year=2025, term=1)
    cc_new = make_course_class(db, c_new, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc_old, process=8, exam=7)
    make_enrollment(db, student, cc_new)
    headers = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    # Không chỉ định kỳ → kỳ mới nhất (2026-T1)
    assert (body["year"], body["term"]) == (2026, 1)
    assert [c["course_code"] for c in body["classes"]] == ["HP_MOI"]
    # Danh sách kỳ trả đủ, mới nhất trước
    assert body["terms"] == [{"year": 2026, "term": 1}, {"year": 2025, "term": 1}]


def test_schedule_explicit_term(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c_old = make_course(db, code="HP_CU")
    c_new = make_course(db, code="HP_MOI")
    cc_old = make_course_class(db, c_old, year=2025, term=1)
    cc_new = make_course_class(db, c_new, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc_old)
    make_enrollment(db, student, cc_new)
    headers = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", params={"year": 2025, "term": 1}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["year"], body["term"]) == (2025, 1)
    assert [c["course_code"] for c in body["classes"]] == ["HP_CU"]


def test_schedule_unknown_term_404(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db), year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", params={"year": 2030, "term": 2}, headers=headers)
    assert resp.status_code == 404


def test_schedule_empty_student(client, db, make_user, make_student):
    student = make_student(db)
    headers = make_user(db, role="student", student=student)
    resp = client.get(f"/schedule/student/{student.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["classes"] == []
    assert body["terms"] == []
    assert body["year"] is None and body["term"] is None


def test_schedule_sorted_by_weekday_period(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c1 = make_course(db, code="HP_T7")
    c2 = make_course(db, code="HP_T2")
    cc_t7 = make_course_class(db, c1, schedule=[{"weekday": 7, "start_period": 1, "end_period": 2, "room": "C1"}], year=2026, term=1)
    cc_t2 = make_course_class(db, c2, schedule=[{"weekday": 2, "start_period": 4, "end_period": 6, "room": "A1"}], year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc_t7)
    make_enrollment(db, student, cc_t2)
    headers = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", headers=headers)
    codes = [c["course_code"] for c in resp.json()["classes"]]
    assert codes == ["HP_T2", "HP_T7"]


def test_schedule_other_student_forbidden(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    victim = make_student(db)
    make_enrollment(db, victim, cc)
    other = make_student(db)
    headers = make_user(db, role="student", student=other)
    resp = client.get(f"/schedule/student/{victim.id}", headers=headers)
    assert resp.status_code == 403


def test_schedule_advisor_scope(client, db, make_user, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    advisor = make_lecturer(db)
    other_advisor = make_lecturer(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db, advisor=other_advisor)
    my_student = make_student(db, homeroom=my_class)
    foreign_student = make_student(db, homeroom=foreign_class)
    cc = make_course_class(db, make_course(db))
    make_enrollment(db, my_student, cc)
    make_enrollment(db, foreign_student, cc)
    h = make_user(db, role="advisor", lecturer=advisor)

    resp = client.get(f"/schedule/student/{my_student.id}", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()["classes"]) == 1
    resp = client.get(f"/schedule/student/{foreign_student.id}", headers=h)
    assert resp.status_code == 403


def test_schedule_lecturer_forbidden(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    """Thời khóa biểu là dữ liệu của sinh viên — giảng viên không xem hộ được."""
    lect = make_lecturer(db)
    cc = make_course_class(db, make_course(db), lecturer=lect)
    student = make_student(db)
    make_enrollment(db, student, cc)
    h = make_user(db, role="lecturer", lecturer=lect)
    resp = client.get(f"/schedule/student/{student.id}", headers=h)
    assert resp.status_code == 403


def test_schedule_office_allowed(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    student = make_student(db)
    make_enrollment(db, student, cc)
    h = make_user(db, role="training_office")
    resp = client.get(f"/schedule/student/{student.id}", headers=h)
    assert resp.status_code == 200


def test_schedule_requires_auth(client, db, make_student, make_course, make_course_class):
    student = make_student(db)
    resp = client.get(f"/schedule/student/{student.id}")
    assert resp.status_code == 401
