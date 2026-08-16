# Hệ thống Quản lý Đào tạo có Tích hợp AI

## 1. Tổng quan dự án

Hệ thống quản lý đào tạo cho cơ sở giáo dục, hỗ trợ quản lý sinh viên, giảng viên, học phần, lớp học, đăng ký học, điểm — kết hợp AI để tư vấn đăng ký học phần, hỏi-đáp quy chế đào tạo (RAG) và tóm tắt kết quả học tập.

**Stack công nghệ:**

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Backend | **FastAPI** (Python) | REST API, nghiệp vụ, xác thực, tích hợp AI/RAG |
| Frontend | **React** | Giao diện người dùng, dashboard theo vai trò |
| Database | **PostgreSQL (Supabase)** | Lưu dữ liệu nghiệp vụ. Triển khai trên Supabase (đã có sẵn pgvector nếu sau này cần) |
| ORM | SQLAlchemy + Alembic | Model hóa dữ liệu, quản lý migration |
| Auth | JWT (python-jose) + passlib (bcrypt) | Đăng nhập, phân quyền theo vai trò |
| AI Engine | LLM online free-tier (Gemini / Openrouter...) | Tư vấn đăng ký, tóm tắt học tập |
| RAG | **Để trống — tích hợp sau** (đã có pipeline RAG triển khai riêng, sẽ ghép vào sau) | Chatbot hỏi-đáp quy chế đào tạo |

Kiến trúc: **client-server 3 tầng** (React ↔ FastAPI ↔ Supabase Postgres), KHÔNG phải microservice. FastAPI là 1 backend duy nhất, gộp cả phần quản lý và phần AI trong cùng codebase Python.

---

## 2. Vai trò người dùng (roles)

| Role | Mã | Quyền hạn chính |
|---|---|---|
| Phòng đào tạo | `training_office` | Toàn quyền: quản lý sinh viên, giảng viên, học phần, lớp học phần; nhập điểm thi; thống kê |
| Giảng viên | `lecturer` | Quản lý các lớp học phần mình dạy (có thể dạy nhiều lớp); chỉ nhập **điểm quá trình** cho lớp mình phụ trách |
| Cố vấn học tập | `advisor` | Giống giáo viên chủ nhiệm — quản lý/theo dõi **nhiều lớp hành chính** được phân công, xem hồ sơ và kết quả học tập của sinh viên trong các lớp đó |
| Sinh viên | `student` | Đăng ký học phần, xem điểm/thời khóa biểu của chính mình, dùng chatbot AI |

**Nguyên tắc phân quyền dữ liệu nhạy cảm:** Điểm và hồ sơ học tập của sinh viên chỉ được truy cập bởi: chính sinh viên đó, giảng viên dạy lớp học phần liên quan, cố vấn phụ trách lớp hành chính của sinh viên đó, hoặc phòng đào tạo. Middleware phải kiểm tra quyền này ở tầng API, không chỉ ẩn ở giao diện.

**Lưu ý quan hệ quản lý (khác với thiết kế trước):**
- **Cố vấn (advisor) gắn với lớp hành chính (HomeroomClass)**, không gắn trực tiếp với từng sinh viên — 1 cố vấn có thể phụ trách nhiều lớp hành chính, giống giáo viên chủ nhiệm.
- **Giảng viên (lecturer) gắn với lớp học phần (CourseClass)** — 1 giảng viên có thể dạy nhiều lớp học phần (nhiều học phần, nhiều kỳ).

---

## 3. Mô hình dữ liệu (ERD logic)

Đặt tên bảng/trường bằng tiếng Anh, ngắn gọn, tránh gộp nhiều từ có dấu gạch dưới kiểu tiếng Việt.

### 3.1. Các bảng chính

**User** (tài khoản đăng nhập)
- id, username, password_hash, role, created_at

**Student**
- id, code (mã SV, unique), name, dob, major_id (FK → Major), class_id (FK → HomeroomClass)

**Lecturer**
- id, code (unique), name, department

**Major** (ngành học)
- id, name, code

**HomeroomClass** (lớp hành chính)
- id, name, major_id (FK), cohort (khóa/năm nhập học), advisor_id (FK → Lecturer, cố vấn phụ trách lớp này)

