"""Phân trang/tìm kiếm/lọc phía server cho 5 module quản trị.

Kiểm tra: shape response {data, page, size, totalElements, totalPages},
không trả quá `size` bản ghi mỗi trang, search áp dụng cả vào totalElements,
và các endpoint /all trả danh sách thuần (không phân trang) cho dropdown.
"""


# ---------- Shape + phân trang chung ----------


def test_page_shape_and_paging(client, db, make_user, make_major):
    """12 bản ghi, size=10 → 2 trang đúng shape và đúng số lượng."""
    for _ in range(12):
        make_major(db)
    h = make_user(db, role="training_office")

    body = client.get("/majors", params={"page": 0, "size": 10}, headers=h).json()
    assert set(body) == {"data", "page", "size", "totalElements", "totalPages"}
    assert body["page"] == 0
    assert body["size"] == 10
    assert body["totalElements"] == 12
    assert body["totalPages"] == 2
    assert len(body["data"]) == 10

    body = client.get("/majors", params={"page": 1, "size": 10}, headers=h).json()
    assert body["page"] == 1
    assert len(body["data"]) == 2

    # Trang vượt quá giới hạn → rỗng nhưng vẫn đúng totalElements
    body = client.get("/majors", params={"page": 5, "size": 10}, headers=h).json()
    assert body["data"] == []
    assert body["totalElements"] == 12


def test_default_page_and_size(client, db, make_user, make_major):
    """Không truyền page/size → mặc định page=0, size=10."""
    for _ in range(15):
        make_major(db)
    h = make_user(db, role="training_office")

    body = client.get("/majors", headers=h).json()
    assert body["page"] == 0
    assert body["size"] == 10
    assert len(body["data"]) == 10
    assert body["totalElements"] == 15


# ---------- Giảng viên ----------


