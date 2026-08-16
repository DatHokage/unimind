import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    ai,
    auth,
    course_classes,
    courses,
    enrollments,
    grades,
    homeroom_classes,
    lecturers,
    majors,
    schedule,
    stats,
    students,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm-up chatbot quy chế (tải embedding model + ChromaDB) ở thread riêng
    # để không chặn server; câu hỏi đầu tiên không phải chờ.
    import os

    from app.services.rag_service import is_configured, warmup

    if os.environ.get("RAG_WARMUP", "1") == "1" and is_configured():
        threading.Thread(target=warmup, daemon=True).start()
    yield


app = FastAPI(title="Hệ thống Quản lý Đào tạo", version="1.0.0", lifespan=lifespan)

# Origin được phép gọi API — cấu hình qua biến môi trường CORS_ORIGINS
# (mặc định localhost:5173 cho dev; khi deploy thêm domain Vercel của frontend).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(majors.router)
app.include_router(students.router)
app.include_router(lecturers.router)
app.include_router(homeroom_classes.router)
app.include_router(courses.router)
app.include_router(course_classes.router)
app.include_router(enrollments.router)
app.include_router(schedule.router)
app.include_router(grades.router)
app.include_router(stats.router)
app.include_router(ai.router)


@app.get("/health")
def health():
    return {"status": "ok"}
