# Hệ thống Quản lý Đào tạo tích hợp AI

Hệ thống quản lý đào tạo cho cơ sở giáo dục: quản lý sinh viên, giảng viên, học phần, lớp học, đăng ký học phần, nhập điểm và thống kê kết quả học tập — tích hợp AI tư vấn đăng ký môn học, tóm tắt kết quả học tập và chatbot hỏi-đáp quy chế đào tạo (RAG).

**Stack:** FastAPI (Python 3.12) · React + Vite · SQLite (chạy local) hoặc PostgreSQL/Supabase (deploy) · JWT · LLM qua OpenRouter (fallback Gemini) · Chatbot quy chế: ChromaDB + embedding qua Voyage AI API (không tải model local, chạy được cả trên Render free tier 512MB).

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

> `requirements.txt` gồm các thư viện cốt lõi (fastapi, sqlalchemy, httpx, chromadb, python-docx) — không có torch/sentence-transformers/langchain nên cài nhanh, máy nhẹ. **Chatbot quy chế** chạy bằng embedding gọi qua **Voyage AI API** (không tải model local), chỉ cần điền `VOYAGE_API_KEY` + 1 key LLM (`OPENROUTER_API_KEY` hoặc `GOOGLE_API_KEY`) trong `backend/.env` là dùng được.

### Bước 2 — Tạo file cấu hình `.env`

```powershell
copy .env.example .env
```

Mở `backend/.env` kiểm tra dòng database đang là SQLite (file `.env.example` đã để sẵn):

```env
SUPABASE_DB_URL=sqlite:///./ql_daotao.db
```

