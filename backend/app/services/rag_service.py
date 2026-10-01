"""Pipeline chatbot quy chế (RAG) — embedding Voyage AI + ChromaDB + LLM OpenRouter/Gemini.

Kiến trúc (2 vai trò độc lập; đã bỏ hẳn embedding local torch/sentence-
transformers để chạy được trên Render free tier 512MB):

    ① EMBEDDING — chỉ Voyage AI (app/services/embedding_service.py):
       câu hỏi → vector (input_type="query")
            → ChromaDB query (vector truyền tường minh — KHÔNG để Chroma tự
              nhúng, xem src/rag/retriever.py) → top-k chunk
    ② LLM SINH CÂU TRẢ LỜI — model người dùng chọn ở dropdown (OpenRouter :free
       hoặc Gemini), mặc định OpenRouter theo .env:
       top-k chunk ghép thành ngữ cảnh + SYSTEM_PROMPT (src/rag/prompts.py)
       → llm_service.call_llm_text (model đã chọn → fallback provider còn lại)
            → {answer, sources, provider, model}

Voyage KHÔNG sinh câu trả lời; OpenRouter/Gemini KHÔNG tạo vector — 2 bước
độc lập, đổi LLM không ảnh hưởng kết quả tìm kiếm. Vector store dựng sẵn
trong backend/vectorstore/ (nhúng bằng VOYAGE_MODEL qua
scripts/rebuild_vector_store.py).

Lịch sử hội thoại giữ server-side theo (session_id, provider, model) — đổi
model là bắt đầu ngữ cảnh mới. Lịch sử lưu QUA CACHE (app/core/cache.py):
Redis trên prod nên SỐNG SÓT qua restart/sleep của Render free — cơ chế
in-memory cũ mất sạch mỗi lần server ngủ 15 phút, sinh viên đang chat đứt
ngữ cảnh.
"""

import hashlib
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.core.cache import TTL_CHAT_SESSION, TTL_RAG_RETRIEVAL, build_key, cache
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


# Lịch sử hội thoại theo session (tối đa 3 cặp hỏi-đáp) — lưu QUA CACHE LỚN
# (app/core/cache.py): Redis trên prod → ngữ cảnh SỐNG SÓT qua restart/sleep
# của Render free (trước đây giữ trong RAM của process, server ngủ là mất);
# REDIS_URL trống → tự fallback in-memory. TTL 24h thay cho cap _MAX_SESSIONS
# cũ (Redis tự hết hạn key). Khóa gồm (session_id, provider, model) — đổi
# model là bắt đầu ngữ cảnh mới, vì mỗi model có giới hạn ngữ cảnh / cách dùng
# lịch sử khác nhau.
_MAX_TURNS = 3


def _chat_key(history_key: tuple) -> str:
    return build_key("chat", *history_key)


async def _load_turns(history_key: tuple) -> list:
    """Đọc lịch sử session từ cache ([] khi chưa có). Cache là I/O sync/mạng
    nên gọi qua thread riêng, không chặn event loop."""
    import anyio

    turns = await anyio.to_thread.run_sync(cache.get_json, _chat_key(history_key))
    return turns or []


async def _save_turn(history_key: tuple, question: str, answer: str) -> None:
    """Lưu một lượt hội thoại, serialize read-modify-write theo process."""
    import anyio

    def _write() -> None:
        key = _chat_key(history_key)
        cache.append_json(key, [question, answer], _MAX_TURNS, TTL_CHAT_SESSION)

    await anyio.to_thread.run_sync(_write)

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


_NOT_FOUND_ANSWER = "Toi khong tim thay thong tin nay trong quy che."


