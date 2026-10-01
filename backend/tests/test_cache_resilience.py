import time

import fakeredis
import pytest

from app.core.cache import CacheService, _PREFIX


@pytest.fixture(params=[False, True])
def store(request):
    client = fakeredis.FakeStrictRedis(decode_responses=True) if request.param else None
    return CacheService(_client=client)


def test_values_are_detached_json(store):
    value = {"items": [1]}
    store.set_json("value", value, 60)
    value["items"].append(2)
    result = store.get_json("value")
    assert result == {"items": [1]}
    result["items"].append(3)
    assert store.get_json("value") == {"items": [1]}


@pytest.mark.parametrize("ttl", [0, -1, True, 0.5, "60"])
def test_invalid_ttl_skips_write(store, ttl):
    store.set_json("value", 1, ttl)
    assert store.get_json("value") is None


def test_recovery_discards_missed_business_invalidations(monkeypatch):
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = CacheService(_client=client)
    store.set_json("grade:stu:1", "stale", 60)
    store.set_json("embed:one", [1], 60)
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise ConnectionError("secret-url-must-not-be-logged")
        patch.setattr(client, "delete", fail)
        store.delete("grade:stu:1")
    assert store.get_json("grade:stu:1") is None
    store._redis_failed_until = time.monotonic() - 1
    assert store.get_json("grade:stu:1") is None
    assert client.get(_PREFIX + "grade:stu:1") is None
    assert store.get_json("embed:one") == [1]
    assert not store._needs_cleanup


def test_malformed_json_is_miss_not_outage():
    client = fakeredis.FakeStrictRedis(decode_responses=True)
    store = CacheService(_client=client)
    client.set(_PREFIX + "bad", "not-json")
    assert store.get_json("bad") is None
    assert not store._needs_cleanup
    store.set_json("ok", 1, 60)
    assert store.get_json("ok") == 1


def test_cache_error_logs_do_not_contain_credentials(caplog):
    store = CacheService()
    store._mark_redis_failure(ValueError("redis://user:secret@host"))
    assert "secret" not in caplog.text


def test_chat_history_is_bounded_and_has_ttl(store):
    for index in range(5):
        store.append_json("chat:test", [str(index), "answer"], limit=3, ttl=60)
    assert store.get_json("chat:test") == [
        ["2", "answer"], ["3", "answer"], ["4", "answer"]
    ]
    if store._redis is not None:
        assert 0 < store._redis.ttl(_PREFIX + "chat:test") <= 60


def test_enrollment_invalidates_shared_availability(store, monkeypatch):
    from app.core.cache import invalidate_after_enrollment_change

    monkeypatch.setattr("app.core.cache.cache", store)
    keys = ["cc:list:2026:1", "cc:all:", "aipayload:advice:2:2026:1"]
    for key in keys:
        store.set_json(key, {"remaining_slots": 1}, 60)
    invalidate_after_enrollment_change(1, 10)
    for key in keys:
        assert store.get_json(key) is None
