import { DataTable, Cell, NumCell, Row, Badge } from "../ui";
import { fmtTerm, fmtScore } from "../../utils/format";

/**
 * Bảng điểm chuẩn hóa — dùng chung cho sinh viên xem bảng điểm của mình
 * và cố vấn xem bảng điểm sinh viên (components/domain, §4).
 *
 * Điểm chữ, điểm hệ 4 và kết quả Đạt/Không đạt do backend quy đổi và quyết định
 * (mục 6.8 đặc tả) — frontend chỉ hiển thị, không tự suy ra từ điểm số.
 */

const STATUS_LABEL = { đạt: "Đạt", "không đạt": "Không đạt", "chưa có điểm": "Chưa có điểm" };
const STATUS_TONE = { đạt: "success", "không đạt": "danger", "chưa có điểm": "neutral" };

export function GradeTable({ grades, empty }) {
  return (
    <DataTable
      columns={[
        { key: "code", label: "Mã HP" },
        { key: "name", label: "Học phần" },
        { key: "credits", label: "TC", align: "right" },
        { key: "term", label: "Kỳ" },
        { key: "process", label: "Quá trình", align: "right" },
        { key: "exam", label: "Thi", align: "right" },
        { key: "total", label: "Hệ 10", align: "right" },
        { key: "letter", label: "Điểm chữ", align: "center" },
        { key: "score4", label: "Hệ 4", align: "right" },
        { key: "result", label: "Kết quả" },
      ]}
      rows={grades}
      empty={empty}
      renderRow={(g) => (
        <Row key={g.enrollment_id}>
          <Cell className="font-medium">{g.course_code}</Cell>
          <Cell className="whitespace-normal min-w-40">{g.course_name}</Cell>
          <NumCell>{g.credits}</NumCell>
          <Cell>{fmtTerm(g.year, g.term)}</Cell>
          <NumCell>{fmtScore(g.process_score)}</NumCell>
          <NumCell>{fmtScore(g.exam_score)}</NumCell>
          <NumCell className="font-semibold">{fmtScore(g.total_score)}</NumCell>
          <Cell className="text-center font-medium">{g.letter_grade ?? "—"}</Cell>
          <NumCell>{g.score4 ?? "—"}</NumCell>
          <Cell>
            <Badge tone={STATUS_TONE[g.status] ?? "neutral"}>
              {STATUS_LABEL[g.status] ?? g.status}
            </Badge>
          </Cell>
        </Row>
      )}
    />
  );
}
