"""Test embedding_service (Voyage AI) — toàn bộ HTTP bị mock, KHÔNG gọi API thật."""
import httpx
import pytest

from app.core.config import settings
from app.services import embedding_service
from app.services.embedding_service import (
    EMBED_BATCH_SIZE,
    MAX_RETRIES,
    VOYAGE_API_URL,
    EmbeddingError,
    get_embedding,
    get_embeddings,
)


def _response(status=200, json_body=None, text=""):
    # json_body và text loại trừ nhau: httpx.Response.json() giải mã content,
    # truyền cả hai thì content = text (rỗng) → .json() nổ.
    if json_body is not None:
        return httpx.Response(status_code=status, json=json_body)
    return httpx.Response(status_code=status, text=text)


@pytest.mark.anyio
async def test_get_embedding_returns_vector(monkeypatch):
    """200 → vector float đúng cấu trúc từ API Voyage."""
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _response(200, {"data": [{"embedding": [0.1, -0.2, 0.3],
                                         "index": 0}],
                               "usage": {"total_tokens": 5}})

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "voyage-test-key")
    monkeypatch.setattr(settings, "VOYAGE_MODEL", "voyage-4")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    vec = await get_embedding("Câu hỏi thử")
    assert vec == [0.1, -0.2, 0.3]
    # Đúng endpoint Voyage + key truyền qua header Bearer (không hardcode rải rác)
    assert captured["url"] == VOYAGE_API_URL
    assert captured["headers"]["Authorization"] == "Bearer voyage-test-key"
    # Model là hằng số duy nhất khai báo trong settings — không hardcode
    assert captured["json"]["model"] == "voyage-4"
    assert captured["json"]["input"] == ["Câu hỏi thử"]
    # Mặc định là "document" (nhúng chunk lúc build index)
    assert captured["json"]["input_type"] == "document"


@pytest.mark.anyio
async def test_get_embedding_query_input_type(monkeypatch):
    """input_type='query' được truyền nguyên vẹn khi nhúng câu hỏi."""
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["json"] = json
        return _response(200, {"data": [{"embedding": [1.0], "index": 0}]})

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await get_embedding("Khi nào bị cấm thi?", input_type="query")
    assert captured["json"]["input_type"] == "query"


@pytest.mark.anyio
async def test_get_embedding_no_key_raises(monkeypatch):
    """Không có VOYAGE_API_KEY → EmbeddingError rõ ràng (không gọi mạng)."""
    calls = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        calls["n"] += 1
        raise AssertionError("KHÔNG được gọi mạng khi thiếu key")

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(EmbeddingError, match="VOYAGE_API_KEY"):
        await get_embedding("x")
    assert calls["n"] == 0


@pytest.mark.anyio
async def test_get_embedding_retries_429_then_succeeds(monkeypatch):
    """429 → tự retry với backoff → lần 2 thành công."""
    calls = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return _response(429, text="rate limited")
        return _response(200, {"data": [{"embedding": [1.0], "index": 0}]})

    async def no_sleep(_):  # không ngủ thật trong test
        pass

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(embedding_service.asyncio, "sleep", no_sleep)

    vec = await get_embedding("x")
    assert vec == [1.0]
    assert calls["n"] == 2  # 1 lần 429 + 1 lần thành công


@pytest.mark.anyio
async def test_get_embedding_retries_timeout_then_succeeds(monkeypatch):
    """Timeout mạng → cũng được retry (không chết ngay lần đầu)."""
    calls = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timeout")
        return _response(200, {"data": [{"embedding": [2.0], "index": 0}]})

    async def no_sleep(_):
        pass

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(embedding_service.asyncio, "sleep", no_sleep)

    vec = await get_embedding("x")
    assert vec == [2.0]
    assert calls["n"] == 2


@pytest.mark.anyio
async def test_get_embedding_exhausts_retries(monkeypatch):
    """429 liên tục quá số lần retry → EmbeddingError."""
    calls = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        calls["n"] += 1
        return _response(429, text="rate limited")

    async def no_sleep(_):
        pass

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(embedding_service.asyncio, "sleep", no_sleep)

    with pytest.raises(EmbeddingError, match="thất bại"):
        await get_embedding("x")
    # 1 lần đầu + MAX_RETRIES lần retry
    assert calls["n"] == MAX_RETRIES + 1


@pytest.mark.anyio
async def test_get_embedding_no_retry_on_client_error(monkeypatch):
    """400 (lỗi client, retry vô ích) → ném ngay, KHÔNG retry."""
    calls = {"n": 0}

    async def fake_post(self, url, json=None, headers=None):
        calls["n"] += 1
        return _response(400, text="bad request")

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    with pytest.raises(EmbeddingError):
        await get_embedding("x")
    assert calls["n"] == 1  # không retry lỗi 4xx client


@pytest.mark.anyio
async def test_get_embeddings_batch_preserves_order(monkeypatch):
    """Nhiều text → tách batch, giữ đúng thứ tự vector (kể cả server trả lộn index)."""
    texts = [f"text {i}" for i in range(3)]
    # Đặt batch size nhỏ để buộc tách nhiều batch
    monkeypatch.setattr(embedding_service, "EMBED_BATCH_SIZE", 2)
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")

    async def fake_post(self, url, json=None, headers=None):
        # Voyage batch: {"input": [...], "model", "input_type"} → data[] kèm index.
        # Trả index LỘN trong batch (2,0 / 3) để kiểm tra code sắp lại theo index.
        start = fake_post.counter
        n = len(json["input"])
        fake_post.counter += n
        items = [{"embedding": [float(start + i)], "index": i} for i in range(n)]
        return _response(200, {"data": list(reversed(items))})

    fake_post.counter = 0

    async def no_sleep(_):
        pass

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    monkeypatch.setattr(embedding_service.asyncio, "sleep", no_sleep)

    vecs = await get_embeddings(texts)
    assert len(vecs) == 3
    # Batch 1 = text0,text1 → [0,1]; batch 2 = text2 → [2]. Giữ thứ tự.
    assert vecs == [[0.0], [1.0], [2.0]]


@pytest.mark.anyio
async def test_get_embeddings_batch_uses_document_input_type(monkeypatch):
    """Batch nhúng chunk truyền input_type do người gọi chỉ định."""
    captured = {}

    async def fake_post(self, url, json=None, headers=None):
        captured["json"] = json
        return _response(200, {"data": [{"embedding": [1.0], "index": 0}]})

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(settings, "VOYAGE_MODEL", "voyage-4")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    await get_embeddings(["chunk 1"], input_type="document")
    assert captured["json"]["input_type"] == "document"
    assert captured["json"]["model"] == "voyage-4"


@pytest.mark.anyio
async def test_get_embeddings_empty(monkeypatch):
    assert await get_embeddings([]) == []
    # EMBED_BATCH_SIZE vẫn là hằng số dương (điều kiện tách batch)
    assert EMBED_BATCH_SIZE >= 1
