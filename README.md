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

## Deploy (Vercel + Render + Supabase)

Kiến trúc & bối cảnh chi tiết: [`DEPLOY.md`](DEPLOY.md). Quy trình rút gọn:

### 1. Supabase (database)
1. Tạo project tại [supabase.com](https://supabase.com) → **Connect** → copy connection string **direct cổng 5432** (không dùng pooler 6543).

### 2. Backend (Render)
1. Đăng nhập [render.com](https://render.com) (bằng GitHub) → **New → Web Service** → kết nối repo `DatHokage/unimind`.
2. Cấu hình service:
   - **Name**: tùy chọn (tên này nằm trong domain `.onrender.com`)
   - **Region**: Singapore (gần VN nhất)
   - **Root Directory**: `backend`
   - **Branch**: `main`
   - **Runtime**: Python (tự nhận qua `requirements.txt` + `runtime.txt`)
   - **Build Command**:
     ```
     pip install -r requirements.txt && python -m src.ingestion.build_index && alembic upgrade head && python -m app.seed
     ```
     Bước `build_index` **tải embedding model tiếng Việt (~500MB) vào ngay trong lúc build** để model được "bake" vào image deploy — service khởi động lại/scale ra không phải tải lại (free tier không có volume). File DOCX gốc không nằm trong repo nên phải đặt biến `SKIP_INDEX_BUILD_IF_NO_DOCS=1` để bước này dùng cache thay vì báo lỗi (xem lưu ý bên dưới). Nếu không muốn bake, bỏ bước `build_index` — model sẽ tải khi service start (lần đầu chậm hơn).
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (hoặc để trống cho Render tự đọc `Procfile`)
   - **Instance Type**: **Free** (đủ demo; server ngủ sau 15 phút không dùng) — hoặc trả phí nếu cần chạy 24/7 lúc bảo vệ.
3. **Environment** (tab Environment):

   | Biến | Giá trị |
   |---|---|
   | `SUPABASE_DB_URL` | connection string Supabase (cổng 5432) |
   | `SECRET_KEY` | chuỗi ngẫu nhiên ≥ 32 ký tự |
   | `OPENROUTER_API_KEY` | key OpenRouter (https://openrouter.ai/keys) |
   | `GOOGLE_API_KEY` | key Gemini (https://aistudio.google.com/apikey) — dự phòng, đặt càng tốt |
   | `CORS_ORIGINS` | `https://<domain-vercel>.vercel.app` (bước 3 xong quay lại điền; có thể thêm `http://localhost:5173` để dev vẫn gọi được) |
   | `SKIP_INDEX_BUILD_IF_NO_DOCS` | `1` (nếu Build Command có bước `build_index`) |

4. **Manual Deploy → Deploy latest commit**.
5. Kiểm tra: mở `https://<name>.onrender.com/health` → `{"status":"ok"}`; `/docs` hiện Swagger.

> ⚠️ **Free tier**: (1) server ngủ sau 15 phút không dùng — request đầu mất ~30–60s để đánh thức, **gọi `/health` trước buổi demo 5–10 phút** để làm ấm; (2) RAM 512MB — đủ chạy nhưng nếu service bị OOM khi warm-up RAG thì nâng instance nhỏ trả phí.

### 3. Frontend (Vercel)
1. [vercel.com](https://vercel.com) → **Add New → Project** → import repo `DatHokage/unimind`.
2. **Root Directory**: `frontend` (Framework tự nhận Vite).
3. **Environment Variable**: `VITE_API_BASE_URL` = `https://<name>.onrender.com` (domain bước 2.5).
4. Deploy → copy domain `https://xxx.vercel.app` → quay lại Render điền `CORS_ORIGINS` → redeploy backend.
5. Mở trang Vercel, đăng nhập `student1` / `password123`, thử chat quy chế.

### 4. Xác minh sau deploy
```bash
python scripts\smoke.py        # set SMOKE_BASE=https://<name>.onrender.com trước khi chạy
```
Và test thủ công: đăng nhập 4 vai trò, đăng ký học phần + AI tư vấn, chat quy chế (kiểm tra `provider` trong câu trả lời).

### Lưu ý vận hành
- **Không có key LLM**: AI tư vấn/tóm tắt trả fallback server-side (không chết API); chatbot quy chế trả 503 — cần ít nhất 1 trong 2 key OpenRouter/Gemini.
- **Cập nhật quy chế**: đặt DOCX vào `backend/data/raw/` → chạy `python -m src.ingestion.build_index` ở máy local → commit `backend/vectorstore/` → push (Render tự redeploy; trên Render nên **bỏ biến `SKIP_INDEX_BUILD_IF_NO_DOCS`** khi có file DOCX trong repo, hoặc tiếp tục dùng index đã commit).
- **Cold start**: free tier ngủ sau 15 phút — làm ấm `/health` trước khi demo; muốn hết hẳn, nâng instance trả phí.

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
