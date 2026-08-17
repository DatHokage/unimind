# Hướng dẫn Deploy từng bước (Render + Vercel + Supabase)

Hệ thống Quản lý Đào tạo tích hợp AI — `DatHokage/unimind`

```
GitHub (code) ──▶ Render (backend FastAPI) ──▶ Supabase (Postgres)
                      ▲
Vercel (frontend React) ─── gọi API ───┘       OpenRouter / Gemini (LLM) + Voyage AI (embedding)
```

**Thứ tự thực hiện:** (0) Push code → (1) Supabase → (2) Lấy API key → (3) Render backend → (4) Vercel frontend → (5) Mở CORS → (6) Test. Toàn bộ làm trên trình duyệt, không cần cài gì thêm.

---

## Chuẩn bị: tạo tài khoản (nếu chưa có)

| Dịch vụ | Đăng ký tại | Dùng để |
|---|---|---|
| GitHub | github.com | Đã có (repo `DatHokage/unimind`) |
| Supabase | supabase.com (đăng nhập bằng GitHub) | Database PostgreSQL |
| Render | render.com (đăng nhập bằng GitHub) | Host backend FastAPI |
| Vercel | vercel.com (đăng nhập bằng GitHub) | Host frontend React |
| Voyage AI | dash.voyageai.com | Key embedding cho chatbot quy chế (bắt buộc, miễn phí) |
| OpenRouter | openrouter.ai | Key LLM chính của chatbot quy chế (miễn phí, bắt buộc cho chatbot) |
| Google AI Studio | aistudio.google.com | Key Gemini — LLM chính của AI tư vấn/tóm tắt + dự phòng cho chatbot (bắt buộc, miễn phí) |

---

## ⭐ Trả lời nhanh: API key dán ở đâu?

> **Không dán key vào code.** Code không cần thay đổi gì thêm để deploy (mọi chỗ cần sửa đã làm xong — xem mục "Những gì đã sửa trong code" cuối bài). Key chỉ dán vào **2 chỗ**:

| Chỗ dán | Khi nào dùng | Dán vào đâu |
|---|---|---|
| **`backend/.env`** (file trên máy bạn) | Chạy **local** (`uvicorn app.main:app --reload`) | Mở file `backend/.env`, dán giá trị vào dòng tương ứng — xem Bước 2 |
| **Render dashboard → tab Environment** | Chạy **production** (deploy thật) | Dán vào ô Value của từng biến — xem Bước 3.6 |

Key **không bao giờ** được commit vào git (`.env` đã nằm trong `.gitignore` — kiểm chứng: `git check-ignore backend/.env`).

---

## Bước 0 — Commit & push code lên GitHub

Mở terminal tại `E:\ql_daotao`:

```bash
git add -A
git commit -m "chore: san sang deploy Render + Vercel + Supabase"
git push origin main
```

> ⚠️ `backend/vectorstore/chroma.sqlite3` (11MB) **bắt buộc** phải được push — thiếu file này chatbot quy chế sẽ chết khi deploy. Kiểm tra: `git ls-files backend/vectorstore` phải thấy `chroma.sqlite3`.

✅ Xong khi: vào https://github.com/DatHokage/unimind thấy commit mới nhất.

---

## Bước 1 — Tạo database Supabase

1. Vào https://supabase.com → **New project**:
   - Name: `ql-daotao` (tùy chọn)
   - Database Password: đặt mật khẩu mạnh → **lưu lại ngay** (chỉ hiện 1 lần)
   - Region: **Southeast Asia (Singapore)**
   - → Create project, chờ ~1 phút.