> Một `Lecturer` có thể vừa dạy `CourseClass` vừa là `advisor` của một hoặc nhiều `HomeroomClass` — không tách bảng riêng, dùng chung bảng `Lecturer`, phân biệt qua vai trò sử dụng (role `lecturer` để dạy, hoặc được gán làm `advisor_id` ở `HomeroomClass`).

**Course** (học phần)
- id, code (unique), name, credits
- Quan hệ tự tham chiếu nhiều-nhiều qua bảng `Prerequisite` (course_id, prerequisite_course_id)

**CourseClass** (lớp học phần — 1 học phần mở nhiều lớp theo kỳ)
- id, course_id (FK), lecturer_id (FK → Lecturer), term, year, max_size, schedule (thứ/tiết/phòng), status (open/closed)

**Enrollment** (đăng ký học phần)
- id, student_id (FK), course_class_id (FK), enrolled_at, status (pending/approved/cancelled)
- Unique constraint: (student_id, course_class_id)

**Grade**
- id, enrollment_id (FK, unique)
- process_score (điểm quá trình — do `lecturer` nhập)
- exam_score (điểm thi — do `training_office` nhập)
- total_score (tính tự động = (process_score + exam_score) / 2)
- updated_by, updated_at

**RegulationDoc** (tài liệu quy chế — placeholder cho RAG, để trống chi tiết, tích hợp sau)
- Để trống — sẽ ghép từ pipeline RAG đã triển khai riêng

### 3.2. Quan hệ chính
- Student (N) — (1) HomeroomClass — (1) Major
- HomeroomClass (N) — (1) Lecturer [qua advisor_id — 1 giảng viên có thể là cố vấn nhiều lớp]
- Course (N) — (N) Course [qua Prerequisite — tự tham chiếu]
- CourseClass (N) — (1) Course
- CourseClass (N) — (1) Lecturer [1 giảng viên dạy nhiều lớp học phần]
- Enrollment (N) — (1) Student, Enrollment (N) — (1) CourseClass
- Grade (1) — (1) Enrollment

---

## 4. API Endpoints (thiết kế REST)

### 4.1. Auth
| Method | Endpoint | Mô tả | Quyền |
|---|---|---|---|
| POST | `/auth/login` | Đăng nhập, trả JWT | Public |
| GET | `/auth/me` | Lấy thông tin user hiện tại từ token | Đã đăng nhập |

### 4.2. Quản lý (CRUD)
| Method | Endpoint | Mô tả | Quyền |
|---|---|---|---|
| GET/POST | `/students` | Danh sách / tạo sinh viên | training_office |
| GET/PUT | `/students/{id}` | Xem / sửa 1 sinh viên | training_office, chính SV đó (chỉ xem) |
| GET/POST | `/lecturers` | Danh sách / tạo giảng viên | training_office |
| GET/POST | `/homeroom-classes` | Danh sách / tạo lớp hành chính, gán advisor | training_office |
| GET | `/homeroom-classes/{id}/students` | Danh sách SV trong lớp hành chính | advisor phụ trách lớp đó, training_office |
| GET/POST | `/courses` | Danh sách / tạo học phần (kèm điều kiện tiên quyết) | training_office |
| GET/POST | `/course-classes` | Danh sách / mở lớp học phần theo kỳ | training_office |
| GET | `/course-classes/mine` | Danh sách lớp học phần mà giảng viên đang đăng nhập phụ trách | lecturer |
| GET | `/course-classes?term=&status=open` | Tra cứu lớp đang mở | Đã đăng nhập |

### 4.3. Đăng ký & Điểm
| Method | Endpoint | Mô tả | Quyền |
|---|---|---|---|
| POST | `/enrollments` | Sinh viên đăng ký 1 lớp học phần (server kiểm tra điều kiện tiên quyết + trùng lịch + sĩ số) | student |
| DELETE | `/enrollments/{id}` | Hủy đăng ký | student (của chính mình), training_office |
| GET | `/enrollments/student/{student_id}` | Lịch sử đăng ký của 1 sinh viên | Chính SV, advisor phụ trách, training_office |
| PUT | `/grades/{enrollment_id}/process` | Nhập/sửa **điểm quá trình** | lecturer (chỉ lớp mình dạy) |
| PUT | `/grades/{enrollment_id}/exam` | Nhập/sửa **điểm thi** | training_office |
| GET | `/grades/student/{student_id}` | Bảng điểm của 1 sinh viên (kèm total_score) | Chính SV, advisor phụ trách, lecturer liên quan, training_office |

