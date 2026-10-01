"""Test tầng cache (app/core/cache.py) + các hàm invalidation.

Hai chế độ được kiểm tra:
- **In-memory** (REDIS_URL trống): đường chạy thật của local dev Windows và
  của prod khi Redis chết — phải đúng TTL, giới hạn quota, xóa prefix.
- **Redis** (fakeredis): cùng hành vi qua client Redis thật về mặt giao thức,
  kèm nhánh circuit-breaker khi Redis lỗi giữa chừng.

Phần cuối kiểm tra các lỗi invalidation đã từng có: key khai báo phải KHỚP key
thực tế mà router/service ghi (sched/aipayload có đuôi year/term, overview
theo homeroom_id chứ không phải course_class_id).
"""

import time

import fakeredis
import pytest
from app.core.cache import (
    _MAX_MEMORY_ENTRIES,
    CACHE_VERSION,
    CacheService,
    _PREFIX,
    build_key,
    invalidate_after_enrollment_change,
    invalidate_after_grade_change,
    invalidate_catalog,
    invalidate_class_caches,
    invalidate_homeroom_rosters,
    invalidate_student_caches,
)


@pytest.fixture()
def mem_cache():
    """Cache thuần in-memory: không REDIS_URL → mọi thao tác đi đường fallback."""
    return CacheService()


@pytest.fixture()
def redis_cache():
    """Cache có Redis (fakeredis) — inject sẵn để bỏ qua lazy init."""
    return CacheService(_client=fakeredis.FakeStrictRedis(decode_responses=True))


# ------------------------------------------------ in-memory (đường chạy mặc định)

def test_memory_set_get(mem_cache):
    mem_cache.set_json("k", {"a": 1}, ttl=60)
    assert mem_cache.get_json("k") == {"a": 1}


def test_memory_get_miss_returns_none(mem_cache):
    assert mem_cache.get_json("khong-ton-tai") is None


def test_memory_ttl_het_han(mem_cache, monkeypatch):
    """TTL phải thật sự hết hạn — không phải chỉ ghi mà không bao giờ quên.

    Dùng đồng hồ giả thay vì sleep: `time.monotonic()` trên Windows chỉ nhích
    mỗi ~15.6ms nên sleep ngắn có thể không làm hết hạn, test sẽ chập chờn.
    """
    clock = {"now": 1000.0}
    monkeypatch.setattr("app.core.cache.time.monotonic", lambda: clock["now"])

    mem_cache.set_json("k", "v", ttl=60)
    assert mem_cache.get_json("k") == "v"  # còn hạn

    clock["now"] += 61  # nhảy qua mốc hết hạn
    assert mem_cache.get_json("k") is None


def test_memory_entry_het_han_bi_don_khi_doc(mem_cache, monkeypatch):
    """Đọc trúng entry hết hạn phải xóa luôn khỏi dict — không để rác tích tụ."""
    clock = {"now": 1000.0}
    monkeypatch.setattr("app.core.cache.time.monotonic", lambda: clock["now"])

    mem_cache.set_json("k", "v", ttl=10)
    clock["now"] += 11
    mem_cache.get_json("k")
    assert "k" not in mem_cache._memory


def test_memory_khong_ttl_thi_khong_het_han(mem_cache):
    mem_cache.set_json("k", "v", ttl=None)
    assert mem_cache.get_json("k") == "v"


def test_memory_delete(mem_cache):
    mem_cache.set_json("a", 1, ttl=60)
    mem_cache.set_json("b", 2, ttl=60)
    mem_cache.delete("a")
    assert mem_cache.get_json("a") is None
    assert mem_cache.get_json("b") == 2  # xóa đích danh, không đụng key khác


def test_memory_delete_prefix(mem_cache):
    mem_cache.set_json("sched:stu:1:2026:1", "x", ttl=60)
    mem_cache.set_json("sched:stu:1:2026:2", "y", ttl=60)
    mem_cache.set_json("sched:stu:2:2026:1", "z", ttl=60)
    mem_cache.delete_prefix("sched:stu:1:")
    assert mem_cache.get_json("sched:stu:1:2026:1") is None
    assert mem_cache.get_json("sched:stu:1:2026:2") is None
    assert mem_cache.get_json("sched:stu:2:2026:1") == "z"  # SV khác còn nguyên


