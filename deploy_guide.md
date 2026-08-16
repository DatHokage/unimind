# Hướng dẫn Deploy từng bước (Render + Vercel + Supabase)

Hệ thống Quản lý Đào tạo tích hợp AI — `DatHokage/unimind`

```
GitHub (code) ──▶ Render (backend FastAPI) ──▶ Supabase (Postgres)
                      ▲
Vercel (frontend React) ─── gọi API ───┘       OpenRouter / Gemini (LLM)
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
| OpenRouter | openrouter.ai | Key LLM chính (miễn phí) |
| Google AI Studio | aistudio.google.com | Key Gemini dự phòng (miễn phí) |

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
git add .gitignore README.md DEPLOY.md backend/.env.example backend/app/core/config.py backend/app/main.py backend/Procfile backend/runtime.txt backend/src/ingestion/build_index.py frontend/src/api/client.js frontend/.env.example frontend/vercel.json backend/vectorstore/chroma.sqlite3
git commit -m "chore: san sang deploy Render + Vercel + Supabase"
git push origin main
```

> ⚠️ `backend/vectorstore/chroma.sqlite3` (11MB) **bắt buộc** phải được push — thiếu file này chatbot quy chế sẽ chết khi deploy. Kiểm tra: `git ls-files backend/vectorstore` phải thấy `chroma.sqlite3`.
> Nếu bạn còn thay đổi dở ở `frontend/src/pages/LoginPage.jsx`, `frontend/src/utils/classification.js` thì `git add` thêm 2 file đó.

✅ Xong khi: vào https://github.com/DatHokage/unimind thấy commit mới nhất.

---

## Bước 1 — Tạo database Supabase

1. Vào https://supabase.com → **New project**:
   - Name: `ql-daotao` (tùy chọn)
   - Database Password: đặt mật khẩu mạnh → **lưu lại ngay** (chỉ hiện 1 lần)
   - Region: **Southeast Asia (Singapore)**
   - → Create project, chờ ~1 phút.
2. Lấy connection string: **Project Settings (icon bánh răng) → Database** → phần **Connection string** → chọn tab **URI**, dạng:
   ```
   postgresql://postgres.abcdefxyz:[YOUR-DATABASE-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
   ```
3. **Sửa thành dạng SQLAlchemy + cổng 5432 direct** (thay `[YOUR-DATABASE-PASSWORD]` bằng mật khẩu ở trên, thêm `?sslmode=require`):
   ```
   postgresql+psycopg2://postgres.abcdefxyz:MatKhauCuaBan@db.abcdefxyz.supabase.co:5432/postgres?sslmode=require
   ```
   > Quy tắc: host dạng `db.<project-ref>.supabase.co`, **cổng 5432** — KHÔNG dùng dòng pooler cổng 6543/5432 có chữ "pooler" (SQLAlchemy chạy không ổn định qua pooler).

📋 **Copy chuỗi này ra notepad** — dán vào Render ở Bước 3.

✅ Xong khi: có connection string trong tay. (Chưa cần tạo bảng — Bước 3 làm tự động.)

---

## Bước 2 — Lấy API key (dán vào `backend/.env` nếu muốn test local)

### 2.1. Key OpenRouter (LLM chính — bật AI tư vấn + chatbot quy chế)

1. Vào https://openrouter.ai/keys → đăng nhập → **Create key** → đặt tên `ql-daotao` → copy key (dạng `sk-or-v1-...`).

### 2.2. Key Google Gemini (dự phòng — nên có)

1. Vào https://aistudio.google.com/apikey → **Create API key** → copy key (dạng `AIza...`).

### 2.3. SECRET_KEY (chữ ký JWT — tự sinh, không phải key dịch vụ nào)

Chạy lệnh này ở `E:\ql_daotao\backend`:

```bash
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy chuỗi in ra.

### 2.4. Dán vào `backend/.env` (chỉ cần nếu muốn chạy/test trên máy)

File `backend/.env` đã tồn tại trên máy bạn. Mở lên, đảm bảo các dòng sau có giá trị:

```ini
SUPABASE_DB_URL=postgresql+psycopg2://postgres.abcdefxyz:MatKhauCuaBan@db.abcdefxyz.supabase.co:5432/postgres?sslmode=require
SECRET_KEY=<chuỗi token_urlsafe vừa sinh>
OPENROUTER_API_KEY=sk-or-v1-...
GOOGLE_API_KEY=AIza...
CORS_ORIGINS=http://localhost:5173
```

Test local nhanh: `uvicorn app.main:app --reload` → mở http://localhost:8000/docs.

> Các key này lát nữa dán lại vào **Render dashboard** (Bước 3.6) — bản `.env` trên máy chỉ phục vụ chạy local, **không liên quan** tới server deploy.

📋 **Chuẩn bị sẵn trong notepad 4 giá trị:** connection string, SECRET_KEY, key OpenRouter, key Gemini.

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
   pip install -r requirements.txt && python -m src.ingestion.build_index && alembic upgrade head && python -m app.seed
   ```
   Ý nghĩa 4 bước: cài thư viện → tải embedding model (~500MB) bake vào image → tạo bảng DB (alembic) → nạp dữ liệu demo (seed, idempotent).

