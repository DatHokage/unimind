import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Lightbulb, ShieldCheck, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Alert, Button, Card, Spinner } from "../../components/ui";

export default function AdvisorClassOverviewPage() {
  const { classId } = useParams();
  const [loading, setLoading] = useState(true);
  const [klass, setKlass] = useState(null);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  useEffect(() => {
    api
      .get(`/homeroom-classes/${classId}`)
      .then(({ data }) => setKlass(data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [classId]);

  const askAI = async () => {
    setAiError("");
    setAiLoading(true);
    try {
      const { data } = await api.post("/ai/class-overview", { class_id: Number(classId) });
      setOverview(data);
    } catch (e) {
      setAiError(errMsg(e));
    } finally {
      setAiLoading(false);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  const stats = overview?.stats;

  return (
    <div className="space-y-6">
      <nav className="text-sm text-secondary">
        <Link to="/advisor" className="hover:text-primary">
          Lớp phụ trách
        </Link>
        <span className="mx-1.5">/</span>
        <Link to={`/advisor/classes/${classId}/students`} className="hover:text-primary">
          {klass?.name ?? "Sinh viên"}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-primary">AI đánh giá</span>
      </nav>

      <div>
        <h2 className="text-lg font-semibold">AI đánh giá lớp {klass?.name}</h2>
        <p className="text-sm text-secondary mt-0.5">
          {klass?.major_name ?? "—"} · Khóa {klass?.cohort ?? "—"} · CVHT{" "}
          {klass?.advisor_name ?? "—"} · Sĩ số {klass?.student_count ?? 0}
        </p>
      </div>

      <Card
        title={
          <span className="inline-flex items-center gap-2">
            <Sparkles size={18} className="text-primary" /> Nhận xét tổng quan của AI
          </span>
        }
        actions={
          <Button onClick={askAI} disabled={aiLoading} size="sm">
            {aiLoading ? "AI đang phân tích…" : overview ? "Phân tích lại" : "Phân tích bằng AI"}
          </Button>
        }
      >
        {aiError && <Alert kind="error">{aiError}</Alert>}
        {!overview && !aiError && (
          <p className="text-sm text-secondary">
            AI nhìn lại TỔNG THỂ lớp: bức tranh điểm số chung, những gì lớp đang làm tốt và những
            điểm cần lưu ý — không bình luận từng sinh viên.
          </p>
        )}
        {overview && (
          <div className="space-y-3 text-sm">
            {overview.fallback && (
              <Alert kind="warn">
                AI tạm thời không khả dụng — vẫn hiển thị số liệu tổng hợp hệ thống tính bên dưới.
              </Alert>
            )}
            {overview.summary && <p className="whitespace-pre-line">{overview.summary}</p>}
            {overview.strengths?.length > 0 && (
              <div>
                <h4 className="font-semibold text-success mb-1 inline-flex items-center gap-1.5">
                  <ThumbsUp size={14} /> Điểm mạnh
                </h4>
                <ul className="list-disc pl-5 space-y-0.5">
                  {overview.strengths.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
            {overview.weaknesses?.length > 0 && (
              <div>
                <h4 className="font-semibold text-warning mb-1 inline-flex items-center gap-1.5">
                  <ThumbsDown size={14} /> Điểm yếu
                </h4>
                <ul className="list-disc pl-5 space-y-0.5">
                  {overview.weaknesses.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}
            {overview.suggestions?.length > 0 && (
              <div>
                <h4 className="font-semibold text-primary mb-1 inline-flex items-center gap-1.5">
                  <Lightbulb size={14} /> Gợi ý cho cố vấn
                </h4>
                <ul className="list-disc pl-5 space-y-0.5">
                  {overview.suggestions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {stats && (
          <div className="mt-4 pt-3 border-t border-border flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <span className="text-secondary num">GPA TB lớp: {stats.avg_gpa4 ?? "—"} (hệ 4) · {stats.avg_gpa10 ?? "—"} (hệ 10)</span>
            <span className="text-secondary num">
              Có điểm: {stats.students_with_grades}/{stats.class_size}
            </span>
            <span className="num">
              Nguy cơ cao <span className="text-danger font-medium">{stats.risk_counts.high}</span>
            </span>
            <span className="num">
              Trung bình <span className="text-warning font-medium">{stats.risk_counts.medium}</span>
            </span>
            <span className="num">
              Ổn định <span className="text-success font-medium">{stats.risk_counts.low}</span>
            </span>
            {stats.students_without_grades > 0 && (
              <span className="num text-secondary">
                Chưa có điểm <span className="font-medium">{stats.students_without_grades}</span>
              </span>
            )}
          </div>
        )}
        <p className="mt-4 pt-3 border-t border-border text-xs text-secondary inline-flex items-start gap-1.5">
          <ShieldCheck size={14} className="shrink-0 mt-0.5 text-success" />
          Chỉ số liệu TỔNG HỢP của cả lớp được gửi tới AI (không kèm dữ liệu riêng của bất kỳ sinh
          viên nào, kể cả tên/MSSV) — nhận xét mang tính tham khảo, không thay thế kết luận của cố vấn.
        </p>
      </Card>
    </div>
  );
}
