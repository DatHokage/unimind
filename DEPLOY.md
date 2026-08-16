# Định hướng & kế hoạch triển khai (Deployment)

Bối cảnh: không có GPU/server mạnh, chỉ có máy tính thường — ưu tiên **dịch vụ free tier / chi phí thấp**, tránh tự host LLM hay vector DB nặng.

> Tài liệu đã được rà soát và **khớp với code thực tế của dự án** (2026-08-16, chốt backend: **Render**).
> Quy trình deploy từng bước: mục **"Deploy"** trong [`README.md`](README.md).

---

## 1. Tổng quan kiến trúc triển khai

```
┌─────────────┐      HTTPS       ┌──────────────┐      SQL        ┌───────────────┐
│   React     │ ───────────────▶ │   FastAPI    │ ───────────────▶│   Supabase    │
│  (Vercel)   │                  │  (Render)    │                  │  (PostgreSQL) │
│             │ ◀─────────────── │              │ ◀─────────────── │               │
└─────────────┘      JSON        └──────┬───────┘      SQL        └───────────────┘
                                          │
                                          │ HTTPS (API call)
                                          ▼
                                  ┌────────────────────────────┐
                                  │  OpenRouter (model :free)  │ ← chính
                                  │  Gemini free tier          │ ← fallback
                                  └────────────────────────────┘
                                  (Chatbot quy chế RAG: ChromaDB + embedding
                                   tiếng Việt chạy LOCAL ngay trong backend,
                                   không tốn API — xem mục 5)
```

4 thành phần độc lập, mỗi thành phần deploy ở dịch vụ phù hợp nhất với đặc tính của nó — không cần tự quản lý server vật lý nào.

---

## 2. Backend (FastAPI) — Render

**Chốt: Render** (lựa chọn cuối cùng).

> **Đánh đổi cần biết (free tier):** server **ngủ sau ~15 phút không dùng** — request đầu mất ~30–60s để đánh thức. Khắc phục: **gọi `/health` trước buổi demo 5–10 phút** để làm ấm server; hoặc nâng instance trả phí (~$7/tháng) nếu muốn chạy 24/7 lúc bảo vệ. RAM free tier **512MB** — đủ chạy nhưng theo dõi log nếu bị OOM khi warm-up RAG (khi đó nâng instance nhỏ).

**Cấu hình đã chuẩn bị sẵn trong repo:**

