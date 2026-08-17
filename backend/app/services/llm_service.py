"""Gọi LLM qua httpx (async, không dùng SDK).

Với chatbot quy chế (RAG) — vai trò ② sinh câu trả lời, KHÔNG tạo vector:
ưu tiên OpenRouter (OPENROUTER_MODEL đổi tự do qua .env, kể cả model :free);
OpenRouter lỗi/rate-limit/không key thì fallback sang Gemini — không để lỗi
lan tới người dùng nếu còn phương án dự phòng.

Tư vấn học phần / tóm tắt học tập (ai_service.py — JSON output) giữ thứ tự
ngược lại: Gemini trước (response_mime_type JSON ổn định), OpenRouter sau.
"""

import json
import re

import httpx

from app.core.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model :free hay thêm dòng ghi chú ở cuối câu trả lời ("Note: ...", "Ghi chú: ...",
# "Nguồn: ..."...) — cắt bỏ nếu nó xuất hiện ở phần cuối bài.
_NOTE_RE = re.compile(
    r"\n\s*(Ghi chu|Ghi chú|Lưu ý|Note|Chú thích|Nguồn|Nguon|Tai lieu tham khao|"
    r"Xem them|Dich boi|Translated|Generated|Mien phi)\s*[:\.\-]?\s*.*$",
    re.IGNORECASE | re.DOTALL)


class LLMError(Exception):
    """Lỗi khi gọi LLM (mạng, HTTP, parse)."""


def extract_json(text: str) -> dict:
    """Parse JSON từ câu trả lời LLM một cách bền vững.

    Thứ tự thử: json.loads trực tiếp → bỏ fence ```json → lấy chuỗi {...} cân bằng đầu tiên.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Bỏ code fence
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if end > start:
            inner = text[start:end]
            inner = inner.split("\n", 1)[1] if "\n" in inner else inner
            try:
                return json.loads(inner.strip().removeprefix("json").strip())
            except (json.JSONDecodeError, ValueError):
                pass
    # Bắt chuỗi {...} cân bằng đầu tiên
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, ValueError):
                        break
    raise LLMError("Không parse được JSON từ câu trả lời của LLM")


def _check_gemini_finished(data: dict) -> None:
    """Gemini free tier hay bị bộ lọc an toàn chặn / không sinh được câu trả lời
    (promptBlocked, RECITATION, hết quota...) — response HTTP 200 nhưng không có
    văn bản dùng được. Ném LLMError để người gọi (call_llm_*) tự fallback sang
    OpenRouter thay vì trả câu trả lời rỗng/rác cho người dùng.
    """
    candidates = data.get("candidates")
    prompt_feedback = (data.get("promptFeedback") or {})
    block_reason = prompt_feedback.get("blockReason")
    if not candidates:
        raise LLMError(f"Gemini API không trả câu trả lời"
                       f" (blockReason={block_reason or 'không rõ'})")
    finish = candidates[0].get("finishReason")
    if finish and finish not in ("STOP", "MAX_TOKENS"):
        raise LLMError(f"Gemini API dừng sinh giữa chừng (finishReason={finish})")
    if not (candidates[0].get("content") or {}).get("parts"):
        raise LLMError("Gemini API trả về câu trả lời rỗng (có thể bị lọc an toàn)")


async def call_gemini_json(prompt: str) -> dict:
    """Gọi Gemini và bắt buộc trả về JSON object. Ném LLMError nếu lỗi."""
    api_key = settings.gemini_api_key
    if not api_key:
        raise LLMError("Chưa cấu hình GOOGLE_API_KEY (hoặc GEMINI_API_KEY)")
    url = GEMINI_URL.format(model=settings.GEMINI_MODEL)
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        response = await client.post(
            url, json=body, headers={"x-goog-api-key": api_key}
        )
    if response.status_code != 200:
        raise LLMError(f"Gemini API trả về HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    _check_gemini_finished(data)
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMError("Gemini API trả về cấu trúc không mong muốn")
    return extract_json(text)


async def call_openrouter_json(prompt: str) -> dict:
    """Gọi OpenRouter (API tương thích OpenAI) và bắt buộc trả về JSON object."""
    if not settings.OPENROUTER_API_KEY:
        raise LLMError("Chưa cấu hình OPENROUTER_API_KEY")
    body = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "Bạn là trợ lý học vụ. Chỉ trả về JSON hợp lệ, không kèm văn bản nào khác."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        # Không dựa vào response_format — nhiều model miễn phí không hỗ trợ;
        # extract_json đã đủ bền cho cả câu trả lời bọc fence / lẫn chữ thừa.
        # 4096: prompt yêu cầu tư vấn chi tiết (overview + reason từng môn +
        # warnings + suggestions), 2048 token dễ bị cắt giữa chừng JSON.
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "He thong Quan ly Dao tao",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        response = await client.post(OPENROUTER_URL, json=body, headers=headers)
    if response.status_code != 200:
        raise LLMError(f"OpenRouter API trả về HTTP {response.status_code}: {response.text[:300]}")
    data = response.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError("OpenRouter API trả về cấu trúc không mong muốn")
    return extract_json(text)


async def call_llm_json(prompt: str) -> dict:
    """Gọi LLM trả về JSON (tư vấn học phần/tóm tắt học tập): Gemini trước
    (JSON mode ổn định), lỗi thì OpenRouter. Ném LLMError nếu cả hai thất bại
    hoặc không có key nào được cấu hình."""
    errors = []
    for call in (call_gemini_json, call_openrouter_json):
        try:
            return await call(prompt)
        except LLMError as e:
            errors.append(str(e))
    raise LLMError(" | ".join(errors))


def _strip_trailing_notes(text: str) -> str:
    """Cắt dòng ghi chú template hay xuất hiện ở cuối câu trả lời của model :free."""
    if not text:
        return text
    cleaned = text.rstrip()
    for _ in range(4):
        prev = cleaned
        cleaned = _NOTE_RE.sub("", cleaned).rstrip()
        if cleaned == prev:
            break
    return cleaned.strip()


def _as_text(data: dict, path: str) -> str:
    """Bóc chuỗi văn bản theo chuỗi key, ví dụ ["candidates", 0, "content"]."""
    cur = data
    for key in path:
        if not isinstance(cur, (dict, list)):
            raise LLMError(f"LLM API trả về cấu trúc không mong muốn (thiếu {key})")
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"LLM API trả về cấu trúc không mong muốn (thiếu {key})")
    if not isinstance(cur, str):
        raise LLMError("LLM API trả về cấu trúc không mong muốn")
    return cur


async def _call_chat_text(provider: str, prompt: str, system: str = "") -> tuple[str, str, str]:
    """Gọi 1 provider chat completion, trả (text, provider, model).

    system: tin nhắn hệ thống riêng; để trống = ghép vào đầu user prompt
    (dùng cho provider không hỗ trợ role system như Gemini).
    """
    if provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise LLMError("Chưa cấu hình OPENROUTER_API_KEY")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": settings.OPENROUTER_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "He thong Quan ly Dao tao",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            response = await client.post(OPENROUTER_URL, json=body, headers=headers)
        if response.status_code != 200:
            raise LLMError(f"OpenRouter API trả về HTTP {response.status_code}: {response.text[:300]}")
        text = _as_text(response.json(), ["choices", 0, "message", "content"])
        return _strip_trailing_notes(text), "openrouter", settings.OPENROUTER_MODEL

    if provider == "gemini":
        api_key = settings.gemini_api_key
        if not api_key:
            raise LLMError("Chưa cấu hình GOOGLE_API_KEY (hoặc GEMINI_API_KEY)")
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        url = GEMINI_URL.format(model=settings.GEMINI_MODEL)
        body = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(
                url, json=body, headers={"x-goog-api-key": api_key})
        if response.status_code != 200:
            raise LLMError(f"Gemini API trả về HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()
        _check_gemini_finished(data)
        text = _as_text(data, ["candidates", 0, "content", "parts", 0, "text"])
        return _strip_trailing_notes(text), "gemini", settings.GEMINI_MODEL

    raise LLMError(f"Provider không hỗ trợ: {provider}")


async def call_openrouter_text(prompt: str, system: str = "") -> tuple[str, str, str]:
    """OpenRouter chat completion trả văn bản thường. Trả (text, provider, model)."""
    return await _call_chat_text("openrouter", prompt, system)


async def call_gemini_text(prompt: str, system: str = "") -> tuple[str, str, str]:
    """Gemini generateContent trả văn bản thường. Trả (text, provider, model)."""
    return await _call_chat_text("gemini", prompt, system)


async def call_llm_text(prompt: str, system: str = "") -> tuple[str, str, str]:
    """Gọi LLM trả văn bản thường cho chatbot quy chế: OpenRouter TRƯỚC
    (model cấu hình trong OPENROUTER_MODEL — đổi tự do, kể cả model :free),
    OpenRouter lỗi/rate-limit thì fallback Gemini.

    Trả (text, provider, model) — provider/model thực tế trả lời để ghi vào kết
    quả chatbot quy chế. Ném LLMError nếu cả hai thất bại/không có key.
    """
    errors = []
    for provider in ("openrouter", "gemini"):
        try:
            return await _call_chat_text(provider, prompt, system)
        except LLMError as e:
            errors.append(f"{provider}: {e}")
    raise LLMError(" | ".join(errors))
