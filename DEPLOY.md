# Định hướng & kế hoạch triển khai (Deployment)

Bối cảnh: không có GPU/server mạnh, chỉ có máy tính thường — ưu tiên **dịch vụ free tier / chi phí thấp**, tránh tự host LLM hay vector DB nặng.

> Tài liệu đã được rà soát và **khớp với code thực tế của dự án** (2026-08-17, chốt backend: **Render**; RAG chuyển sang embedding qua Voyage AI API — chạy được trên free tier 512MB).
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
                                  │  OpenRouter (model :free)  │ ← LLM chính
                                  │  Gemini free tier          │ ← LLM dự phòng
                                  └────────────────────────────┘
                                  (Chatbot quy chế RAG: ChromaDB vector store
                                   dựng sẵn trong repo + embedding câu hỏi
                                   qua Voyage AI API, không tải model local —
                                   xem mục 5)
```

4 thành phần độc lập, mỗi thành phần deploy ở dịch vụ phù hợp nhất với đặc tính của nó — không cần tự quản lý server vật lý nào.

---

## 2. Backend (FastAPI) — Render

**Chốt: Render** (lựa chọn cuối cùng).

> **Đánh đổi cần biết (free tier):** server **ngủ sau ~15 phút không dùng** — request đầu mất ~30–60s để đánh thức. Khắc phục: **gọi `/health` trước buổi demo 5–10 phút** để làm ấm server; hoặc nâng instance trả phí (~$7/tháng) nếu muốn chạy 24/7 lúc bảo vệ. RAM free tier **512MB** — đã đo pipeline RAG thực tế chỉ tốn ~126MB RSS (đo bằng `python scripts/measure_rag_ram.py`: import app 78MB → mở ChromaDB 109MB → query 126MB), nên **không còn kịch bản OOM khi warm-up RAG** như thời embedding local.

**Cấu hình đã chuẩn bị sẵn trong repo:**

| File | Nội dung |
|---|---|
| `backend/requirements.txt` | Toàn bộ dependency của backend (fastapi, sqlalchemy, httpx, psycopg2-binary, chromadb, python-docx...) — KHÔNG có torch/sentence-transformers/langchain nên cài vừa máy 512MB |
| `backend/Procfile` | `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| `backend/runtime.txt` | `python-3.12` (Render đọc file này để chọn phiên bản Python) |
| `backend/alembic/env.py` | Đọc connection string từ biến môi trường — chạy được trên Render không cần sửa |
| `backend/app/seed.py` | Seed idempotent — chạy lại mỗi lần deploy không sinh dữ liệu trùng |
| `backend/src/ingestion/build_index.py` | Shim chuyển hướng sang `scripts/rebuild_vector_store.py` — dựng lại vector store từ DOCX, **chỉ chạy local** khi cập nhật quy chế, KHÔNG nằm trong Build Command của Render |

**Thiết lập trên Render dashboard (New → Web Service, chọn repo GitHub):**
- Region: **Singapore** (gần VN nhất)
- Root Directory: `backend`
- Build Command:
  ```
  pip install -r requirements.txt && alembic upgrade head && python -m app.seed
  ```
  - `pip install -r requirements.txt`: cài toàn bộ dependency (không có torch/sentence-transformers — embedding chuyển sang gọi Voyage API nên stack gọn lại, chromadb chỉ lưu/tra vector).
  - `alembic upgrade head && python -m app.seed`: migration + seed ngay trong build, mỗi lần deploy schema luôn được cập nhật (seed idempotent). Chạy được là nhờ `SUPABASE_DB_URL` trỏ **Session Pooler** (xem mục 4) — host direct không dùng được vì chỉ có IPv6.
  - KHÔNG có bước rebuild vector store — vectorstore dựng sẵn (nhúng bằng Voyage `voyage-4`) và commit trong repo (`backend/vectorstore/`).
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (hoặc để trống cho Render tự đọc Procfile)
- Instance Type: **Free** (đủ demo)

**Biến môi trường** (tên biến thật — khai báo trong `app/core/config.py`, mẫu ở `backend/.env.example`):