| File | Nội dung |
|---|---|
| `backend/requirements.txt` | Đầy đủ dependency, gồm cả stack RAG (langchain, chromadb, sentence-transformers, psycopg2-binary...) |
| `backend/Procfile` | `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `backend/runtime.txt` | `python-3.12` (Render đọc file này để chọn phiên bản Python) |
| `backend/alembic/env.py` | Đọc connection string từ biến môi trường — chạy được trên Render không cần sửa |
| `backend/app/seed.py` | Seed idempotent — chạy lại mỗi lần deploy không sinh dữ liệu trùng |
| `backend/src/ingestion/build_index.py` | Hỗ trợ biến `SKIP_INDEX_BUILD_IF_NO_DOCS=1` — dùng trong build để bake embedding model vào image (xem bên dưới) |

**Thiết lập trên Render dashboard (New → Web Service, chọn repo GitHub):**
- Region: **Singapore** (gần VN nhất)
- Root Directory: `backend`
- Build Command:
  ```
  pip install -r requirements.txt && python -m src.ingestion.build_index && alembic upgrade head && python -m app.seed
  ```
  - `build_index` với `SKIP_INDEX_BUILD_IF_NO_DOCS=1`: không có DOCX trong repo thì **chỉ tải embedding model vào cache** (bake vào image deploy) — service khởi động lại/scale ra không phải tải lại ~500MB từ mạng.
  - `alembic upgrade head && python -m app.seed`: migration + seed ngay trong build, mỗi lần deploy schema luôn được cập nhật (seed idempotent).
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (hoặc để trống cho Render tự đọc Procfile)
- Instance Type: **Free** (đủ demo)

**Biến môi trường** (tên biến thật — khai báo trong `app/core/config.py`, mẫu ở `backend/.env.example`):

| Biến | Ý nghĩa |
|---|---|
| `SUPABASE_DB_URL` | Connection string Supabase — **cổng 5432 direct**, không dùng pooler 6543 |
| `SECRET_KEY` | Chuỗi ngẫu nhiên ≥ 32 ký tự (ký JWT) |
| `OPENROUTER_API_KEY` | Key OpenRouter — bật AI tư vấn, tóm tắt học tập + chatbot quy chế |
| `OPENROUTER_MODEL` | Mặc định `nvidia/nemotron-3-super-120b-a12b:free` (không đặt cũng được) |
| `GOOGLE_API_KEY` | Key Gemini — fallback khi OpenRouter lỗi/hết quota (đặt được thì càng tốt) |
| `GEMINI_MODEL` | Mặc định `gemini-2.0-flash` |
| `CORS_ORIGINS` | Danh sách origin được phép, phân tách bằng dấu phẩy — **bắt buộc có domain Vercel** |
| `PASS_THRESHOLD` | Ngưỡng qua môn, mặc định 5.0 |
| `SKIP_INDEX_BUILD_IF_NO_DOCS` | `1` — cho bước `build_index` trong Build Command chạy êm khi repo không có file DOCX gốc |

> ⚠️ Các tên `LLM_API_KEY` / `LLM_API_URL` trong bản kế hoạch cũ **không tồn tại trong code** — dùng đúng bảng trên.

**CORS — đã sửa trong code:** `main.py` trước đây hardcode `allow_origins=["http://localhost:5173"]`, nay đọc từ biến `CORS_ORIGINS` (mặc định vẫn là localhost:5173 cho dev). Khi deploy phải điền domain Vercel thật, ví dụ:
```
CORS_ORIGINS=http://localhost:5173,https://unimind.vercel.app
```

**Lưu ý về stack RAG trên Render (quan trọng):**
- Backend chạy **embedding model tiếng Việt local** (`bkai-foundation-models/vietnamese-bi-encoder`, ~500MB) qua sentence-transformers. Render free tier **không có volume** và mỗi lần deploy tạo container mới → mặc định sẽ phải tải lại model mỗi lần deploy.
- Cách khắc phục (đã làm sẵn): bước `python -m src.ingestion.build_index` trong Build Command tải model **vào cache ngay lúc build**, cache được đóng gói vào image deploy → lúc chạy không phải tải lại.
- Chatbot tự warm-up (tải ChromaDB + embedding + LLM) ở thread nền khi server start (`RAG_WARMUP=1` mặc định) — sau khi server thức dậy, câu hỏi đầu tiên không phải chờ.
- **Trước buổi demo:** mở `https://<name>.onrender.com/health` (hoặc vào `/docs`) trước 5–10 phút để server thức + warm-up xong.

---

## 3. Frontend (React) — Vercel

**Đề xuất:** Vercel — đã có kinh nghiệm deploy Vercel từ dự án quiz (team "DatHokage's projects"), tái sử dụng được quy trình quen thuộc.

**Thiết lập trên Vercel:**
1. Import repo GitHub → **Root Directory: `frontend`** (framework Vite tự nhận).
2. Biến môi trường:
   ```
   VITE_API_BASE_URL=https://<backend-name>.onrender.com
   ```
   **Đã hỗ trợ trong code** (`frontend/src/api/client.js`): đọc `import.meta.env.VITE_API_BASE_URL`, để trống thì dùng `/api` (chế độ dev qua vite proxy). Không cần file `.env` khi deploy — đặt trực tiếp trên Vercel dashboard.
3. SPA rewrite: đã có `frontend/vercel.json` (rewrite mọi đường dẫn về `index.html` cho BrowserRouter).
4. Domain `*.vercel.app` miễn phí — đủ dùng cho demo đồ án.

**Lưu ý CORS (quy trình 2 chiều):** deploy frontend trước để có domain Vercel → quay lại Render điền domain đó vào `CORS_ORIGINS` → redeploy backend. Nếu quên, frontend gọi API sẽ bị trình duyệt chặn (lỗi CORS trong console).

---

## 4. Database (Supabase — PostgreSQL)

**Đã chốt dùng Supabase** — lý do phù hợp:
- Free tier đủ dùng cho quy mô đồ án (500MB storage, đủ cho dữ liệu sinh viên/điểm/học phần).
- Connection string PostgreSQL chuẩn, dùng thẳng với SQLAlchemy — code đã chạy đúng không cần đổi (`app/core/database.py` đọc `SUPABASE_DB_URL`).
- Dashboard quản lý dữ liệu trực quan (table editor), tiện khi cần xem/sửa dữ liệu nhanh lúc demo hoặc debug.
- Migration đầy đủ trong `backend/alembic/versions/` (3 bản: schema gốc, index tên sinh viên, cột chuyển đổi điểm) — chạy `alembic upgrade head` là đủ bảng.

