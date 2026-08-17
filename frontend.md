# Frontend — Tổ chức bố cục & Design System

## 1. Định hướng sản phẩm

Đây là phần mềm nội bộ dùng ở môi trường công sở (phòng đào tạo, giảng viên tra cứu hằng ngày), không phải sản phẩm marketing — ưu tiên: **sạch, rõ, dễ quét thông tin nhanh, ít phân tâm**. Tránh hiệu ứng màu mè, tránh animation thừa, tránh trang trí không phục vụ mục đích đọc/thao tác. Lấy cảm hứng bố cục kiểu LMS/ERP (sidebar cố định + nội dung chính giữa màn hình) — quen thuộc với người dùng đã dùng qua các hệ thống quản lý đào tạo khác, giảm chi phí học cách dùng.

---

## 2. Design tokens

### 2.1. Màu sắc

Màu chủ đạo: **`#0095FF`** (xanh dương sáng, rõ, tin cậy — phù hợp bối cảnh công sở/giáo dục).

| Token | Hex | Dùng cho |
|---|---|---|
| `--color-primary` | `#0095FF` | Nút hành động chính, link, mục menu đang active, tiêu đề section quan trọng |
| `--color-primary-hover` | `#007ACC` | Hover/active state của nút/link chính |
| `--color-primary-soft` | `#E6F4FF` | Nền mục menu active, badge, highlight nhẹ |
| `--color-text-primary` | `#1A1A1A` | Chữ chính |
| `--color-text-secondary` | `#6B7280` | Chữ phụ, caption, placeholder |
| `--color-border` | `#E5E7EB` | Đường viền, chia section |
| `--color-bg-app` | `#F7F9FC` | Nền toàn ứng dụng (vùng nội dung) |
| `--color-bg-surface` | `#FFFFFF` | Nền card, sidebar, bảng |
| `--color-success` | `#16A34A` | Trạng thái "Đúng tiến độ", "Đã duyệt" |
| `--color-warning` | `#F59E0B` | Trạng thái "Chờ duyệt", cảnh báo nhẹ |
| `--color-danger` | `#DC2626` | Lỗi, "Từ chối", điểm dưới ngưỡng |

**Nguyên tắc dùng màu:** `#0095FF` chỉ dùng cho hành động/điều hướng (nút, link, active state) — KHÔNG dùng làm màu nền lớn tràn cả block, tránh gây chói khi dùng nhiều giờ liền (đặc điểm phần mềm công sở, dùng lâu, không phải trang landing).

### 2.2. Typography

- Font chính: **Inter** (hoặc "Be Vietnam Pro" nếu ưu tiên hiển thị tiếng Việt có dấu đẹp hơn) — sans-serif rõ ràng, hỗ trợ tốt số liệu (bảng điểm, thống kê).
- Type scale:

| Cấp | Size | Weight | Dùng cho |
|---|---|---|---|
| `text-2xl` | 24px | 600 | Tiêu đề trang (VD "Bảng điểm sinh viên") |
| `text-lg` | 18px | 600 | Tiêu đề section/card |
| `text-base` | 14px | 400 | Nội dung chính, bảng dữ liệu |
| `text-sm` | 13px | 400 | Caption, label phụ, timestamp |
| `text-xs` | 12px | 500 | Badge, tag trạng thái |

Số liệu (điểm, tín chỉ, GPA) dùng font có chữ số đều (`font-variant-numeric: tabular-nums`) để bảng điểm thẳng hàng, dễ so sánh.

### 2.3. Spacing & bo góc

- Spacing scale theo bội số 4px: `4, 8, 12, 16, 24, 32, 48`.
- Bo góc: `8px` cho card/input, `6px` cho button/badge — bo nhẹ, không bo tròn quá mức (giữ cảm giác nghiêm túc, công sở).
- Shadow: dùng rất tiết chế, chỉ 1 cấp `shadow-sm` (`0 1px 2px rgba(0,0,0,0.05)`) cho card nổi nhẹ trên nền `--color-bg-app`. Không dùng shadow đậm/nhiều lớp.

---

## 3. Bố cục tổng thể (Layout)

Theo mô hình **sidebar trái cố định + nội dung chính bên phải**, tương tự các hệ thống LMS/ERP quen thuộc:

```
┌─────────────┬──────────────────────────────────────────┐
│             │  Header (tiêu đề trang + thông tin phụ)   │
│  SIDEBAR    ├──────────────────────────────────────────┤
│  (cố định)  │                                            │
│             │         NỘI DUNG CHÍNH                     │
│  - Logo     │      (căn giữa, max-width, có padding)     │
│  - User     │                                            │
│  - Menu     │                                            │
│    (theo    │                                            │
│    role)    │                                            │
│             │                                            │
└─────────────┴──────────────────────────────────────────┘
```