4. **ĐỪNG bấm Deploy vội** — nhấn **Advanced** (mở mục nâng cao) để thêm biến môi trường trước.

5. **Tab Environment** → **Add Environment Variable**, thêm lần lượt 6 biến:

   | Key | Value |
   |---|---|
   | `SUPABASE_DB_URL` | connection string Bước 1 |
   | `SECRET_KEY` | chuỗi token Bước 2.3 |
   | `OPENROUTER_API_KEY` | key `sk-or-v1-...` |
   | `GOOGLE_API_KEY` | key `AIza...` |
   | `SKIP_INDEX_BUILD_IF_NO_DOCS` | `1` |
   | `CORS_ORIGINS` | `https://ten-bat-ky.vercel.app` — **tạm để vậy, sửa lại ở Bước 5** khi có domain Vercel thật |

   > Đây chính là chỗ **dán API key** trên production. Render tự che giá trị (masked), không ai xem được ngoài bạn.

6. Bấm **Create Web Service** (hoặc Manual Deploy → Deploy latest commit nếu đã lỡ tạo xong).
7. Chờ build (~5–10 phút: riêng `pip install` đã lâu vì tải torch/sentence-transformers). Theo dõi log:
   - Thấy dòng `SKIP] Khong co DOCX/PDF nao...` → đúng, embedding model đang tải vào cache.
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

1. Mở domain Vercel → đăng nhập `student1` / `password123`.
2. Vào **Đăng ký học phần** → bấm **AI tư vấn** → chờ nhận gợi ý môn học (mất 10–30s do gọi LLM).
3. Vào **Chat quy chế** → hỏi: *"Sinh viên bị cấm thi khi nào?"* → trả lời phải kèm nguồn **Điều/Khoản/trang**.
4. Đăng xuất, thử thêm: `lecturer1`, `advisor1`, `ptdt` (cùng mật khẩu `password123`).

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
| `backend/src/ingestion/build_index.py` | Thêm `SKIP_INDEX_BUILD_IF_NO_DOCS=1` | Build trên Render không có file DOCX gốc, chỉ bake embedding model |
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
| Chat quy chế trả lỗi **503** | Chưa có key LLM nào trên Render | Kiểm tra tab Environment có `OPENROUTER_API_KEY` hoặc `GOOGLE_API_KEY` chưa |
| Chat quy chế trả lỗi **502** | LLM bị rate-limit/hết quota | Code tự fallback model khác; nếu vẫn lỗi → dán thêm key Gemini |
| AI tư vấn trả lời dạng "fallback" (không thông minh) | Key OpenRouter hết quota hoặc model lỗi | Vẫn chạy được (fallback server-side); kiểm tra tài khoản OpenRouter |
| Log build báo lỗi `alembic` / `connection refused` | `SUPABASE_DB_URL` sai (nhầm pooler 6543, thiếu `sslmode=require`, sai mật khẩu) | Dán lại connection string dạng Bước 1.3 |
| Log build báo `FileNotFoundError: ... data/raw` | Quên biến `SKIP_INDEX_BUILD_IF_NO_DOCS=1` | Thêm biến = `1` ở tab Environment |
| Render báo service bị **killed** (OOM) | Free tier 512MB RAM không đủ khi warm-up RAG | Nâng Instance Type lên gói trả phí nhỏ nhất |
| Vercel trắng trang khi reload ở route con | Thiếu `vercel.json` | File đã có trong repo — kiểm tra push đủ chưa |
| Đổi `VITE_API_BASE_URL` trên Vercel mà không thấy tác dụng | Biến Vite ăn lúc **build** | Sau khi đổi biến phải **Redeploy** trên Vercel |

---

## Chi phí

| Dịch vụ | Gói | Chi phí |
|---|---|---|
| Render | Free (Web Service) | 0đ |
| Vercel | Hobby | 0đ |
| Supabase | Free | 0đ |
| OpenRouter | Model `:free` | 0đ |
| Gemini | Free tier | 0đ |

**Tổng: 0đ.** Nếu muốn backend chạy 24/7 không ngủ (cho ngày bảo vệ): nâng Render instance ~$7/tháng, chỉ bật trong tuần bảo vệ rồi hạ xuống Free.