> **Lưu ý phân quyền quan trọng:** `process_score` và `exam_score` là 2 endpoint riêng biệt, không dùng chung 1 endpoint PUT `/grades/{id}` — vì 2 vai trò khác nhau (`lecturer` vs `training_office`) chỉ được sửa đúng phần của mình. Backend phải chặn `lecturer` không được set `exam_score` và ngược lại.

### 4.4. Thống kê
| Method | Endpoint | Mô tả | Quyền |
|---|---|---|---|
| GET | `/stats/academic-results` | Thống kê kết quả học tập theo lớp/khóa | training_office, advisor |
| GET | `/stats/popular-courses` | Học phần có nhiều SV đăng ký nhất | training_office |

### 4.5. AI
| Method | Endpoint | Mô tả | Quyền |
|---|---|---|---|
| POST | `/ai/course-advice` | Input: student_id → AI gợi ý học phần nên đăng ký kỳ tới + giải thích điều kiện tiên quyết | student (chính mình) |
| POST | `/ai/regulation-chat` | **Để trống — placeholder**, sẽ ghép pipeline RAG đã triển khai riêng vào sau | Đã đăng nhập |
| POST | `/ai/study-summary` | Input: student_id → AI tóm tắt tiến độ + gợi ý cải thiện | Chính SV, advisor phụ trách |

---

## 5. Chi tiết chức năng AI

### 5.1. Chatbot hỏi-đáp quy chế (RAG) — ĐỂ TRỐNG, TÍCH HỢP SAU
Pipeline RAG đã được triển khai riêng trước đó (chunk → embedding → vector store → retrieval → LLM). Khi ghép vào dự án này, chỉ cần:
1. Expose endpoint `/ai/regulation-chat` nhận `question: str`, gọi sang module/service RAG hiện có.
2. Không cần thiết kế lại bảng `RegulationDoc`/`RegulationChunk` trong dự án này — dùng lại vector store đã có sẵn từ pipeline cũ.
3. Tạm thời để endpoint trả về response mẫu hoặc HTTP 501 "chưa triển khai" trong giai đoạn code CRUD, ghép thật ở giai đoạn cuối.

### 5.2. AI tư vấn đăng ký học phần
**Input cần chuẩn bị trước khi gọi AI:**
- Danh sách học phần sinh viên đã học và điểm đạt (query từ bảng Grade/Enrollment)
- Danh sách lớp học phần đang mở kỳ tới (query từ CourseClass)
- Điều kiện tiên quyết của từng học phần (query từ Prerequisite)

**Luồng xử lý:**
1. Backend tự truy vấn DB lấy 3 nhóm dữ liệu trên (KHÔNG để AI tự "đoán" — AI chỉ suy luận trên dữ liệu thật được cung cấp).
2. Đưa vào prompt dạng JSON có cấu trúc.
3. AI trả về gợi ý học phần nên đăng ký kỳ tới + giải thích lý do (đã đủ điều kiện tiên quyết / còn thiếu học phần nào).
4. **Ràng buộc quan trọng:** AI chỉ gợi ý, KHÔNG tự động đăng ký thay. Sinh viên vẫn phải bấm xác nhận đăng ký qua endpoint `/enrollments` (được server validate lại điều kiện tiên quyết một lần nữa, không tin tưởng hoàn toàn output của AI).

### 5.3. AI tóm tắt kết quả học tập
- Input: toàn bộ điểm (total_score) của sinh viên theo từng kỳ.
- Output: đoạn văn tóm tắt xu hướng học tập (tăng/giảm điểm trung bình theo kỳ), cảnh báo học phần điểm thấp, gợi ý kế hoạch cải thiện chung chung (không thay thế tư vấn chính thức của cố vấn học tập).

---

# Phần 6 (cập nhật): Công thức tính điểm
 
> Thay thế phần 6.1 trước đó — điểm quá trình (`process_score`) không còn là 1 con số nhập tay đơn giản, mà được **tính tự động** từ điểm chuyên cần, điểm thường xuyên và điểm test giữa kỳ. Điểm thi (`exam_score`) và công thức GPA (6.2) giữ nguyên như thiết kế trước.
 
