import { Row, Cell, NumCell, Badge } from "../ui";
import { fmtTerm, fmtSlot } from "../../utils/format";

/** Nhãn trạng thái lớp học phần: open → closed → completed (khóa vĩnh viễn). */
export const classStatusBadge = (status) =>
  status === "open"
    ? { label: "Mở đăng ký", tone: "success" }
    : status === "completed"
      ? { label: "Hoàn thành", tone: "info" }
      : { label: "Đóng", tone: "neutral" };

/**
 * Hàng lớp học phần chuẩn hóa — dùng chung cho "Lớp học phần của tôi"
 * (giảng viên) và "Quản lý lớp học phần" (phòng đào tạo).
 * `showLecturer`: thêm cột giảng viên sau lịch học (trang phòng đào tạo).
 * `stt`: ô số thứ tự do DataTable render sẵn (chỉ trang admin truyền vào).
 * `children`: các ô bổ sung riêng từng trang (thao tác đóng/mở lớp...).
 */
export function CourseClassRow({ cls, showLecturer = false, stt = null, children }) {
  const st = classStatusBadge(cls.status);
  return (
    <Row>
      {stt}
      <Cell className="font-medium whitespace-nowrap">{cls.code}</Cell>
      <Cell className="whitespace-normal min-w-40">{cls.course_name}</Cell>
      <NumCell>{cls.credits ?? "—"}</NumCell>
      <Cell>{fmtTerm(cls.year, cls.term)}</Cell>
      <Cell className="text-xs whitespace-normal">{fmtSlot(cls)}</Cell>
      {showLecturer && <Cell>{cls.lecturer_name ?? "—"}</Cell>}
      <NumCell>
        {cls.enrolled_count}/{cls.max_size}
      </NumCell>
      <Cell>
        <Badge tone={st.tone}>{st.label}</Badge>
      </Cell>
      {children}
    </Row>
  );
}
