def test_missing_prerequisite_blocked(client, db, make_user, make_student, make_course, make_course_class):
    base = make_course(db)  # môn tiên quyết, chưa học
    target = make_course(db, prereqs=[base])
    cc = make_course_class(db, target)
    student = make_student(db)
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 400
    assert "tiên quyết" in resp.json()["detail"]


def test_passed_prerequisite_allows(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    base = make_course(db)
    target = make_course(db, prereqs=[base])
    base_cc = make_course_class(db, base, year=2025, term=1)
    target_cc = make_course_class(db, target, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, base_cc, process=8, exam=7)  # total 7.5 >= 5.0
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": target_cc.id}, headers=headers)
    assert resp.status_code == 201


def test_prerequisite_at_exact_threshold(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    base = make_course(db)
    target = make_course(db, prereqs=[base])
    base_cc = make_course_class(db, base, year=2025, term=1)
    target_cc = make_course_class(db, target, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, base_cc, process=5, exam=5)  # total đúng 5.0 → đạt
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": target_cc.id}, headers=headers)
    assert resp.status_code == 201


def test_prerequisite_below_threshold_blocked(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    base = make_course(db)
    target = make_course(db, prereqs=[base])
    base_cc = make_course_class(db, base, year=2025, term=1)
    target_cc = make_course_class(db, target, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, base_cc, process=5, exam=4.8)  # total 4.9 < 5.0
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": target_cc.id}, headers=headers)
    assert resp.status_code == 400
    assert "tiên quyết" in resp.json()["detail"]


def test_schedule_conflict_same_term_blocked(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c1 = make_course(db)
    c2 = make_course(db)
    same_schedule = [{"weekday": 3, "start_period": 1, "end_period": 3, "room": "B1"}]
    cc1 = make_course_class(db, c1, schedule=same_schedule, year=2026, term=1)
    cc2 = make_course_class(db, c2, schedule=same_schedule, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc1)
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc2.id}, headers=headers)
    assert resp.status_code == 400
    assert "Trùng lịch" in resp.json()["detail"]


def test_schedule_overlap_different_term_allowed(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c1 = make_course(db)
    c2 = make_course(db)
    same_schedule = [{"weekday": 3, "start_period": 1, "end_period": 3, "room": "B1"}]
    cc1 = make_course_class(db, c1, schedule=same_schedule, year=2025, term=1)
    cc2 = make_course_class(db, c2, schedule=same_schedule, year=2026, term=1)
    student = make_student(db)
    make_enrollment(db, student, cc1)
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc2.id}, headers=headers)
    assert resp.status_code == 201


def test_full_class_blocked(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c = make_course(db)
    cc = make_course_class(db, c, max_size=1)
    other = make_student(db)
    make_enrollment(db, other, cc)
    me = make_student(db)
    headers = make_user(db, role="student", student=me)
    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 400
    assert "sĩ số" in resp.json()["detail"]


def test_duplicate_enrollment_blocked(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c = make_course(db)
    cc = make_course_class(db, c)
    student = make_student(db)
    make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 400
    assert "Đã đăng ký" in resp.json()["detail"]


def test_closed_class_blocked(client, db, make_user, make_student, make_course, make_course_class):
    cc = make_course_class(db, make_course(db), status="closed")
    student = make_student(db)
    headers = make_user(db, role="student", student=student)
    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 400


def test_cancel_and_reenroll(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc)
    headers = make_user(db, role="student", student=student)

    resp = client.delete(f"/enrollments/{enrollment.id}", headers=headers)
    assert resp.status_code == 200

    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 201


def test_cancel_other_students_enrollment_forbidden(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    victim = make_student(db)
    enrollment = make_enrollment(db, victim, cc)
    attacker = make_student(db)
    headers = make_user(db, role="student", student=attacker)
    resp = client.delete(f"/enrollments/{enrollment.id}", headers=headers)
    assert resp.status_code == 403


def test_cancel_with_existing_grade_conflict(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    cc = make_course_class(db, make_course(db))
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc, process=8)
    headers = make_user(db, role="student", student=student)
    resp = client.delete(f"/enrollments/{enrollment.id}", headers=headers)
    assert resp.status_code == 409