## 6.1. Bổ sung các thành phần điểm quá trình
 
Trước đây `Grade.process_score` là 1 field do `lecturer` nhập trực tiếp. Nay tách nhỏ thành các thành phần, `lecturer` nhập từng phần, hệ thống **tự tính** `process_score`:
 
| Field | Ý nghĩa | Người nhập |
|---|---|---|
| `attendance_score` (C.Cần) | Điểm chuyên cần | lecturer |
| `midterm_avg` (TBCTN) | Điểm trung bình test/kiểm tra giữa kỳ | lecturer |
| `tx1, tx2, tx3, tx4` (TX1–TX4) | Điểm thường xuyên (bài tập, quiz...) — có thể để trống nếu chưa có cột điểm đó | lecturer |
| `process_score` (TBC) | **Tính tự động**, không cho nhập tay | hệ thống tự tính |
| `exam_score` | Điểm thi | training_office (giữ nguyên như thiết kế trước) |
| `total_score` | **Tính tự động** = `(process_score + exam_score) / 2` | hệ thống tự tính (giữ nguyên) |
 
## 6.2. Bước 1 — Tính điểm thường xuyên (TX)
 
Chỉ tính trung bình trên các cột TX **có điểm**, bỏ qua ô trống:
 
```
TX = average(TX1, TX2, TX3, TX4)   # chỉ tính các giá trị không null
```
 
Ví dụ:
```
TX1 = 7.2
TX2 = 9.8
TX3 = trống
TX4 = trống
 
TX = (7.2 + 9.8) / 2 = 8.5
```
 
## 6.3. Bước 2 — Tính điểm quá trình (process_score / TBC)
 
```
process_score = attendance_score × 0.10
              + midterm_avg      × 0.30
              + TX                × 0.60
```
 
| Thành phần | Trọng số |
|---|---|
| `attendance_score` (C.Cần) | 10% |
| `midterm_avg` (TBCTN) | 30% |
| `TX` | 60% |
 
Ví dụ:
```
attendance_score = 8
midterm_avg      = 8.9
TX                = 8.5
 
process_score = 8×0.10 + 8.9×0.30 + 8.5×0.60
              = 0.8 + 2.67 + 5.1
              = 8.57
              → làm tròn 1 chữ số → 8.6
```
 
Làm tròn:
```
process_score = round(process_score, 1)
```
 
## 6.4. Bước 3 — Tính điểm tổng kết học phần (total_score)
 
Giữ nguyên công thức đã thiết kế trước — không đổi:
 
```
total_score = (process_score + exam_score) / 2
```
 
## 6.5. Cập nhật mô hình dữ liệu (`Grade`)
 
```
Grade
- id
- enrollment_id (FK, unique)
- tx1, tx2, tx3, tx4        (nullable, do lecturer nhập)
- attendance_score           (do lecturer nhập)
- midterm_avg                (do lecturer nhập)
- process_score               (tự tính từ 6.3, không nhận input trực tiếp)
- exam_score                  (do training_office nhập, giữ nguyên)
- total_score                  (tự tính từ 6.4, không nhận input trực tiếp)
- updated_by, updated_at
```
 
**Ràng buộc phân quyền (giữ nguyên nguyên tắc trước):**
- Endpoint `PUT /grades/{enrollment_id}/process` — vẫn chỉ `lecturer` (đúng lớp mình dạy) được gọi, nhưng giờ nhận body gồm `tx1, tx2, tx3, tx4, attendance_score, midterm_avg` thay vì 1 số đơn — server tự tính `process_score` sau khi lưu.
- Endpoint `PUT /grades/{enrollment_id}/exam` — không đổi, chỉ `training_office`.
- Validate: tất cả các điểm thành phần (`tx1-4`, `attendance_score`, `midterm_avg`, `exam_score`) đều trong khoảng [0, 10].
## 6.6. Code mẫu (`services/grade_service.py`)
 
