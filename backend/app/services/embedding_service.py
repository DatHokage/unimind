"""Embedding qua Voyage AI API (async, httpx — không dùng SDK, không tải model local).

Voyage CHỈ đảm nhận bước ① tạo vector cho chatbot quy chế (RAG): nhúng chunk
khi build vector store và nhúng câu hỏi khi tìm kiếm. Voyage KHÔNG sinh câu
trả lời (không có model chat) — việc trả lời là của OpenRouter/Gemini
(app/services/llm_service.py).

Model duy nhất: settings.VOYAGE_MODEL (mặc định voyage-4) — khai báo 1 chỗ,
dùng chung cho MỌI nơi gọi embedding. Cố định model giữa lúc build index và
lúc query là bắt buộc (mỗi model = 1 không gian vector riêng).

input_type:
  - "document" — nhúng chunk lúc build vector store (mặc định của hàm).
  - "query"    — nhúng câu hỏi user lúc tìm kiếm.
Voyage khuyến nghị phân biệt 2 loại này để tối ưu chất lượng retrieval.

Endpoint: POST https://api.voyageai.com/v1/embeddings
Key: VOYAGE_API_KEY trong backend/.env (đọc qua settings).
Lỗi 429/5xx/mạng/timeout tự retry tối đa 2 lần với backoff ngắn (1s, 2s);
lỗi client (400/401/403...) KHÔNG retry.
"""

import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"

# Batch nhiều text trong 1 request để giảm số lần gọi API khi rebuild vector
# store (Voyage miễn phí giới hạn request/phút).
EMBED_BATCH_SIZE = 10

# Retry tối đa 2 lần với backoff tăng dần cho 429/5xx/lỗi mạng/timeout.
MAX_RETRIES = 2
_RETRY_DELAYS = (1.0, 2.0)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class EmbeddingError(Exception):
    """Lỗi khi gọi embedding API (mạng, rate-limit sau khi đã retry, thiếu key)."""


def _parse_embedding(item: dict, context: str) -> list[float]:
    """Lấy vector từ 1 phần tử response. Ném EmbeddingError nếu cấu trúc lạ."""
    try:
        values = item["embedding"]
    except (KeyError, TypeError):
        raise EmbeddingError(
            f"Voyage API trả về cấu trúc không mong muốn ({context})")
    if not values:
        raise EmbeddingError(f"Voyage API trả về vector rỗng ({context})")
    return [float(v) for v in values]


async def _embed_one_call(client: httpx.AsyncClient, texts: list[str],
                          input_type: str) -> dict:
    """Gọi Voyage embeddings 1 lần (batch 1..n text), retry 429/5xx/mạng/timeout.

    Trả dict response thô {"data": [...], "usage": ...}; người gọi tự parse.
    """
    if not settings.VOYAGE_API_KEY:
        raise EmbeddingError(
            "Chưa cấu hình VOYAGE_API_KEY trong backend/.env — embedding cho "
            "chatbot quy chế bắt buộc dùng Voyage AI (key: dash.voyageai.com)")
    body = {
        "input": list(texts),
        "model": settings.VOYAGE_MODEL,
        "input_type": input_type,
    }
    last_error = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.post(
                VOYAGE_API_URL, json=body,
                headers={"Authorization": f"Bearer {settings.VOYAGE_API_KEY}"})
        except httpx.TimeoutException:
            last_error = f"timeout sau {_TIMEOUT.read}s"
            logger.warning("Voyage API %s (lần %d/%d)", last_error,
                           attempt + 1, MAX_RETRIES + 1)
        except httpx.HTTPError as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning("Voyage API lỗi mạng %s (lần %d/%d)", last_error,
                           attempt + 1, MAX_RETRIES + 1)
        else:
            if response.status_code == 200:
                return response.json()
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code == 429 or response.status_code >= 500:
                logger.warning("Voyage API %s (lần %d/%d)", last_error,
                               attempt + 1, MAX_RETRIES + 1)
            else:
                # Lỗi client (key sai, input quá dài...) — retry cũng không hết
                logger.error("Voyage API lỗi vĩnh viễn: %s", last_error)
                raise EmbeddingError(f"Voyage API {last_error}")
        if attempt < MAX_RETRIES:
            await asyncio.sleep(_RETRY_DELAYS[attempt])
    raise EmbeddingError(
        f"Voyage API thất bại sau {MAX_RETRIES + 1} lần thử: {last_error}")


def _parse_batch(data: dict, expected: int, context: str) -> list[list[float]]:
    """Parse {"data": [{"embedding": [...], "index": i}, ...]} giữ thứ tự input."""
    try:
        items = data["data"]
    except (KeyError, TypeError):
        raise EmbeddingError(f"Voyage API trả về cấu trúc không mong muốn ({context})")
    if len(items) != expected:
        raise EmbeddingError(
            f"Voyage API trả {len(items)} vector cho {expected} text ({context})")
    # Phòng xa: response có trường index — sắp theo index để chắc chắn đúng
    # thứ tự input dù server trả không theo thứ tự.
    if all(isinstance(it, dict) and "index" in it for it in items):
        items = sorted(items, key=lambda it: it["index"])
    return [_parse_embedding(it, context) for it in items]


async def get_embedding(text: str, input_type: str = "document") -> list[float]:
    """Nhúng 1 đoạn văn bản → vector. Ném EmbeddingError khi không gọi được.

    input_type="document" khi nhúng chunk (build vector store), "query" khi
    nhúng câu hỏi user (tìm kiếm).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        data = await _embed_one_call(client, [text], input_type)
    return _parse_batch(data, 1, "embed 1 text")[0]


async def get_embeddings(texts: list[str],
                         input_type: str = "document") -> list[list[float]]:
    """Nhúng nhiều text theo batch — dùng khi rebuild index. Giữ thứ tự input.

    Tách batch thay vì gộp hết vào 1 request vì Voyage giới hạn số text/lần.
    """
    if not texts:
        return []
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i:i + EMBED_BATCH_SIZE]
            data = await _embed_one_call(client, batch, input_type)
            vectors.extend(_parse_batch(data, len(batch), f"batch {i}"))
    return vectors