def test_lecturers_search_by_code_and_name(client, db, make_user, make_lecturer):
    make_lecturer(db, code="GV-SEARCH")
    keep = make_lecturer(db)
    keep.name = "Nguyễn Tìm Kiếm"
    db.commit()
    make_lecturer(db)
    h = make_user(db, role="training_office")

    body = client.get("/lecturers", params={"search": "GV-SEARCH"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["code"] == "GV-SEARCH"

    body = client.get("/lecturers", params={"search": "tìm kiếm"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["name"] == "Nguyễn Tìm Kiếm"


def test_lecturers_filter_by_department(client, db, make_user, make_lecturer):
    a = make_lecturer(db)
    a.department = "Toán"
    db.commit()
    make_lecturer(db)  # mặc định department CNTT
    h = make_user(db, role="training_office")

    body = client.get("/lecturers", params={"department": "Toán"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["department"] == "Toán"


def test_lecturers_all_returns_plain_list(client, db, make_user, make_lecturer):
    for _ in range(3):
        make_lecturer(db)
    h = make_user(db, role="training_office")

    data = client.get("/lecturers/all", headers=h).json()
    assert isinstance(data, list)
    assert len(data) == 3


# ---------- Ngành học ----------


def test_majors_search_by_code_and_name(client, db, make_user, make_major):
    m = make_major(db)
    m.code = "CNTT-DL"
    m.name = "Khoa học dữ liệu"
    db.commit()
    make_major(db)
    h = make_user(db, role="training_office")

    body = client.get("/majors", params={"search": "CNTT-DL"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["code"] == "CNTT-DL"

    body = client.get("/majors", params={"search": "dữ liệu"}, headers=h).json()
    assert body["totalElements"] == 1


# ---------- Lớp hành chính ----------


def test_homerooms_search_and_filters(client, db, make_user, make_homeroom, make_major):
    it = make_major(db)
    it.code = "CNTT"
    db.commit()
    hc1 = make_homeroom(db, cohort=2024)
    hc1.name = "CNTT1-K2024"
    hc1.major_id = it.id
    hc2 = make_homeroom(db, cohort=2025)
    hc2.name = "KHMT1-K2025"
    db.commit()
    make_homeroom(db, cohort=2024)
    h = make_user(db, role="training_office")

    # Tìm theo tên lớp
    body = client.get("/homeroom-classes", params={"search": "CNTT1"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["name"] == "CNTT1-K2024"

    # Lọc theo khóa
    body = client.get("/homeroom-classes", params={"cohort": 2024}, headers=h).json()
    assert body["totalElements"] == 2

    # Lọc theo ngành
    body = client.get("/homeroom-classes", params={"major_id": it.id}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["major_id"] == it.id

    # Kết hợp search + filter
    body = client.get(
        "/homeroom-classes", params={"search": "CNTT1", "cohort": 2025}, headers=h
    ).json()
    assert body["totalElements"] == 0


def test_homerooms_all_returns_plain_list(client, db, make_user, make_homeroom):
    for _ in range(3):
        make_homeroom(db)
    h = make_user(db, role="training_office")

    data = client.get("/homeroom-classes/all", headers=h).json()
    assert isinstance(data, list)
    assert len(data) == 3


# ---------- Học phần ----------


def test_courses_search_and_paging(client, db, make_user, make_course):
    c = make_course(db)
    c.code = "MMT"
    c.name = "Mạng máy tính"
    db.commit()
    for _ in range(11):
        make_course(db)
    h = make_user(db, role="training_office")

    body = client.get("/courses", params={"search": "mạng máy"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["code"] == "MMT"

    body = client.get("/courses", params={"size": 10}, headers=h).json()
    assert body["totalElements"] == 12
    assert len(body["data"]) == 10


def test_courses_all_returns_plain_list(client, db, make_user, make_course):
    for _ in range(3):
        make_course(db)
    h = make_user(db, role="training_office")

    data = client.get("/courses/all", headers=h).json()
    assert isinstance(data, list)
    assert len(data) == 3


# ---------- Lớp học phần ----------


def test_course_classes_search_by_course_and_lecturer(client, db, make_user, make_lecturer,
                                                      make_course, make_course_class):
    gv = make_lecturer(db)
    gv.name = "Lê Văn Dạy"
    db.commit()
    c1 = make_course(db)
    c1.code = "TTNT"
    c1.name = "Trí tuệ nhân tạo"
    db.commit()
    make_course_class(db, c1, lecturer=gv)
    make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    # Tìm theo mã học phần
    body = client.get("/course-classes", params={"search": "TTNT"}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["course_code"] == "TTNT"

    # Tìm theo tên giảng viên
    body = client.get("/course-classes", params={"search": "Lê Văn Dạy"}, headers=h).json()
    assert body["totalElements"] == 1

    # Lớp không có giảng viên vẫn trả về khi không search
    body = client.get("/course-classes", headers=h).json()
    assert body["totalElements"] == 2


def test_course_classes_filters(client, db, make_user, make_lecturer, make_course, make_course_class):
    gv = make_lecturer(db)
    c = make_course(db)
    cc1 = make_course_class(db, c, lecturer=gv, year=2026, term=1, status="open")
    make_course_class(db, c, year=2026, term=2, status="closed")
    h = make_user(db, role="training_office")

    body = client.get("/course-classes", params={"term": 2}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["term"] == 2

    body = client.get("/course-classes", params={"year": 2026, "term": 1}, headers=h).json()
    assert body["totalElements"] == 1

    body = client.get("/course-classes", params={"status": "closed"}, headers=h).json()
    assert body["totalElements"] == 1

    body = client.get("/course-classes", params={"course_id": c.id}, headers=h).json()
    assert body["totalElements"] == 2

    body = client.get("/course-classes", params={"lecturer_id": gv.id}, headers=h).json()
    assert body["totalElements"] == 1
    assert body["data"][0]["id"] == cc1.id


def test_course_classes_all_route_not_swallowed_by_id(client, db, make_user, make_course,
                                                      make_course_class):
    """/course-classes/all phải đứng trước /{id} — trả list thuần, không 422."""
    make_course_class(db, make_course(db))
    h = make_user(db, role="training_office")

    resp = client.get("/course-classes/all", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