```python
def calculate_tx(tx_scores: list[float | None]) -> float | None:
    """TX = trung bình các cột TX có điểm, bỏ qua giá trị None."""
    valid_scores = [s for s in tx_scores if s is not None]
    if not valid_scores:
        return None
    return sum(valid_scores) / len(valid_scores)
 
 
def calculate_process_score(attendance_score: float, midterm_avg: float, tx: float) -> float:
    """process_score (TBC) = C.Cần×0.10 + TBCTN×0.30 + TX×0.60"""
    process_score = (
        attendance_score * 0.10
        + midterm_avg * 0.30
        + tx * 0.60
    )
    return round(process_score, 1)
 
 
def update_process_components(
    db,
    enrollment_id: int,
    lecturer_id: int,
    tx1: float | None = None,
    tx2: float | None = None,
    tx3: float | None = None,
    tx4: float | None = None,
    attendance_score: float | None = None,
    midterm_avg: float | None = None,
):
    grade = get_or_create_grade(db, enrollment_id)
 
    # Cập nhật các thành phần được truyền lên (giữ giá trị cũ nếu không truyền)
    if tx1 is not None: grade.tx1 = tx1
    if tx2 is not None: grade.tx2 = tx2
    if tx3 is not None: grade.tx3 = tx3
    if tx4 is not None: grade.tx4 = tx4
    if attendance_score is not None: grade.attendance_score = attendance_score
    if midterm_avg is not None: grade.midterm_avg = midterm_avg
 
    # Tự tính lại process_score nếu đủ dữ liệu bắt buộc
    tx = calculate_tx([grade.tx1, grade.tx2, grade.tx3, grade.tx4])
    if grade.attendance_score is not None and grade.midterm_avg is not None and tx is not None:
        grade.process_score = calculate_process_score(grade.attendance_score, grade.midterm_avg, tx)
 
    grade.updated_by = lecturer_id
    recalculate_total(grade)  # hàm đã có ở thiết kế trước — total_score = (process+exam)/2
    db.commit()
    return grade
```
 
## 6.7. Router cập nhật (`routers/grades.py`)
 
```python
from pydantic import BaseModel
 
class ProcessScoreInput(BaseModel):
    tx1: float | None = None
    tx2: float | None = None
    tx3: float | None = None
    tx4: float | None = None
    attendance_score: float | None = None
    midterm_avg: float | None = None
 
@router.put("/{enrollment_id}/process")
def set_process_components(
    enrollment_id: int,
    payload: ProcessScoreInput,
    db=Depends(get_db),
    user=Depends(require_role("lecturer")),
):
    for value in [payload.tx1, payload.tx2, payload.tx3, payload.tx4,
                  payload.attendance_score, payload.midterm_avg]:
        if value is not None and not (0 <= value <= 10):
            raise HTTPException(status_code=400, detail="Điểm phải trong khoảng 0-10")
 
    enrollment = get_enrollment(db, enrollment_id)
    course_class = get_course_class(db, enrollment.course_class_id)
    if course_class.lecturer_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
 
    return update_process_components(db, enrollment_id, user["user_id"], **payload.dict())
```
 
---
 
## 6.8. Điểm trung bình tích lũy — GPA (`Student.gpa`) — giữ nguyên như trước
 
```
GPA = Σ(total_score_i × credits_i) / Σ(credits_i)
```
 
với `i` chạy qua tất cả các học phần sinh viên **đã có `total_score`** (không null).
 
**Quy tắc áp dụng:**
1. Chỉ tính học phần đã có đủ `process_score` và `exam_score` (tức đã có `total_score`).
2. `credits` lấy từ bảng `Course`, không lấy từ `CourseClass`.
3. Học phần học lại/cải thiện: cần chốt quy tắc trước khi code (lấy điểm cao nhất hay lần học gần nhất) — *chưa có trong đề bài, cần xác nhận thêm.*
4. Có thể tính GPA toàn khóa hoặc theo từng kỳ (truyền `term`).
```python
def calculate_gpa(db, student_id: int, term: str | None = None) -> float:
    grades = get_completed_grades(db, student_id, term=term)  # total_score is not null
    total_weighted = sum(
        g.total_score * g.enrollment.course_class.course.credits
        for g in grades
    )
    total_credits = sum(
        g.enrollment.course_class.course.credits
        for g in grades
    )
    if total_credits == 0:
        return 0.0
    return round(total_weighted / total_credits, 2)
```
 

## 7. Bảo mật & kiểm soát truy cập

