# Hệ thống Quản lý Đào tạo tích hợp AI

Full-stack hệ thống quản lý đào tạo theo `DAC_TA_DU_AN.md`: **FastAPI + React + Supabase Postgres**. AI tư vấn môn học + tóm tắt học tập qua **OpenRouter** (fallback Gemini), chatbot hỏi-đáp quy chế **RAG** (LangChain + ChromaDB, embedding tiếng Việt chạy local — tích hợp từ dự án `rag_langchain`).

## Tính năng theo vai trò

| Vai trò | Chức năng |
|---|---|
| **Sinh viên** (`student`) | Đăng ký học phần (kèm AI tư vấn), hủy đăng ký, xem **thời khóa biểu**, xem bảng điểm, chat quy chế |
| **Giảng viên** (`lecturer`) | Xem lớp dạy, nhập điểm **quá trình** cho lớp mình dạy |
| **Cố vấn** (`advisor`) | Xem lớp chủ nhiệm + sinh viên, thống kê lớp mình, nhận xét AI cho từng sinh viên |
| **Phòng đào tạo** (`training_office`) | CRUD sinh viên/giảng viên/lớp/học phần, nhập điểm **thi**, thống kê toàn trường |

**Quy tắc nghiệp vụ chính**
- Điểm tổng kết = `(quá trình + thi) / 2` — tính server-side, **không API nào nhận total_score**.
- Ngưỡng qua môn: `total_score ≥ 5.0` (cấu hình `PASS_THRESHOLD`) — dùng xét điều kiện tiên quyết.
- Điều kiện đăng ký kiểm tra theo thứ tự: lớp mở → sĩ số → tiên quyết → trùng lịch (cùng kỳ) → trùng đăng ký.
- Hủy đăng ký chỉ khi chưa nhập điểm (ngược lại 409).

## Cấu trúc

```
backend/
  app/
    core/          config, security (JWT+bcrypt), database
    models/        SQLAlchemy 2.x (user, person, academic)
    schemas/       Pydantic v2
    routers/       auth, majors, students, lecturers, homeroom_classes,
                   courses, course_classes, enrollments, schedule, grades,
                   stats, ai
    services/      enrollment, grade, user, course, ai, llm, prompts, rag_service
    dependencies/  auth_dependency (get_current_user, require_role, get_target_student)
    seed.py        dữ liệu demo idempotent
  alembic/         migrations
  tests/           56 test pytest (SQLite in-memory)
  scripts/smoke.py smoke test end-to-end qua HTTP
frontend/          Vite + React 19 + Tailwind v4 + React Router + axios
```

## Chạy trên Windows

Yêu cầu: Python 3.12, Node 20+, tài khoản Supabase (Postgres) và key OpenRouter (hoặc Gemini) cho chức năng AI.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Sửa `backend/.env`:

