import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Badge, Spinner, Alert } from "../../components/ui";

/** Màu tỷ lệ đạt theo ngưỡng (§2.1): dưới ngưỡng → danger. */
const passRateTone = (v) => (v == null ? "neutral" : v >= 0.7 ? "success" : v >= 0.5 ? "warning" : "danger");

export default function OfficeDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState([]);
  const [popular, setPopular] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api.get("/stats/academic-results"),
      api.get("/stats/popular-courses"),
    ])
      .then(([r, p]) => {
        setResults(r.data);
        setPopular(p.data);
      })
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);
  const num = (v) => (v == null ? "—" : Number(v).toFixed(2));

  return (
    <div className="grid lg:grid-cols-2 gap-6 items-start">
      <Card
        title="Kết quả học tập theo lớp hành chính"
        actions={
          <Link
            to="/office/students"
            className="text-sm text-primary hover:text-primary-hover inline-flex items-center gap-0.5"
          >
            Quản lý sinh viên <ChevronRight size={14} />
          </Link>
        }
        padded={false}
      >
        <DataTable
          columns={[
            { key: "class", label: "Lớp" },
            { key: "cohort", label: "Khóa" },
            { key: "students", label: "SV", align: "right" },
            { key: "graded", label: "Đã chấm", align: "right" },
            { key: "avg", label: "TB", align: "right" },
            { key: "pass", label: "Tỷ lệ đạt", align: "right" },
          ]}
          rows={results}
          renderRow={(r) => (
            <Row key={r.class_id}>
              <Cell className="font-medium">{r.class_name}</Cell>
              <Cell>{r.cohort ?? "—"}</Cell>
              <NumCell>{r.student_count}</NumCell>
              <NumCell>{r.graded_count}</NumCell>
              <NumCell>{num(r.avg_score)}</NumCell>
              <NumCell>
                <Badge tone={passRateTone(r.pass_rate)}>{pct(r.pass_rate)}</Badge>
              </NumCell>
            </Row>
          )}
        />
      </Card>

      <Card title="Học phần được đăng ký nhiều nhất" padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Học phần" },
            { key: "credits", label: "TC", align: "right" },
            { key: "count", label: "Số đăng ký", align: "right" },
          ]}
          rows={popular}
          renderRow={(r) => (
            <Row key={r.course_code}>
              <Cell className="font-medium">{r.course_code}</Cell>
              <Cell className="whitespace-normal min-w-36">{r.course_name}</Cell>
              <NumCell>{r.credits}</NumCell>
              <NumCell>{r.enrollment_count}</NumCell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
