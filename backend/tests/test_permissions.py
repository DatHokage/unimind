def test_student_sees_own_grades_only(client, db, make_user, make_student, make_course, make_course_class, make_enrollment):
    c = make_course(db)
    cc = make_course_class(db, c)
    s1 = make_student(db)
    s2 = make_student(db)
    make_enrollment(db, s1, cc)
    h1 = make_user(db, role="student", student=s1)
    h2 = make_user(db, role="student", student=s2)

    resp = client.get(f"/grades/student/{s1.id}", headers=h1)
    assert resp.status_code == 200
    resp = client.get(f"/grades/student/{s1.id}", headers=h2)
    assert resp.status_code == 403


def test_advisor_sees_only_own_homeroom_students(client, db, make_user, make_advisor, make_homeroom, make_student, make_course, make_course_class, make_enrollment):
    advisor = make_advisor(db)
    other_advisor = make_advisor(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db, advisor=other_advisor)
    my_student = make_student(db, homeroom=my_class)
    foreign_student = make_student(db, homeroom=foreign_class)
    h_advisor = make_user(db, role="advisor", advisor=advisor)

    # Xem điểm sinh viên lớp mình
    resp = client.get(f"/grades/student/{my_student.id}", headers=h_advisor)
    assert resp.status_code == 200
    # Không xem được sinh viên lớp khác
    resp = client.get(f"/grades/student/{foreign_student.id}", headers=h_advisor)
    assert resp.status_code == 403
    # Danh sách sinh viên lớp mình / lớp khác
    resp = client.get(f"/homeroom-classes/{my_class.id}/students", headers=h_advisor)
    assert resp.status_code == 200
    resp = client.get(f"/homeroom-classes/{foreign_class.id}/students", headers=h_advisor)
    assert resp.status_code == 403


def test_advisor_lists_only_own_homeroom_classes(client, db, make_user, make_advisor, make_homeroom):
    advisor = make_advisor(db)
    make_homeroom(db, advisor=advisor)
    make_homeroom(db, advisor=advisor)
    make_homeroom(db)  # lớp không có advisor
    h = make_user(db, role="advisor", advisor=advisor)
    resp = client.get("/homeroom-classes/mine", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_lecturer_grade_access_limited_to_taught_students(client, db, make_user, make_lecturer, make_student, make_course, make_course_class, make_enrollment):
    teaching = make_lecturer(db)
    unrelated = make_lecturer(db)
    cc = make_course_class(db, make_course(db), lecturer=teaching)
    student = make_student(db)
    make_enrollment(db, student, cc)

    h_teaching = make_user(db, role="lecturer", lecturer=teaching)
    h_unrelated = make_user(db, role="lecturer", lecturer=unrelated)

    resp = client.get(f"/grades/student/{student.id}", headers=h_teaching)
    assert resp.status_code == 200
    resp = client.get(f"/grades/student/{student.id}", headers=h_unrelated)
    assert resp.status_code == 403


def test_student_cannot_create_student(client, db, make_user, make_student):
    h = make_user(db, role="student", student=make_student(db))
    resp = client.post("/students", json={"code": "SVX", "name": "X"}, headers=h)
    assert resp.status_code == 403


def test_lecturer_course_classes_mine_only(client, db, make_user, make_lecturer, make_course, make_course_class):
    l1 = make_lecturer(db)
    l2 = make_lecturer(db)
    make_course_class(db, make_course(db), lecturer=l1)
    make_course_class(db, make_course(db), lecturer=l1)
    make_course_class(db, make_course(db), lecturer=l2)
    h = make_user(db, role="lecturer", lecturer=l1)
    resp = client.get("/course-classes/mine", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_lecturer_cannot_list_other_class_enrollments(client, db, make_user, make_lecturer, make_course, make_course_class):
    l1 = make_lecturer(db)
    l2 = make_lecturer(db)
    cc = make_course_class(db, make_course(db), lecturer=l1)
    h2 = make_user(db, role="lecturer", lecturer=l2)
    resp = client.get(f"/course-classes/{cc.id}/enrollments", headers=h2)
    assert resp.status_code == 403