- Toàn bộ endpoint (trừ `/auth/login`) yêu cầu JWT hợp lệ qua header `Authorization: Bearer <token>`.
- Áp dụng dependency `require_role(*roles)` ở từng endpoint để giới hạn theo vai trò (xem ví dụ code phần 9).
- Với endpoint liên quan điểm/hồ sơ của MỘT sinh viên cụ thể, phải kiểm tra thêm:
  - Nếu người gọi là `student` → `student_id` phải trùng với chính họ.
  - Nếu là `lecturer` → phải đang dạy ít nhất 1 `CourseClass` mà sinh viên đó có `Enrollment`.
  - Nếu là `advisor` → sinh viên đó phải thuộc `HomeroomClass` mà họ là `advisor_id`.
- Endpoint `PUT /grades/{id}/process` chỉ chấp nhận nếu `lecturer_id` của `CourseClass` liên quan trùng với `lecturer` đang đăng nhập.
- Endpoint `PUT /grades/{id}/exam` chỉ `training_office` mới gọi được — kể cả lecturer đang dạy lớp đó cũng không được sửa điểm thi.
- Password không bao giờ lưu plaintext — dùng `passlib` (bcrypt) để hash.
- Endpoint AI (`/ai/*`) không được truyền toàn bộ DB vào prompt — chỉ truyền đúng dữ liệu của sinh viên đang yêu cầu, tránh rò rỉ dữ liệu sinh viên khác qua AI.

---

## 8. Cấu trúc thư mục đề xuất

```
training-management-system/
├── backend/
│   ├── app/
│   │   ├── main.py                # Khởi tạo FastAPI app, include routers
│   │   ├── core/
│   │   │   ├── config.py          # Biến môi trường (SUPABASE_DB_URL, SECRET_KEY, LLM_API_KEY)
│   │   │   ├── security.py        # Hàm tạo/verify JWT, hash password
│   │   │   └── database.py        # SQLAlchemy engine, session (kết nối Supabase Postgres)
│   │   ├── models/                # SQLAlchemy models (User, Student, Lecturer, Course...)
│   │   ├── schemas/                # Pydantic schemas (request/response)
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── students.py
│   │   │   ├── lecturers.py
│   │   │   ├── homeroom_classes.py
│   │   │   ├── courses.py
│   │   │   ├── course_classes.py
│   │   │   ├── enrollments.py
│   │   │   ├── grades.py
│   │   │   ├── stats.py
│   │   │   └── ai.py               # course-advice, regulation-chat (placeholder), study-summary
│   │   ├── services/
│   │   │   ├── enrollment_service.py   # logic kiểm tra điều kiện tiên quyết, trùng lịch
│   │   │   ├── grade_service.py        # tính total_score
│   │   │   ├── rag_service.py          # PLACEHOLDER — ghép pipeline RAG có sẵn vào sau
│   │   │   └── llm_service.py          # gọi LLM API (Gemini/Groq)
│   │   └── dependencies/
│   │       └── auth_dependency.py  # get_current_user, require_role, quyền theo advisor/lecturer
│   ├── alembic/                    # migration
│   ├── tests/                      # pytest
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── api/                    # hàm gọi axios/fetch tới backend
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── student/            # dashboard, đăng ký, xem điểm, chatbot
│   │   │   ├── lecturer/           # nhập điểm quá trình, xem lớp dạy
│   │   │   ├── training-office/    # quản lý toàn bộ, nhập điểm thi
│   │   │   └── advisor/            # xem các lớp hành chính được phân công
│   │   ├── context/                # AuthContext (lưu JWT, user info)
│   │   └── App.jsx
│   └── package.json
└── README.md
```

---

## 9. Ví dụ code khung (để AI code bám theo)

### 9.1. Auth dependency (`dependencies/auth_dependency.py`)
```python
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.core.config import SECRET_KEY, ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # {"sub": username, "role": ..., "user_id": ...}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn")

def require_role(*allowed_roles: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Không đủ quyền truy cập")
        return user
    return checker

def require_lecturer_owns_class(course_class_id: int):
    """Kiểm tra lecturer đang đăng nhập có phải người dạy course_class_id không."""
    def checker(db=Depends(get_db), user: dict = Depends(require_role("lecturer"))):
        course_class = get_course_class(db, course_class_id)
        if course_class.lecturer_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
        return user
    return checker

def require_advisor_owns_student(student_id: int):
    """Kiểm tra advisor đang đăng nhập có phụ trách HomeroomClass chứa student_id không."""
    def checker(db=Depends(get_db), user: dict = Depends(require_role("advisor"))):
        student = get_student(db, student_id)
        homeroom = get_homeroom_class(db, student.class_id)
        if homeroom.advisor_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="Không phải sinh viên bạn phụ trách")
        return user
    return checker
```