2. Lấy connection string: **Project Settings (icon bánh răng) → Database** → phần **Connection Pooling** → chọn **Session Pooler** (mode "Session", cổng **5432**), dạng:
   ```
   postgresql://postgres.abcdefxyz:[YOUR-DATABASE-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
3. **Sửa thành dạng SQLAlchemy** (thay `[YOUR-DATABASE-PASSWORD]` bằng mật khẩu ở trên, thêm `?sslmode=require`):
   ```
   postgresql+psycopg2://postgres.abcdefxyz:MatKhauCuaBan@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
   ```
   > ⚠️ Bắt buộc dùng **Session Pooler** (host `aws-0-<region>.pooler.supabase.com`, cổng 5432, user `postgres.<project-ref>`). KHÔNG dùng direct connection `db.<project-ref>.supabase.co` — host đó ở nhiều region chỉ có IPv6, Render free tier không nối được → lỗi `Network is unreachable`. Cũng không dùng Transaction Pooler cổng 6543 (reset state giữa các kết nối, SQLAlchemy chạy không ổn định).

📋 **Copy chuỗi này ra notepad** — dán vào Render ở Bước 3.

✅ Xong khi: có connection string trong tay. (Chưa cần tạo bảng — Bước 3 làm tự động.)

---

## Bước 2 — Lấy API key (dán vào `backend/.env` nếu muốn test local)

### 2.1. Key Voyage AI (embedding chatbot quy chế — BẮT BUỘC)

1. Vào https://dash.voyageai.com/ → đăng nhập → **API Keys** → **Generate API Key** → đặt tên `ql-daotao` → copy key (dạng `pa-...`).

### 2.2. Key Google Gemini (LLM chính của AI tư vấn/tóm tắt + dự phòng chatbot — BẮT BUỘC)

1. Vào https://aistudio.google.com/apikey → **Create API key** → copy key (dạng `AIza...`).

### 2.3. Key OpenRouter (LLM chính của chatbot quy chế — BẮT BUỘC cho chatbot)

1. Vào https://openrouter.ai/keys → đăng nhập → **Create key** → đặt tên `ql-daotao` → copy key (dạng `sk-or-v1-...`).

### 2.4. SECRET_KEY (chữ ký JWT — tự sinh, không phải key dịch vụ nào)

Chạy lệnh này ở `E:\ql_daotao\backend`:

```bash
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy chuỗi in ra.

### 2.5. Dán vào `backend/.env` (chỉ cần nếu muốn chạy/test trên máy)

File `backend/.env` đã tồn tại trên máy bạn. Mở lên, đảm bảo các dòng sau có giá trị:

```ini
SUPABASE_DB_URL=postgresql+psycopg2://postgres.abcdefxyz:MatKhauCuaBan@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres?sslmode=require
SECRET_KEY=<chuỗi token_urlsafe vừa sinh>
VOYAGE_API_KEY=pa-...
OPENROUTER_API_KEY=sk-or-v1-...
GOOGLE_API_KEY=AIza...
CORS_ORIGINS=http://localhost:5173
```

Test local nhanh: `uvicorn app.main:app --reload` → mở http://localhost:8000/docs.

> Các key này lát nữa dán lại vào **Render dashboard** (Bước 3.6) — bản `.env` trên máy chỉ phục vụ chạy local, **không liên quan** tới server deploy.

> ✅ Vector store trong repo **đã được nhúng bằng Voyage `voyage-4`** (741 chunks, đã commit) — deploy xong chatbot chạy ngay, không cần rebuild. Chỉ chạy `python scripts/rebuild_vector_store.py` khi cập nhật quy chế mới (DOCX vào `data/raw/`) hoặc đổi `VOYAGE_MODEL`.

📋 **Chuẩn bị sẵn trong notepad 5 giá trị:** connection string, SECRET_KEY, key Voyage, key OpenRouter, key Gemini.

---

## Bước 3 — Deploy backend lên Render

1. Vào https://render.com → **New → Web Service**.
2. **Connect a repository** → chọn `DatHokage/unimind` (nếu chưa thấy repo: nhấn "Configure account", cấp quyền cho repo này).
3. Trang cấu hình service, điền chính xác:

   | Ô | Giá trị |
   |---|---|
   | **Name** | `unimind-api` (tên này tạo thành domain `unimind-api.onrender.com` — chọn tên ngắn, nhớ nó) |
   | **Region** | **Singapore** |
   | **Branch** | `main` |
   | **Root Directory** | `backend` |
   | **Runtime** | **Python** (tự nhận) |
   | **Build Command** | dán dòng bên dưới ⬇ |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (hoặc để trống — Render tự đọc `backend/Procfile`) |
   | **Instance Type** | **Free** |

   **Build Command** (1 dòng duy nhất):
   ```
   pip install -r requirements.txt && alembic upgrade head && python -m app.seed
   ```
   Ý nghĩa 3 bước: cài thư viện (không có torch/sentence-transformers nên cài nhanh) → tạo bảng DB (alembic) → nạp dữ liệu demo (seed, idempotent). KHÔNG có bước build vector store — chatbot quy chế dùng vector store dựng sẵn đã commit trong repo, embedding câu hỏi gọi qua Voyage AI API.

4. **ĐỪNG bấm Deploy vội** — nhấn **Advanced** (mở mục nâng cao) để thêm biến môi trường trước.