| Biến | Ý nghĩa |
|---|---|
| `SUPABASE_DB_URL` | Connection string Supabase — **Session Pooler** `aws-0-<region>.pooler.supabase.com:5432` (user `postgres.<project-ref>`, có IPv4); KHÔNG dùng direct `db.<ref>.supabase.co` (chỉ IPv6 → Render không nối được). Chi tiết ở mục 4. |
| `SECRET_KEY` | Chuỗi ngẫu nhiên ≥ 32 ký tự (ký JWT) |
| `VOYAGE_API_KEY` | Key Voyage AI — **BẮT BUỘC** cho chatbot quy chế: embedding duy nhất (nhúng câu hỏi + nhúng chunk khi rebuild vector store). Voyage chỉ tạo vector, KHÔNG sinh câu trả lời |
| `VOYAGE_MODEL` | Model embedding, mặc định `voyage-4` (không đặt cũng được). **Đổi model này là phải rebuild vector store** (`python scripts/rebuild_vector_store.py`) — mỗi model là một không gian vector riêng |
| `OPENROUTER_API_KEY` | Key OpenRouter — **LLM chính của chatbot quy chế** (bắt buộc cho chatbot; Gemini bên dưới là dự phòng) |
| `OPENROUTER_MODEL` | Mặc định `nvidia/nemotron-3-super-120b-a12b:free` (không đặt cũng được) |
| `GOOGLE_API_KEY` | Key Gemini — vẫn **BẮT BUỘC**: LLM chính của 2 chức năng AI dạng JSON (tư vấn đăng ký, tóm tắt học tập) + **dự phòng** cho chatbot quy chế khi OpenRouter lỗi/rate-limit |
| `GEMINI_MODEL` | Mặc định `gemini-2.0-flash` |
| `CORS_ORIGINS` | Danh sách origin được phép, phân tách bằng dấu phẩy — **bắt buộc có domain Vercel** |
| `PASS_THRESHOLD` | Ngưỡng qua môn, mặc định 5.0 |

> ⚠️ Biến `SKIP_INDEX_BUILD_IF_NO_DOCS` không còn cần — bước `build_index` đã bỏ khỏi Build Command (vectorstore dựng sẵn + commit trong repo, không build lại khi deploy).

> ⚠️ Các tên `LLM_API_KEY` / `LLM_API_URL` trong bản kế hoạch cũ **không tồn tại trong code** — dùng đúng bảng trên.

**CORS — đã sửa trong code:** `main.py` trước đây hardcode `allow_origins=["http://localhost:5173"]`, nay đọc từ biến `CORS_ORIGINS` (mặc định vẫn là localhost:5173 cho dev). Khi deploy phải điền domain Vercel thật, ví dụ:
```
CORS_ORIGINS=http://localhost:5173,https://unimind.vercel.app
```

**Lưu ý về stack RAG / chatbot quy chế trên Render (cập nhật sau khi chuyển embedding sang Voyage AI API):**
- Chatbot quy chế **chạy được trên Render free tier 512MB**: embedding câu hỏi gọi qua Voyage AI API (`app/services/embedding_service.py`), **không tải model local** nữa (đã bỏ hẳn torch/sentence-transformers/langchain khỏi dependency). RAM thực đo bằng `python scripts/measure_rag_ram.py`: import app ~78MB → mở ChromaDB ~109MB → sau query ~126MB — thoải mái dưới 512MB.
- chromadb vẫn là dependency bắt buộc nhưng code luôn truyền vector tường minh (`collection.add(embeddings=...)` / `collection.query(query_embeddings=...)`), không bao giờ để Chroma tự nhúng văn bản → onnxruntime (dependency kéo theo) không bao giờ được tải vào RAM.
- Trả 503 chỉ khi **chưa điền `VOYAGE_API_KEY`** (hoặc thiếu cả 2 key LLM) trong Environment (thông báo hướng dẫn cấu hình rõ ràng). App vẫn chạy; mọi chức năng khác không ảnh hưởng.
- **Trước buổi demo:** mở `https://<name>.onrender.com/` trước 5–10 phút để server thức (free tier ngủ sau 15 phút không dùng).

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
1. Tạo project trên Supabase → mở **Settings → Database → Connection Pooling**, copy connection string của **Session Pooler** (port **5432**).
2. Đặt vào biến môi trường `SUPABASE_DB_URL` của backend trên Render. Format chuẩn:
   `postgresql+psycopg2://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require`
   (region của project ví dụ `ap-southeast-1` = Singapore; `<password>` thay bằng database password thật).
   - **KHÔNG dùng direct connection** (`db.<project-ref>.supabase.co:5432`, đuôi `.co`): host này
     ở nhiều region **chỉ trả địa chỉ IPv6** → Render free tier không route được IPv6 →
     lỗi `Network is unreachable` khi alembic/app nối DB (đã gặp ngày 2026-08-16).
   - **Transaction Pooler** (port 6543) cũng không dùng cho dự án này — nó reset state
     giữa các kết nối (prepared statement/listen-notify), trong khi Session Pooler (cũng host pooler
     nhưng port 5432, có IPv4) hoạt động trong suốt với SQLAlchemy, dùng được cho cả alembic lẫn app.
   - Username khi qua pooler bắt buộc là `postgres.<project-ref>` (không phải `postgres` trần).
   - Nếu lỡ dán dạng cũ `postgres://...` hoặc thiếu driver `postgresql://...`, code
     (`app/core/config.py` → `normalize_db_url`) tự chuẩn hóa về `postgresql+psycopg2://` — không cần sửa tay.
   - Lỗi `NoSuchModuleError: sqlalchemy.dialects:postgresql.postgresql` nghĩa là URL
     bị gõ nhầm thành `postgresql+postgresql://...` (lặp dialect) — sửa lại biến
     `SUPABASE_DB_URL` trên Render Dashboard → Environment.
