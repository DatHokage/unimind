"""Gọi LLM qua httpx (async, không dùng SDK).

Với chatbot quy chế (RAG) — vai trò ② sinh câu trả lời, KHÔNG tạo vector:
model do người dùng chọn ở dropdown là model trả lời; không chọn gì thì mặc
định Gemini (GEMINI_MODEL trong .env) và OpenRouter là dự phòng. Provider đang
gọi lỗi/rate-limit/không key thì tự chuyển sang provider còn lại — không để lỗi
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


_PROVIDERS = ("gemini", "openrouter")


def _attempts(provider: str = "", model: str = "") -> list[tuple[str, str]]:
    """Danh sách (provider, model) theo thứ tự gọi cho một lượt hỏi.

    Provider được chọn chạy trước, provider còn lại là dự phòng; không chọn gì
    thì giữ thứ tự mặc định (Gemini trước, OpenRouter sau).

    CHỈ provider được chọn nhận model id từ client — model id thuộc không gian
    tên của một provider, gửi id của provider này cho provider kia sẽ lỗi. Nên
    provider dự phòng luôn nhận chuỗi rỗng để tự dùng model trong .env.
    """
    order = list(_PROVIDERS)
    if provider in _PROVIDERS:
        order.remove(provider)
        order.insert(0, provider)
    return [(p, model if p == provider else "") for p in order]


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


async def _call_chat_text(provider: str, prompt: str, system: str = "",
                          model: str = "") -> tuple[str, str, str]:
    """Gọi 1 provider chat completion, trả (text, provider, model).

    system: tin nhắn hệ thống riêng; để trống = ghép vào đầu user prompt
    (dùng cho provider không hỗ trợ role system như Gemini).
    model: model id do client chọn ở dropdown; để trống = model trong .env.
    """
    if provider == "openrouter":
        if not settings.OPENROUTER_API_KEY:
            raise LLMError("Chưa cấu hình OPENROUTER_API_KEY")
        model = model or settings.OPENROUTER_MODEL
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": model,
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
        return _strip_trailing_notes(text), "openrouter", model

    if provider == "gemini":
        api_key = settings.gemini_api_key
        if not api_key:
            raise LLMError("Chưa cấu hình GOOGLE_API_KEY (hoặc GEMINI_API_KEY)")
        model = model or settings.GEMINI_MODEL
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        url = GEMINI_URL.format(model=model)
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
        return _strip_trailing_notes(text), "gemini", model

    raise LLMError(f"Provider không hỗ trợ: {provider}")


async def call_llm_text(prompt: str, system: str = "",
                        provider: str = "", model: str = "") -> tuple[str, str, str]:
    """Gọi LLM trả văn bản thường cho chatbot quy chế.

    provider/model: lựa chọn từ dropdown trên web (đã qua resolve_selection).
    Để trống = dùng mặc định: Gemini TRƯỚC (GEMINI_MODEL trong .env), lỗi thì
    fallback OpenRouter. Chọn provider nào thì provider đó chạy trước, provider
    còn lại là dự phòng.

    Trả (text, provider, model) — provider/model thực tế trả lời để ghi vào kết
    quả chatbot quy chế. Ném LLMError nếu cả hai thất bại/không có key.
    """
    errors = []
    for p, sel in _attempts(provider, model):
        try:
            return await _call_chat_text(p, prompt, system, sel)
        except LLMError as e:
            errors.append(f"{p}: {e}")
    raise LLMError(" | ".join(errors))


# ---------------------------------------------------------------------------
# Streaming (SSE) — bản "chảy từng mảnh" của call_llm_text cho chatbot quy chế.
# Fallback chỉ xảy ra TRƯỚC mảnh chữ đầu tiên: provider đang gọi lỗi lúc kết nối
# thì thử provider còn lại; đã bắn chữ rồi mà đứt thì lỗi lan lên (không đổi
# model giữa chừng).
# ---------------------------------------------------------------------------

GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}"
    ":streamGenerateContent?alt=sse"
)


async def _stream_openrouter_text(prompt: str, system: str = "",
                                  info: dict | None = None, model: str = ""):
    """Yield từng mảnh chữ từ OpenRouter (stream: true, SSE dạng `data: {...}`).

    model: model id client chọn; để trống = OPENROUTER_MODEL trong .env.
    """
    if not settings.OPENROUTER_API_KEY:
        raise LLMError("Chưa cấu hình OPENROUTER_API_KEY")
    model = model or settings.OPENROUTER_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4096,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "He thong Quan ly Dao tao",
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream("POST", OPENROUTER_URL, json=body, headers=headers) as response:
            if response.status_code != 200:
                raw = (await response.aread()).decode("utf-8", "replace")
                raise LLMError(
                    f"OpenRouter API trả về HTTP {response.status_code}: {raw[:300]}")
            got_any = False
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[len("data: "):].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except ValueError:
                    continue
                # delta.content có thể None (chunk đầu chỉ mang role)
                delta = ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if delta:
                    if not got_any and info is not None:
                        info.update(provider="openrouter", model=model)
                    got_any = True
                    yield delta
            if not got_any:
                raise LLMError("OpenRouter API stream không trả nội dung nào")


async def _stream_gemini_text(prompt: str, system: str = "",
                              info: dict | None = None, model: str = ""):
    """Yield từng mảnh chữ từ Gemini streamGenerateContent (alt=sse).

    Mỗi event SSE là một response generateContent đầy đủ dạng JSON — phần mới
    nằm ở candidates[0].content.parts[*].text (có thể nhiều parts trong 1 chunk).
    """
    api_key = settings.gemini_api_key
    if not api_key:
        raise LLMError("Chưa cấu hình GOOGLE_API_KEY (hoặc GEMINI_API_KEY)")
    model = model or settings.GEMINI_MODEL
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    url = GEMINI_STREAM_URL.format(model=model)
    body = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        async with client.stream("POST", url, json=body,
                                 headers={"x-goog-api-key": api_key}) as response:
            if response.status_code != 200:
                raw = (await response.aread()).decode("utf-8", "replace")
                raise LLMError(
                    f"Gemini API trả về HTTP {response.status_code}: {raw[:300]}")
            got_any = False
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[len("data: "):].strip())
                except ValueError:
                    continue
                if data.get("error"):
                    raise LLMError(
                        f"Gemini API stream lỗi: {data['error'].get('message', '')}")
                candidates = data.get("candidates") or []
                parts = ((candidates[0].get("content") or {}).get("parts")
                         if candidates else None) or []
                text = "".join(p.get("text", "") for p in parts)
                if text:
                    if not got_any and info is not None:
                        info.update(provider="gemini", model=model)
                    got_any = True
                    yield text
            if not got_any:
                raise LLMError("Gemini API stream không trả nội dung nào")


async def stream_llm_text(prompt: str, system: str = "",
                          info: dict | None = None,
                          provider: str = "", model: str = ""):
    """Bản streaming của call_llm_text — yield từng mảnh chữ ngay khi LLM sinh ra.

    info: dict tùy chọn, được ghi (provider, model) của provider THỰC TẾ trả lời
    ngay khi mảnh đầu xuất hiện (người gọi đọc lại sau khi stream xong — cần vì
    generator không trả giá trị như call_llm_text).

    provider/model: lựa chọn từ dropdown trên web. Để trống = Gemini trước rồi
    OpenRouter (model theo .env); chọn provider nào thì provider đó chạy trước,
    provider còn lại là dự phòng với model mặc định trong .env.

    Ném LLMError khi: cả hai provider đều lỗi trước khi bắn mảnh nào (được
    fallback qua nhau như call_llm_text), hoặc provider đang stream đứt giữa
    chừng sau khi đã yield (lỗi lan thẳng lên — không fallback được nữa).
    """
    fns = {"openrouter": _stream_openrouter_text, "gemini": _stream_gemini_text}
    errors: list[str] = []
    for label, sel in _attempts(provider, model):
        yielded = False
        try:
            async for chunk in fns[label](prompt, system, info, sel):
                yielded = True
                yield chunk
            return
        except LLMError as e:
            if yielded:
                raise LLMError(f"{label} đứt giữa chừng: {e}") from e
            errors.append(f"{label}: {e}")
    raise LLMError(" | ".join(errors))