- Chạy thử ở máy mình: **giữ nguyên** dòng trên là đủ.
- Muốn bật **chatbot quy chế**: điền `VOYAGE_API_KEY` ([dash.voyageai.com](https://dash.voyageai.com/)) — key này **bắt buộc** vì embedding câu hỏi gọi qua Voyage AI API; thêm `OPENROUTER_API_KEY` ([openrouter.ai/keys](https://openrouter.ai/keys)) để có LLM trả lời (`GOOGLE_API_KEY` là dự phòng).
- Muốn bật AI tư vấn đăng ký + tóm tắt học tập: chỉ cần điền `GOOGLE_API_KEY` ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) — Gemini là LLM chính của 2 chức năng này; `OPENROUTER_API_KEY` là dự phòng — Gemini lỗi/bị lọc an toàn thì hệ thống tự chuyển sang OpenRouter. **Không có key nào thì mọi chức năng quản lý vẫn chạy**, chỉ có AI trả fallback.
- `SECRET_KEY`: nên đổi thành chuỗi ngẫu nhiên dài (bắt buộc khi deploy).

### Bước 3 — Tạo bảng + nạp dữ liệu mẫu + chạy backend

```powershell
alembic upgrade head     # tạo cấu trúc bảng
python -m app.seed       # nạp dữ liệu demo (tài khoản, học phần, điểm mẫu)
uvicorn app.main:app --reload
```

Backend chạy tại **http://localhost:8000** — xem danh sách API tại http://localhost:8000/docs.

> Chatbot quy chế **không tải model nào khi khởi động** — vector store đã dựng sẵn trong `backend/vectorstore/`, embedding câu hỏi gọi qua Voyage AI API lúc hỏi. Biến môi trường `RAG_WARMUP=0` nếu muốn tắt bước mở sẵn ChromaDB khi server chạy lên.

### Bước 4 — Chạy frontend (mở một cửa sổ terminal **mới**)

```powershell
cd frontend
npm install
npm run dev
```

Mở **http://localhost:5173**, đăng nhập `DTC001` / `password123` và dùng thử. (Frontend dev tự proxy `/api` sang backend port 8000 — đã cấu hình sẵn, không cần làm gì thêm.)

### Đặt lại dữ liệu về trạng thái demo ban đầu

Xóa file database rồi chạy lại Bước 3:

```powershell
del ql_daotao.db
alembic upgrade head
python -m app.seed
```

---

## Tài khoản demo

Sau khi seed, mật khẩu chung cho tất cả tài khoản là `password123`. **Tên đăng nhập chính là mã** của người dùng và **không phân biệt hoa/thường** (gõ `dtc001` vẫn đăng nhập được):

| Username | Vai trò | Ghi chú dữ liệu |
|---|---|---|
| `DTCAD001` | Admin (quản trị hệ thống) | quyền phòng đào tạo + quản trị |
| `ptdt` | Phòng đào tạo | nhập điểm thi, CRUD, thống kê |
| `DTCGV001` | Giảng viên Nguyễn Văn An | dạy TH1.A, CTDL.A, OOP.A |
| `DTCGV002` | Giảng viên Trần Thị Bình | dạy CTDL.B, OOP.B |
| `DTCCV001` | Cố vấn Ngô Thị Lan | phụ trách CNTT1-K12 + CNTT2-K12 |
| `DTC001` | Sinh viên Phạm Văn Nhất | đã đạt TH1 (7.5) → đăng ký được CTDL/CSDL |
| `DTC002` | Sinh viên Lê Thị Nhị | TH1 4.0 (< 5.0) → demo chặn tiên quyết |
| `DTC003` | Sinh viên Hoàng Văn Tam | đạt TH1 (6.0), đang học CSDL.A |
| `DTC004` | Sinh viên Đỗ Thị Tư | lớp CNTT2-K12, dữ liệu đủ 3 học kỳ: môn đạt B/C, môn trượt F, môn đang học, HP không tính GPA (GDTC1) |
| `DTC005`..`DTC015` | Sinh viên DTC005..DTC015 | dữ liệu phân trang/tìm kiếm danh sách sinh viên |

**Kịch bản demo nhanh**

1. `DTC001` → *Đăng ký học phần*: bấm AI tư vấn → AI gợi ý CTDL/CSDL/GDTC1 kèm lý do; đăng ký CTDL.A thành công.
2. `DTC002` đăng ký CTDL.A → bị chặn *"chưa hoàn thành học phần tiên quyết"*.
3. `DTC001` đăng ký CSDL.A → *"lớp đã đầy"*; đăng ký OOP.A → trùng lịch / chưa đạt tiên quyết.
4. `DTCGV001` nhập điểm quá trình OK; gọi endpoint nhập điểm thi → **403** (chỉ phòng đào tạo được nhập điểm thi).
5. `ptdt` nhập điểm thi → điểm tổng kết + điểm chữ + hệ 4 tự tính; gọi endpoint nhập điểm quá trình → **403**.
6. `DTCCV001` xem đúng 2 lớp phụ trách → mở một sinh viên thấy bảng điểm + bấm *"Tạo nhận xét"* để AI nhận xét.
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

> Cần `VOYAGE_API_KEY` trong `backend/.env` (bắt buộc — embedding gọi qua Voyage AI API) + 1 key LLM (`OPENROUTER_API_KEY` chính, hoặc `GOOGLE_API_KEY` dự phòng). Không có key thì endpoint trả 503 kèm hướng dẫn, các chức năng khác không ảnh hưởng.

- Vector store dựng sẵn từ **Sổ tay sinh viên 2024–2025** nằm trong `backend/vectorstore/` (đã commit, clone về là có). Câu hỏi được nhúng bằng **Voyage AI API** (`voyage-4`, `input_type="query"`) — **không tải model local** nên chạy được cả trên Render free tier 512MB; chỉ bước trả lời mới gọi LLM (OpenRouter, fallback Gemini).
- Câu hỏi **ngoài quy chế** (không chunk nào khớp) → chatbot trả "không tìm thấy thông tin trong quy chế" và **không gọi LLM** — không bịa câu trả lời.
- Endpoint `POST /ai/regulation-chat` trả `answer` + `sources` (Điều / Khoản / trang) + `provider` + `model`; ngữ cảnh hội thoại giữ theo `session_id`.
- **Cập nhật quy chế mới:** đặt file DOCX vào `backend/data/raw/` → chạy `python scripts/rebuild_vector_store.py` → commit + push thư mục `backend/vectorstore/`. Script nhúng toàn bộ chunk qua Voyage API (`input_type="document"`) rồi mới xóa index cũ (lỗi giữa chừng thì vector store cũ vẫn còn nguyên). Đổi `VOYAGE_MODEL` cũng phải rebuild — mỗi model là một không gian vector riêng.
- Thử retrieval: `python -m src.rag.retriever "cau hoi"` (cần `VOYAGE_API_KEY` để nhúng câu hỏi).

---

## Deploy (Vercel + Render + Supabase)

Khi đưa lên mạng: **Vercel** (frontend) + **Render** (backend) + **Supabase** (Postgres). Toàn bộ thiết lập chi tiết (từng bước trên dashboard, biến môi trường, lưu ý free tier, checklist trước ngày bảo vệ) ở [`DEPLOY.md`](DEPLOY.md). Tóm tắt:

1. **Supabase**: tạo project → Settings → Database → Connection Pooling → copy connection string của **Session Pooler** (host `aws-0-<region>.pooler.supabase.com`, port **5432**, user `postgres.<project-ref>`). KHÔNG dùng direct connection `db.<ref>.supabase.co` — host đó chỉ có IPv6 ở nhiều region, Render free tier không nối được.
2. **Render**: New Web Service, Root Directory `backend`, Build Command:
   `pip install -r requirements.txt && alembic upgrade head && python -m app.seed`
   (chatbot quy chế chạy được trên Render free 512MB vì embedding gọi qua Voyage AI API, không tải model local — cần điền `VOYAGE_API_KEY` + `OPENROUTER_API_KEY` ở tab Environment; chi tiết ở DEPLOY.md mục 2).
3. **Vercel**: import repo, Root Directory `frontend`, biến `VITE_API_BASE_URL=https://<ten>.onrender.com`.
4. Quay lại Render điền `CORS_ORIGINS=https://<domain>.vercel.app` rồi redeploy.

> ⚠️ Free tier Render ngủ sau 15 phút không dùng — **mở `/health` trước buổi demo 5–10 phút** để làm ấm server.

---

## Lỗi thường gặp

| Triệu chứng | Nguyên nhân / cách xử lý |
|---|---|
| `uvicorn: command not found` | Chưa activate venv — chạy lại `.venv\Scripts\activate` |
| `address already in use` khi chạy uvicorn | Port 8000 bị chiếm — tắt chương trình khác hoặc chạy `uvicorn app.main:app --port 8001 --reload` |
| `pip install` rất lâu | Ít gặp — `requirements.txt` không có torch/sentence-transformers; nếu chậm thường do mạng, thử `pip install -r requirements.txt -i https://pypi.org/simple` |
| Frontend báo lỗi CORS / không gọi được API | Backend chưa chạy, hoặc chạy không đúng port 8000 |
| Chat quy chế trả 503 | Chưa điền `VOYAGE_API_KEY` (bắt buộc cho embedding) trong `backend/.env`, hoặc chưa rebuild vector store sau khi đổi `VOYAGE_MODEL` (retriever tự phát hiện lệch model và chặn kèm hướng dẫn) |
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
    services/      enrollment, grade, user, course, ai, llm, embedding, prompts, rag_service
    dependencies/  auth_dependency (get_current_user, require_role, get_target_student)
    seed.py        dữ liệu demo idempotent
  alembic/         migrations
  src/rag/         pipeline RAG chatbot quy chế (ChromaDB explicit-vector + prompt + LLM)
  src/ingestion/   parse + chunk DOCX khi rebuild vector store
  vectorstore/     ChromaDB dựng sẵn (index cũ nhúng Gemini — phải rebuild bằng Voyage voyage-4 trước khi dùng chatbot)
  tests/           pytest backend
  scripts/         smoke test end-to-end, rebuild_vector_store.py, đo RAM
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