3. Migration + seed chạy tự động qua Build Command (mục 2).
4. Row Level Security (RLS): **không bắt buộc** — hệ thống tự kiểm soát quyền ở tầng FastAPI (JWT + `require_role`); có thể bật thêm như lớp bảo vệ phụ nếu có thời gian.

---

## 5. AI / RAG — hiện trạng thực tế (khác bản kế hoạch cũ)

### 5.1. LLM: OpenRouter chính + Gemini dự phòng

Hướng chốt (2026-08-17): **2 vai trò độc lập** — embedding **chỉ Voyage AI**, sinh câu trả lời **chỉ OpenRouter/Gemini** (Voyage không sinh văn bản; OpenRouter/Gemini không tạo vector). Riêng chatbot quy chế: **OpenRouter là LLM chính, Gemini là dự phòng**. Toàn bộ logic gom ở 2 điểm vào duy nhất `call_llm_json` / `call_llm_text` trong `app/services/llm_service.py` (httpx async, không SDK):

- **OpenRouter (chính cho chatbot quy chế)** — key đặt ở `OPENROUTER_API_KEY`, model trong biến `OPENROUTER_MODEL` (mặc định `nvidia/nemotron-3-super-120b-a12b:free`); gọi REST `chat/completions` chuẩn OpenAI-compatible.
- **Gemini (dự phòng)** — code tự chuyển sang khi OpenRouter lỗi: HTTP ≠ 200, hết quota (429), hoặc timeout (helper `_check_gemini_finished` vẫn giữ để lọc câu trả lời rỗng do bộ lọc an toàn chặn). Key `GOOGLE_API_KEY` (chấp nhận cả tên cũ `GEMINI_API_KEY`), model `GEMINI_MODEL` (mặc định `gemini-2.0-flash`).
- **Ngoại lệ — 2 chức năng AI dạng JSON** (tư vấn đăng ký, tóm tắt học tập qua `call_llm_json`): vẫn chạy **Gemini trước → OpenRouter fallback** vì đã ổn định; chỉ chatbot quy chế (dạng văn bản tự do) dùng thứ tự OpenRouter trước.
- **Không dùng Groq** — không cần thêm tài khoản/key thứ 3, hướng OpenRouter→Gemini đã đủ độ dự phòng cho demo.
- Không có key nào: AI tư vấn/tóm tắt vẫn trả fallback server-side (không chết API), chatbot quy chế trả 503 với thông báo rõ ràng.

### 5.2. Vector store cho RAG: đã nhúng sẵn, embedding câu hỏi qua Voyage AI API

Hai "Hướng A/B" trong bản kế hoạch cũ (deploy service RAG riêng / gộp vào pgvector) **đều không còn phải cân nhắc** — dự án đã triển khai xong theo cách gọn nhất:

