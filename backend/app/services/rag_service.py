"""Pipeline chatbot quy chế (RAG) — embedding Voyage AI + ChromaDB + LLM OpenRouter/Gemini.

Kiến trúc (2 vai trò độc lập; đã bỏ hẳn embedding local torch/sentence-
transformers để chạy được trên Render free tier 512MB):

    ① EMBEDDING — chỉ Voyage AI (app/services/embedding_service.py):
       câu hỏi → vector (input_type="query")
            → ChromaDB query (vector truyền tường minh — KHÔNG để Chroma tự
              nhúng, xem src/rag/retriever.py) → top-k chunk
    ② LLM SINH CÂU TRẢ LỜI — OpenRouter (chính), Gemini (dự phòng):
       top-k chunk ghép thành ngữ cảnh + SYSTEM_PROMPT (src/rag/prompts.py)
       → llm_service.call_llm_text (OpenRouter → fallback Gemini)
            → {answer, sources, provider, model}

Voyage KHÔNG sinh câu trả lời; OpenRouter/Gemini KHÔNG tạo vector — 2 bước
độc lập, đổi LLM không ảnh hưởng kết quả tìm kiếm. Vector store dựng sẵn
trong backend/vectorstore/ (nhúng bằng VOYAGE_MODEL qua
scripts/rebuild_vector_store.py).

Lịch sử hội thoại giữ server-side theo (session_id, provider, model) — đổi
model là bắt đầu ngữ cảnh mới.
"""

import logging
import os
import sys
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv

from app.core.config import settings

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Pipeline đọc cấu hình qua os.getenv — nạp .env của backend và đặt đường
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


# Lịch sử hội thoại theo session (tối đa 3 cặp hỏi-đáp, 200 session).
# Khóa gồm (session_id, provider, model) — đổi model là bắt đầu ngữ cảnh mới,
# vì mỗi model có giới hạn ngữ cảnh / cách dùng lịch sử khác nhau.
_sessions: "OrderedDict[tuple, list[tuple[str, str]]]" = OrderedDict()
_MAX_SESSIONS = 200
_MAX_TURNS = 3

RETRIEVER_TOP_K = int(os.getenv("RETRIEVER_TOP_K", "5"))


def rag_status() -> dict:
    """Trạng thái cấu hình RAG — kiểm tra nhanh, không mở ChromaDB.

    embedding_model = Voyage AI (API) — chatbot không còn tải model local.
    """
    voyage_key = os.getenv("VOYAGE_API_KEY", "")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    return {
        "vectorstore": os.path.isdir(os.environ["VECTORSTORE_DIR"]),
        "openrouter_key": bool(os.getenv("OPENROUTER_API_KEY")),
        # Key dán dở từ .env.example (chứa "PASTE...") coi như chưa cấu hình
        "google_key": bool(google_key) and "PASTE" not in google_key,
        "voyage_key": bool(voyage_key) and "PASTE" not in voyage_key,
        "embedding_model": settings.VOYAGE_MODEL,
    }


def is_configured() -> bool:
    s = rag_status()
    return s["vectorstore"] and s["voyage_key"] and \
        (s["openrouter_key"] or s["google_key"])


def _ensure_ready() -> None:
    s = rag_status()
    if not s["vectorstore"]:
        raise RagNotAvailableError(
            "Chưa có vector store cho chatbot quy chế. Đặt tài liệu quy chế "
            "(DOCX) vào backend/data/raw/ rồi chạy: python scripts/rebuild_vector_store.py"
        )
    if not s["voyage_key"]:
        raise RagNotAvailableError(
            "Chưa cấu hình VOYAGE_API_KEY trong backend/.env — embedding cho "
            "chatbot quy chế bắt buộc dùng Voyage AI (key: dash.voyageai.com)"
        )
    if not (s["openrouter_key"] or s["google_key"]):
        raise RagNotAvailableError(
            "Chưa cấu hình API key LLM cho chatbot quy chế: OPENROUTER_API_KEY "
            "(chính — openrouter.ai/keys) hoặc GOOGLE_API_KEY (dự phòng — "
            "aistudio.google.com/apikey) trong backend/.env"
        )


def _get_retriever_module():
    """Import module truy vấn ChromaDB — thiếu chromadb thì báo lỗi rõ ràng."""
    try:
        from src.rag import retriever
    except ImportError as e:
        raise RagNotAvailableError(
            f"Thiếu thư viện chatbot quy chế ({e.name}) — "
            "chạy: pip install -r requirements.txt"
        ) from e
    return retriever


def list_models() -> dict:
    """Danh sách model cho dropdown chọn model trên web.

    Trả {"models": [{provider, model, label}], "default": {...} | None}.
    """
    _ensure_ready()
    try:
        from src.rag import models as rag_models
    except ImportError as e:
        raise RagNotAvailableError(
            f"Thiếu thư viện chatbot quy chế ({e.name}) — "
            "chạy: pip install -r requirements.txt"
        ) from e
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
    from src.rag import models as rag_models
    for spec in rag_models.list_available_models():
        if spec["provider"] == provider and spec["model"] == model:
            return provider, model
    logger.warning("Model được chọn %s/%s không khả dụng -> dùng mặc định",
                   provider, model)
    return "", ""


