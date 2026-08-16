import { Row, Cell, NumCell, Badge } from "../ui";
import { fmtTerm, fmtSchedule } from "../../utils/format";

/** Nhãn trạng thái lớp học phần. */
export const classStatusBadge = (status) =>
  status === "open"
    ? { label: "Mở đăng ký", tone: "success" }
    : { label: "Đóng", tone: "neutral" };

/**
 * Hàng lớp học phần chuẩn hóa — dùng chung cho "Lớp học phần của tôi"
 * (giảng viên) và "Quản lý lớp học phần" (phòng đào tạo).
 * `showLecturer`: thêm cột giảng viên sau lịch học (trang phòng đào tạo).
 * `children`: các ô bổ sung riêng từng trang (thao tác đóng/mở lớp...).
 */
export function CourseClassRow({ cls, showLecturer = false, children }) {
  const st = classStatusBadge(cls.status);
  return (
    <Row>
      <Cell className="font-medium">{cls.course_code}</Cell>
      <Cell className="whitespace-normal min-w-40">{cls.course_name}</Cell>
      <Cell>{fmtTerm(cls.year, cls.term)}</Cell>
      <Cell className="text-xs whitespace-normal">{fmtSchedule(cls.schedule)}</Cell>
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