def test_memory_quota_khong_vuot_gioi_han(mem_cache):
    """Vượt quota thì bỏ entry cũ nhất — RAM Render free chỉ 512MB."""
    for i in range(_MAX_MEMORY_ENTRIES + 50):
        mem_cache.set_json(f"k{i}", i, ttl=None)
    assert len(mem_cache._memory) <= _MAX_MEMORY_ENTRIES
    assert mem_cache.get_json(f"k{_MAX_MEMORY_ENTRIES + 49}") is not None  # entry mới nhất còn


def test_memory_luu_duoc_unicode(mem_cache):
    """Tiếng Việt phải round-trip nguyên vẹn (ensure_ascii=False)."""
    mem_cache.set_json("k", {"ten": "Nguyễn Văn A", "mon": "Lập trình"}, ttl=60)
    assert mem_cache.get_json("k")["ten"] == "Nguyễn Văn A"


def test_clear_all_xoa_ca_hai_tang(mem_cache):
    mem_cache.set_json("k", "v", ttl=60)
    mem_cache.clear_all()
    assert mem_cache.get_json("k") is None
    assert mem_cache._memory == {}


# --------------------------------------------------------------- qua Redis

def test_redis_set_get(redis_cache):
    redis_cache.set_json("k", [1, 2, 3], ttl=60)
    assert redis_cache.get_json("k") == [1, 2, 3]


def test_redis_key_co_prefix_version(redis_cache):
    """Mọi key phải nằm trong namespace ql:{version}: — bump version là xả sạch."""
    redis_cache.set_json("k", "v", ttl=60)
    assert redis_cache._redis.get(f"{_PREFIX}k") is not None


def test_redis_delete_prefix_dung_scan(redis_cache):
    for term in (1, 2, 3):
        redis_cache.set_json(f"sched:stu:1:2026:{term}", term, ttl=60)
    redis_cache.set_json("sched:stu:2:2026:1", "khac", ttl=60)
    redis_cache.delete_prefix("sched:stu:1:")
    assert redis_cache.get_json("sched:stu:1:2026:1") is None
    assert redis_cache.get_json("sched:stu:2:2026:1") == "khac"


def test_redis_ttl_duoc_dat(redis_cache):
    redis_cache.set_json("k", "v", ttl=123)
    assert 0 < redis_cache._redis.ttl(f"{_PREFIX}k") <= 123


def test_redis_ping(redis_cache):
    assert redis_cache.ping() is True


def test_redis_loi_thi_ngung_thu_lai(redis_cache, monkeypatch):
    """Redis lỗi giữa chừng → circuit breaker 30s, request sau không chờ timeout."""

    def _boom(*a, **kw):
        raise ConnectionError("Redis sập")

    monkeypatch.setattr(redis_cache._redis, "get", _boom)
    assert redis_cache.get_json("k") is None  # nuốt lỗi, coi như miss
    assert redis_cache._redis_failed_until > time.monotonic()  # đã đánh dấu
    monkeypatch.undo()
    # Trong 30s tới, _client() trả None → đi thẳng in-memory, không thử Redis
    assert redis_cache._client() is None


def test_redis_failure_does_not_fallback_to_memory(redis_cache, monkeypatch):
    """Redis chết → miss/write skip, không dùng state riêng của worker."""
    def _boom(*a, **kw):
        raise ConnectionError("Redis sập")

    monkeypatch.setattr(redis_cache._redis, "set", _boom)
    redis_cache.set_json("k", "v", ttl=60)
    assert redis_cache.get_json("k") is None


