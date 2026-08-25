import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Card, DataTable, Cell, Row, Badge, Spinner, Alert, Button } from "../../components/ui";
import { enrollmentStatus } from "../../components/domain/EnrollmentCard";
import { fmtSlot, fmtTerm, fmtDate } from "../../utils/format";

export default function MyEnrollmentsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [enrollments, setEnrollments] = useState([]);
  const [error, setError] = useState("");
  const [confirmId, setConfirmId] = useState(null);

  const load = async () => {
    const { data } = await api.get(`/enrollments/student/${user.student_id}`);
    setEnrollments(data);
  };

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const cancel = async (id) => {
    setError("");
    try {
      await api.delete(`/enrollments/${id}`);
      setConfirmId(null);
      await load();
    } catch (e) {
      setError(errMsg(e));
      setConfirmId(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary">
        Hủy đăng ký chỉ khả dụng khi lớp chưa nhập điểm.
      </p>
      {error && (
        <Alert kind="error" onClose={() => setError("")}>
          {error}
        </Alert>
      )}
      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã lớp" },
            { key: "name", label: "Học phần" },
            { key: "term", label: "Kỳ" },
            { key: "schedule", label: "Lịch học" },
            { key: "date", label: "Ngày đăng ký" },
            { key: "status", label: "Trạng thái" },
            { key: "action", label: "" },
          ]}
          rows={enrollments}
          sttStart={1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <ClipboardList size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có học phần nào được đăng ký.</p>
              <div className="mt-4">
                <Link to="/student/register">
                  <Button size="sm">Xem các lớp đang mở →</Button>
                </Link>
              </div>
            </div>
          }
          renderRow={(e, _i, stt) => {
            const st = enrollmentStatus(e.status);
            return (
              <Row key={e.id}>
                {stt}
                <Cell className="font-medium whitespace-nowrap">{e.class_code ?? e.course_code}</Cell>
                <Cell className="whitespace-normal min-w-40">{e.course_name}</Cell>
                <Cell>{fmtTerm(e.year, e.term)}</Cell>
                <Cell className="text-xs whitespace-normal">{fmtSlot(e)}</Cell>
                <Cell className="text-xs">{fmtDate(e.enrolled_at)}</Cell>
                <Cell>
                  <Badge tone={st.tone}>{st.label}</Badge>
                </Cell>
                <Cell className="text-right">
                  {confirmId === e.id ? (
                    <span className="inline-flex gap-2">
                      <Button size="sm" variant="danger" onClick={() => cancel(e.id)}>
                        Chắc chắn hủy
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                        Giữ lại
                      </Button>
                    </span>
                  ) : (
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(e.id)}>
                      Hủy đăng ký
                    </Button>
                  )}
                </Cell>
              </Row>
            );
          }}
        />
      </Card>
    </div>
  );
}