- **Sidebar:** rộng cố định `260px` trên desktop, có thể thu gọn (`collapse`) còn `72px` (chỉ icon) khi người dùng bấm nút toggle — hữu ích khi làm việc với bảng dữ liệu rộng (bảng điểm nhiều cột).
- **Nội dung chính:** không tràn hết màn hình rộng — giới hạn `max-width: 1280px`, căn giữa (`margin: 0 auto`), có padding `24px` hai bên. Tránh dòng chữ/bảng kéo dài hết màn hình ultra-wide gây khó đọc.
- **Header của vùng nội dung:** hiển thị tiêu đề trang hiện tại (đổi theo route), có thể kèm breadcrumb hoặc nút hành động chính (VD "Đăng ký học phần", "Thêm sinh viên") nằm bên phải header.
- **Responsive:** dưới `768px`, sidebar chuyển thành menu ẩn/hiện (hamburger), nội dung chính chiếm toàn bộ chiều rộng.

---

## 4. Cấu trúc thư mục component

```
src/
├── layouts/
│   └── MainLayout.jsx          # Khung chung: Sidebar + Header + vùng nội dung
├── components/
│   ├── layout/
│   │   ├── Sidebar.jsx
│   │   ├── SidebarMenuItem.jsx
│   │   └── Header.jsx
│   ├── ui/                     # Component dùng chung, không gắn nghiệp vụ
│   │   ├── Button.jsx
│   │   ├── Card.jsx
│   │   ├── Badge.jsx           # Badge trạng thái (Đúng tiến độ/Chờ duyệt/...)
│   │   ├── DataTable.jsx       # Bảng dữ liệu chuẩn hóa (dùng lại cho SV/GV/điểm...)
│   │   └── EmptyState.jsx      # Trạng thái rỗng, có hướng dẫn hành động tiếp theo
│   └── domain/                 # Component gắn nghiệp vụ cụ thể
│       ├── GradeTable.jsx
│       ├── EnrollmentCard.jsx
│       └── CourseClassRow.jsx
├── config/
│   └── menuConfig.js           # Định nghĩa menu sidebar theo từng role
├── context/
│   └── AuthContext.jsx
├── api/
│   └── ...                     # hàm gọi API tới FastAPI backend
├── styles/
│   └── tokens.css              # Khai báo CSS variables theo mục 2
└── pages/
    ├── student/
    ├── lecturer/
    ├── training-office/
    └── advisor/
```

**Nguyên tắc phân chia:**
- `components/ui/`: KHÔNG biết gì về nghiệp vụ (không import khái niệm "sinh viên", "điểm"...) — chỉ nhận props chung (label, data, onClick...). Dùng lại được ở mọi trang.
- `components/domain/`: gắn với khái niệm nghiệp vụ cụ thể (Grade, Enrollment...), được build từ các `ui/` component bên dưới.
- `pages/<role>/`: mỗi role có thư mục riêng, chỉ import component cần cho vai trò đó — tránh 1 trang phải tự check "if role === ..." lan tràn khắp nơi.

---

## 5. Sidebar — chi tiết tổ chức

### 5.1. Vùng trên cùng (branding + user)
- Logo/tên hệ thống (dùng `--color-primary` cho icon/wordmark).
- Thông tin người dùng đang đăng nhập: avatar, tên, vai trò (badge nhỏ ghi rõ "Sinh viên" / "Giảng viên" / "Phòng đào tạo" / "Cố vấn") — giúp người dùng luôn biết mình đang thao tác với quyền nào, tránh nhầm lẫn (nhất là giảng viên kiêm cố vấn).

### 5.2. Vùng menu — chia nhóm theo chức năng, đổi theo role

Menu được định nghĩa tập trung tại `config/menuConfig.js`, mỗi role có 1 danh sách nhóm riêng:

| Role | Các nhóm menu |
|---|---|
| `student` | Học tập (Thời khóa biểu, Đăng ký học phần, Bảng điểm) · Trợ lý AI (Tư vấn đăng ký, Hỏi đáp quy chế) |
| `lecturer` | Giảng dạy (Lớp học phần của tôi, Nhập điểm quá trình) |
| `training_office` | Quản lý (Sinh viên, Giảng viên, Học phần, Lớp học phần, Nhập điểm thi) · Thống kê (Kết quả học tập) |
| `advisor` | Cố vấn (Lớp phụ trách, Kết quả sinh viên) |

