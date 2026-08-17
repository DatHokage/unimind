from app.core.security import hash_password
from app.models import User


def test_login_success(client, db):
    db.add(User(username="ptdt", password_hash=hash_password("password123"), role="training_office"))
    db.commit()
    resp = client.post("/auth/login", data={"username": "ptdt", "password": "password123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["role"] == "training_office"


def test_login_case_insensitive(client, db):
    db.add(User(username="DTCGV001", password_hash=hash_password("password123"), role="lecturer"))
    db.commit()
    for typed in ("DTCGV001", "dtcgv001", "Dtcgv001"):
        resp = client.post("/auth/login", data={"username": typed, "password": "password123"})
        assert resp.status_code == 200, typed
        assert resp.json()["user"]["username"] == "DTCGV001"  # trả về tên gốc trong DB


def test_login_wrong_password(client, db):
    db.add(User(username="ptdt", password_hash=hash_password("password123"), role="training_office"))
    db.commit()
    resp = client.post("/auth/login", data={"username": "ptdt", "password": "sai"})
    assert resp.status_code == 401


def test_me(client, db, make_user):
    headers = make_user(db, role="training_office")
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "training_office"


def test_me_garbage_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})
    assert resp.status_code == 401