### 9.2. Service kiểm tra điều kiện đăng ký (`services/enrollment_service.py`)
```python
def check_enrollment_eligibility(db, student_id: int, course_class_id: int) -> tuple[bool, str]:
    course_class = get_course_class(db, course_class_id)

    # 1. Kiểm tra sĩ số
    current_count = count_enrollments(db, course_class_id)
    if current_count >= course_class.max_size:
        return False, "Lớp đã đầy sĩ số"

    # 2. Kiểm tra điều kiện tiên quyết
    prerequisites = get_prerequisites(db, course_class.course_id)
    passed_courses = get_passed_courses(db, student_id)  # total_score >= ngưỡng qua môn
    missing = [c for c in prerequisites if c not in passed_courses]
    if missing:
        return False, f"Còn thiếu điều kiện tiên quyết: {', '.join(c.name for c in missing)}"

    # 3. Kiểm tra trùng lịch với các lớp đã đăng ký trong cùng kỳ
    enrolled_classes = get_enrolled_classes_same_term(db, student_id, course_class.term)
    for other in enrolled_classes:
        if schedule_conflicts(course_class.schedule, other.schedule):
            return False, f"Trùng lịch với {other.course.name}"

    # 4. Kiểm tra đã đăng ký lớp này chưa
    if already_enrolled(db, student_id, course_class_id):
        return False, "Đã đăng ký lớp học phần này rồi"

    return True, "Hợp lệ"
```

### 9.3. Service tính điểm tổng kết (`services/grade_service.py`)
```python
def update_process_score(db, enrollment_id: int, score: float, lecturer_id: int):
    grade = get_or_create_grade(db, enrollment_id)
    grade.process_score = score
    grade.updated_by = lecturer_id
    recalculate_total(grade)
    db.commit()
    return grade

def update_exam_score(db, enrollment_id: int, score: float, staff_id: int):
    grade = get_or_create_grade(db, enrollment_id)
    grade.exam_score = score
    grade.updated_by = staff_id
    recalculate_total(grade)
    db.commit()
    return grade

def recalculate_total(grade):
    if grade.process_score is not None and grade.exam_score is not None:
        grade.total_score = round((grade.process_score + grade.exam_score) / 2, 2)
```

### 9.4. Router điểm (`routers/grades.py`)
```python
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/grades", tags=["Điểm"])

@router.put("/{enrollment_id}/process")
def set_process_score(
    enrollment_id: int,
    score: float,
    db=Depends(get_db),
    user=Depends(require_role("lecturer")),
):
    if not (0 <= score <= 10):
        raise HTTPException(status_code=400, detail="Điểm phải trong khoảng 0-10")
    enrollment = get_enrollment(db, enrollment_id)
    course_class = get_course_class(db, enrollment.course_class_id)
    if course_class.lecturer_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Không phải lớp bạn phụ trách")
    return update_process_score(db, enrollment_id, score, user["user_id"])

@router.put("/{enrollment_id}/exam")
def set_exam_score(
    enrollment_id: int,
    score: float,
    db=Depends(get_db),
    user=Depends(require_role("training_office")),
):
    if not (0 <= score <= 10):
        raise HTTPException(status_code=400, detail="Điểm phải trong khoảng 0-10")
    return update_exam_score(db, enrollment_id, score, user["user_id"])
```

### 9.5. Placeholder RAG service (`services/rag_service.py`)
```python
# PLACEHOLDER — pipeline RAG đã được triển khai riêng ở dự án chatbot quy chế.
# Khi ghép vào, thay nội dung hàm này bằng cách gọi sang module/service RAG thật
# (import trực tiếp nếu cùng codebase, hoặc gọi qua HTTP nếu để dạng service riêng).

async def answer_regulation_question(question: str) -> str:
    raise NotImplementedError("RAG chưa được tích hợp — sẽ ghép ở giai đoạn sau")
```