5. **Tab Environment** → **Add Environment Variable**, thêm lần lượt 6 biến:

   | Key | Value |
   |---|---|
   | `SUPABASE_DB_URL` | connection string Bước 1 (Session Pooler) |
   | `SECRET_KEY` | chuỗi token Bước 2.4 |
   | `VOYAGE_API_KEY` | key `pa-...` — bắt buộc cho chatbot quy chế (embedding) |
   | `OPENROUTER_API_KEY` | key `sk-or-v1-...` — LLM chính của chatbot quy chế |
   | `GOOGLE_API_KEY` | key `AIza...` — bắt buộc (LLM chính AI tư vấn/tóm tắt + dự phòng chatbot) |
   | `CORS_ORIGINS` | `https://ten-bat-ky.vercel.app` — **tạm để vậy, sửa lại ở Bước 5** khi có domain Vercel thật |

   > Đây chính là chỗ **dán API key** trên production. Render tự che giá trị (masked), không ai xem được ngoài bạn.

6. Bấm **Create Web Service** (hoặc Manual Deploy → Deploy latest commit nếu đã lỡ tạo xong).
7. Chờ build (~2–5 phút). Theo dõi log:
   - Thấy `Running upgrade ... -> ..., ...` (alembic) và vài dòng `+ tài khoản student1/password123...` (seed) → DB OK.
   - Kết thúc bằng **`Your service is live 🎉`**.

8. **Kiểm tra backend sống:** mở `https://<name>.onrender.com/health` → phải thấy `{"status":"ok"}`. Mở thêm `/docs` thấy trang Swagger là chuẩn.

📋 **Copy domain `https://<name>.onrender.com` ra notepad.**

✅ Xong khi: `/health` trả `{"status":"ok"}`.

---

## Bước 4 — Deploy frontend lên Vercel

1. Vào https://vercel.com → **Add New... → Project** → **Import** cạnh repo `DatHokage/unimind`.
2. Trang cấu hình:

   | Ô | Giá trị |
   |---|---|
   | **Project Name** | tùy chọn |
   | **Framework Preset** | tự nhận **Vite** (không đổi) |
   | **Root Directory** | bấm **Edit** → điền `frontend` |
   | **Environment Variables** | thêm biến bên dưới ⬇ |

   **Thêm biến môi trường** (đây là biến duy nhất frontend cần — KHÔNG dán API key vào Vercel):

   | Key | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://<name>.onrender.com` (domain Render ở Bước 3) |

3. Bấm **Deploy**, chờ ~30 giây.
4. Vercel cho domain dạng `https://unimind-xxx.vercel.app` — bấm vào mở thử.

📋 **Copy domain Vercel.**

✅ Xong khi: trang login hiện ra (đăng nhập lúc này có thể chưa được vì CORS chưa mở — bình thường).

---

## Bước 5 — Mở CORS cho domain Vercel

1. Quay lại Render: **Dashboard → service của bạn → tab Environment**.
2. Sửa biến `CORS_ORIGINS` thành domain Vercel thật (thêm localhost để dev vẫn gọi được):
   ```
   http://localhost:5173,https://unimind-xxx.vercel.app
   ```
   (phân tách bằng dấu phẩy, không có khoảng trắng thừa giữa các domain)
3. **Save Changes** → Render tự redeploy (chờ ~2–3 phút, lần này build nhanh hơn vì cache).

> Nếu quên bước này: frontend gọi API sẽ bị trình duyệt chặn, console hiện lỗi **CORS** (xem mục Xử lý sự cố).

✅ Xong khi: redeploy xong, log lại thấy `Your service is live 🎉`.

---

## Bước 6 — Kiểm tra toàn bộ

### 6.1. Test nhanh trên trình duyệt

1. Mở domain Vercel → đăng nhập `DTC001` / `password123`.
2. Vào **Đăng ký học phần** → bấm **AI tư vấn** → chờ nhận gợi ý môn học (mất 10–30s do gọi LLM).
3. Vào **Chat quy chế** → hỏi: *"Sinh viên bị cấm thi khi nào?"* → trả lời phải kèm nguồn **Điều/Khoản/trang**.
4. Đăng xuất, thử thêm: `DTCGV001`, `DTCCV001`, `ptdt` (cùng mật khẩu `password123`). Gõ thường `dtcgv001` vẫn đăng nhập được (không phân biệt hoa/thường).

### 6.2. Chạy smoke test vào thẳng backend (32 bước end-to-end)

```bash
cd E:\ql_daotao\backend
set SMOKE_BASE=https://<name>.onrender.com
.venv\Scripts\python scripts\smoke.py
```

✅ Nếu cả 2 phần trên OK — **deploy xong.**

---

