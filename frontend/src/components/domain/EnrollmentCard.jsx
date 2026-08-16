import { Badge } from "../ui";
import { fmtTerm, fmtSchedule } from "../../utils/format";

/** Nhãn + màu trạng thái đăng ký nhất quán xuyên suốt hệ thống (§8). */
export const ENROLLMENT_STATUS = {
  approved: { label: "Đã duyệt", tone: "success" },
  pending: { label: "Chờ duyệt", tone: "warning" },
  rejected: { label: "Từ chối", tone: "danger" },
  cancelled: { label: "Đã hủy", tone: "neutral" },
};

export const enrollmentStatus = (status) =>
  ENROLLMENT_STATUS[status] ?? { label: status, tone: "neutral" };

/**
 * Thẻ học phần đã đăng ký — hiển thị trên trang tổng quan của sinh viên.
 */
export function EnrollmentCard({ enrollment: e }) {
  const st = enrollmentStatus(e.status);
  return (
    <div className="bg-surface border border-border rounded-lg shadow-sm p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">{e.course_code}</span>
        <Badge tone={st.tone}>{st.label}</Badge>
      </div>
      <div className="text-sm truncate" title={e.course_name}>
        {e.course_name}
      </div>
      <div className="text-xs text-secondary">
        {fmtTerm(e.year, e.term)} · {fmtSchedule(e.schedule)}
      </div>
    </div>
  );
}