```python
# routers/ai.py
@router.post("/regulation-chat")
async def regulation_chat(question: str, user=Depends(get_current_user)):
    try:
        return {"answer": await answer_regulation_question(question)}
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Chức năng đang được tích hợp, chưa khả dụng")
```

---

## 10. Kế hoạch triển khai theo giai đoạn (bám theo yêu cầu SDLC của đề bài)

**Giai đoạn 1 — Phân tích & thiết kế:**
- Hoàn thiện ERD (mục 3), use case cho 4 vai trò, thiết kế API (mục 4).
- Dùng AI sinh prototype UI trang đăng ký học phần và bảng điểm (Figma hoặc React tĩnh trước).

**Giai đoạn 2 — Xây dựng chức năng quản lý:**
- Setup FastAPI project theo cấu trúc mục 8, models + Alembic migration, kết nối Supabase Postgres.
- Code CRUD cho: Student, Lecturer, HomeroomClass (kèm advisor_id), Course, CourseClass.
- Code logic `check_enrollment_eligibility` (mục 9.2) — đây là phần nghiệp vụ khó nhất, cần test kỹ.
- Code 2 endpoint điểm riêng biệt (process/exam) + `recalculate_total` (mục 9.3, 9.4).

**Giai đoạn 3 — Tích hợp AI, tối ưu prompt, kiểm thử:**
- Ghép pipeline RAG đã triển khai riêng vào endpoint `/ai/regulation-chat` (thay placeholder ở mục 9.5).
- Code endpoint `/ai/course-advice`, `/ai/study-summary`.
- Viết test case: thiếu điều kiện tiên quyết, trùng lịch, lecturer cố nhập điểm thi (kỳ vọng bị chặn 403), training_office cố nhập điểm quá trình (kỳ vọng bị chặn hoặc cho phép tùy chính sách — cần chốt rõ).
- Tối ưu prompt qua nhiều vòng, so sánh chất lượng câu trả lời trước/sau.

**Giai đoạn 4 — Hoàn thiện & triển khai:**
- Deploy backend (Render/Railway), frontend (Vercel/Netlify), DB (Supabase — connection string qua `SUPABASE_DB_URL`).
- Viết README hướng dẫn demo theo từng vai trò đăng nhập.
- Review lại bảo mật: đảm bảo không endpoint nào lộ điểm/hồ sơ sinh viên khác qua lỗi phân quyền, đặc biệt kiểm tra kỹ ranh giới `process_score` vs `exam_score`.

---

## 11. Lưu ý quan trọng cho AI khi code

1. **Không hardcode điều kiện tiên quyết/công thức điểm trong code business logic mà không tách rõ** — điều kiện tiên quyết lưu trong DB (bảng `Prerequisite`), công thức tính điểm giữ cố định `(process + exam) / 2` như mục 6 nhưng đặt thành hàm riêng `recalculate_total()` để dễ sửa nếu sau này đổi trọng số.
2. **Tuyệt đối không dùng chung 1 endpoint cho process_score và exam_score** — đây là ranh giới phân quyền quan trọng nhất của hệ thống này theo yêu cầu, phải tách endpoint và tách kiểm tra role rõ ràng.
3. **Luôn validate lại ở server**, kể cả khi gợi ý đến từ AI (mục 5.2) — AI chỉ gợi ý, không được là nguồn duy nhất quyết định ghi vào DB.
4. **RAG là placeholder** — không cần thiết kế bảng vector/embedding trong migration đầu, chỉ cần chừa endpoint `/ai/regulation-chat` trả 501 cho đến khi ghép pipeline RAG có sẵn vào.
5. **Không để lộ dữ liệu sinh viên khác** qua bất kỳ endpoint hay qua AI response — đặc biệt chú ý quyền `advisor` chỉ giới hạn trong các `HomeroomClass` mình phụ trách, quyền `lecturer` chỉ giới hạn trong các `CourseClass` mình dạy.
6. **Đặt tên bảng/trường bằng tiếng Anh, ngắn gọn** theo đúng mục 3 (`Student`, `Lecturer`, `Course`, `CourseClass`, `Enrollment`, `Grade`...), tránh đặt tên kiểu tiếng Việt có dấu gạch dưới dài.
7. Ưu tiên async cho các endpoint gọi LLM (`async def`) vì đây là I/O-bound, tránh block toàn bộ server khi nhiều người dùng dùng tính năng AI cùng lúc.