## Những gì đã sửa trong code (bạn không cần sửa gì thêm)

| File | Thay đổi | Vì sao |
|---|---|---|
| `backend/app/main.py` + `core/config.py` | CORS đọc từ biến `CORS_ORIGINS` | Trước hardcode `localhost:5173` → Vercel bị chặn |
| `frontend/src/api/client.js` | Đọc `VITE_API_BASE_URL`, để trống thì dùng `/api` | Trước hardcode `/api` → không gọi được backend khác domain |
| `backend/src/ingestion/build_index.py` | Shim chuyển hướng sang `scripts/rebuild_vector_store.py` | Vector store dựng sẵn trong repo, không build lại khi deploy Render |
| `backend/Procfile`, `backend/runtime.txt` | Lệnh start + Python 3.12 | Render cần để biết cách chạy |
| `frontend/vercel.json` | Rewrite mọi route về `index.html` | SPA (BrowserRouter) trên Vercel |
| `.gitignore` | Giữ `backend/vectorstore/chroma.sqlite3` trong repo | Thiếu file này chatbot chết |

**Không có file code nào chứa API key** — và phải giữ nguyên như vậy.

---

## Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách sửa |
|---|---|---|
| Login bấm không được, console lỗi **CORS** | `CORS_ORIGINS` thiếu/sai domain Vercel | Bước 5: điền đúng domain, đủ `https://`, không có `/` cuối |
| `https://<name>.onrender.com` load rất lâu lần đầu rồi mới trả lời | Free tier **ngủ sau 15 phút** không dùng — đây là hành vi bình thường | Trước buổi demo, mở `/health` trước 5–10 phút để đánh thức. Muốn hết hẳn: nâng instance trả phí |
| Chat quy chế trả lỗi **503** | Chưa điền `VOYAGE_API_KEY` (bắt buộc cho embedding) trên Render, hoặc vector store chưa rebuild bằng Voyage | Dán key Voyage vào tab Environment; nếu index lệch model thì rebuild + commit lại `backend/vectorstore/` |
| Chat quy chế trả lỗi **502** | Cả OpenRouter lẫn Gemini đều lỗi/hết quota | Code tự fallback OpenRouter → Gemini; nếu vẫn lỗi kiểm tra quota cả 2 tài khoản |
| AI tư vấn trả lời dạng "fallback" (không thông minh) | Gemini hết quota/bị lọc an toàn và OpenRouter cũng lỗi | Vẫn chạy được (fallback server-side); kiểm tra quota 2 tài khoản |
| Log build báo lỗi `alembic` / `Network is unreachable` | `SUPABASE_DB_URL` đang trỏ host direct `db.<ref>.supabase.co` (chỉ IPv6) hoặc sai pooler | Dán lại connection string **Session Pooler** dạng Bước 1.3 |
| `FATAL: password authentication failed for user "postgres"` | User trong chuỗi pooler đang là `postgres` trần — Supabase pooler bắt buộc `postgres.<project-ref>` để định tuyến đúng project, dù password đúng vẫn báo sai | Sửa `SUPABASE_DB_URL` trên Render: user phải là `postgres.<project-ref>` (xem Bước 1.3) |
| Render báo service bị **killed** (OOM) | Rất khó xảy ra — pipeline RAG đã đo chỉ tốn ~126MB RSS (embedding gọi API, không tải model local); nếu gặp thì kiểm tra có ai thêm dependency nặng (torch...) vào `requirements.txt` không | Giữ requirements đúng như trong repo |
| Vercel trắng trang khi reload ở route con | Thiếu `vercel.json` | File đã có trong repo — kiểm tra push đủ chưa |
| Đổi `VITE_API_BASE_URL` trên Vercel mà không thấy tác dụng | Biến Vite ăn lúc **build** | Sau khi đổi biến phải **Redeploy** trên Vercel |

---

## Chi phí

| Dịch vụ | Gói | Chi phí |
|---|---|---|
| Render | Free (Web Service) | 0đ |
| Vercel | Hobby | 0đ |
| Supabase | Free | 0đ |
| Voyage AI | Free tier (embedding chatbot quy chế) | 0đ |
| OpenRouter | Model `:free` (LLM chính chatbot quy chế) | 0đ |
| Gemini | Free tier (LLM chính AI tư vấn/tóm tắt + dự phòng chatbot) | 0đ |

**Tổng: 0đ.** Nếu muốn backend chạy 24/7 không ngủ (cho ngày bảo vệ): nâng Render instance ~$7/tháng, chỉ bật trong tuần bảo vệ rồi hạ xuống Free.