def test_tat_redis_thi_dung_memory(monkeypatch):
    """REDIS_URL trống → không bao giờ thử import/khởi tạo Redis."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "REDIS_URL", "")
    c = CacheService()
    assert c._client() is None
    c.set_json("k", "v", ttl=60)
    assert c.get_json("k") == "v"


# ------------------------------------------------------------- build_key

def test_build_key_ghep_cac_phan():
    assert build_key("cat", "majors", "all") == "cat:majors:all"
    assert build_key("sched", "stu", 1, 2026, 1) == "sched:stu:1:2026:1"


def test_build_key_bo_qua_none_thanh_chuoi_rong():
    """Router truyền `year or ""` — key phải ổn định, không sinh 'None'."""
    assert build_key("sched", "stu", 1, None, None) == "sched:stu:1::"


# --------------------------------------------------- invalidation: khớp key thật
#
# Nhóm test dưới đây khoá lại các lỗi đã từng có: hàm invalidate xóa key
# KHÔNG khớp key mà router/service thực tế ghi → cache trả dữ liệu cũ tới
# khi hết TTL. Mỗi test ghi key ĐÚNG như code thật rồi kiểm tra nó bị xóa.


def test_enrollment_change_xoa_sched_theo_prefix(mem_cache, monkeypatch):
    """sched:stu:{id}:{year}:{term} có ĐUÔI — xóa tên trần sẽ trượt hết."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("sched:stu:7:2026:1", "lich-ky-1", ttl=300)
    mem_cache.set_json("sched:stu:7:2026:2", "lich-ky-2", ttl=300)
    mem_cache.set_json("sched:stu:8:2026:1", "sv-khac", ttl=300)

    invalidate_after_enrollment_change(7, course_class_id=55)

    assert mem_cache.get_json("sched:stu:7:2026:1") is None
    assert mem_cache.get_json("sched:stu:7:2026:2") is None
    assert mem_cache.get_json("sched:stu:8:2026:1") == "sv-khac"


def test_enrollment_change_xoa_advice_theo_prefix(mem_cache, monkeypatch):
    """aipayload:advice:{id}:{year}:{term} cũng có đuôi."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("aipayload:advice:7:2026:1", "tu-van", ttl=300)
    mem_cache.set_json("aipayload:advice:7::", "tu-van-mac-dinh", ttl=300)

    invalidate_after_enrollment_change(7)

    assert mem_cache.get_json("aipayload:advice:7:2026:1") is None
    assert mem_cache.get_json("aipayload:advice:7::") is None


def test_enrollment_change_xoa_bang_diem_va_gpa(mem_cache, monkeypatch):
    """Hủy đăng ký xóa luôn dòng Grade → bảng điểm/GPA cached phải bỏ."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("grade:stu:7", "bang-diem", ttl=300)
    mem_cache.set_json("grade:gpa:7", "gpa", ttl=300)
    mem_cache.set_json("enr:stu:7", "dang-ky", ttl=300)

    invalidate_after_enrollment_change(7, course_class_id=55)

    assert mem_cache.get_json("grade:stu:7") is None
    assert mem_cache.get_json("grade:gpa:7") is None
    assert mem_cache.get_json("enr:stu:7") is None
    assert mem_cache.get_json("cc:item:55") is None


def test_grade_change_xoa_overview_theo_homeroom(mem_cache, monkeypatch):
    """Nhận xét lớp cache theo homeroom_id — KHÔNG phải course_class_id."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("aipayload:overview:3", "nhan-xet-lop-hc-3", ttl=300)
    mem_cache.set_json("aipayload:overview:9", "lop-hc-khac", ttl=300)

    invalidate_after_grade_change(student_id=7, course_class_id=55, homeroom_id=3)

    assert mem_cache.get_json("aipayload:overview:3") is None
    assert mem_cache.get_json("aipayload:overview:9") == "lop-hc-khac"


def test_grade_change_bo_qua_overview_khi_thieu_homeroom(mem_cache, monkeypatch):
    """Không truyền homeroom_id → không đụng nhận xét lớp nào (tránh xóa mù)."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("aipayload:overview:3", "nhan-xet", ttl=300)

    invalidate_after_grade_change(student_id=7, course_class_id=55)

    assert mem_cache.get_json("aipayload:overview:3") == "nhan-xet"


