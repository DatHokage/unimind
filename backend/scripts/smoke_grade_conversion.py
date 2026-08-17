"""Smoke tính năng quy đổi điểm chữ/hệ 4 + GPA tín chỉ trên server thật.

Chạy:  python scripts/smoke_grade_conversion.py   (từ backend/, server port 8000;
       đổi server: set SMOKE_BASE=http://127.0.0.1:8001)
Các ca mutate điểm đều được restore về giá trị gốc ở cuối.
"""
import os
import sys
import httpx

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")

# Chạy trực tiếp "python scripts/smoke_grade_conversion.py" vẫn import được app/*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ok = True


def check(name, cond, detail=""):
    global ok
    status = "PASS" if cond else "FAIL"
    if not cond:
        ok = False
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))


def login(username, password="password123"):
    r = httpx.post(f"{BASE}/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------- 1) Hàm quy đổi thuần (boundaries) ----------
from app.services.grade_service import convert_score10

cases = [
    (10, "A", 4), (8.5, "A", 4), (8.49, "B", 3), (7.0, "B", 3),
    (6.99, "C", 2), (5.5, "C", 2), (5.49, "D", 1), (4.0, "D", 1),
    (3.99, "F", 0), (0, "F", 0),
]
for total, letter, score4 in cases:
    got = convert_score10(total)
    check(f"convert({total}) == {letter}/{score4}", got == (letter, score4), str(got))
check("convert(None) == (None, None)", convert_score10(None) == (None, None))

h_stu1 = login("DTC001")   # SV001 — TH1 7.5
h_stu2 = login("DTC002")   # SV002 — TH1 4.0
h_office = login("ptdt")
h_lecturer = login("DTCGV001")

# ---------- 2) Bảng điểm trả điểm chữ / hệ 4 / kết quả ----------
r_me = httpx.get(f"{BASE}/auth/me", headers=h_stu1)
sid1 = r_me.json().get("student_id") if r_me.status_code == 200 else None

if sid1:
    g1 = httpx.get(f"{BASE}/grades/student/{sid1}", headers=h_stu1).json()
    check("DTC001 có bản ghi điểm", len(g1) >= 1, str(g1)[:200])
    row = next((x for x in g1 if x.get("total_score") is not None), None)
    if row:
        check("SV001 total=7.5 → letter B / score4 3 / đạt",
              row["letter_grade"] == "B" and row["score4"] == 3 and row["status"] == "đạt",
              str(row)[:200])
        check("SV001 row có counted_in_gpa", "counted_in_gpa" in row, str(row)[:200])

    gpa1 = httpx.get(f"{BASE}/grades/student/{sid1}/gpa", headers=h_stu1).json()
    # SV001 chỉ có TH1 (2 TC, 7.5→B/3) → GPA = 3*2/2 = 3.0
    check("SV001 GPA hệ 4 = 3.0 (tín chỉ-weighted)", gpa1.get("gpa4") == 3.0, str(gpa1))
    check("SV001 credits đã tính = 2", gpa1.get("credits") == 2, str(gpa1))
else:
    check("có student_id từ /auth/me", False, "auth/me không trả student_id")

# SV002 total 4.0 → D/1 → đạt (theo bảng quy đổi mới: 4.0–5.5 là D = Đạt)
r_me2 = httpx.get(f"{BASE}/auth/me", headers=h_stu2)
sid2 = r_me2.json().get("student_id") if r_me2.status_code == 200 else None
if sid2:
    g2 = httpx.get(f"{BASE}/grades/student/{sid2}", headers=h_stu2).json()
    row2 = next((x for x in g2 if x.get("total_score") is not None), None)
    if row2:
        check("SV002 total=4.0 → letter D / score4 1 / đạt",
              row2["letter_grade"] == "D" and row2["score4"] == 1 and row2["status"] == "đạt",
              str(row2)[:200])
    gpa2 = httpx.get(f"{BASE}/grades/student/{sid2}/gpa", headers=h_stu2).json()
    check("SV002 GPA hệ 4 = 1.0", gpa2.get("gpa4") == 1.0, str(gpa2))

# ---------- 3) Courses có counted_in_gpa (endpoint phân trang) ----------
courses = httpx.get(f"{BASE}/courses", params={"size": 100}, headers=h_office).json()["data"]
check("course list có counted_in_gpa", all("counted_in_gpa" in c for c in courses), str(courses)[:200])

# ---------- 4) Mutation: đổi điểm → tự quy đổi lại (rồi restore) ----------
if sid1:
    g1 = httpx.get(f"{BASE}/grades/student/{sid1}", headers=h_stu1).json()
    row = next((x for x in g1 if x.get("total_score") is not None), None)
    if row:
        eid = row["enrollment_id"]
        orig_process, orig_exam = row["process_score"], row["exam_score"]

        # Office nâng điểm thi lên 10 → total (8+10)/2 = 9.0 → A/4
        r = httpx.put(f"{BASE}/grades/{eid}/exam", json={"score": 10}, headers=h_office)
        check("office set exam=10 → total 9.0 → A/4/đạt",
              r.status_code == 200 and r.json()["total_score"] == 9.0
              and r.json()["letter_grade"] == "A" and r.json()["score4"] == 4,
              r.text[:200])
        # Restore exam
        httpx.put(f"{BASE}/grades/{eid}/exam", json={"score": orig_exam}, headers=h_office)

        # F: cả hai điểm = 0 → total 0 → F/0/không đạt
        httpx.put(f"{BASE}/grades/{eid}/process", json={"score": 0}, headers=h_lecturer)
        r = httpx.put(f"{BASE}/grades/{eid}/exam", json={"score": 0}, headers=h_office)
        check("process=0 & exam=0 → total 0 → F/0/không đạt",
              r.json()["total_score"] == 0 and r.json()["letter_grade"] == "F"
              and r.json()["score4"] == 0 and r.json()["passed"] is False,
              r.text[:200])
        # Restore cả hai về giá trị gốc
        httpx.put(f"{BASE}/grades/{eid}/process", json={"score": orig_process}, headers=h_lecturer)
        httpx.put(f"{BASE}/grades/{eid}/exam", json={"score": orig_exam}, headers=h_office)

        # Xác nhận đã restore
        g1b = httpx.get(f"{BASE}/grades/student/{sid1}", headers=h_stu1).json()
        rowb = next((x for x in g1b if x["enrollment_id"] == eid), None)
        check("restore điểm về giá trị gốc (7.5/B)",
              rowb and rowb["total_score"] == 7.5 and rowb["letter_grade"] == "B",
              str(rowb)[:200])

# ---------- 5) Permission: student không xem GPA người khác ----------
if sid1 and sid2:
    r = httpx.get(f"{BASE}/grades/student/{sid2}/gpa", headers=h_stu1)
    check("DTC001 xem GPA của DTC002 → 403", r.status_code == 403, str(r.status_code))

print("\n" + ("TẤT CẢ PASS ✅" if ok else "CÓ FAIL ❌"))
sys.exit(0 if ok else 1)