**Việc cần làm:**
1. Tạo project trên Supabase → copy connection string **direct cổng 5432** (không dùng pooler cổng 6543).
2. Đặt vào biến môi trường `SUPABASE_DB_URL` của backend trên Render. Format chuẩn:
   `postgresql+psycopg2://postgres.<project-ref>:<password>@db.<project-ref>.supabase.co:5432/postgres?sslmode=require`
   - Nếu lỡ dán dạng cũ `postgres://...` hoặc thiếu driver `postgresql://...`, code
     (`app/core/config.py` → `normalize_db_url`) tự chuẩn hóa về `postgresql+psycopg2://` — không cần sửa tay.
   - Lỗi `NoSuchModuleError: sqlalchemy.dialects:postgresql.postgresql` nghĩa là URL
     bị gõ nhầm thành `postgresql+postgresql://...` (lặp dialect) — sửa lại biến
     `SUPABASE_DB_URL` trên Render Dashboard → Environment.
3. Migration + seed chạy tự động qua Build Command (mục 2).
4. Row Level Security (RLS): **không bắt buộc** — hệ thống tự kiểm soát quyền ở tầng FastAPI (JWT + `require_role`); có thể bật thêm như lớp bảo vệ phụ nếu có thời gian.

---

## 5. AI / RAG — hiện trạng thực tế (khác bản kế hoạch cũ)

### 5.1. LLM: OpenRouter chính + Gemini fallback

Bản kế hoạch cũ đề xuất "Gemini chính / Groq dự phòng". **Code thực tế đã chốt hướng khác** và hoạt động ổn định:

- **OpenRouter (chính)** — 1 key dùng được cho cả 3 chức năng (tư vấn đăng ký, tóm tắt học tập, chatbot quy chế); registry `src/rag/models.py` tự lấy danh sách model `:free` mới nhất từ API công khai OpenRouter (cache 1h), model lỗi tự fallback sang model khác trong danh sách.
- **Gemini (fallback)** — code tự chuyển sang Gemini khi OpenRouter lỗi/hết quota (`app/services/llm_service.py`); key đặt ở `GOOGLE_API_KEY`.
- **Không dùng Groq** — không cần thêm tài khoản/key thứ 3, hướng OpenRouter→Gemini đã đủ độ dự phòng cho demo.
- Không có key nào: AI tư vấn/tóm tắt vẫn trả fallback server-side (không chết API), chatbot quy chế trả 503 với thông báo rõ ràng.

### 5.2. Vector store cho RAG: đã nhúng thẳng vào backend

Hai "Hướng A/B" trong bản kế hoạch cũ (deploy service RAG riêng / gộp vào pgvector) **đều không còn phải cân nhắc** — dự án đã triển khai xong theo cách gọn nhất:

- Pipeline RAG (từ dự án `rag_langchain`) **nằm ngay trong backend chính**: `app/services/rag_service.py` nối FastAPI → `src/rag/` (chain LCEL + retriever MMR). Không có service thứ hai, không HTTP nội bộ.
- **ChromaDB persist** trong `backend/vectorstore/` — **đã commit vào git** (~11MB, gồm `chroma.sqlite3` + HNSW index). Deploy từ GitHub là có sẵn, không cần build lại.
- **Embedding chạy local 100%** (vietnamese-bi-encoder qua sentence-transformers) — retrieval không tốn API key, chỉ LLM mới gọi OpenRouter/Gemini.
- Endpoint `POST /ai/regulation-chat` trả `answer` + `sources` (Điều/Khoản/trang) + `provider`/`model`; ngữ cảnh hội thoại giữ server-side theo `session_id`.

> Nếu sau này muốn "gọn kiến trúc" cho báo cáo/slide: phương án pgvector trên Supabase vẫn để ngỏ nhưng **không cần làm** — cách hiện tại đã 0đ và chạy ổn định.

**Cập nhật quy chế mới (quy trình chuẩn):** đặt DOCX vào `backend/data/raw/` → chạy `python -m src.ingestion.build_index` ở máy local → commit thư mục `backend/vectorstore/` → push, Render tự redeploy với index mới. (Tài liệu gốc DOCX/PDF không nằm trong repo — chỉ có index đã build.)

