"""Tích hợp pipeline RAG từ dự án chatbot quy chế (rag_langchain).

Pipeline gốc đặt tại backend/src/rag (retriever + chain LCEL, ChromaDB +
embedding tiếng Việt chạy local 100%), vector store dựng sẵn trong
backend/vectorstore/ (Sổ tay sinh viên 2024-2025). Muốn cập nhật quy chế:
đặt file DOCX mới vào backend/data/raw/ rồi chạy
`python -m src.ingestion.build_index` (từ thư mục backend/).

Module này chỉ làm cầu nối: nạp cấu hình cho pipeline + lazy-load chain
(không chặn server khi khởi động) + quản lý lịch sử hội thoại theo session.
"""

import logging
import os
import sys
import threading
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

from app.core.config import settings

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Pipeline RAG đọc cấu hình qua os.getenv — nạp .env của backend và đặt đường
# dẫn tuyệt đối để không phụ thuộc thư mục chạy lệnh.
load_dotenv(_BACKEND_ROOT / ".env")
os.environ.setdefault("VECTORSTORE_DIR", str(_BACKEND_ROOT / "vectorstore"))
os.environ.setdefault("DATA_RAW_DIR", str(_BACKEND_ROOT / "data" / "raw"))
# models.py của pipeline đọc GOOGLE_API_KEY (tên chuẩn của SDK Google).
# .env có thể đặt GOOGLE_API_KEY hoặc GEMINI_API_KEY (tên cũ) — đồng bộ cả hai
# từ giá trị gộp settings.gemini_api_key để mọi nơi đọc nhất quán.
_gemini_key = settings.gemini_api_key
if _gemini_key:
    os.environ.setdefault("GOOGLE_API_KEY", _gemini_key)
    os.environ.setdefault("GEMINI_API_KEY", _gemini_key)

if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class RagNotAvailableError(Exception):
    """RAG chưa thể chạy: thiếu vector store, thiếu API key hoặc thiếu thư viện."""


class RagLLMError(Exception):
    """RAG đã sẵn sàng nhưng quá trình xử lý câu hỏi thất bại."""


_chain_module = None
_load_lock = threading.Lock()

# Lịch sử hội thoại theo session (tối đa 3 cặp hỏi-đáp, 200 session).
# Khóa gồm (session_id, provider, model) — đổi model là bắt đầu ngữ cảnh mới,
# vì mỗi model có giới hạn ngữ cảnh / cách dùng lịch sử khác nhau.
_sessions: "OrderedDict[tuple, list[tuple[str, str]]]" = OrderedDict()
_MAX_SESSIONS = 200
_MAX_TURNS = 3


def rag_status() -> dict:
    """Trạng thái cấu hình RAG — kiểm tra nhanh, không import pipeline."""
    google_key = os.getenv("GOOGLE_API_KEY", "")
    return {
        "vectorstore": os.path.isdir(os.environ["VECTORSTORE_DIR"]),
        "openrouter_key": bool(os.getenv("OPENROUTER_API_KEY")),
        # Key dán dở từ .env.example (chứa "PASTE...") coi như chưa cấu hình
        "google_key": bool(google_key) and "PASTE" not in google_key,
    }


def is_configured() -> bool:
    s = rag_status()
    return s["vectorstore"] and (s["openrouter_key"] or s["google_key"])


def _ensure_ready() -> None:
    s = rag_status()
    if not s["vectorstore"]:
        raise RagNotAvailableError(
            "Chưa có vector store cho chatbot quy chế. Đặt tài liệu quy chế "
            "(DOCX) vào backend/data/raw/ rồi chạy: python -m src.ingestion.build_index"
        )
    if not (s["openrouter_key"] or s["google_key"]):
        raise RagNotAvailableError(
            "Chưa cấu hình API key cho chatbot quy chế (OPENROUTER_API_KEY "
            "hoặc GOOGLE_API_KEY trong backend/.env)"
        )