async def prepare_regulation_question(question: str, session_id: str = "default",
                                      provider: str = "", model: str = "") -> dict:
    """Các bước TRƯỚC khi LLM sinh chữ — dùng chung cho bản thường và streaming.

    Ném RagNotAvailableError/RagLLMError tại đây (router chuyển thành 503/502
    TRƯỚC khi bắt đầu stream — sau khi response 200 đã bắn header thì không còn
    cách nào đổi status). Trả dict:
    - found=False  : câu hỏi ngoài vùng phủ (không chunk khớp) — không gọi LLM
    - found=True   : {"sources", "prompt", "system", "history_key", "selection"}
      sẵn sàng cho bước gọi LLM; "selection" là (provider, model) đã kiểm tra
      hợp lệ, để nguyên cho llm_service quyết định thứ tự gọi/fallback.
    """
    import anyio

    from app.services.embedding_service import EmbeddingError, get_embedding
    from src.rag.chain import format_context, format_sources
    from src.rag.prompts import SYSTEM_PROMPT
    # Hằng số ngưỡng đọc thẳng từ module (không qua `retriever` bên dưới) —
    # `_get_retriever_module()` có thể bị thay bằng module giả trong test.
    from src.rag.retriever import RETRIEVER_MAX_DISTANCE

    _ensure_ready()
    retriever = _get_retriever_module()
    sel_provider, sel_model = resolve_selection(provider, model)
    # Lịch sử hội thoại khóa theo LỰA CHỌN (ổn định giữa các lượt hỏi),
    # không theo model thực tế trả lời (model trả lời có thể đổi do fallback).
    history_key = (session_id, sel_provider, sel_model)

    # 1+2) Kết quả tìm kiếm cache theo câu hỏi (24h): hỏi lặp câu cũ — chuyện
    # rất phổ biến — bỏ qua trọn Voyage API lẫn Chroma query. Key gồm
    # VOYAGE_MODEL nên đổi model (bắt buộc rebuild index) tự miss; thêm tài
    # liệu mới CÙNG model thì bump CACHE_VERSION trong app/core/cache.py (hoặc
    # chờ hết TTL) để câu hỏi cũ không trả nguồn cũ.
    rag_key = (
        "rag:" + settings.VOYAGE_MODEL + ":" + str(RETRIEVER_TOP_K) + ":v1:" +
        hashlib.sha256(question.encode("utf-8")).hexdigest()
    )
    cached = await anyio.to_thread.run_sync(cache.get_json, rag_key)
    if cached is not None:
        texts = cached["texts"]
        metadatas = cached["metadatas"]
        distances = cached["distances"]
    else:
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
                    include=["documents", "metadatas", "distances"])
            )
        except FileNotFoundError as e:
            raise RagNotAvailableError(str(e)) from e
        except Exception as e:
            raise RagLLMError(
                f"Lỗi truy vấn vector store: {type(e).__name__}: {e}") from e

        texts = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        texts, metadatas, distances = texts[0], metadatas[0], distances[0]
        await anyio.to_thread.run_sync(
            cache.set_json, rag_key,
            {"texts": texts, "metadatas": metadatas, "distances": distances},
            TTL_RAG_RETRIEVAL)

    # 3) Câu hỏi ngoài vùng phủ của quy chế (không chunk nào khớp) -> trả
    # lời "không tìm thấy" ngay, KHÔNG gọi LLM -> triệt tiêu hallucination.
    # Lưới an toàn: top-k gần như luôn trả đủ chunk nên nhánh này hiếm khi chạy,
    # việc chặn thật nằm ở ngưỡng distance bên dưới.
    if not texts:
        return {"found": False}

    # 4) Ghép prompt: system prompt (kèm ngữ cảnh) + lịch sử + câu hỏi
    # Ngữ cảnh gửi LLM giữ NGUYÊN toàn bộ top-k — lọc ngưỡng chỉ áp cho khối
    # trích dẫn hiển thị, không cắt bớt thông tin của model.
    context = format_context(texts)
    system = SYSTEM_PROMPT.format(context=context)
    history_text = _format_history(await _load_turns(history_key))
    prompt = f"{history_text}\n\nCâu hỏi: {question}" if history_text \
        else f"Câu hỏi: {question}"

    # 5) Nguồn trích dẫn: chỉ giữ chunk đủ gần câu hỏi (ngưỡng
    # RETRIEVER_MAX_DISTANCE trong src/rag/retriever.py — đọc chung 1 nguồn để
    # không có 2 giá trị mặc định lệch nhau). Không lọc thì top-k luôn đủ 5
    # chunk nên "xin chào" hay câu ngoài phạm vi cũng hiện khối "N nguồn trích
    # dẫn" — trong khi câu trả lời cho những câu đó do LLM tự sinh (chào lại /
    # báo không tìm thấy), không dựa vào chunk nào.
    if len(distances) == len(texts):
        relevant = [(t, m) for t, m, d in zip(texts, metadatas, distances)
                    if d <= RETRIEVER_MAX_DISTANCE]
    else:
        # Chroma không trả distances (bất thường) — hiện đủ nguồn như trước
        # thay vì ẩn sạch, để lỗi lạ không làm mất trích dẫn của câu hỏi thật.
        relevant = list(zip(texts, metadatas))

    return {
        "found": True,
        "history_key": history_key,
        "selection": (sel_provider, sel_model),
        "prompt": prompt,
        "system": system,
        "sources": format_sources([t for t, _ in relevant],
                                  [m for _, m in relevant]),
    }


