import { useEffect, useState } from "react";
import { Award } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Card, Spinner, Alert, StatCard, Badge } from "../../components/ui";
import { GradeTable } from "../../components/domain/GradeTable";
import { StudySummaryCard } from "../../components/domain/StudySummaryCard";
import { classifyGpa4 } from "../../utils/classification";

export default function GradesPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [grades, setGrades] = useState([]);
  const [gpa, setGpa] = useState(null); // GPA hệ 4 + hệ 10 do backend tính theo tín chỉ
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get(`/grades/student/${user.student_id}`),
      api.get(`/grades/student/${user.student_id}/gpa`),
    ])
      .then(([g, gpaRes]) => {
        setGrades(g.data);
        setGpa(gpaRes.data);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [user.student_id]);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  // Tổng tín chỉ đã học = mọi học phần đã đăng ký (kể cả chưa có điểm / trượt)
  const totalCredits = grades.reduce((s, g) => s + (g.credits ?? 0), 0);
  const rank = classifyGpa4(gpa?.gpa4);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Tổng số tín chỉ tích lũy (Đã đạt)"
          value={`${gpa?.accumulated_credits ?? 0} / ${totalCredits}`}
        />
        <StatCard
          label="Điểm TB tích lũy (hệ 10)"
          value={gpa?.gpa10 != null ? Number(gpa.gpa10).toFixed(2) : "—"}
          tone={gpa?.gpa10 != null && gpa.gpa10 >= 5 ? "success" : "neutral"}
        />
        <StatCard
          label="GPA tích lũy (hệ 4)"
          value={gpa?.gpa4 != null ? Number(gpa.gpa4).toFixed(2) : "—"}
          tone={gpa?.gpa4 != null && gpa.gpa4 >= 2 ? "success" : "neutral"}
        />
        <div className="bg-surface border border-border rounded-lg shadow-sm px-4 py-3.5">
          <div className="text-sm text-secondary">Xếp loại học lực</div>
          <div className="mt-2">
            <Badge tone={rank.tone} solid className="text-sm px-2.5 py-1">
              {rank.label}
            </Badge>
          </div>
        </div>
      </div>
      <StudySummaryCard studentId={user.student_id} />
      <Card padded={false}>
        <GradeTable
          grades={grades}
          empty={
            <div className="py-12 text-center">
              <Award size={36} strokeWidth={1.5} className="mx-auto text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có học phần nào được tính điểm.</p>
              <p className="text-sm text-secondary mt-1">
                Điểm sẽ xuất hiện sau khi bạn đăng ký học phần và giảng viên nhập điểm.
              </p>
            </div>
          }
        />
      </Card>
    </div>
  );
}
