"""Smoke SV004 (DTC004) — kiểm tra đủ bộ dữ liệu dashboard + GPA mới trên server thật.

Chạy:  PYTHONPATH=. python scripts/smoke_DTC004.py   (từ backend/, server chạy ở port 8000;
       đổi server: set SMOKE_BASE=http://127.0.0.1:8001)
Tiên quyết: đã chạy `python -m app.seed` (seed idempotent nên chạy lại được).

Bộ dữ liệu SV004 từ seed:
    2025-T1: TH1.A    7.0 (B)      Đạt
    2025-T2: CTDL.B   5.5 (C)      Đạt
             GDTC1.B  9.0 (A)      Đạt — counted_in_gpa=False → loại khỏi GPA
             GT1.B    2.5 (F)      Trượt — tính GPA 0đ, KHÔNG cộng tín chỉ tích lũy
    2026-T1: CSDL.A   —            đang học (chưa có điểm)
             OOP.B    —            đang học (chưa có điểm)

Kỳ vọng: 3 học kỳ · 6 đăng ký · gpa4=1.50 · gpa10=4.75 · credits=8 · tích lũy=6
         (tích lũy gồm GDTC1 dù không tính GPA — môn Đạt là tích lũy)
"""

import os
import sys

import httpx

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8000")
USERNAME = "DTC004"
PASSWORD = "password123"


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    if not cond:
        check.fails.append(name)
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))


check.fails = []


def login(username):
    r = httpx.post(f"{BASE}/auth/login", data={"username": username, "password": PASSWORD})
    assert r.status_code == 200, f"login {username}: {r.status_code} {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    h = login(USERNAME)
    me = httpx.get(f"{BASE}/auth/me", headers=h).json()
    sid = me.get("student_id")
    if not sid:
        print("[FAIL] /auth/me không trả student_id")
        sys.exit(1)

    # ---------- 1) Bảng điểm: đủ 6 đăng ký, đủ kỳ, đủ trạng thái ----------
    grades = httpx.get(f"{BASE}/grades/student/{sid}", headers=h).json()
    check("có 6 dòng điểm", len(grades) == 6, f"len={len(grades)}")

    by_code = {g["course_code"]: g for g in grades}
    terms = {(g["year"], g["term"]) for g in grades}
    check("đủ 3 học kỳ (2025-T1, 2025-T2, 2026-T1)",
          terms == {(2025, 1), (2025, 2), (2026, 1)}, str(terms))

    exp = {  # code: (total, letter, status, counted_in_gpa, credits)
        "TH1": (7.0, "B", "đạt", True, 2),
        "CTDL": (5.5, "C", "đạt", True, 3),
        "GDTC1": (9.0, "A", "đạt", False, 1),
        "GT1": (2.5, "F", "không đạt", True, 3),
        "CSDL": (None, None, "chưa có điểm", True, 3),
        "OOP": (None, None, "chưa có điểm", True, 3),
    }
    for code, (total, letter, status, counted, credits) in exp.items():
        g = by_code.get(code)
        if g is None:
            check(f"{code}: có trong bảng điểm", False, str(list(by_code)))
            continue
        ok = (
            g["total_score"] == total
            and g["letter_grade"] == letter
            and g["status"] == status
            and g["counted_in_gpa"] == counted
            and g["credits"] == credits
        )
        check(f"{code}: total={total} letter={letter} status='{status}' counted={counted}",
              ok, str(g)[:200])

    # ---------- 2) Dashboard: 5 thẻ thống kê ----------
    enrollments = httpx.get(f"{BASE}/enrollments/student/{sid}", headers=h).json()
    gpa = httpx.get(f"{BASE}/grades/student/{sid}/gpa", headers=h).json()

    n_terms = len(terms)  # số học kỳ đã học = số kỳ có dòng điểm
    check("card 'Học kỳ đã học' = 3", n_terms == 3, f"got {n_terms}")
    check("card 'Số lớp đăng ký' = 6", len(enrollments) == 6, f"got {len(enrollments)}")
    check("card 'Tổng số tín chỉ tích lũy' = 6 (mọi môn Đạt, kể cả GDTC1)",
          gpa.get("accumulated_credits") == 6, str(gpa))
    check("card 'GPA tích lũy (hệ 4)' = 1.50", gpa.get("gpa4") == 1.50, str(gpa))
    check("card 'Điểm TB tích lũy (hệ 10)' = 4.75", gpa.get("gpa10") == 4.75, str(gpa))
    check("credits đã tính vào GPA = 8 (F vẫn tính, GDTC1 loại)",
          gpa.get("credits") == 8, str(gpa))

    # ---------- 3) Thời khóa biểu kỳ hiện tại 2026-T1 ----------
    r = httpx.get(f"{BASE}/schedule/student/{sid}", headers=h)
    sched = r.json() if r.status_code == 200 else {}
    check("TKB → 200, kỳ 2026-T1, có CSDL + OOP",
          r.status_code == 200 and (sched.get("year"), sched.get("term")) == (2026, 1)
          and {c.get("course_code") for c in sched.get("classes", [])} == {"CSDL", "OOP"},
          r.text[:200])

    # ---------- 4) Phân quyền: SV004 không xem GPA/điểm SV khác ----------
    r = httpx.get(f"{BASE}/grades/student/{sid - 1}/gpa", headers=h)
    check("xem GPA sinh viên khác → 403", r.status_code == 403, str(r.status_code))

    # ---------- 5) AI course-advice: CTDL đạt 5.5 ≥ 5.0 → đủ tiên quyết OOP/CSDL ----------
    r = httpx.post(f"{BASE}/ai/course-advice", json={"student_id": sid}, headers=h, timeout=180)
    check("AI course-advice SV004 → 200, có eligible",
          r.status_code == 200 and len(r.json().get("eligible_classes", [])) >= 1,
          r.text[:200])
    r = httpx.post(f"{BASE}/ai/study-summary", json={"student_id": sid}, headers=h, timeout=180)
    check("AI study-summary SV004 → 200 (có GT1 low score trong dữ liệu)",
          r.status_code == 200, r.text[:200])

    fails = check.fails
    print(f"\nTổng: PASS {len(check.fails) == 0 and 'hết' or (28 - len(fails))}, FAIL {len(fails)}")
    if fails:
        print("Các bước FAIL:", *fails, sep="\n  - ")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