def warmup() -> None:
    """Mở sẵn ChromaDB (chạy nền khi server khởi động) để câu hỏi đầu không phải chờ.

    Embedding là API Voyage nên không còn bước tải model ~500MB như trước —
    warmup chỉ là mở file vector store.
    """
    try:
        _ensure_ready()
        _get_retriever_module().get_collection()
        logger.info("RAG sẵn sàng (ChromaDB đã mở, embedding = Voyage API)")
    except Exception as e:
        logger.warning("Warm-up chatbot quy chế bỏ qua: %s", e)


def _format_history(turns: list[tuple[str, str]]) -> str:
    """Lịch sử hỏi-đáp thành văn bản ghép vào prompt (multi-turn không phụ
    thuộc tính năng chat của từng provider)."""
    if not turns:
        return ""
    lines = ["Các lượt hỏi-đáp trước trong phiên này:"]
    for q, a in turns:
        lines.append(f"- Sinh viên hỏi: {q}\n- Trả lời: {a}")
    return "\n".join(lines)


async def answer_regulation_question(question: str, session_id: str = "default",
                                     provider: str = "", model: str = "") -> dict:
    """Hỏi quy chế → {"answer", "sources", "provider", "model"}.

    Pipeline: ① nhúng câu hỏi bằng Voyage API (input_type="query") → ChromaDB
    trả top-k chunk (vector truyền tường minh, không auto-encode) → ② ngữ cảnh
    + system prompt → LLM (OpenRouter, lỗi thì fallback Gemini) → dọn dẹp câu
    trả lời.

    provider/model: nhận để giữ nguyên khóa lịch sử hội thoại theo session,
    KHÔNG đổi model trả lời — model trả lời luôn theo cấu hình .env
    (OPENROUTER_MODEL, lỗi thì fallback GEMINI_MODEL). Lịch sử hội thoại giữ server-side.
    Ném RagNotAvailableError / RagLLMError khi có lỗi.
    """
    import anyio

    from app.services.embedding_service import EmbeddingError, get_embedding
    from app.services.llm_service import LLMError, call_llm_text
    from src.rag.chain import clean_answer, format_context, format_sources
    from src.rag.prompts import SYSTEM_PROMPT

    _ensure_ready()
    retriever = _get_retriever_module()
    provider, model = resolve_selection(provider, model)
    # Lịch sử hội thoại khóa theo LỰA CHỌN (ổn định giữa các lượt hỏi),
    # không theo model thực tế trả lời (model trả lời có thể đổi do fallback).
    history_key = (session_id, provider, model)

    # 1) Nhúng câu hỏi (Voyage API — input_type 'query' khác 'document' lúc
    # build index để tối ưu retrieval)
    try:
        vector = await get_embedding(question, input_type="query")
    except EmbeddingError as e:
        raise RagLLMError(f"Lỗi embedding câu hỏi: {e}") from e

    # 2) Truy vấn ChromaDB — query_embeddings tường minh, KHÔNG query_texts
    # (query_texts sẽ khiến Chroma tự tải model nhúng local). Chạy trong
    # thread riêng để không chặn event loop (Chroma I/O sync).
    try:
        result = await anyio.to_thread.run_sync(
            lambda: retriever.get_collection().query(
                query_embeddings=[vector], n_results=RETRIEVER_TOP_K,
                include=["documents", "metadatas"])
        )
    except FileNotFoundError as e:
        raise RagNotAvailableError(str(e)) from e
    except Exception as e:
        raise RagLLMError(f"Lỗi truy vấn vector store: {type(e).__name__}: {e}") from e

    texts = result.get("documents") or [[]]
    metadatas = result.get("metadatas") or [[]]
    texts, metadatas = texts[0], metadatas[0]

    # 3) Câu hỏi ngoài vùng phủ của quy chế (không chunk nào khớp) -> trả
    # lời "không tìm thấy" ngay, KHÔNG gọi LLM -> triệt tiêu hallucination.
    if not texts:
        return {
            "answer": "Toi khong tim thay thong tin nay trong quy che.",
            "sources": [],
            "provider": "",
            "model": "",
        }

    # 4) Ghép prompt: system prompt (kèm ngữ cảnh) + lịch sử + câu hỏi
    context = format_context(texts)
    system = SYSTEM_PROMPT.format(context=context)
    history_text = _format_history(_sessions.get(history_key, []))
    prompt = f"{history_text}\n\nCâu hỏi: {question}" if history_text \
        else f"Câu hỏi: {question}"

    # 5) Gọi LLM plain-text (OpenRouter -> fallback Gemini)
    try:
        answer, provider, model = await call_llm_text(prompt, system=system)
    except LLMError as e:
        raise RagLLMError(f"Lỗi xử lý câu hỏi: {e}") from e

    answer = clean_answer(answer)

    # 6) Cập nhật lịch sử hội thoại
    turns = _sessions.get(history_key, [])
    turns.append((question, answer))
    _sessions[history_key] = turns[-_MAX_TURNS:]
    _sessions.move_to_end(history_key)
    while len(_sessions) > _MAX_SESSIONS:
        _sessions.popitem(last=False)

    return {
        "answer": answer,
        "sources": format_sources(texts, metadatas),
        "provider": provider,
        "model": model,
    }
