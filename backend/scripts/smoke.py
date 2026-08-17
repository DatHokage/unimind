"""Smoke test end-to-end các luồng vai trò trên server đang chạy (port 8000).

Chạy:  python scripts/smoke.py   (từ backend/, sau khi server + seed sẵn sàng)
Đổi server:  set SMOKE_BASE=http://127.0.0.1:8001 (mặc định :8000)
"""

import os
import sys

import httpx

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")

results = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    return cond


def login(username):
    r = httpx.post(f"{BASE}/auth/login", data={"username": username, "password": "password123"})
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def main():
    # Console Windows mặc định cp1252 — ép UTF-8 để in tiếng Việt không lỗi
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    h_stu1 = login("DTC001")
    h_stu2 = login("DTC002")
    h_stu3 = login("DTC003")
    h_lect = login("DTCGV001")
    h_advisor = login("DTCCV001")
    h_office = login("ptdt")
    h_admin = login("DTCAD001")
    check("đăng nhập đủ 7 tài khoản demo", True)

    # Đăng nhập không phân biệt hoa/thường: gõ thường dtcgv001 vẫn được
    r = httpx.post(f"{BASE}/auth/login", data={"username": "dtcgv001", "password": "password123"})
    check("đăng nhập không phân biệt hoa/thường (dtcgv001) → 200", r.status_code == 200, r.text[:120])

    # id sinh viên lấy qua /auth/me (không hardcode id — seed có thể thay đổi)
    sid1 = httpx.get(f"{BASE}/auth/me", headers=h_stu1).json()["student_id"]
    sid3 = httpx.get(f"{BASE}/auth/me", headers=h_stu3).json()["student_id"]

    # Idempotent: dọn đăng ký kỳ 2026-T1 của DTC001 do lần chạy trước để lại
    # (seed không đăng ký sẵn kỳ này cho DTC001 — có là của smoke run cũ)
    for e in httpx.get(f"{BASE}/enrollments/student/{sid1}", headers=h_stu1).json():
        if (e.get("year"), e.get("term")) == (2026, 1):
            httpx.delete(f"{BASE}/enrollments/{e['id']}", headers=h_stu1)

    # Lấy id lớp đang mở kỳ 2026-T1 (endpoint phân trang; định danh lớp bằng phòng)
    classes = httpx.get(
        f"{BASE}/course-classes", params={"status": "open", "size": 100}, headers=h_stu1
    ).json()["data"]
    by_room = {(c["course_code"], (c["schedule"][0] or {}).get("room")): c for c in classes}
    ctdl = by_room[("CTDL", "B201")]     # CTDL.A — lớp chính demo đăng ký
    csdl = by_room[("CSDL", "B202")]     # CSDL.A — max_size=2, đã đầy từ seed
    oop = by_room[("OOP", "B203")]       # OOP.A — trùng lịch CTDL.A + cần tiên quyết CTDL

    # 1) DTC001 (đã đạt TH1) đăng ký CTDL → 201
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": ctdl["id"]}, headers=h_stu1)
    check("DTC001 đăng ký CTDL.A → 201", r.status_code == 201, r.text[:120])
    enr_stu1_ctdl = r.json().get("id")

    # 2) DTC002 (trượt TH1) đăng ký CTDL → 400 tiên quyết
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": ctdl["id"]}, headers=h_stu2)
    check("DTC002 bị chặn tiên quyết CTDL.A → 400", r.status_code == 400, r.text[:120])

    # 3) CSDL.A đã đủ chỗ từ seed (DTC003+DTC004, max_size=2) → mọi đăng ký mới đều 400
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": csdl["id"]}, headers=h_stu1)
    check("DTC001 đăng ký CSDL.A đầy lớp → 400", r.status_code == 400, r.text[:120])
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": csdl["id"]}, headers=h_stu3)
    check("DTC003 đăng ký CSDL.A đầy lớp → 400", r.status_code == 400, r.text[:120])

    # 4) DTC001 đăng ký OOP.A trùng lịch CTDL.A → 400; hơn nữa chưa đạt CTDL
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": oop["id"]}, headers=h_stu1)
    check("DTC001 đăng ký OOP.A (chưa đạt CTDL + trùng lịch) → 400", r.status_code == 400, r.text[:120])

    # 5) trùng đăng ký
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": ctdl["id"]}, headers=h_stu1)
    check("đăng ký trùng CTDL.A → 400", r.status_code == 400, r.text[:120])

    # 6) hủy đăng ký rồi đăng ký lại
    r = httpx.delete(f"{BASE}/enrollments/{enr_stu1_ctdl}", headers=h_stu1)
    check("DTC001 hủy đăng ký CTDL.A → 200", r.status_code == 200, r.text[:120])
    r = httpx.post(f"{BASE}/enrollments", json={"course_class_id": ctdl["id"]}, headers=h_stu1)
    check("DTC001 đăng ký lại CTDL.A → 201", r.status_code == 201, r.text[:120])

    # 7) ranh giới nhập điểm: lấy 1 enrollment kỳ 2025 (TH1.A của DTC003)
    enr_stu3 = httpx.get(f"{BASE}/enrollments/student/{sid3}", headers=h_advisor).json()
    enr_2025 = [e for e in enr_stu3 if e["year"] == 2025][0]
    r = httpx.put(f"{BASE}/grades/{enr_2025['id']}/exam", json={"score": 5.0}, headers=h_lect)
    check("lecturer nhập điểm THI → 403", r.status_code == 403, r.text[:120])
    r = httpx.put(f"{BASE}/grades/{enr_2025['id']}/process", json={"score": 9.0}, headers=h_office)
    check("office nhập điểm QUÁ TRÌNH → 403", r.status_code == 403, r.text[:120])
    r = httpx.put(f"{BASE}/grades/{enr_2025['id']}/process", json={"score": 8.0}, headers=h_lect)
    check("lecturer (đúng lớp) nhập điểm quá trình → 200", r.status_code == 200, r.text[:120])
    r = httpx.put(f"{BASE}/grades/{enr_2025['id']}/exam", json={"score": 6.0}, headers=h_office)
    total = r.json().get("total_score")
    check("office nhập điểm thi → 200 và total tự tính = 7.0", r.status_code == 200 and total == 7.0, f"total={total}")
    r = httpx.put(f"{BASE}/grades/{enr_2025['id']}/process", json={"score": 11.0}, headers=h_lect)
    check("điểm ngoài 0–10 → 422", r.status_code == 422, r.text[:80])

    # 8) phân quyền đọc điểm
    r = httpx.get(f"{BASE}/grades/student/{sid1}", headers=h_stu2)
    check("student xem điểm sinh viên khác → 403", r.status_code == 403, r.text[:80])
    r = httpx.get(f"{BASE}/grades/student/{sid1}", headers=h_stu1)
    check("student xem bảng điểm của mình → 200", r.status_code == 200)

    # 8b) thời khóa biểu sinh viên (DTC001 đã đăng ký CTDL kỳ 2026-T1)
    r = httpx.get(f"{BASE}/schedule/student/{sid1}", headers=h_stu1)
    sched = r.json() if r.status_code == 200 else {}
    check(
        "student xem thời khóa biểu của mình → 200, kỳ mới nhất 2026-T1 có CTDL",
        r.status_code == 200 and (sched.get("year"), sched.get("term")) == (2026, 1)
        and any(c.get("course_code") == "CTDL" for c in sched.get("classes", [])),
        r.text[:120],
    )
    r = httpx.get(f"{BASE}/schedule/student/{sid1}", headers=h_stu2)
    check("student xem thời khóa biểu sinh viên khác → 403", r.status_code == 403)
    r = httpx.get(f"{BASE}/schedule/student/{sid1}", headers=h_lect)
    check("lecturer xem thời khóa biểu sinh viên → 403", r.status_code == 403)
    r = httpx.get(f"{BASE}/schedule/student/{sid1}", params={"year": 2026, "term": 1}, headers=h_office)
    check("office xem thời khóa biểu theo kỳ → 200", r.status_code == 200)

    # 9) advisor: chỉ thấy lớp mình, thống kê bị giới hạn
    mine = httpx.get(f"{BASE}/homeroom-classes/mine", headers=h_advisor).json()
    check("advisor thấy đúng 2 lớp chủ nhiệm", len(mine) == 2, str(mine)[:120])
    r = httpx.get(f"{BASE}/stats/academic-results", headers=h_advisor)
    check("advisor xem thống kê (mặc định lớp mình) → 200, đủ 2 lớp", r.status_code == 200 and len(r.json()) == 2)
    r = httpx.get(f"{BASE}/stats/academic-results", headers=h_stu1)
    check("student gọi thống kê → 403", r.status_code == 403)

    # 10) office: thống kê đầy đủ + popular courses
    r = httpx.get(f"{BASE}/stats/popular-courses", headers=h_office)
    check("office xem popular-courses → 200", r.status_code == 200)
    r = httpx.get(f"{BASE}/stats/popular-courses", headers=h_stu1)
    check("student gọi popular-courses → 403", r.status_code == 403)

    # 11) AI: course-advice + study-summary (có key LLM thì AI trả thật, không thì fallback server-side)
    r = httpx.post(f"{BASE}/ai/course-advice", json={"student_id": sid1}, headers=h_stu1, timeout=180)
    body = r.json()
    check(
        "AI course-advice DTC001 → 200, có eligible",
        r.status_code == 200 and len(body.get("eligible_classes", [])) >= 1,
        r.text[:150],
    )
    r = httpx.post(f"{BASE}/ai/course-advice", json={"student_id": sid1}, headers=h_stu2, timeout=60)
    check("AI course-advice hộ người khác → 403", r.status_code == 403)
    r = httpx.post(f"{BASE}/ai/study-summary", json={"student_id": sid1}, headers=h_advisor, timeout=180)
    check("AI study-summary (advisor xem SV lớp mình) → 200", r.status_code == 200, r.text[:150])

    # 12) regulation chat (RAG): status → sẵn sàng thì chat thật, không thì 503
    r = httpx.get(f"{BASE}/ai/regulation-chat/status", headers=h_stu1)
    check("regulation-chat status → 200", r.status_code == 200, r.text[:120])
    ready = r.json().get("ready") is True
    r = httpx.post(
        f"{BASE}/ai/regulation-chat",
        json={"question": "Sinh viên vắng thi quá bao nhiêu % thì bị cấm thi?"},
        headers=h_stu1,
        timeout=180,
    )
    if ready:
        body = r.json()
        check(
            "regulation-chat → 200 có answer",
            r.status_code == 200 and bool(body.get("answer")),
            r.text[:150],
        )
    else:
        check("regulation-chat chưa cấu hình → 503", r.status_code == 503, r.text[:120])

    # 13) health
    r = httpx.get(f"{BASE}/health")
    check("GET /health → 200", r.status_code == 200)

    fails = [x for x in results if x[0] == "FAIL"]
    print(f"\nTổng: {len(results)} bước, {len(results) - len(fails)} PASS, {len(fails)} FAIL")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
