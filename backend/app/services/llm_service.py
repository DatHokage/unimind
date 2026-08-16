"""Gọi LLM qua httpx (async, không dùng SDK).

Ưu tiên OpenRouter (OPENROUTER_API_KEY) — API tương thích OpenAI;
lỗi hoặc không có key thì fallback sang Gemini REST.
"""

import json

import httpx

from app.core.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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
    """Gọi LLM trả về JSON: ưu tiên OpenRouter, lỗi thì thử Gemini. Ném LLMError
    nếu cả hai đều thất bại hoặc không có key nào được cấu hình."""
    errors = []
    for call in (call_openrouter_json, call_gemini_json):
        try:
            return await call(prompt)
        except LLMError as e:
            errors.append(str(e))
    raise LLMError(" | ".join(errors))