def _get_models_module():
    """Lazy-import registry model (nhe hon chain — khong tai vectorstore)."""
    _ensure_ready()
    try:
        from src.rag import models as rag_models
    except ImportError as e:
        raise RagNotAvailableError(
            f"Thiếu thư viện RAG ({e.name}) — chạy: pip install -r requirements.txt"
        ) from e
    return rag_models


def list_models() -> dict:
    """Danh sách model cho dropdown chọn model trên web.

    Trả {"models": [{provider, model, label}], "default": {...} | None}.
    Model gọi lỗi sẽ tự fallback sang các model còn lại (src/rag/chain.py).
    """
    rag_models = _get_models_module()
    models = rag_models.list_available_models()
    default = rag_models.default_selection() or None
    return {"models": models, "default": default}


def resolve_selection(provider: str, model: str) -> tuple[str, str]:
    """Kiểm tra lựa chọn (provider, model) từ client.

    Chỉ chấp nhận model đang khả dụng (tránh client tự bịa model id);
    lựa chọn sai/không có -> quay về model mặc định theo .env.
    """
    if not provider and not model:
        return "", ""
    rag_models = _get_models_module()
    for spec in rag_models.list_available_models():
        if spec["provider"] == provider and spec["model"] == model:
            return provider, model
    logger.warning("Model được chọn %s/%s không khả dụng -> dùng mặc định",
                   provider, model)
    return "", ""


def _get_chain_module():
    """Lazy-import pipeline RAG (import nặng: langchain + chroma + embeddings)."""
    global _chain_module
    with _load_lock:
        if _chain_module is None:
            _ensure_ready()
            try:
                from src.rag import chain as rag_chain
            except ImportError as e:
                raise RagNotAvailableError(
                    f"Thiếu thư viện RAG ({e.name}) — chạy: "
                    "pip install -r requirements.txt"
                ) from e
            _chain_module = rag_chain
    return _chain_module


def warmup() -> None:
    """Tải sẵn embedding model + ChromaDB + LLM (chạy nền khi server khởi động)."""
    try:
        rag_chain = _get_chain_module()
        rag_chain.build_chain()
        logger.info("RAG chain sẵn sàng (vectorstore + embedding + LLM)")
    except Exception as e:
        logger.warning("Warm-up chatbot quy chế bỏ qua: %s", e)


async def answer_regulation_question(question: str, session_id: str = "default",
                                     provider: str = "", model: str = "") -> dict:
    """Hỏi quy chế → {"answer", "sources", "provider", "model"}.

    provider/model (tùy chọn, từ dropdown trên web): ép dùng model đó trước;
    model lỗi (rate-limit/hết quota...) vẫn tự fallback sang model miễn phí
    khác trong registry (src/rag/chain.py). Bỏ trống → model mặc định theo .env.

    Lịch sử hội thoại (theo session_id + model) giữ server-side để câu hỏi sau
    kế thừa ngữ cảnh câu trước. Ném RagNotAvailableError / RagLLMError khi có lỗi.
    """
    import anyio

    rag_chain = _get_chain_module()
    provider, model = resolve_selection(provider, model)

    history_key = (session_id, provider, model)
    turns = _sessions.get(history_key, [])
    from langchain_core.messages import AIMessage, HumanMessage

    history = [
        m for q, a in turns for m in (HumanMessage(content=q), AIMessage(content=a))
    ]

    try:
        # Pipeline gốc chạy sync — chạy trong thread riêng để không chặn
        # event loop của FastAPI
        result = await anyio.to_thread.run_sync(
            lambda: rag_chain.ask(question, chat_history=history,
                                  provider=provider, model=model)
        )
    except RagNotAvailableError:
        raise
    except FileNotFoundError as e:
        raise RagNotAvailableError(str(e)) from e
    except RuntimeError as e:
        raise RagLLMError(str(e)) from e
    except Exception as e:
        raise RagLLMError(f"Lỗi xử lý câu hỏi: {type(e).__name__}: {e}") from e

    turns.append((question, result.get("answer", "")))
    _sessions[history_key] = turns[-_MAX_TURNS:]
    _sessions.move_to_end(history_key)
    while len(_sessions) > _MAX_SESSIONS:
        _sessions.popitem(last=False)

    return result
