# Hệ thống Quản lý Đào tạo tích hợp AI

Hệ thống quản lý đào tạo cho cơ sở giáo dục: quản lý sinh viên, giảng viên, học phần, lớp học, đăng ký học phần, nhập điểm và thống kê kết quả học tập — tích hợp AI tư vấn đăng ký môn học, tóm tắt kết quả học tập và chatbot hỏi-đáp quy chế đào tạo (RAG).

**Stack:** FastAPI (Python 3.12) · React + Vite · SQLite (chạy local) hoặc PostgreSQL/Supabase (deploy) · JWT · LangChain + ChromaDB (embedding tiếng Việt chạy local) · LLM qua OpenRouter (fallback Gemini).

| Tài liệu | Nội dung |
|---|---|
| [`DAC_TA_DU_AN.md`](DAC_TA_DU_AN.md) | Đặc tả đầy đủ của đồ án |
| [`DEPLOY.md`](DEPLOY.md) | Phân tích kiến trúc + kế hoạch triển khai |
| [`frontend.md`](frontend.md) | Ghi chú frontend |

---

## Tính năng theo vai trò

| Vai trò | Chức năng chính |
|---|---|
| **Sinh viên** (`student`) | Đăng ký / hủy học phần (kèm AI tư vấn), xem thời khóa biểu, xem bảng điểm + GPA tích lũy, chat quy chế |
| **Giảng viên** (`lecturer`) | Xem lớp đang dạy, nhập **điểm quá trình** cho lớp mình phụ trách |
| **Cố vấn học tập** (`advisor`) | Xem lớp chủ nhiệm và sinh viên, xem bảng điểm, nhận xét AI cho từng sinh viên |
| **Phòng đào tạo** (`training_office`) | CRUD sinh viên / giảng viên / ngành / lớp / học phần / lớp học phần, nhập **điểm thi**, thống kê toàn trường |

**Quy tắc nghiệp vụ chính**

- Điểm tổng kết = `(quá trình + thi) / 2` — tính ở backend, **không API nào nhận total_score từ client**.
- Quy đổi điểm: `8.5–10 → A/4` · `7.0–<8.5 → B/3` · `5.5–<7.0 → C/2` · `4.0–<5.5 → D/1` · `<4.0 → F/0` (F → Không đạt, các mức khác → Đạt).
- GPA tích lũy = `SUM(điểm × tín chỉ) / SUM(tín chỉ)` trên các học phần **đã có điểm và được đánh dấu "Tính vào GPA tích lũy"** (môn như Giáo dục thể chất có thể bị loại khỏi GPA qua cờ này, dù đạt vẫn cộng tín chỉ tích lũy).
- Điều kiện đăng ký kiểm tra theo thứ tự: lớp mở → sĩ số → tiên quyết → trùng lịch (cùng kỳ) → trùng đăng ký.

---

## Chạy trên máy local (clone là dùng được)

> Đường dẫn mặc định dùng **Windows PowerShell**. Trên macOS/Linux chỉ cần đổi `.venv\Scripts\activate` thành `source .venv/bin/activate` và dùng `cp` thay `copy`.

**Yêu cầu cài sẵn**

