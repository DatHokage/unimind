import { useState } from "react";
import { Lightbulb, Sparkles, TriangleAlert } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, Alert, Button } from "../ui";

/**
 * Panel AI tóm tắt kết quả học tập (đặc tả §5.3) — dùng chung cho
 * sinh viên (trang bảng điểm) và cố vấn (hồ sơ sinh viên).
 * Backend tự chặn quyền: sinh viên chỉ xem của mình, advisor chỉ lớp phụ trách.
 */
export function StudySummaryCard({ studentId }) {
  const [summary, setSummary] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const askAI = async () => {
    setAiError("");
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/study-summary", {
        student_id: Number(studentId),
      });
      setSummary(data);
    } catch (e) {
      setAiError(errMsg(e));
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-2">
          <Sparkles size={18} className="text-primary" /> AI nhận xét tình hình học tập
        </span>
      }
      actions={
        <Button onClick={askAI} disabled={aiLoading} size="sm">
          {aiLoading ? "AI đang phân tích…" : "Tạo nhận xét"}
        </Button>
      }
    >
      {aiError && <Alert kind="error">{aiError}</Alert>}
      {!summary && !aiError && (
        <p className="text-sm text-secondary">
          AI tổng hợp kết quả các kỳ, cảnh báo môn điểm thấp và gợi ý hướng cải thiện.
        </p>
      )}
      {summary && (
        <div className="space-y-3 text-sm">
          {summary.fallback && (
            <Alert kind="warn">
              AI tạm thời không khả dụng — hiển thị số liệu hệ thống tính sẵn bên dưới.
            </Alert>
          )}
          {summary.summary && <p className="whitespace-pre-line">{summary.summary}</p>}
          {summary.warnings?.length > 0 && (
            <div>
              <h4 className="font-semibold text-danger mb-1 inline-flex items-center gap-1.5">
                <TriangleAlert size={14} /> Cảnh báo
              </h4>
              <ul className="list-disc pl-5 space-y-0.5">
                {summary.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {summary.suggestions?.length > 0 && (
            <div>
              <h4 className="font-semibold text-success mb-1 inline-flex items-center gap-1.5">
                <Lightbulb size={14} /> Gợi ý
              </h4>
              <ul className="list-disc pl-5 space-y-0.5">
                {summary.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {summary.stats?.overall_gpa != null && (
            <p className="text-secondary num">
              Số liệu hệ thống: GPA hệ 4 {summary.stats.overall_gpa} ·{" "}
              {summary.stats.terms?.length ?? 0} học kỳ đã đăng ký
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
