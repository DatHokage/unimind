import datetime


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
    cc_t7 = make_course_class(db, c1, weekday=7, block="morning", room="C1", year=2026, term=1)
    cc_t2 = make_course_class(db, c2, weekday=2, block="afternoon", room="A1", year=2026, term=1)
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


def test_schedule_advisor_scope(client, db, make_user, make_advisor, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    advisor = make_advisor(db)
    other_advisor = make_advisor(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db, advisor=other_advisor)
    my_student = make_student(db, homeroom=my_class)
    foreign_student = make_student(db, homeroom=foreign_class)
    cc = make_course_class(db, make_course(db))
    make_enrollment(db, my_student, cc)
    make_enrollment(db, foreign_student, cc)
    h = make_user(db, role="advisor", advisor=advisor)

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


# ---------- Buổi học quy đổi ra ngày cụ thể (view tháng / tuần học) ----------

def test_schedule_sessions_dated(client, db, make_user, make_student, make_course,
                                 make_course_class, make_enrollment, make_term):
    """Có start_date → trả đủ (credits×3) buổi với date/week tính đúng từ thứ Hai tuần 1."""
    make_term(db, year=2026, term=1, start_date=datetime.date(2026, 8, 24))  # Thứ 2
    c = make_course(db, code="HP9T", credits=3)  # 3 TC × 3 = 9 buổi
    cc = make_course_class(db, c, weekday=3, block="morning", year=2026, term=1)  # Thứ 3
    student = make_student(db)
    make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)

    resp = client.get(f"/schedule/student/{student.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["start_date"] == "2026-08-24"
    sessions = body["sessions"]
    assert len(sessions) == 9
    # Buổi 1 = thứ 3 ngay sau thứ Hai bắt đầu kỳ; buổi k cách 7 ngày
    first = datetime.date(2026, 8, 25)
    for i, s in enumerate(sessions, start=1):
        assert s["seq"] == i and s["week"] == i
        assert s["date"] == (first + datetime.timedelta(days=(i - 1) * 7)).isoformat()
        assert s["weekday"] == 3 and s["status"] == "normal"
        assert s["start_period"] == 1 and s["end_period"] == 5
    # Sắp theo ngày tăng dần
    dates = [s["date"] for s in sessions]
    assert dates == sorted(dates)


def test_schedule_sessions_apply_overrides(client, db, make_user, make_student, make_course,
                                           make_course_class, make_enrollment, make_term,
                                           make_session_override):
    """moved → đổi sang thứ/khối/phòng bù cùng tuần; cancelled → giữ ngày gốc, đánh dấu nghỉ."""
    make_term(db, year=2026, term=1, start_date=datetime.date(2026, 8, 24))
    c = make_course(db, code="HP_OV", credits=2)  # 6 buổi
    cc = make_course_class(db, c, weekday=3, block="morning", room="A1", year=2026, term=1)
    make_session_override(db, cc, seq=1, action="moved", weekday=6, block="afternoon", room="P999")
    make_session_override(db, cc, seq=2, action="cancelled")
    student = make_student(db)
    make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)

    sessions = client.get(f"/schedule/student/{student.id}", headers=headers).json()["sessions"]
    s1, s2 = sessions[0], sessions[1]
    # Buổi 1 dời sang chiều thứ 6 tuần 1 (28/08), phòng bù
    assert s1["status"] == "moved" and s1["weekday"] == 6
    assert s1["date"] == "2026-08-28" and s1["block"] == "afternoon" and s1["room"] == "P999"
    # Buổi 2 nghỉ — vẫn hiện đúng ngày gốc thứ 3 tuần 2
    assert s2["status"] == "cancelled" and s2["date"] == "2026-09-01" and s2["room"] == "A1"
    # Các buổi còn lại bình thường
    assert all(s["status"] == "normal" for s in sessions[2:])


def test_schedule_sessions_without_term_start(client, db, make_user, make_student, make_course,
                                              make_course_class, make_enrollment):
    """Kỳ chưa nhập ngày bắt đầu → sessions rỗng, UI tự ẩn view tháng/tuần học."""
    cc = make_course_class(db, make_course(db), year=2030, term=2)
    student = make_student(db)
    make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)

    body = client.get(f"/schedule/student/{student.id}", headers=headers).json()
    assert body["start_date"] is None
    assert body["sessions"] == []
    assert len(body["classes"]) == 1  # lưới tuần điển hình vẫn hoạt động