async def answer_regulation_question(question: str, session_id: str = "default",
                                     provider: str = "", model: str = "") -> dict:
    """Hỏi quy chế → {"answer", "sources", "provider", "model"} — bản không
    streaming (POST /ai/regulation-chat). Chuẩn bị pipeline chung ở
    prepare_regulation_question; ở đây chỉ gọi LLM trọn câu, dọn dẹp và lưu
    lịch sử hội thoại.

    provider/model: lựa chọn từ dropdown trên web (đã kiểm tra hợp lệ ở
    prepare_regulation_question) — model được chọn là model trả lời; lỗi thì
    tự fallback sang provider còn lại với model mặc định trong .env. Ném
    RagNotAvailableError / RagLLMError khi có lỗi.
    """
    from app.services.llm_service import LLMError, call_llm_text
    from src.rag.chain import clean_answer

    prepared = await prepare_regulation_question(
        question, session_id, provider=provider, model=model)
    if not prepared["found"]:
        return {
            "answer": _NOT_FOUND_ANSWER,
            "sources": [],
            "provider": "",
            "model": "",
        }

    # 5) Gọi LLM plain-text (model đã chọn -> fallback provider còn lại)
    sel_provider, sel_model = prepared["selection"]
    try:
        answer, provider, model = await call_llm_text(
            prepared["prompt"], system=prepared["system"],
            provider=sel_provider, model=sel_model)
    except LLMError as e:
        raise RagLLMError(f"Lỗi xử lý câu hỏi: {e}") from e

    answer = clean_answer(answer)
    await _save_turn(prepared["history_key"], question, answer)

    return {
        "answer": answer,
        "sources": prepared["sources"],
        "provider": provider,
        "model": model,
    }


async def stream_answer_regulation_question(prepared: dict, question: str):
    """Bản streaming của answer_regulation_question — gọi SAU khi
    prepare_regulation_question đã thành công.

    Yield từng event dict (router bọc thành SSE `data: {...}`):
    - {"type": "meta",  "sources": [...]}          — trích dẫn, trước mảnh chữ đầu
    - {"type": "delta", "text": "mảnh chữ"}        — lặp nhiều lần, chữ chảy ra
    - {"type": "done",  "answer", "provider", "model"} — câu hoàn chỉnh đã dọn
      (clean_answer + cắt ghi chú template) — frontend thay text đang chảy bằng nó
    - {"type": "error", "message": "..."}          — LLM lỗi; lịch sử KHÔNG lưu

    Chỉ yield event, không ném exception (mọi lỗi sau meta đều thành event error
    vì stream đã bắt đầu, không đổi được HTTP status nữa).
    """
    from app.services.llm_service import LLMError, stream_llm_text
    from src.rag.chain import clean_answer

    if not prepared["found"]:
        yield {"type": "meta", "sources": []}
        yield {"type": "delta", "text": _NOT_FOUND_ANSWER}
        yield {"type": "done", "answer": _NOT_FOUND_ANSWER,
               "provider": "", "model": ""}
        return

    yield {"type": "meta", "sources": prepared["sources"]}

    # Gọi LLM stream (model đã chọn -> fallback provider còn lại trước mảnh đầu)
    # — gom đủ chữ để lưu lịch sử + dọn dẹp, đồng thời đẩy từng mảnh cho người dùng.
    pieces: list[str] = []
    info: dict = {}
    sel_provider, sel_model = prepared["selection"]
    try:
        async for chunk in stream_llm_text(prepared["prompt"],
                                           system=prepared["system"], info=info,
                                           provider=sel_provider, model=sel_model):
            pieces.append(chunk)
            yield {"type": "delta", "text": chunk}
    except LLMError as e:
        yield {"type": "error",
               "message": f"Chatbot quy chế gặp lỗi: {e}"}
        return

    answer = clean_answer("".join(pieces))
    await _save_turn(prepared["history_key"], question, answer)
    yield {"type": "done", "answer": answer,
           "provider": info.get("provider", ""), "model": info.get("model", "")}
