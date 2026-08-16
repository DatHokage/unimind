import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Award, Lightbulb, Sparkles, TriangleAlert } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, Spinner, Alert, Button, Badge } from "../../components/ui";
import { GradeTable } from "../../components/domain/GradeTable";
import { fmtDate } from "../../utils/format";
import { classifyGpa4 } from "../../utils/classification";

export default function AdvisorStudentDetailPage() {
  const { studentId } = useParams();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [grades, setGrades] = useState([]);
  const [gpa, setGpa] = useState(null); // GPA hệ 4 do backend tính theo tín chỉ
  const [error, setError] = useState("");
  const [summary, setSummary] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get(`/students/${studentId}`),
      api.get(`/grades/student/${studentId}`),
      api.get(`/grades/student/${studentId}/gpa`),
    ])
      .then(([p, g, gpaRes]) => {
        setProfile(p.data);
        setGrades(g.data);
        setGpa(gpaRes.data);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [studentId]);

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

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-6">
      {/* §6 — breadcrumb mỏng khi vào sâu */}
      <nav className="text-sm text-secondary">
        <Link to="/advisor" className="hover:text-primary">
          Lớp phụ trách
        </Link>
        <span className="mx-1.5">/</span>
        <Link
          to={profile?.class_id ? `/advisor/classes/${profile.class_id}/students` : "/advisor/results"}
          className="hover:text-primary"
        >
          {profile?.class_name ?? "Kết quả sinh viên"}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-primary">{profile?.code}</span>
      </nav>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <div>
          <h2 className="text-lg font-semibold">{profile?.name}</h2>
          <p className="text-sm text-secondary mt-0.5">
            {profile?.code} · {profile?.major_name ?? "—"} · Lớp {profile?.class_name ?? "—"} ·
            Sinh {fmtDate(profile?.dob)}
          </p>
        </div>
        <div className="ml-auto text-sm text-secondary num">
          Điểm TB tích lũy (hệ 10):{" "}
          {gpa?.gpa10 != null ? Number(gpa.gpa10).toFixed(2) : "—"} · GPA tích lũy (hệ 4):{" "}
          {gpa?.gpa4 != null ? Number(gpa.gpa4).toFixed(2) : "—"} ·{" "}
          <Badge tone={classifyGpa4(gpa?.gpa4).tone} solid>
            {classifyGpa4(gpa?.gpa4).label}
          </Badge>
        </div>
      </div>

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

      <Card title="Bảng điểm" padded={false}>
        <GradeTable
          grades={grades}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Award size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Sinh viên chưa có học phần nào được tính điểm.</p>
              <p className="text-sm text-secondary mt-1">
                Điểm sẽ xuất hiện sau khi sinh viên đăng ký học phần và có điểm.
              </p>
            </div>
          }
        />
      </Card>
    </div>
  );
}