| Biến | Giá trị |
|---|---|
| `SUPABASE_DB_URL` | `postgresql+psycopg2://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require` — **cổng 5432 (direct)**, không dùng pooler 6543 |
| `SECRET_KEY` | chuỗi ngẫu nhiên ≥ 32 ký tự |
| `OPENROUTER_API_KEY` | key OpenRouter (https://openrouter.ai/keys) — bật AI tư vấn + chatbot quy chế. Trống thì thử Gemini, không có key nào thì AI trả fallback server-side |
| `OPENROUTER_MODEL` | mặc định `nvidia/nemotron-3-super-120b-a12b:free` |
| `GEMINI_API_KEY` | (tùy chọn) dự phòng cho OpenRouter |
| `GEMINI_MODEL` | mặc định `gemini-2.0-flash` |

Tạo bảng + seed + chạy:

```bash
.venv\Scripts\alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173 (proxy `/api` → `localhost:8000` đã cấu hình sẵn trong `vite.config.js`).

### 3. Kiểm tra

```bash
cd backend
.venv\Scripts\python -m pytest -q          # 56 test
.venv\Scripts\python scripts\smoke.py      # 32 bước end-to-end (cần server đang chạy; đổi server: set SMOKE_BASE=http://127.0.0.1:8001)
```

## Tài khoản demo (sau `python -m app.seed`)

Mật khẩu chung: `password123`

| Username | Vai trò | Ghi chú |
|---|---|---|
| `ptdt` | Phòng đào tạo | nhập điểm thi, CRUD, thống kê |
| `lecturer1` | Giảng viên Trần Thị Bình | dạy mọi lớp trong seed |
| `advisor1` | Cố vấn Nguyễn Văn An | phụ trách CNTT1-K12 + CNTT2-K12 |
| `student1` | SV001 Phạm Văn Nhất | đã đạt TH1 (7.5) → đăng ký được CTDL/CSDL |
| `student2` | SV002 Lê Thị Nhị | trượt TH1 (4.0) → demo chặn tiên quyết |
| `student3` | SV003 Hoàng Văn Tam | đạt TH1 (6.0), đã chiếm chỗ CSDL.A |
| `student4` | SV004 Đỗ Thị Tư | lớp CNTT2-K12, đã chiếm chỗ CSDL.A |

**Kịch bản demo nhanh**
- `student1` vào "Đăng ký học phần": bấm AI tư vấn → AI (OpenRouter) gợi ý CTDL/CSDL/GDTC1 kèm lý do; đăng ký CTDL.A OK.
- `student2` đăng ký CTDL.A → bị chặn "chưa hoàn thành học phần tiên quyết".
- `student1` đăng ký CSDL.A → "lớp đã đầy"; đăng ký OOP.A → trùng lịch / chưa đạt CTDL.
- `lecturer1` nhập điểm quá trình; gọi endpoint điểm thi → 403.
- `ptdt` nhập điểm thi → tổng kết tự tính; office gọi endpoint quá trình → 403.
- `advisor1` xem đúng 2 lớp, mở sinh viên → bảng điểm + nhận xét AI.
- Chat quy chế: hỏi "Sinh viên bị cấm thi khi nào?" → AI trả lời kèm trích dẫn Điều / Khoản / trang từ Sổ tay sinh viên.

## Ghi chú sai lệch so với đặc tả

1. **Liên kết User ↔ Student/Lecturer**: đặc tả không định nghĩa cách nối tài khoản với hồ sơ. Hệ thống dùng 2 FK nullable unique trên bảng `users` (`student_id`, `lecturer_id`). Mọi kiểm tra sở hữu so sánh `user["lecturer_id"]`/`user["student_id"]` trong JWT — **không phải `user_id`** như ví dụ code trong đặc tả (ví dụ đó không hoạt động được vì User và Lecturer là 2 bảng riêng).
2. **Bảng `users`** thay vì `user` (từ khóa dành riêng của PostgreSQL).
3. **Grade.updated_by → users.id** (không phải lecturer.id) vì phòng đào tạo cũng ghi điểm.
4. **RAG chatbot**: đã tích hợp — pipeline từ dự án `rag_langchain`, xem mục dưới.
5. Thêm endpoint ngoài đặc tả để đủ UI: `GET /course-classes/{id}/enrollments`, `GET /homeroom-classes/mine`, `PATCH /course-classes/{id}`, `GET /students/{id}`, `GET /schedule/student/{id}?year=&term=` (thời khóa biểu theo kỳ).
6. Lịch học lưu `JSON`: `[{"weekday": 2..8, "start_period", "end_period", "room"}]`; trùng lịch = cùng weekday + giao khoảng tiết, chỉ xét trong cùng (year, term).
7. Xóa sinh viên/lớp/học phần: chưa triển khai DELETE (tránh orphan dữ liệu điểm/đăng ký) — quản lý qua trạng thái nếu cần.

## Chatbot quy chế (RAG)

Đã tích hợp pipeline từ dự án `rag_langchain`: `data/raw/*.docx → chunk theo Điều/Khoản → embedding tiếng Việt chạy local (vietnamese-bi-encoder) → ChromaDB → retriever MMR → LLM (OpenRouter, fallback Gemini)`. Vector store dựng sẵn từ **Sổ tay sinh viên 2024-2025** trong `backend/vectorstore/` — có `OPENROUTER_API_KEY` là chat được ngay, endpoint `POST /ai/regulation-chat` trả `answer` + `sources` (Điều / Khoản / trang) + `provider`, ngữ cảnh hội thoại giữ theo `session_id`.

**Cập nhật dữ liệu quy chế:** đặt file DOCX mới vào `backend/data/raw/` rồi build lại index (lần đầu tải embedding model ~500MB, các lần sau dùng cache):

```bash
cd backend
.venv\Scripts\python -m src.ingestion.build_index
```

**Thử retrieval không cần API key:** `.venv\Scripts\python -m src.rag.retriever "cau hoi"`
