from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth_dependency import (
    assert_advisor_owns_homeroom,
    get_current_user,
    get_target_student,
    require_role,
)
from app.schemas.ai import (
    ClassOverviewRequest,
    ClassOverviewResponse,
    CourseAdviceRequest,
    CourseAdviceResponse,
    RegulationChatRequest,
    RegulationChatResponse,
    RegulationModelListResponse,
    StudySummaryRequest,
    StudySummaryResponse,
)
from app.services.ai_service import (
    build_study_summary_payload,
    run_class_overview,
    run_course_advice,
    run_study_summary,
)
from app.services.rag_service import (
    RagLLMError,
    RagNotAvailableError,
    answer_regulation_question,
    is_configured,
    list_models,
    rag_status,
)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/course-advice", response_model=CourseAdviceResponse)
async def course_advice(
    body: CourseAdviceRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("student")),
):
    """AI tư vấn đăng ký học phần — chỉ cho chính sinh viên đang đăng nhập.

    AI chỉ gợi ý, KHÔNG tự đăng ký; sinh viên vẫn phải gọi POST /enrollments
    (server validate lại toàn bộ điều kiện).
    """
    if user["student_id"] != body.student_id:
        raise HTTPException(status_code=403, detail="Chỉ được tư vấn cho chính mình")
    ai_result, eligible, fallback = await run_course_advice(
        db, body.student_id, body.target_year, body.target_term
    )
    return CourseAdviceResponse(
        overview=ai_result["overview"],
        recommendations=ai_result["recommendations"],
        warnings=ai_result["warnings"],
        suggestions=ai_result["suggestions"],
        notes=ai_result["notes"],
        eligible_classes=eligible,
        fallback=fallback,
    )


@router.post("/study-summary", response_model=StudySummaryResponse)
async def study_summary(
    body: StudySummaryRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """AI tóm tắt tiến độ học tập — chính sinh viên hoặc advisor phụ trách."""
    get_target_student(db, user, body.student_id)
    result, fallback = await run_study_summary(db, body.student_id)
    return StudySummaryResponse(
        summary=result["summary"],
        warnings=result["warnings"],
        suggestions=result["suggestions"],
        stats=build_study_summary_payload(db, body.student_id),
        fallback=fallback,
    )


@router.post("/class-overview", response_model=ClassOverviewResponse)
async def class_overview(
    body: ClassOverviewRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_role("advisor")),
):
    """AI đánh giá TỔNG QUAN lớp hành chính — CHỈ cố vấn phụ trách lớp đó.

    Payload gửi LLM chỉ là số liệu tổng hợp của cả lớp (không dữ liệu riêng
    từng sinh viên, không tên/MSSV). Số liệu stats do server tự tính.
    """
    assert_advisor_owns_homeroom(db, user, body.class_id)
    result = await run_class_overview(db, body.class_id)
    return ClassOverviewResponse(**result)


@router.get("/regulation-chat/status")
def regulation_chat_status(user: dict = Depends(get_current_user)):
    """Kiểm tra nhanh chatbot quy chế đã sẵn sàng chưa (không cần chờ load model)."""
    return {"ready": is_configured(), **rag_status()}


@router.get("/regulation-chat/models", response_model=RegulationModelListResponse)
async def regulation_chat_models(user: dict = Depends(get_current_user)):
    """Danh sách model miễn phí khả dụng (OpenRouter :free + Gemini theo .env).

    Trả 503 khi chatbot chưa cấu hình.
    """
    try:
        data = list_models()
    except RagNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return RegulationModelListResponse(**data)


@router.post("/regulation-chat", response_model=RegulationChatResponse)
async def regulation_chat(
    body: RegulationChatRequest,
    user: dict = Depends(get_current_user),
):
    """Chatbot hỏi-đáp quy chế (RAG): truy vấn Sổ tay sinh viên, trả lời kèm
    trích dẫn Điều / Khoản / trang. Ngữ cảnh hội thoại giữ theo session_id.

    provider/model: nhận để tương thích dropdown trên web (giữ khóa lịch sử
    theo session); model trả lời thực tế luôn theo cấu hình .env — OpenRouter,
    lỗi tự fallback Gemini, không cần dropdown ép model như bản LangChain cũ.
    Trả 503 khi pipeline chưa sẵn sàng (chưa có vector store hoặc API key).
    """
    try:
        result = await answer_regulation_question(
            body.question, body.session_id,
            provider=body.provider, model=body.model,
        )
    except RagNotAvailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RagLLMError as e:
        raise HTTPException(status_code=502, detail=f"Chatbot quy chế gặp lỗi: {e}")

    return RegulationChatResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        provider=result.get("provider", ""),
        model=result.get("model", ""),
    )
