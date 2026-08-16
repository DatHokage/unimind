def test_list_students_paginated_shape(client, db, make_user, make_student):
    """GET /students trả về page metadata đúng và chỉ chứa dữ liệu của trang hiện tại."""
    for _ in range(25):
        make_student(db)
    h = make_user(db, role="training_office")

    resp = client.get("/students", params={"page": 0, "size": 20}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 0
    assert body["size"] == 20
    assert body["totalElements"] == 25
    assert body["totalPages"] == 2
    assert len(body["data"]) == 20
    # Sắp xếp theo mã SV
    codes = [s["code"] for s in body["data"]]
    assert codes == sorted(codes)

    first_page_ids = {s["id"] for s in body["data"]}

    resp = client.get("/students", params={"page": 1, "size": 20}, headers=h)
    body = resp.json()
    assert body["page"] == 1
    assert len(body["data"]) == 5
    # Trang 1 không trùng bản ghi với trang 0
    assert all(s["id"] not in first_page_ids for s in body["data"])


def test_list_students_search_by_code_and_name(client, db, make_user, make_student):
    """Search xử lý ở backend: khớp cả mã SV lẫn họ tên."""
    make_student(db, code="SV-RIENG-01")
    for _ in range(3):
        make_student(db)
    h = make_user(db, role="training_office")

    resp = client.get("/students", params={"search": "SV-RIENG-01"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalElements"] == 1
    assert body["data"][0]["code"] == "SV-RIENG-01"

    # 4 sinh viên đều có tên chứa "sinh viên" (factory đặt tên "Sinh viên N")
    resp = client.get("/students", params={"search": "sinh viên"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["totalElements"] == 4


def test_list_students_search_paging_consistency(client, db, make_user, make_student):
    """totalPages tính đúng cho kết quả search; trang vượt quá tổng số trả về mảng rỗng."""
    for _ in range(10):
        make_student(db)
    h = make_user(db, role="training_office")

    resp = client.get("/students", params={"search": "Sinh viên", "page": 0, "size": 4}, headers=h)
    body = resp.json()
    assert body["totalElements"] == 10
    assert body["totalPages"] == 3
    assert len(body["data"]) == 4

    resp = client.get("/students", params={"page": 99, "size": 20}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["totalElements"] == 10


def test_list_students_invalid_params_rejected(client, db, make_user):
    h = make_user(db, role="training_office")
    assert client.get("/students", params={"page": -1}, headers=h).status_code == 422
    assert client.get("/students", params={"size": 0}, headers=h).status_code == 422
    assert client.get("/students", params={"size": 101}, headers=h).status_code == 422


def test_list_students_requires_role(client, db, make_user, make_student):
    h = make_user(db, role="student", student=make_student(db))
    resp = client.get("/students", headers=h)
    assert resp.status_code == 403
