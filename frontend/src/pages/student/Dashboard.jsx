import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, CalendarClock, MessageCircle, ChevronRight } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Card, DataTable, Cell, Row, Spinner, Alert, StatCard, Badge } from "../../components/ui";
import { EnrollmentCard, enrollmentStatus } from "../../components/domain/EnrollmentCard";
import { fmtTerm } from "../../utils/format";

export default function StudentDashboard() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState(null);
  const [enrollments, setEnrollments] = useState([]);
  const [grades, setGrades] = useState([]);
  const [gpa, setGpa] = useState(null); // GPA hệ 4 do backend tính theo tín chỉ

  useEffect(() => {
    (async () => {
      try {
        const [p, e, g, gpaRes] = await Promise.all([
          api.get(`/students/${user.student_id}`),
          api.get(`/enrollments/student/${user.student_id}`),
          api.get(`/grades/student/${user.student_id}`),
          api.get(`/grades/student/${user.student_id}/gpa`),
        ]);
        setProfile(p.data);
        setEnrollments(e.data);
        setGrades(g.data);
        setGpa(gpaRes.data);
      } catch (err) {
        setError(errMsg(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [user.student_id]);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">
          Xin chào, {profile?.name ?? user.username}
        </h2>
        {profile && (
          <p className="text-sm text-secondary mt-0.5">
            {profile.code} · {profile.major_name ?? "—"} · Lớp {profile.class_name ?? "—"}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Học kỳ đã học" value={new Set(grades.map((g) => `${g.year}-${g.term}`)).size} />
        <StatCard label="Số lớp đăng ký" value={enrollments.length} />
        <StatCard label="Tổng số tín chỉ tích lũy" value={gpa?.accumulated_credits ?? 0} />
        <StatCard
          label="GPA tích lũy (hệ 4)"
          value={gpa?.gpa4 != null ? Number(gpa.gpa4).toFixed(2) : "—"}
          tone={gpa?.gpa4 != null && gpa.gpa4 >= 2 ? "success" : "neutral"}
        />
        <StatCard
          label="Điểm TB tích lũy (hệ 10)"
          value={gpa?.gpa10 != null ? Number(gpa.gpa10).toFixed(2) : "—"}
          tone={gpa?.gpa10 != null && gpa.gpa10 >= 5 ? "success" : "neutral"}
        />
      </div>

      <Card
        title="Đăng ký gần đây"
        actions={
          <Link
            to="/student/enrollments"
            className="text-sm text-primary hover:text-primary-hover inline-flex items-center gap-0.5"
          >
            Xem tất cả <ChevronRight size={14} />
          </Link>
        }
        padded={false}
      >
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Học phần" },
            { key: "term", label: "Kỳ" },
            { key: "status", label: "Trạng thái" },
          ]}
          rows={enrollments.slice(0, 5)}
          empty={
            <div className="py-10 text-center text-sm text-secondary">
              Chưa có học phần nào được đăng ký.{" "}
              <Link to="/student/register" className="text-primary hover:text-primary-hover font-medium">
                Xem các lớp đang mở →
              </Link>
            </div>
          }
          renderRow={(e) => (
            <Row key={e.id}>
              <Cell className="font-medium">{e.course_code}</Cell>
              <Cell>{e.course_name}</Cell>
              <Cell>{fmtTerm(e.year, e.term)}</Cell>
              <Cell>
                {(() => {
                  const st = enrollmentStatus(e.status);
                  return <Badge tone={st.tone}>{st.label}</Badge>;
                })()}
              </Cell>            </Row>
          )}
        />
      </Card>

      {/* Lớp học trong kỳ hiện tại — tận dụng luôn dữ liệu enrollments */}
      {enrollments.length > 0 && (
        <Card title="Lớp học đã đăng ký" padded={false}>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
            {enrollments.slice(0, 6).map((e) => (
              <EnrollmentCard key={e.id} enrollment={e} />
            ))}
          </div>
        </Card>
      )}

      <div className="grid md:grid-cols-3 gap-4">
        <Link
          to="/student/register"
          className="bg-surface border border-border hover:border-primary/50 rounded-lg shadow-sm p-5 flex items-start gap-3 transition-colors duration-150"
        >
          <span className="w-10 h-10 rounded-lg bg-primary-soft text-primary flex items-center justify-center shrink-0">
            <CalendarDays size={20} />
          </span>
          <span>
            <span className="block font-semibold">Đăng ký học phần</span>
            <span className="block text-sm text-secondary mt-0.5">
              Xem lớp đang mở và nhận gợi ý từ AI
            </span>
          </span>
        </Link>
        <Link
          to="/student/schedule"
          className="bg-surface border border-border hover:border-primary/50 rounded-lg shadow-sm p-5 flex items-start gap-3 transition-colors duration-150"
        >
          <span className="w-10 h-10 rounded-lg bg-primary-soft text-primary flex items-center justify-center shrink-0">
            <CalendarClock size={20} />
          </span>
          <span>
            <span className="block font-semibold">Thời khóa biểu</span>
            <span className="block text-sm text-secondary mt-0.5">
              Xem lịch học theo tuần và theo kỳ
            </span>
          </span>
        </Link>
        <Link
          to="/student/chat"
          className="bg-surface border border-border hover:border-primary/50 rounded-lg shadow-sm p-5 flex items-start gap-3 transition-colors duration-150"
        >
          <span className="w-10 h-10 rounded-lg bg-primary-soft text-primary flex items-center justify-center shrink-0">
            <MessageCircle size={20} />
          </span>
          <span>
            <span className="block font-semibold">Hỏi đáp quy chế</span>
            <span className="block text-sm text-secondary mt-0.5">
              Chatbot hỗ trợ tra cứu quy chế đào tạo
            </span>
          </span>
        </Link>
      </div>
    </div>
  );
}