- Mỗi nhóm có tiêu đề nhỏ (uppercase, `text-xs`, màu `--color-text-secondary`) phân cách các mục — giống cách LMS chia "HỌC TẬP" thành 1 nhóm riêng.
- Mục đang active: nền `--color-primary-soft`, chữ + icon màu `--color-primary`, có thanh dọc `3px` màu primary bên trái để nhận diện nhanh khi liếc mắt (thường gặp ở sidebar office tool).
- Icon dùng bộ nhất quán (VD `lucide-react`), kích thước cố định `18px`, không lẫn nhiều style icon khác nhau.

### 5.3. Vùng dưới cùng (tuỳ chọn)
- Nút đăng xuất, link hỗ trợ/liên hệ phòng đào tạo — đặt cố định đáy sidebar, tách biệt khỏi menu điều hướng chính bằng 1 đường `--color-border`.

---

## 6. Header vùng nội dung

- Bên trái: tiêu đề trang hiện tại (`text-2xl`, weight 600) — lấy theo route, KHÔNG lặp lại tên hệ thống (đã có ở sidebar).
- Bên phải: nút hành động chính của trang đó nếu có (VD trang "Lớp học phần" của `training_office` có nút "+ Mở lớp mới" màu `--color-primary`).
- Dưới tiêu đề có thể có breadcrumb mỏng (`text-sm`, màu secondary) khi vào sâu (VD "Sinh viên / DTC012 / Bảng điểm").

---

## 7. Bảng dữ liệu (DataTable) — thành phần dùng nhiều nhất trong hệ thống này

Vì phần lớn màn hình là bảng (danh sách sinh viên, lớp học phần, bảng điểm...), chuẩn hóa 1 component `DataTable` dùng chung:

- Header cột: nền `--color-bg-app` nhạt hơn 1 chút so với hàng dữ liệu, chữ `text-sm`, weight 600, màu secondary.
- Hàng dữ liệu: nền trắng, hover nhẹ `--color-bg-app` để dễ dò theo hàng ngang (quan trọng với bảng điểm nhiều cột).
- Cột trạng thái dùng `Badge` component với màu theo ngữ nghĩa (`success` xanh lá cho "Đúng tiến độ", `warning` vàng cho "Chờ duyệt", `danger` đỏ cho điểm dưới ngưỡng) — nhất quán với bảng màu mục 2.1.
- Cột số liệu (điểm, tín chỉ) căn phải, dùng `tabular-nums` để thẳng hàng.
- Có trạng thái rỗng (`EmptyState`) rõ ràng khi chưa có dữ liệu (VD sinh viên chưa đăng ký học phần nào) — không để bảng trống trơn không giải thích gì.

---

## 8. Nguyên tắc chữ nghĩa trong giao diện

- Nút hành động dùng động từ chủ động, đúng những gì xảy ra: "Lưu điểm", "Đăng ký học phần", "Hủy đăng ký" — không dùng từ mơ hồ như "Xác nhận", "Gửi" chung chung.
- Tên hành động giữ nhất quán xuyên suốt luồng: nút "Đăng ký học phần" → thông báo sau khi xong phải là "Đã đăng ký học phần" (không đổi thành "Thành công" chung chung).
- Thông báo lỗi nói rõ nguyên nhân + hướng xử lý, theo giọng hệ thống chứ không nhân cách hóa: VD "Không thể đăng ký: còn thiếu học phần tiên quyết [CTDL&GT]" — không viết "Ối, có lỗi rồi!".
- Trạng thái rỗng luôn có gợi ý hành động tiếp theo: VD sinh viên chưa đăng ký học phần nào → "Chưa có học phần nào được đăng ký. [Xem các lớp đang mở →]".

---

## 9. Việc KHÔNG làm (giữ đúng tinh thần công sở, sạch sẽ)

- Không dùng gradient, không dùng nhiều màu accent ngoài bảng màu đã định nghĩa ở mục 2.1.
- Không dùng animation trang trí (parallax, hiệu ứng bay vào...) — chỉ giữ transition ngắn (150–200ms) cho hover/active state để cảm giác mượt, không giật.
- Không dùng illustration/minh họa màu mè ở trang quản lý dữ liệu — nếu cần hình minh họa (VD trang trống), dùng icon đơn sắc đơn giản, không dùng ảnh minh họa nhiều màu.
- Không để sidebar hoặc header thay đổi vị trí/kích thước giữa các trang — bố cục phải ổn định tuyệt đối để người dùng quen tay, thao tác nhanh (đặc thù phần mềm dùng hằng ngày).