def test_student_change_xoa_roster_lop_hanh_chinh(mem_cache, monkeypatch):
    """SV đổi lớp/xóa → danh sách lớp HC đếm SV và nhận xét lớp phải nạp lại."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("cat:homerooms:all", "ds-lop", ttl=600)
    mem_cache.set_json("cat:homerooms:mine:2", "lop-cua-cv-2", ttl=600)
    mem_cache.set_json("aipayload:overview:3", "nhan-xet", ttl=300)
    mem_cache.set_json("sched:stu:7:2026:1", "lich", ttl=300)

    invalidate_student_caches(7)

    assert mem_cache.get_json("cat:homerooms:all") is None
    assert mem_cache.get_json("cat:homerooms:mine:2") is None
    assert mem_cache.get_json("aipayload:overview:3") is None
    assert mem_cache.get_json("sched:stu:7:2026:1") is None


def test_homeroom_rosters_xoa_stats(mem_cache, monkeypatch):
    """stats tính từ danh sách SV của lớp → thêm/bớt SV phải xóa stats."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("stats:academic:office:0:0:0:0", "thong-ke", ttl=600)
    mem_cache.set_json("stats:popular:10", "pho-bien", ttl=600)
    mem_cache.set_json("cat:majors:all", "nganh", ttl=600)  # nhóm khác, phải giữ

    invalidate_homeroom_rosters()

    assert mem_cache.get_json("stats:academic:office:0:0:0:0") is None
    assert mem_cache.get_json("stats:popular:10") is None
    assert mem_cache.get_json("cat:majors:all") == "nganh"


def test_catalog_xoa_ca_stats_va_danh_muc(mem_cache, monkeypatch):
    """Đổi tên ngành → bảng stats in kèm tên ngành phải tính lại."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("cat:majors:all", "nganh", ttl=600)
    mem_cache.set_json("stats:academic:office:0:0:0:0", "thong-ke", ttl=600)
    mem_cache.set_json("cc:list:1:2026:::", "lop", ttl=60)
    mem_cache.set_json("sched:stu:7:2026:1", "lich", ttl=300)  # không đụng

    invalidate_catalog()

    assert mem_cache.get_json("cat:majors:all") is None
    assert mem_cache.get_json("stats:academic:office:0:0:0:0") is None
    assert mem_cache.get_json("cc:list:1:2026:::") is None
    assert mem_cache.get_json("sched:stu:7:2026:1") is None


def test_class_caches_xoa_lich_va_stats(mem_cache, monkeypatch):
    """CRUD lớp/buổi học đổi lịch → thời khóa biểu SV và stats phải bỏ."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    mem_cache.set_json("cc:item:55", "lop", ttl=60)
    mem_cache.set_json("sched:stu:7:2026:1", "lich", ttl=300)
    mem_cache.set_json("stats:popular:10", "pho-bien", ttl=600)
    mem_cache.set_json("enr:stu:7", "dang-ky", ttl=300)  # không đụng

    invalidate_class_caches()

    assert mem_cache.get_json("cc:item:55") is None
    assert mem_cache.get_json("sched:stu:7:2026:1") is None
    assert mem_cache.get_json("stats:popular:10") is None
    assert mem_cache.get_json("enr:stu:7") is None


def test_invalidate_khong_vo_khi_cache_trong(mem_cache, monkeypatch):
    """Gọi invalidate lúc cache rỗng không được ném lỗi."""
    monkeypatch.setattr("app.core.cache.cache", mem_cache)
    invalidate_catalog()
    invalidate_class_caches()
    invalidate_homeroom_rosters()
    invalidate_student_caches(1)
    invalidate_after_enrollment_change(1, 2)
    invalidate_after_grade_change(1, 2, 3)


def test_cache_version_nam_trong_prefix():
    """Đổi CACHE_VERSION là cách xả sạch key cũ — prefix phải theo version."""
    assert CACHE_VERSION in _PREFIX


# ------------------------------------------- tích hợp: invalidate qua API thật
#
# Các test trên khẳng định hàm invalidate xóa đúng KEY. Nhóm dưới đây khẳng
# định điều đó nối thành hành vi đúng từ góc nhìn người dùng: gọi API lần 2
# sau khi ghi dữ liệu phải thấy dữ liệu MỚI, không phải bản cache cũ. Đây
# chính là kịch bản đã hỏng trước khi sửa (key có đuôi year/term bị xóa trượt).


