def _scenario(db, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    """2 SV cùng lớp, đã có điểm: 1 đạt (7.5), 1 trượt (4.0)."""
    advisor = make_lecturer(db)
    hc = make_homeroom(db, advisor=advisor)
    s1 = make_student(db, homeroom=hc)
    s2 = make_student(db, homeroom=hc)
    cc = make_course_class(db, make_course(db), year=2025, term=1)
    make_enrollment(db, s1, cc, process=8, exam=7)   # 7.5 đạt
    make_enrollment(db, s2, cc, process=5, exam=3)   # 4.0 trượt
    return advisor, hc


def test_academic_results(client, db, make_user, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    advisor, hc = _scenario(db, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment)
    h = make_user(db, role="training_office")
    resp = client.get("/stats/academic-results", headers=h)
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["class_id"] == hc.id
    assert row["student_count"] == 2
    assert row["graded_count"] == 2
    assert row["avg_score"] == 5.75  # (7.5+4.0)/2
    assert row["pass_rate"] == 0.5   # 1/2 đạt


def test_advisor_stats_restricted(client, db, make_user, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    advisor, hc = _scenario(db, make_lecturer, make_homeroom, make_student, make_course, make_course_class, make_enrollment)
    foreign_class = make_homeroom(db)
    h = make_user(db, role="advisor", lecturer=advisor)

    # Mặc định chỉ trả về lớp của mình
    resp = client.get("/stats/academic-results", headers=h)
    assert resp.status_code == 200
    assert [r["class_id"] for r in resp.json()] == [hc.id]

    # Hỏi lớp khác → 403
    resp = client.get(f"/stats/academic-results?class_id={foreign_class.id}", headers=h)
    assert resp.status_code == 403

    # Hỏi đúng lớp mình → 200
    resp = client.get(f"/stats/academic-results?class_id={hc.id}", headers=h)
    assert resp.status_code == 200


def test_popular_courses_office_only(client, db, make_user):
    h_office = make_user(db, role="training_office")
    h_student = make_user(db, role="student")
    assert client.get("/stats/popular-courses", headers=h_office).status_code == 200
    assert client.get("/stats/popular-courses", headers=h_student).status_code == 403


def test_popular_courses_ordering(client, db, make_user, make_course, make_course_class, make_student, make_enrollment):
    popular = make_course(db)
    unpopular = make_course(db)
    cc_pop = make_course_class(db, popular, year=2025, term=1)
    cc_unpop = make_course_class(db, unpopular, year=2025, term=1)
    for _ in range(3):
        make_enrollment(db, make_student(db), cc_pop)
    make_enrollment(db, make_student(db), cc_unpop)

    h = make_user(db, role="training_office")
    rows = client.get("/stats/popular-courses", headers=h).json()
    assert rows[0]["course_code"] == popular.code
    assert rows[0]["enrollment_count"] == 3
    assert rows[1]["enrollment_count"] == 1