- **Python 3.12** trở lên — [python.org/downloads](https://www.python.org/downloads/) (khi cài nhớ tick *"Add python.exe to PATH"*)
- **Node.js 20 LTS** trở lên — [nodejs.org](https://nodejs.org/)
- **Không cần cài database** — chạy local dùng SQLite, file DB tự tạo trong `backend/`

### Bước 1 — Clone và cài backend

```powershell
git clone https://github.com/DatHokage/unimind.git
cd unimind/backend

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

> Lần đầu `pip install` có thể mất **5–10 phút** vì phải tải PyTorch + các thư viện AI (~2GB). Máy cấu hình yếu cứ để chạy, đừng tưởng bị treo.

### Bước 2 — Tạo file cấu hình `.env`

```powershell
copy .env.example .env
```

Mở `backend/.env` kiểm tra dòng database đang là SQLite (file `.env.example` đã để sẵn):

```env
SUPABASE_DB_URL=sqlite:///./ql_daotao.db
```

- Chạy thử ở máy mình: **giữ nguyên** dòng trên là đủ.
- Muốn bật AI tư vấn + chatbot quy chế: điền `OPENROUTER_API_KEY` (lấy miễn phí tại [openrouter.ai/keys](https://openrouter.ai/keys)); có thể điền thêm `GOOGLE_API_KEY` ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) để dự phòng. **Không có key nào thì mọi chức năng quản lý vẫn chạy**, chỉ có AI trả fallback.
- `SECRET_KEY`: nên đổi thành chuỗi ngẫu nhiên dài (bắt buộc khi deploy).

### Bước 3 — Tạo bảng + nạp dữ liệu mẫu + chạy backend

```powershell
alembic upgrade head     # tạo cấu trúc bảng
python -m app.seed       # nạp dữ liệu demo (tài khoản, học phần, điểm mẫu)
uvicorn app.main:app --reload
```

Backend chạy tại **http://localhost:8000** — xem danh sách API tại http://localhost:8000/docs.

> Lần khởi động đầu tiên, server tự tải embedding model tiếng Việt (~500MB, dùng một lần rồi cache) cho chatbot quy chế ở thread nền. Không muốn tải thì chạy với biến môi trường `RAG_WARMUP=0`.

### Bước 4 — Chạy frontend (mở một cửa sổ terminal **mới**)

```powershell
cd frontend
npm install
npm run dev
```

Mở **http://localhost:5173**, đăng nhập `student1` / `password123` và dùng thử. (Frontend dev tự proxy `/api` sang backend port 8000 — đã cấu hình sẵn, không cần làm gì thêm.)

### Đặt lại dữ liệu về trạng thái demo ban đầu

Xóa file database rồi chạy lại Bước 3:

```powershell
del ql_daotao.db
alembic upgrade head
python -m app.seed
```

---

## Tài khoản demo

Sau khi seed, mật khẩu chung cho tất cả tài khoản là `password123`:

| Username | Vai trò | Ghi chú dữ liệu |
|---|---|---|
| `ptdt` | Phòng đào tạo | nhập điểm thi, CRUD, thống kê |
| `lecturer1` | Giảng viên Trần Thị Bình | dạy mọi lớp trong dữ liệu mẫu |
| `advisor1` | Cố vấn Nguyễn Văn An | phụ trách CNTT1-K12 + CNTT2-K12 |
| `student1` | SV001 Phạm Văn Nhất | đã đạt TH1 (7.5) → đăng ký được CTDL/CSDL |
| `student2` | SV002 Lê Thị Nhị | trượt TH1 (4.0) → demo chặn tiên quyết |
| `student3` | SV003 Hoàng Văn Tam | đạt TH1 (6.0) |
| `student4` | SV004 Đỗ Thị Tư | lớp CNTT2-K12, dữ liệu đủ 3 học kỳ: môn đạt B/C, môn trượt F, môn đang học, HP không tính GPA (GDTC1) |

**Kịch bản demo nhanh**

1. `student1` → *Đăng ký học phần*: bấm AI tư vấn → AI gợi ý CTDL/CSDL/GDTC1 kèm lý do; đăng ký CTDL.A thành công.
2. `student2` đăng ký CTDL.A → bị chặn *"chưa hoàn thành học phần tiên quyết"*.
3. `student1` đăng ký CSDL.A → *"lớp đã đầy"*; đăng ký OOP.A → trùng lịch / chưa đạt tiên quyết.
4. `lecturer1` nhập điểm quá trình OK; gọi endpoint nhập điểm thi → **403** (chỉ phòng đào tạo được nhập điểm thi).
5. `ptdt` nhập điểm thi → điểm tổng kết + điểm chữ + hệ 4 tự tính; gọi endpoint nhập điểm quá trình → **403**.
6. `advisor1` xem đúng 2 lớp phụ trách → mở một sinh viên thấy bảng điểm + bấm *"Tạo nhận xét"* để AI nhận xét.
7. Chat quy chế (cần key LLM): hỏi *"Sinh viên bị cấm thi khi nào?"* → trả lời kèm trích dẫn Điều / Khoản / trang từ Sổ tay sinh viên.

---

## Chạy test

```powershell
cd backend
python -m pytest -q                       # test backend (SQLite in-memory)
python scripts\smoke.py                   # 32 bước end-to-end — cần backend đang chạy ở port 8000
```

Các script kiểm tra thêm (cần server đang chạy): `scripts\smoke_student4.py`, `scripts\smoke_grade_conversion.py`.

---

## Chatbot quy chế (RAG)

- Vector store dựng sẵn từ **Sổ tay sinh viên 2024–2025** nằm trong `backend/vectorstore/` (đã commit ~11MB, clone về là có). Embedding tiếng Việt chạy **local 100%** — chỉ bước trả lời mới gọi LLM.
- Endpoint `POST /ai/regulation-chat` trả `answer` + `sources` (Điều / Khoản / trang) + `provider`; ngữ cảnh hội thoại giữ theo `session_id`.
- **Cập nhật quy chế mới:** đặt file DOCX vào `backend/data/raw/` → chạy `python -m src.ingestion.build_index` → commit + push thư mục `backend/vectorstore/`.
- Thử retrieval không cần API key: `python -m src.rag.retriever "cau hoi"`.

---

## Deploy (Vercel + Render + Supabase)

Khi đưa lên mạng: **Vercel** (frontend) + **Render** (backend) + **Supabase** (Postgres). Toàn bộ thiết lập chi tiết (từng bước trên dashboard, biến môi trường, lưu ý free tier, checklist trước ngày bảo vệ) ở [`DEPLOY.md`](DEPLOY.md). Tóm tắt:

1. **Supabase**: tạo project → lấy connection string **cổng 5432 direct** (không dùng pooler 6543).
2. **Render**: New Web Service, Root Directory `backend`, Build Command:
   `pip install -r requirements.txt && python -m src.ingestion.build_index && alembic upgrade head && python -m app.seed`
   (kèm biến môi trường `SKIP_INDEX_BUILD_IF_NO_DOCS=1` — chi tiết ở DEPLOY.md mục 2).
3. **Vercel**: import repo, Root Directory `frontend`, biến `VITE_API_BASE_URL=https://<ten>.onrender.com`.
4. Quay lại Render điền `CORS_ORIGINS=https://<domain>.vercel.app` rồi redeploy.

> ⚠️ Free tier Render ngủ sau 15 phút không dùng — **mở `/health` trước buổi demo 5–10 phút** để làm ấm server.

---

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `uvicorn: command not found` | Chưa activate venv — chạy lại `.venv\Scripts\activate` |
| `address already in use` khi chạy uvicorn | Port 8000 bị chiếm — tắt chương trình khác hoặc chạy `uvicorn app.main:app --port 8001 --reload` |
| `pip install` rất lâu | Bình thường — PyTorch và thư viện AI ~2GB, chỉ chậm lần đầu |
| Frontend báo lỗi CORS / không gọi được API | Backend chưa chạy, hoặc chạy không đúng port 8000 |
| Chat quy chế trả 503 | Chưa điền `OPENROUTER_API_KEY` / `GOOGLE_API_KEY` trong `backend/.env` |
| `ModuleNotFoundError: No module named 'app'` | Đang chạy lệnh ngoài thư mục `backend/`, hoặc chưa activate venv |
| Dữ liệu demo bị lộn xộn sau khi thử | Xóa `backend/ql_daotao.db` rồi chạy lại `alembic upgrade head` + `python -m app.seed` |
| Lỗi connect database dù đã dùng SQLite | File `.env` đang trỏ Postgres — đổi `SUPABASE_DB_URL=sqlite:///./ql_daotao.db` |

---

## Cấu trúc thư mục

```
backend/
  app/
    core/          config, security (JWT + bcrypt), database
    models/        SQLAlchemy 2.x (user, person, academic)
    schemas/       Pydantic v2
    routers/       auth, majors, students, lecturers, homeroom_classes,
                   courses, course_classes, enrollments, schedule, grades,
                   stats, ai
    services/      enrollment, grade, user, course, ai, llm, prompts, rag_service
    dependencies/  auth_dependency (get_current_user, require_role, get_target_student)
    seed.py        dữ liệu demo idempotent
  alembic/         migrations
  src/rag/         pipeline RAG chatbot quy chế (LCEL + retriever MMR)
  src/ingestion/   build vector store từ DOCX
  vectorstore/     ChromaDB dựng sẵn (đã commit vào repo)
  tests/           pytest backend
  scripts/         smoke test end-to-end qua HTTP
frontend/
  src/
    pages/         dashboard + trang theo vai trò (student, lecturer, advisor, office)
    components/    ui + domain (GradeTable, EnrollmentCard...)
    api/           axios client
  vite.config.js   proxy /api → localhost:8000 khi dev
```

---

## Ghi chú sai lệch so với đặc tả

1. **Liên kết User ↔ Student/Lecturer**: dùng 2 FK nullable unique trên bảng `users` (`student_id`, `lecturer_id`); kiểm tra sở hữu so sánh giá trị trong JWT.
2. **Bảng `users`** thay vì `user` (từ khóa dành riêng của PostgreSQL).
3. **Grade.updated_by → users.id** (không phải lecturer.id) vì phòng đào tạo cũng ghi điểm.
4. Lịch học lưu `JSON`: `[{"weekday": 2..8, "start_period", "end_period", "room"}]`; trùng lịch = cùng weekday + giao khoảng tiết, chỉ xét trong cùng (year, term).
5. Chưa triển khai DELETE sinh viên / lớp / học phần (tránh orphan dữ liệu điểm / đăng ký).
6. Một số endpoint thêm ngoài đặc tả để đủ UI: `GET /course-classes/{id}/enrollments`, `GET /homeroom-classes/mine`, `PATCH /course-classes/{id}`, `GET /students/{id}`, `GET /schedule/student/{id}?year=&term=`.