def test_dang_ky_lam_moi_thoi_khoa_bieu(
    client, db, make_user, make_student, make_course, make_course_class
):
    """Đăng ký xong, GET /schedule lần 2 phải thấy lớp mới (không phải cache rỗng)."""
    cc = make_course_class(db, make_course(db), year=2026, term=1)
    student = make_student(db)
    headers = make_user(db, role="student", student=student)

    first = client.get(f"/schedule/student/{student.id}", headers=headers)
    assert first.status_code == 200
    assert first.json()["classes"] == []  # cache miss đầu tiên: chưa có lớp

    resp = client.post("/enrollments", json={"course_class_id": cc.id}, headers=headers)
    assert resp.status_code == 201

    second = client.get(f"/schedule/student/{student.id}", headers=headers)
    assert second.status_code == 200
    assert len(second.json()["classes"]) == 1  # KHÔNG được là cache rỗng


def test_huy_dang_ky_xoa_dong_trong_bang_diem(
    client, db, make_user, make_student, make_course, make_course_class, make_enrollment
):
    """Hủy đăng ký (chưa có điểm) xóa luôn dòng Grade → bảng điểm phải bỏ dòng đó."""
    cc = make_course_class(db, make_course(db), year=2026, term=1)
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc)  # không điểm → hủy được
    headers = make_user(db, role="student", student=student)

    before = client.get(f"/grades/student/{student.id}", headers=headers)
    assert before.status_code == 200
    assert len(before.json()) == 1  # dòng "chưa có điểm"

    resp = client.delete(f"/enrollments/{enrollment.id}", headers=headers)
    assert resp.status_code == 200

    after = client.get(f"/grades/student/{student.id}", headers=headers)
    assert after.status_code == 200
    assert after.json() == []  # KHÔNG được còn dòng đã hủy


def test_chuyen_lop_cap_nhat_si_so_lop_hanh_chinh(
    client, db, make_user, make_homeroom, make_student, make_advisor
):
    """SV chuyển lớp HC → dropdown lớp HC (đếm SV) phải cập nhật."""
    advisor = make_advisor(db)
    lop_cu = make_homeroom(db, advisor=advisor)
    lop_moi = make_homeroom(db, advisor=advisor)
    student = make_student(db, homeroom=lop_cu)
    headers = make_user(db, role="training_office")

    before = client.get("/homeroom-classes/all", headers=headers)
    assert before.status_code == 200
    counts = {h["id"]: h["student_count"] for h in before.json()}
    assert counts[lop_cu.id] == 1 and counts[lop_moi.id] == 0

    resp = client.put(
        f"/students/{student.id}", json={"class_id": lop_moi.id}, headers=headers
    )
    assert resp.status_code == 200

    after = client.get("/homeroom-classes/all", headers=headers)
    assert after.status_code == 200
    counts = {h["id"]: h["student_count"] for h in after.json()}
    assert counts[lop_cu.id] == 0  # KHÔNG được còn 1
    assert counts[lop_moi.id] == 1


def test_nhap_diem_lam_moi_bang_diem_va_stats(
    client, db, make_user, make_lecturer, make_student, make_course,
    make_course_class, make_enrollment,
):
    """Nhập điểm xong, bảng điểm và stats phải thấy điểm mới."""
    lecturer = make_lecturer(db)
    cc = make_course_class(db, make_course(db), lecturer=lecturer, year=2026, term=1)
    student = make_student(db)
    enrollment = make_enrollment(db, student, cc)
    h_lecturer = make_user(db, role="lecturer", lecturer=lecturer)
    h_office = make_user(db, role="training_office")

    before = client.get(f"/grades/student/{student.id}", headers=h_office)
    assert before.json()[0]["total_score"] is None

    resp = client.put(
        f"/grades/{enrollment.id}/process", json={"score": 8.0}, headers=h_lecturer
    )
    assert resp.status_code == 200

    after = client.get(f"/grades/student/{student.id}", headers=h_office)
    assert after.json()[0]["process_score"] == 8.0

    stats = client.get("/stats/popular-courses", headers=h_office)
    assert stats.status_code == 200  # stats bị xóa, tính lại không lỗi