- Pipeline RAG **nằm ngay trong backend chính**: `app/services/rag_service.py` nối FastAPI → `src/rag/` (ChromaDB + prompt + LLM qua httpx, không dùng LangChain). Không có service thứ hai, không HTTP nội bộ.
- **ChromaDB persist** trong `backend/vectorstore/` — **đã commit vào git** (gồm `chroma.sqlite3` + HNSW index). Deploy từ GitHub là có sẵn, không cần build lại.
- **Embedding câu hỏi gọi qua Voyage AI API** (`voyage-4`, `app/services/embedding_service.py` — httpx, async, retry 429/5xx tối đa 2 lần) thay vì tải model local: đây là thay đổi quyết định giúp chatbot chạy được trên Render free 512MB. Nhúng câu hỏi dùng `input_type="query"` (khác `"document"` lúc build index — Voyage tối ưu retrieval bất đối xứng). Retrieval cần `VOYAGE_API_KEY`; LLM trả lời dùng OpenRouter → fallback Gemini.
- **Chống bịa (anti-hallucination):** câu hỏi không khớp chunk nào → trả thẳng "không tìm thấy thông tin trong quy chế" và **không gọi LLM**.
- Endpoint `POST /ai/regulation-chat` trả `answer` + `sources` (Điều/Khoản/trang) + `provider`/`model`; ngữ cảnh hội thoại giữ server-side theo `session_id`. (Dropdown provider/model trên frontend được nhận để tương thích API nhưng model trả lời luôn theo cấu hình .env: OpenRouter chính, Gemini fallback.)

> Nếu sau này muốn "gọn kiến trúc" cho báo cáo/slide: phương án pgvector trên Supabase vẫn để ngỏ nhưng **không cần làm** — cách hiện tại đã 0đ và chạy ổn định.

**Cập nhật quy chế mới (quy trình chuẩn):** đặt DOCX vào `backend/data/raw/` → chạy `python scripts/rebuild_vector_store.py` ở máy local (cần `VOYAGE_API_KEY`; script nhúng toàn bộ chunk qua Voyage `input_type="document"` rồi mới xóa index cũ — lỗi giữa chừng thì vector store cũ vẫn nguyên) → commit thư mục `backend/vectorstore/` → push, Render tự redeploy với index mới. (Tài liệu gốc DOCX/PDF không nằm trong repo — chỉ có index đã build.)

---

## 6. Tóm tắt domain/dịch vụ sử dụng

| Thành phần | Dịch vụ | Chi phí |
|---|---|---|
| Frontend | Vercel | Free |
| Backend | Render (free tier) | 0đ — nếu cần chạy 24/7 lúc bảo vệ thì nâng instance trả phí (~$7/tháng) |
| Database | Supabase | Free tier |
| LLM | OpenRouter model `:free` (chính) / Gemini free (dự phòng) | Free tier |
| Vector store (RAG) | ChromaDB dựng sẵn trong repo (nhúng Voyage `voyage-4`); embedding câu hỏi gọi Voyage API lúc runtime | Free tier (Voyage free có quota đủ cho demo) |

**Tổng chi phí dự kiến: 0đ** trong phạm vi free tier — phù hợp quy mô đồ án, không cần đầu tư server riêng.

---

## 7. Các thay đổi code đã thực hiện để sẵn sàng deploy (2026-08-16)

