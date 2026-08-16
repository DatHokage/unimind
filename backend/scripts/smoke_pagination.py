"""Smoke nhanh endpoint GET /students phân trang trên server chạy thật (port 8001)."""
import sys
import httpx

BASE = "http://127.0.0.1:8001"
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


r = httpx.post(f"{BASE}/auth/login", data={"username": "ptdt", "password": "password123"})
assert r.status_code == 200, f"login ptdt: {r.status_code} {r.text}"
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 1) shape + page 0/size 2
r = httpx.get(f"{BASE}/students", params={"page": 0, "size": 2}, headers=h)
b = r.json()
check("GET /students?page=0&size=2 → 200", r.status_code == 200, r.text[:150])
check("response có đủ key data/page/size/totalElements/totalPages",
      all(k in b for k in ("data", "page", "size", "totalElements", "totalPages")), str(b)[:200])
check("size=2 → đúng 2 bản ghi", len(b.get("data", [])) == 2, str(b)[:200])
check("totalElements=4, totalPages=2 (seed 4 SV)",
      b.get("totalElements") == 4 and b.get("totalPages") == 2, str(b)[:200])
check("page vọng lại = 0, size = 2", b.get("page") == 0 and b.get("size") == 2)

# 2) trang 2 chứa phần còn lại, không trùng trang 1
r2 = httpx.get(f"{BASE}/students", params={"page": 1, "size": 2}, headers=h).json()
check("trang 2 có 2 bản ghi", len(r2["data"]) == 2, str(r2)[:200])
ids1 = {s["id"] for s in b["data"]}
check("trang 2 không trùng trang 1", all(s["id"] not in ids1 for s in r2["data"]))

# 3) search theo mã SV (backend)
r3 = httpx.get(f"{BASE}/students", params={"search": "SV003"}, headers=h).json()
check("search 'SV003' → 1 kết quả đúng mã",
      r3["totalElements"] == 1 and r3["data"][0]["code"] == "SV003", str(r3)[:200])

# 4) search theo họ tên (backend, tiếng Việt)
r4 = httpx.get(f"{BASE}/students", params={"search": "hoàng văn"}, headers=h).json()
check("search họ tên 'hoàng văn' → 1 kết quả (Hoàng Văn Tam)",
      r4["totalElements"] == 1 and r4["data"][0]["name"] == "Hoàng Văn Tam", str(r4)[:200])

# 5) search không khớp
r5 = httpx.get(f"{BASE}/students", params={"search": "zzz-khong-ton-tai"}, headers=h).json()
check("search vô nghĩa → 0 kết quả, totalPages=0",
      r5["totalElements"] == 0 and r5["data"] == [] and r5["totalPages"] == 0, str(r5)[:200])

# 6) page vượt quá tổng → mảng rỗng
r6 = httpx.get(f"{BASE}/students", params={"page": 50, "size": 20}, headers=h).json()
check("page=50 → data rỗng, totalElements vẫn 4",
      r6["data"] == [] and r6["totalElements"] == 4, str(r6)[:200])

# 7) tham số không hợp lệ → 422
check("page=-1 → 422", httpx.get(f"{BASE}/students", params={"page": -1}, headers=h).status_code == 422)
check("size=0 → 422", httpx.get(f"{BASE}/students", params={"size": 0}, headers=h).status_code == 422)
check("size=500 → 422", httpx.get(f"{BASE}/students", params={"size": 500}, headers=h).status_code == 422)

# 8) student không được list toàn bộ
r = httpx.post(f"{BASE}/auth/login", data={"username": "student1", "password": "password123"})
h_stu = {"Authorization": f"Bearer {r.json()['access_token']}"}
check("student gọi GET /students → 403", httpx.get(f"{BASE}/students", headers=h_stu).status_code == 403)

print("\n" + ("TẤT CẢ PASS ✅" if ok else "CÓ FAIL ❌"))
sys.exit(0 if ok else 1)
