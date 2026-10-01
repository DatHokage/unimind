"""Best-effort JSON cache backed by Redis, with a local development fallback.

Redis is the shared cache used in production.  When ``REDIS_URL`` is empty,
this module uses a bounded process-local cache so local development needs no
Redis server.  A configured Redis outage is treated as a cache miss/write skip;
this avoids serving divergent stale data from one web worker.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
_PREFIX = f"ql:{CACHE_VERSION}:"
_MAX_MEMORY_ENTRIES = 1000
_RETRY_AFTER_SECONDS = 30.0
_MEMORY_ONLY = object()

TTL_CATALOG = 600
TTL_CLASS_LIST = 60
TTL_TERM = 900
TTL_STUDENT = 300
TTL_STATS = 600
TTL_AI_PAYLOAD = 300
TTL_RAG_RETRIEVAL = 86400
TTL_CHAT_SESSION = 86400


class CacheService:
    """Small cache-aside service whose failures never escape to business code."""

    def __init__(self, *, _client: Any = None) -> None:
        self._redis = _client
        self._memory: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.RLock()
        self._redis_failed_until = 0.0
        self._recovery_lock = threading.Lock()
        self._needs_cleanup = False
        self._redis_failure_logged = False

    @property
    def _redis_configured(self) -> bool:
        return self._redis is not _MEMORY_ONLY and (
            self._redis is not None or bool(settings.REDIS_URL.strip())
        )

    def _client(self) -> Any:
        """Return the injected/lazy client, or None while the breaker is open."""
        if self._redis is _MEMORY_ONLY or not self._redis_configured:
            return None
        if time.monotonic() < self._redis_failed_until:
            return None
        if self._needs_cleanup:
            if not self._recovery_lock.acquire(blocking=False):
                return None
            try:
                if self._redis is None:
                    self._create_client()
                self._redis.ping()
                # Invalidations may have been missed during the outage. Only
                # DB-derived families are purged; embeddings/chat are separate.
                for family in (
                    "cat:", "cc:", "sched:", "enr:", "grade:",
                    "stats:", "aipayload:",
                ):
                    self._delete_matching(self._redis, _PREFIX + family)
                self._needs_cleanup = False
                self._mark_redis_success()
            except Exception as exc:
                self._mark_redis_failure(exc)
                return None
            finally:
                self._recovery_lock.release()
        if self._redis is not None:
            return self._redis
        try:
            self._create_client()
            return self._redis
        except Exception as exc:
            self._mark_redis_failure(exc)
            return None

    def _create_client(self) -> None:
        import redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        self._redis = redis.Redis.from_url(
            settings.REDIS_URL.strip(),
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            health_check_interval=30,
            retry=Retry(NoBackoff(), 0),
        )

    def _mark_redis_failure(self, exc: Exception) -> None:
        self._needs_cleanup = True
        self._redis_failed_until = time.monotonic() + _RETRY_AFTER_SECONDS
        if not self._redis_failure_logged:
            logger.warning(
                "Redis cache unavailable; bypassing cache for %.0fs (%s)",
                _RETRY_AFTER_SECONDS,
                type(exc).__name__,
            )
            self._redis_failure_logged = True

    def _mark_redis_success(self) -> None:
        if self._redis_failure_logged:
            logger.info("Redis cache recovered")
        self._redis_failure_logged = False
        self._redis_failed_until = 0.0

    @staticmethod
    def _ttl(ttl: int | None) -> int | None:
        if ttl is None:
            return None
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0:
            raise ValueError("cache TTL must be a positive integer")
        return ttl

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode(raw: str) -> Any:
        return json.loads(raw)

    def get_json(self, key: str) -> Any | None:
        full_key = _PREFIX + key
        client = self._client()
        if client is not None:
            try:
                raw = client.get(full_key)
                self._mark_redis_success()
                if raw is None:
                    return None
                try:
                    return self._decode(raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    try:
                        client.delete(full_key)
                    except Exception:
                        pass
                    logger.warning("Ignoring malformed cache entry")
                    return None
            except Exception as exc:
                self._mark_redis_failure(exc)
                return None
        if self._redis_configured:
            return None
        return self._memory_get(full_key)

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        full_key = _PREFIX + key
        try:
            ttl = self._ttl(ttl)
            encoded = self._encode(value)
        except (TypeError, ValueError):
            logger.debug("Skipping invalid cache value or TTL")
            return
        client = self._client()
        if client is not None:
            try:
                if ttl is None:
                    client.set(full_key, encoded)
                else:
                    client.set(full_key, encoded, ex=ttl)
                self._mark_redis_success()
                return
            except Exception as exc:
                self._mark_redis_failure(exc)
                return
        if not self._redis_configured:
            self._memory_set(full_key, encoded, ttl)

    def append_json(self, key: str, value: Any, limit: int, ttl: int) -> None:
        """Bounded JSON history; WATCH prevents lost updates across workers."""
        from redis.exceptions import WatchError

        full_key = _PREFIX + key
        client = self._client()
        if client is not None:
            try:
                for _ in range(5):
                    with client.pipeline() as pipe:
                        try:
                            pipe.watch(full_key)
                            raw = pipe.get(full_key)
                            try:
                                values = self._decode(raw) if raw else []
                            except (TypeError, ValueError):
                                values = []
                            if not isinstance(values, list):
                                values = []
                            encoded = self._encode((values + [value])[-limit:])
                            pipe.multi()
                            pipe.set(full_key, encoded, ex=ttl)
                            pipe.execute()
                            self._mark_redis_success()
                            return
                        except WatchError:
                            continue
                logger.warning("Skipping chat history write after contention")
            except Exception as exc:
                self._mark_redis_failure(exc)
            return
        if not self._redis_configured:
            with self._lock:
                values = self._memory_get(full_key) or []
                if not isinstance(values, list):
                    values = []
                self.set_json(key, (values + [value])[-limit:], ttl)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        full_keys = [_PREFIX + key for key in keys]
        client = self._client()
        if client is not None:
            try:
                client.delete(*full_keys)
                self._mark_redis_success()
            except Exception as exc:
                self._mark_redis_failure(exc)
        if not self._redis_configured:
            self._memory_delete(*full_keys)

    def delete_prefix(self, prefix: str) -> None:
        full_prefix = _PREFIX + prefix
        client = self._client()
        if client is not None:
            try:
                self._delete_matching(client, full_prefix)
                self._mark_redis_success()
            except Exception as exc:
                self._mark_redis_failure(exc)
        if not self._redis_configured:
            self._memory_delete_prefix(full_prefix)

    @staticmethod
    def _delete_matching(client: Any, prefix: str) -> None:
        batch: list[str] = []
        for key in client.scan_iter(match=prefix + "*", count=200):
            batch.append(key)
            if len(batch) == 200:
                client.unlink(*batch)
                batch.clear()
        if batch:
            client.unlink(*batch)

    def ping(self) -> bool:
        client = self._client()
        if client is None:
            return False
        try:
            result = bool(client.ping())
            if result:
                self._mark_redis_success()
            return result
        except Exception as exc:
            self._mark_redis_failure(exc)
            return False

    def clear_all(self) -> None:
        self.delete_prefix("")
        with self._lock:
            self._memory.clear()

    def close(self) -> None:
        client = self._redis
        if client not in (None, _MEMORY_ONLY):
            try:
                close = getattr(client, "close", None)
                if close:
                    close()
            except Exception:
                logger.debug("Unable to close Redis cache client")

    def _memory_get(self, key: str) -> Any | None:
        with self._lock:
            item = self._memory.get(key)
            if item is None:
                return None
            raw, expire_at = item
            if expire_at is not None and time.monotonic() >= expire_at:
                self._memory.pop(key, None)
                return None
        try:
            return self._decode(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            self._memory_delete(key)
            return None

    def _memory_set(self, key: str, encoded: str, ttl: int | None) -> None:
        with self._lock:
            now = time.monotonic()
            for existing, (_, expiry) in list(self._memory.items()):
                if expiry is not None and now >= expiry:
                    del self._memory[existing]
            if key in self._memory:
                del self._memory[key]
            while len(self._memory) >= _MAX_MEMORY_ENTRIES:
                del self._memory[next(iter(self._memory))]
            self._memory[key] = (encoded, now + ttl if ttl is not None else None)

    def _memory_delete(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._memory.pop(key, None)

    def _memory_delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in tuple(self._memory):
                if key.startswith(prefix):
                    del self._memory[key]


cache = CacheService()


def build_key(*parts: Any) -> str:
    return ":".join("" if part is None else str(part) for part in parts)


def invalidate_catalog() -> None:
    for prefix in ("cat:", "cc:", "sched:", "enr:", "grade:", "aipayload:", "stats:"):
        cache.delete_prefix(prefix)


def invalidate_class_caches() -> None:
    for prefix in ("cc:", "sched:", "aipayload:", "stats:", "enr:"):
        cache.delete_prefix(prefix)


def invalidate_homeroom_rosters() -> None:
    for prefix in ("cat:homerooms", "cat:advisors:", "aipayload:", "stats:"):
        cache.delete_prefix(prefix)


def invalidate_after_enrollment_change(student_id: int, course_class_id: int | None = None) -> None:
    cache.delete(
        f"enr:stu:{student_id}",
        f"grade:stu:{student_id}",
        f"grade:gpa:{student_id}",
        f"aipayload:summary:{student_id}",
    )
    cache.delete_prefix(f"sched:stu:{student_id}:")
    cache.delete_prefix("aipayload:advice:")
    cache.delete_prefix("cc:list:")
    cache.delete_prefix("cc:all:")
    if course_class_id is not None:
        cache.delete(f"cc:item:{course_class_id}")
    cache.delete_prefix("stats:")


def invalidate_after_grade_change(
    student_id: int,
    course_class_id: int | None = None,
    homeroom_id: int | None = None,
) -> None:
    cache.delete(
        f"grade:stu:{student_id}",
        f"grade:gpa:{student_id}",
        f"aipayload:summary:{student_id}",
    )
    if homeroom_id is not None:
        cache.delete(f"aipayload:overview:{homeroom_id}")
    if course_class_id is not None:
        cache.delete(f"cc:item:{course_class_id}")
    cache.delete_prefix("stats:")


def invalidate_student_caches(student_id: int) -> None:
    cache.delete(
        f"enr:stu:{student_id}",
        f"grade:stu:{student_id}",
        f"grade:gpa:{student_id}",
        f"aipayload:summary:{student_id}",
    )
    cache.delete_prefix(f"sched:stu:{student_id}:")
    cache.delete_prefix(f"aipayload:advice:{student_id}:")
    invalidate_homeroom_rosters()