---

## 6. Tóm tắt domain/dịch vụ sử dụng

| Thành phần | Dịch vụ | Chi phí |
|---|---|---|
| Frontend | Vercel | Free |
| Backend | Render (free tier) | 0đ — nếu cần chạy 24/7 lúc bảo vệ thì nâng instance trả phí (~$7/tháng) |
| Database | Supabase | Free tier |
| LLM | OpenRouter model `:free` (chính) / Gemini free (fallback) | Free tier |
| Vector store (RAG) | ChromaDB trong repo + embedding local trong container backend | Free |

**Tổng chi phí dự kiến: 0đ** trong phạm vi free tier — phù hợp quy mô đồ án, không cần đầu tư server riêng.

---

## 7. Các thay đổi code đã thực hiện để sẵn sàng deploy (2026-08-16)

| Thay đổi | File | Lý do |
|---|---|---|
| CORS đọc từ biến môi trường `CORS_ORIGINS` (mặc định localhost:5173) | `backend/app/core/config.py`, `backend/app/main.py` | Trước đó hardcode localhost → Vercel gọi API sẽ bị chặn |
| Frontend đọc `VITE_API_BASE_URL` (fallback `/api` cho dev) | `frontend/src/api/client.js`, `frontend/.env.example` | Trước đó hardcode `/api` → không gọi được backend khác domain |
| Commit `backend/vectorstore/chroma.sqlite3` + rule giữ trong `.gitignore` | `.gitignore` | Rule `*.sqlite3` từng bỏ sót file lõi của ChromaDB → deploy lên chatbot sẽ chết |
| Procfile + `runtime.txt` cho Render | `backend/Procfile`, `backend/runtime.txt` | Lệnh start + phiên bản Python 3.12 chuẩn khi Render build |
| `build_index.py` hỗ trợ `SKIP_INDEX_BUILD_IF_NO_DOCS` | `backend/src/ingestion/build_index.py` | Cho Build Command trên Render bake embedding model vào image mà không lỗi khi thiếu DOCX |
| `vercel.json` rewrite SPA | `frontend/vercel.json` | BrowserRouter cần rewrite mọi route về `index.html` |
| Runbook deploy từng bước | `README.md` mục "Deploy" | Quy trình thao tác cho cả 3 dịch vụ |
| Thêm `CORS_ORIGINS` vào `.env.example` | `backend/.env.example` | Đồng bộ biến mới |

---

## 8. Checklist trước khi demo/bảo vệ đồ án

**Hạ tầng**
- [ ] `git ls-files backend/vectorstore` có `chroma.sqlite3` (nếu không, chatbot chết khi deploy).
- [ ] Build Command trên Render đủ 4 bước: `pip install` → `build_index` (với `SKIP_INDEX_BUILD_IF_NO_DOCS=1`) → `alembic upgrade head` → `python -m app.seed`.
- [ ] **Làm ấm trước giờ demo:** mở `/health` (hoặc `/docs`) trước 5–10 phút — free tier ngủ sau 15 phút không dùng.
- [ ] Nếu bị OOM khi warm-up RAG (log Render báo killed): nâng instance type nhỏ trả phí.

**Cấu hình**
- [ ] `CORS_ORIGINS` trên Render chứa **đúng** domain Vercel (và localhost nếu vẫn muốn dev).
- [ ] `VITE_API_BASE_URL` đã đặt trên Vercel và đã redeploy sau khi đặt.
- [ ] Secrets (`SECRET_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `SUPABASE_DB_URL`) không nằm trong git — chỉ trong `.env` local + dashboard Render/Vercel.

**Dữ liệu & chức năng**
- [ ] Chạy `scripts/smoke.py` với `SMOKE_BASE=https://<name>.onrender.com` trước ngày demo.
- [ ] Tài khoản demo đủ 4 vai trò (`student1`, `lecturer1`, `advisor1`, `ptdt` — mật khẩu `password123`) — seed chạy tự động khi deploy.
- [ ] Test rate limit model `:free` của OpenRouter — nếu bị 429, code tự fallback model khác/Gemini; kiểm tra trước là chat vẫn trả lời khi nhiều người thử cùng lúc.
- [ ] Chat quy chế trả về `sources` có Điều/Khoản/trang (vectorstore còn nguyên sau khi deploy).
