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


def test_study_summary_advisor_permission(client, db, make_user, make_lecturer, make_homeroom, make_student, monkeypatch):
    from app.services import ai_service

    async def fake_run(db_, student_id):
        return {"summary": "ok", "warnings": [], "suggestions": []}, False

    monkeypatch.setattr(ai_service, "run_study_summary", fake_run)

    advisor = make_lecturer(db)
    my_class = make_homeroom(db, advisor=advisor)
    foreign_class = make_homeroom(db)
    my_student = make_student(db, homeroom=my_class)
    foreign_student = make_student(db, homeroom=foreign_class)
    h = make_user(db, role="advisor", lecturer=advisor)

    resp = client.post("/ai/study-summary", json={"student_id": my_student.id}, headers=h)
    assert resp.status_code == 200
    resp = client.post("/ai/study-summary", json={"student_id": foreign_student.id}, headers=h)
    assert resp.status_code == 403


def test_course_advice_fallback_when_no_llm(client, db, make_user, make_student, make_course, make_course_class, monkeypatch):
    """Không có API key nào → fallback=True nhưng vẫn trả danh sách lớp eligible."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    student = make_student(db)
    cc = make_course_class(db, make_course(db))
    h = make_user(db, role="student", student=student)
    resp = client.post("/ai/course-advice", json={"student_id": student.id}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["fallback"] is True
    assert len(body["eligible_classes"]) == 1


@pytest.mark.anyio
async def test_call_llm_json_openrouter_then_gemini_fallback(monkeypatch):
    """call_llm_json: OpenRouter lỗi → tự chuyển sang Gemini."""
    from app.services import llm_service

    calls = []

    async def fake_openrouter(prompt):
        calls.append("openrouter")
        raise llm_service.LLMError("OpenRouter API trả về HTTP 429")

    async def fake_gemini(prompt):
        calls.append("gemini")
        return {"recommended": [], "notes": "ok"}

    monkeypatch.setattr(llm_service, "call_openrouter_json", fake_openrouter)
    monkeypatch.setattr(llm_service, "call_gemini_json", fake_gemini)

    result = await llm_service.call_llm_json("prompt")
    assert result == {"recommended": [], "notes": "ok"}
    assert calls == ["openrouter", "gemini"]


@pytest.mark.anyio
async def test_call_llm_json_no_keys_raises(monkeypatch):
    from app.services import llm_service

    async def fake_openrouter(prompt):
        raise llm_service.LLMError("Chưa cấu hình OPENROUTER_API_KEY")

    async def fake_gemini(prompt):
        raise llm_service.LLMError("Chưa cấu hình GEMINI_API_KEY")

    monkeypatch.setattr(llm_service, "call_openrouter_json", fake_openrouter)
    monkeypatch.setattr(llm_service, "call_gemini_json", fake_gemini)

    with pytest.raises(LLMError):
        await llm_service.call_llm_json("prompt")


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": {"b": 2}} thanks') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        extract_json("không có json nào cả")