| Thay đổi | File | Lý do |
|---|---|---|
| CORS đọc từ biến môi trường `CORS_ORIGINS` (mặc định localhost:5173) | `backend/app/core/config.py`, `backend/app/main.py` | Trước đó hardcode localhost → Vercel gọi API sẽ bị chặn |
| Frontend đọc `VITE_API_BASE_URL` (fallback `/api` cho dev) | `frontend/src/api/client.js`, `frontend/.env.example` | Trước đó hardcode `/api` → không gọi được backend khác domain |
| Commit `backend/vectorstore/chroma.sqlite3` + rule giữ trong `.gitignore` | `.gitignore` | Rule `*.sqlite3` từng bỏ sót file lõi của ChromaDB → deploy lên chatbot sẽ chết |
| Procfile + `runtime.txt` cho Render | `backend/Procfile`, `backend/runtime.txt` | Lệnh start + phiên bản Python 3.12 chuẩn khi Render build |
| **Chuyển RAG sang embedding Voyage AI API** (bỏ hẳn torch/sentence-transformers/langchain; gộp chromadb vào `requirements.txt`; xóa `requirements-rag.txt`; script `scripts/rebuild_vector_store.py`) | `backend/app/services/embedding_service.py`, `requirements.txt`, `scripts/` | 2026-08-17 — Embedding local cần >1GB RAM, Render free 512MB không chạy nổi. Gọi Voyage API giúp chatbot chạy trên free tier; đo RAM còn ~126MB. **Vector store phải rebuild** bằng `python scripts/rebuild_vector_store.py` sau khi đưa lại file DOCX vào `data/raw/` — index cũ nhúng bằng Gemini, không cùng không gian vector với Voyage |
| `vercel.json` rewrite SPA | `frontend/vercel.json` | BrowserRouter cần rewrite mọi route về `index.html` |
| Runbook deploy từng bước | `README.md` mục "Deploy" | Quy trình thao tác cho cả 3 dịch vụ |
| Thêm `CORS_ORIGINS` vào `.env.example` | `backend/.env.example` | Đồng bộ biến mới |

---

## 8. Checklist trước khi demo/bảo vệ đồ án

**Hạ tầng**
- [ ] `git ls-files backend/vectorstore` có `chroma.sqlite3` (nếu không, chatbot chết khi deploy).
- [ ] Build Command trên Render 3 bước: `pip install -r requirements.txt` → `alembic upgrade head` → `python -m app.seed` (KHÔNG có `build_index`; stack RAG không cài trên Render free).
- [ ] `SUPABASE_DB_URL` trỏ **Session Pooler** (`aws-0-<region>.pooler.supabase.com:5432`, user `postgres.<project-ref>`), KHÔNG phải host direct `db.<ref>.supabase.co` — host direct chỉ có IPv6 ở nhiều region, Render free tier không route được.
- [ ] **Làm ấm trước giờ demo:** mở `/health` (hoặc `/docs`) trước 5–10 phút — free tier ngủ sau 15 phút không dùng.
- [ ] `VOYAGE_API_KEY` đã điền trên Render (bắt buộc cho chatbot quy chế — embedding câu hỏi + rebuild vector store).
- [ ] `OPENROUTER_API_KEY` đã điền trên Render (LLM chính của chatbot quy chế).
- [ ] `GOOGLE_API_KEY` đã điền trên Render (bắt buộc — LLM chính của AI tư vấn/tóm tắt, dự phòng cho chatbot).
- [x] Vector store trong `backend/vectorstore/` đã được **rebuild bằng Voyage** (`python scripts/rebuild_vector_store.py` + commit) — index cũ nhúng bằng Gemini không cùng không gian vector với `voyage-4`; retriever sẽ tự phát hiện lệch model và chặn với hướng dẫn rebuild. ✅ Đã rebuild xong: 741 chunks, `voyage-4`, 1024 chiều.

**Cấu hình**
- [ ] `CORS_ORIGINS` trên Render chứa **đúng** domain Vercel (và localhost nếu vẫn muốn dev).
- [ ] `VITE_API_BASE_URL` đã đặt trên Vercel và đã redeploy sau khi đặt.
- [ ] Secrets (`SECRET_KEY`, `VOYAGE_API_KEY`, `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, `SUPABASE_DB_URL`) không nằm trong git — chỉ trong `.env` local + dashboard Render/Vercel.

**Dữ liệu & chức năng**
- [ ] Chạy `scripts/smoke.py` với `SMOKE_BASE=https://<name>.onrender.com` trước ngày demo.
- [ ] Tài khoản demo đủ vai trò (`DTCAD001` admin, `ptdt`, `DTCGV001`..`DTCGV002`, `DTCCV001`..`DTCCV004`, `DTC001`..`DTC015` — mật khẩu `password123`; **tên đăng nhập = mã**) — seed chạy tự động khi deploy. Đăng nhập không phân biệt hoa/thường.
- [ ] Test quota free tier: OpenRouter bị 429 / lỗi → code tự fallback Gemini; kiểm tra trước là chatbot quy chế vẫn trả lời khi nhiều người thử cùng lúc.
- [ ] Chat quy chế trả về `sources` có Điều/Khoản/trang (vectorstore còn nguyên sau khi deploy).
