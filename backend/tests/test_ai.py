import pytest

from app.services.llm_service import LLMError, extract_json
from app.services.rag_service import RagNotAvailableError


def test_regulation_chat_unavailable_returns_503(client, db, make_user, monkeypatch):
    """Chưa có vector store/API key → 503 kèm hướng dẫn cấu hình."""
    from app.routers import ai as ai_router

    async def fake_answer(question, session_id="default", provider="", model=""):
        raise RagNotAvailableError("Chưa có vector store cho chatbot quy chế.")

    monkeypatch.setattr(ai_router, "answer_regulation_question", fake_answer)

    h = make_user(db, role="student")
    resp = client.post("/ai/regulation-chat", json={"question": "Quy chế thi thế nào?"}, headers=h)
    assert resp.status_code == 503
    assert "vector store" in resp.json()["detail"]


def test_regulation_chat_success_with_sources(client, db, make_user, monkeypatch):
    """Pipeline sẵn sàng → 200 kèm answer + sources + provider."""
    from app.routers import ai as ai_router

    async def fake_answer(question, session_id="default", provider="", model=""):
        return {
            "answer": "Theo Điều 12, sinh viên vắng thi quá 20% bị cấm thi.",
            "sources": [
                {"dieu": "Điều 12", "ten_dieu": "Cấm thi", "so_trang": 45, "text": "..."}
            ],
            "provider": "openrouter",
            "model": "test-model:free",
        }

    monkeypatch.setattr(ai_router, "answer_regulation_question", fake_answer)

    h = make_user(db, role="student")
    resp = client.post("/ai/regulation-chat", json={"question": "Khi nào bị cấm thi?"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "Điều 12" in body["answer"]
    assert body["provider"] == "openrouter"
    assert len(body["sources"]) == 1
    assert body["sources"][0]["dieu"] == "Điều 12"
    assert body["sources"][0]["so_trang"] == 45


def test_regulation_chat_llm_error_returns_502(client, db, make_user, monkeypatch):
    """LLM của chatbot lỗi → 502 (không phải 500)."""
    from app.routers import ai as ai_router
    from app.services.rag_service import RagLLMError

    async def fake_answer(question, session_id="default", provider="", model=""):
        raise RagLLMError("Tat ca model deu loi")

    monkeypatch.setattr(ai_router, "answer_regulation_question", fake_answer)

    h = make_user(db, role="student")
    resp = client.post("/ai/regulation-chat", json={"question": "hi"}, headers=h)
    assert resp.status_code == 502


def test_regulation_chat_status(client, db, make_user, monkeypatch):
    from app.routers import ai as ai_router

    monkeypatch.setattr(ai_router, "is_configured", lambda: False)
    monkeypatch.setattr(ai_router, "rag_status", lambda: {
        "vectorstore": False, "openrouter_key": False, "google_key": False,
        "voyage_key": False, "embedding_model": "voyage-4",
    })

    h = make_user(db, role="student")
    resp = client.get("/ai/regulation-chat/status", headers=h)
    assert resp.status_code == 200
    assert resp.json()["ready"] is False


def test_regulation_chat_requires_auth(client):
    resp = client.post("/ai/regulation-chat", json={"question": "hi"})
    assert resp.status_code == 401


def test_course_advice_only_self(client, db, make_user, make_student):
    s1 = make_student(db)
    s2 = make_student(db)
    h = make_user(db, role="student", student=s1)
    resp = client.post("/ai/course-advice", json={"student_id": s2.id}, headers=h)
    assert resp.status_code == 403


def test_course_advice_forbidden_for_non_student(client, db, make_user, make_student):
    s = make_student(db)
    h = make_user(db, role="training_office")
    resp = client.post("/ai/course-advice", json={"student_id": s.id}, headers=h)
    assert resp.status_code == 403


def test_study_summary_advisor_permission(client, db, make_user, make_advisor, make_homeroom, make_student, monkeypatch):
    from app.services import ai_service

    async def fake_run(db_, student_id):
        return {"summary": "ok", "warnings": [], "suggestions": []}, False

    monkeypatch.setattr(ai_service, "run_study_summary", fake_run)

    advisor = make_advisor(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db)
    my_student = make_student(db, homeroom=my_class)
    foreign_student = make_student(db, homeroom=foreign_class)
    h = make_user(db, role="advisor", advisor=advisor)

    resp = client.post("/ai/study-summary", json={"student_id": my_student.id}, headers=h)
    assert resp.status_code == 200
    resp = client.post("/ai/study-summary", json={"student_id": foreign_student.id}, headers=h)
    assert resp.status_code == 403


def test_class_overview_advisor_permission(client, db, make_user, make_advisor, make_homeroom, monkeypatch):
    """Chỉ cố vấn phụ trách lớp được AI đánh giá lớp đó."""
    from app.routers import ai as ai_router

    async def fake_run(db_, class_id):
        return {"summary": "ok", "strengths": [], "weaknesses": [], "suggestions": [], "stats": {}, "fallback": False}

    monkeypatch.setattr(ai_router, "run_class_overview", fake_run)

    advisor = make_advisor(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db)
    h = make_user(db, role="advisor", advisor=advisor)

    assert client.post("/ai/class-overview", json={"class_id": my_class.id}, headers=h).status_code == 200
    assert client.post("/ai/class-overview", json={"class_id": foreign_class.id}, headers=h).status_code == 403

    # training_office / student không được dùng tính năng này
    h_office = make_user(db, role="training_office")
    assert client.post("/ai/class-overview", json={"class_id": my_class.id}, headers=h_office).status_code == 403


def test_class_overview_sends_only_aggregates(
    client, db, make_user, make_advisor, make_homeroom, make_student,
    make_course, make_course_class, make_enrollment, monkeypatch,
):
    """Bảo mật tối đa: prompt gửi LLM chỉ gồm số liệu TỔNG HỢP của lớp —
    không tên/MSSV, không còn dữ liệu từng sinh viên (kể cả mã giả SV-xx)."""
    from app.services import ai_service

    advisor = make_advisor(db)
    hc = make_homeroom(db, advisor=advisor)
    good = make_student(db, homeroom=hc)    # điểm 8.0 → B/3.0
    weak = make_student(db, homeroom=hc)    # điểm 4.0 → D/1.0, nợ môn
    cc = make_course_class(db, make_course(db))
    make_enrollment(db, good, cc, process=8.0, exam=8.0)
    make_enrollment(db, weak, cc, process=4.0, exam=4.0)

    captured = {}

    async def fake_llm(prompt):
        captured["prompt"] = prompt
        return {
            "summary": "Lớp có nền tảng khá nhưng còn phân hóa.",
            "strengths": ["GPA trung bình hệ 10 đạt 6.0."],
            "weaknesses": ["Còn môn nợ trong lớp."],
            "suggestions": ["Tổ chức buổi tổng kết nhận xét."],
        }

    monkeypatch.setattr(ai_service, "call_llm_json", fake_llm)

    h = make_user(db, role="advisor", advisor=advisor)
    resp = client.post("/ai/class-overview", json={"class_id": hc.id}, headers=h)
    assert resp.status_code == 200
    body = resp.json()

    # Prompt gửi đi: không danh tính thật, không mã giả từng SV, không mảng cá nhân
    prompt = captured["prompt"]
    assert good.name not in prompt and weak.name not in prompt
    assert good.code not in prompt and weak.code not in prompt
    assert "SV-01" not in prompt and "SV-02" not in prompt
    assert '"students"' not in prompt

    # Văn bản AI đi thẳng ra response (không cần map danh tính nữa)
    assert body["summary"].startswith("Lớp")
    assert body["strengths"] == ["GPA trung bình hệ 10 đạt 6.0."]
    assert body["weaknesses"] == ["Còn môn nợ trong lớp."]
    assert body["suggestions"] == ["Tổ chức buổi tổng kết nhận xét."]

    # Số liệu tổng hợp do server tự tính — không phụ thuộc output AI
    stats = body["stats"]
    assert stats["class_size"] == 2
    assert stats["students_with_grades"] == 2
    assert stats["students_without_grades"] == 0
    assert stats["avg_gpa4"] == 2.0   # (3.0 + 1.0)/2
    assert stats["avg_gpa10"] == 6.0  # (8.0 + 4.0)/2
    assert stats["risk_counts"]["high"] == 1
    assert "students" not in stats
    assert body["fallback"] is False


def test_class_overview_fallback_when_no_llm(
    client, db, make_user, make_advisor, make_homeroom, make_student, monkeypatch
):
    """Không có API key nào → fallback=True nhưng vẫn trả đủ số liệu tổng hợp."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    advisor = make_advisor(db)
    hc = make_homeroom(db, advisor=advisor)
    make_student(db, homeroom=hc)  # chưa có điểm
    h = make_user(db, role="advisor", advisor=advisor)

    resp = client.post("/ai/class-overview", json={"class_id": hc.id}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is True
    assert body["summary"] is None
    assert body["strengths"] == [] and body["weaknesses"] == []
    assert body["stats"]["class_size"] == 1
    assert body["stats"]["students_with_grades"] == 0
    assert body["stats"]["students_without_grades"] == 1
    assert body["stats"]["avg_gpa4"] is None


def test_course_advice_fallback_when_no_llm(client, db, make_user, make_student, make_course, make_course_class, monkeypatch):
    """Không có API key nào → fallback=True nhưng vẫn trả danh sách lớp eligible."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    student = make_student(db)
    make_course_class(db, make_course(db))  # có lớp để advice không rỗng
    h = make_user(db, role="student", student=student)
    resp = client.post("/ai/course-advice", json={"student_id": student.id}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is True
    assert len(body["eligible_classes"]) == 1


@pytest.mark.anyio
async def test_call_llm_json_gemini_then_openrouter_fallback(monkeypatch):
    """call_llm_json: Gemini lỗi → tự chuyển sang OpenRouter (Gemini là chính)."""
    from app.services import llm_service

    calls = []

    async def fake_gemini(prompt):
        calls.append("gemini")
        raise llm_service.LLMError("Gemini API trả về HTTP 429")

    async def fake_openrouter(prompt):
        calls.append("openrouter")
        return {"recommended": [], "notes": "ok"}

    monkeypatch.setattr(llm_service, "call_gemini_json", fake_gemini)
    monkeypatch.setattr(llm_service, "call_openrouter_json", fake_openrouter)

    result = await llm_service.call_llm_json("prompt")
    assert result == {"recommended": [], "notes": "ok"}
    assert calls == ["gemini", "openrouter"]


@pytest.mark.anyio
async def test_call_llm_json_no_keys_raises(monkeypatch):
    from app.services import llm_service

    async def fake_gemini(prompt):
        raise llm_service.LLMError("Chưa cấu hình GOOGLE_API_KEY (hoặc GEMINI_API_KEY)")

    async def fake_openrouter(prompt):
        raise llm_service.LLMError("Chưa cấu hình OPENROUTER_API_KEY")

    monkeypatch.setattr(llm_service, "call_gemini_json", fake_gemini)
    monkeypatch.setattr(llm_service, "call_openrouter_json", fake_openrouter)

    with pytest.raises(LLMError):
        await llm_service.call_llm_json("prompt")


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        extract_json("không có json nào cả")


@pytest.mark.anyio
async def test_call_llm_text_openrouter_success_no_gemini(monkeypatch):
    """OpenRouter (chính) thành công → trả ngay, KHÔNG gọi sang Gemini."""
    from app.core.config import settings
    from app.services import llm_service

    calls = []
    openrouter_ok = {"choices": [{"message": {"content": "tra loi tu openrouter"}}]}

    class _FakeResponse:
        def __init__(self, data, status=200, text=""):
            self._data = data
            self.status_code = status
            self.text = text

        def json(self):
            return self._data

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            return _FakeResponse(openrouter_ok)

    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-or-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm_service.httpx, "AsyncClient", _FakeClient)

    text, provider, model = await llm_service.call_llm_text("hi")
    assert text == "tra loi tu openrouter"
    assert provider == "openrouter"
    assert model == settings.OPENROUTER_MODEL
    # Chỉ 1 cuộc gọi — OpenRouter thành công là dừng, không đụng tới Gemini
    assert len(calls) == 1
    assert "openrouter" in calls[0]


@pytest.mark.anyio
async def test_call_llm_text_openrouter_error_falls_back_gemini(monkeypatch):
    """OpenRouter (chính) bị rate-limit 429 → tự fallback sang Gemini,
    không để lỗi lan tới người dùng khi còn phương án dự phòng."""
    from app.core.config import settings
    from app.services import llm_service

    gemini_ok = {"candidates": [{"finishReason": "STOP",
                                 "content": {"parts": [{"text": "tra loi tu gemini"}]}}]}
    calls = []

    class _FakeResponse:
        def __init__(self, data=None, status=200, text=""):
            self._data = data
            self.status_code = status
            self.text = text

        def json(self):
            return self._data

    class _FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            if "openrouter" in url:
                return _FakeResponse(status=429, text="rate limited")
            return _FakeResponse(gemini_ok)

    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-or-key")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "test-gemini-key")
    monkeypatch.setattr(llm_service.httpx, "AsyncClient", _FakeClient)

    text, provider, model = await llm_service.call_llm_text("hi")
    assert text == "tra loi tu gemini"
    assert provider == "gemini"
    assert model == settings.GEMINI_MODEL
    assert len(calls) == 2  # openrouter 429 -> gọi tiếp gemini
    assert "openrouter" in calls[0]
    assert "generativelanguage" in calls[1]


@pytest.mark.anyio
async def test_call_llm_text_both_fail_raises(monkeypatch):
    """Cả OpenRouter lẫn Gemini đều lỗi → LLMError (không crash 500)."""
    from app.services import llm_service

    async def broken(provider, prompt, system=""):
        raise llm_service.LLMError(f"{provider}: loi")

    monkeypatch.setattr(llm_service, "_call_chat_text", broken)

    with pytest.raises(LLMError, match="openrouter.*gemini"):
        await llm_service.call_llm_text("hi")


# ---------- Pipeline RAG (mock collection + mock LLM, không gọi API thật) ----------

class _FakeCollection:
    """Giả lập Chroma collection: query() trả kết quả định trước."""

    def __init__(self, result):
        self._result = result
        self.last_kwargs = None

    def query(self, **kwargs):
        self.last_kwargs = kwargs
        return self._result


def _patch_pipeline(monkeypatch, collection, llm_text=None, embedding=None):
    """Ráp pipeline RAG với các phần giả lập; trả về dict để kiểm tra sau."""
    import types

    from app.services import embedding_service, llm_service
    from app.services import rag_service

    async def fake_get_embedding(text, input_type="document"):
        fake_get_embedding.last_input_type = input_type
        return embedding if embedding is not None else [0.01] * 8

    fake_get_embedding.last_input_type = None

    async def fake_call_llm_text(prompt, system=""):
        # Mặc định OpenRouter — LLM chính của chatbot quy chế (Voyage chỉ embed)
        return llm_text(prompt, system) if llm_text else (
            "trả lời mẫu", "openrouter", "test-model:free")

    fake_retriever = types.SimpleNamespace(get_collection=lambda: collection)

    monkeypatch.setattr(rag_service, "_ensure_ready", lambda: None)
    monkeypatch.setattr(rag_service, "_get_retriever_module", lambda: fake_retriever)
    monkeypatch.setattr(embedding_service, "get_embedding", fake_get_embedding)
    monkeypatch.setattr(llm_service, "call_llm_text", fake_call_llm_text)
    return {"rag_service": rag_service,
            "fake_get_embedding": fake_get_embedding}


@pytest.mark.anyio
async def test_answer_regulation_question_in_scope(monkeypatch):
    """Câu hỏi trong vùng phủ quy chế → answer + sources + provider/model,
    câu hỏi nhúng bằng Voyage input_type='query', ChromaDB được truy vấn bằng
    query_embeddings tường minh (KHÔNG query_texts)."""
    chunk = ("Phần I > Chương II > Quy chế đào tạo > Điều 12. Cấm thi\n"
             "Sinh viên vắng quá 20% số buổi bị cấm thi.")
    meta = {"phan": "Phần I", "chuong": "Chương II", "chuong_con": "",
            "muc": "A. Quy chế đào tạo", "trich": "", "dieu": "Điều 12",
            "ten_dieu": "Cấm thi", "khoan": "1", "so_trang": 45,
            "nguon": "Sổ tay sinh viên", "text": chunk}
    collection = _FakeCollection({
        "documents": [[chunk]], "metadatas": [[meta]], "distances": [[0.3]],
    })

    def fake_llm(prompt, system):
        assert "Điều 12" in system        # ngữ cảnh đã ghép vào system prompt
        assert "Câu hỏi:" in prompt
        return ("Theo Điều 12, vắng quá 20% bị cấm thi (Điều 12, Quy chế đào tạo, trang ~45).",
                "openrouter", "test-model:free")

    ctx = _patch_pipeline(monkeypatch, collection, llm_text=fake_llm)
    rag_service = ctx["rag_service"]

    result = await rag_service.answer_regulation_question(
        "Khi nào bị cấm thi?", session_id="t-in-scope")

    assert "Điều 12" in result["answer"]
    assert result["provider"] == "openrouter"
    assert result["model"] == "test-model:free"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["dieu"] == "Điều 12"
    assert result["sources"][0]["so_trang"] == 45
    # Câu hỏi nhúng bằng Voyage với input_type="query" (khác "document" lúc build)
    assert ctx["fake_get_embedding"].last_input_type == "query"
    # Vector truyền tường minh — tuyệt đối không để Chroma tự nhúng văn bản
    assert "query_embeddings" in collection.last_kwargs
    assert "query_texts" not in collection.last_kwargs
    # Lịch sử hội thoại được lưu server-side
    assert ("t-in-scope", "", "") in rag_service._sessions
    rag_service._sessions.clear()


@pytest.mark.anyio
async def test_answer_regulation_question_out_of_scope_no_llm(monkeypatch):
    """Câu hỏi ngoài vùng phủ (không chunk nào) → 'không tìm thấy', KHÔNG gọi LLM."""
    collection = _FakeCollection({"documents": [[]], "metadatas": [[]], "distances": [[]]})
    called = {"n": 0}

    def fake_llm(prompt, system):
        called["n"] += 1
        raise AssertionError("KHÔNG được gọi LLM cho câu hỏi ngoài vùng phủ")

    ctx = _patch_pipeline(monkeypatch, collection, llm_text=fake_llm)
    rag_service = ctx["rag_service"]

    result = await rag_service.answer_regulation_question(
        "Giá vàng hôm nay bao nhiêu?", session_id="t-oos")

    assert result["answer"] == "Toi khong tim thay thong tin nay trong quy che."
    assert result["sources"] == []
    assert called["n"] == 0
    rag_service._sessions.clear()


@pytest.mark.anyio
async def test_answer_regulation_question_embedding_error(monkeypatch):
    """Embedding API lỗi → RagLLMError (không phải crash 500)."""
    import types

    from app.services import embedding_service, rag_service
    from app.services.embedding_service import EmbeddingError

    async def broken_embedding(text, input_type="document"):
        raise EmbeddingError("Voyage API HTTP 429")

    monkeypatch.setattr(rag_service, "_ensure_ready", lambda: None)
    monkeypatch.setattr(rag_service, "_get_retriever_module",
                        lambda: types.SimpleNamespace(get_collection=lambda: None))
    monkeypatch.setattr(embedding_service, "get_embedding", broken_embedding)

    with pytest.raises(rag_service.RagLLMError, match="embedding"):
        await rag_service.answer_regulation_question("hi", session_id="t-err")


@pytest.mark.anyio
async def test_answer_regulation_question_missing_collection(monkeypatch):
    """Vector store chưa build (collection lỗi) → RagNotAvailableError (503)."""
    import types

    from app.services import rag_service

    def broken_collection():
        raise FileNotFoundError("Chua co collection 'quy_che' — chay rebuild")

    _patch_pipeline(monkeypatch, _FakeCollection(None))
    monkeypatch.setattr(rag_service, "_get_retriever_module",
                        lambda: types.SimpleNamespace(get_collection=broken_collection))

    with pytest.raises(rag_service.RagNotAvailableError):
        await rag_service.answer_regulation_question("hi", session_id="t-miss")


@pytest.mark.anyio
async def test_answer_regulation_question_model_mismatch_blocks(monkeypatch):
    """Index nhúng bằng model khác VOYAGE_MODEL hiện tại → chặn ngay
    (503 kèm hướng dẫn rebuild), KHÔNG trả lời bằng vector lệch không gian."""
    import types

    from app.services import rag_service

    def mismatch_collection():
        raise FileNotFoundError(
            "Vector store duoc nhúng bang 'model-cu' nhung VOYAGE_MODEL "
            "hien tai la 'voyage-4' — chay: python scripts/rebuild_vector_store.py")

    _patch_pipeline(monkeypatch, _FakeCollection(None))
    monkeypatch.setattr(rag_service, "_get_retriever_module",
                        lambda: types.SimpleNamespace(get_collection=mismatch_collection))

    with pytest.raises(rag_service.RagNotAvailableError, match="rebuild"):
        await rag_service.answer_regulation_question("hi", session_id="t-model")

