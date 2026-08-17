import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { School } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Spinner, Alert, Button } from "../../components/ui";

export default function AdvisorMyClassesPage() {
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/homeroom-classes/mine")
      .then(({ data }) => setClasses(data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary">
        Các lớp hành chính bạn được phân công phụ trách.
      </p>
      <Card padded={false}>
        <DataTable
          columns={[
            { key: "name", label: "Tên lớp" },
            { key: "major", label: "Ngành" },
            { key: "cohort", label: "Khóa" },
            { key: "count", label: "Số sinh viên", align: "right" },
            { key: "action", label: "" },
          ]}
          rows={classes}
          sttStart={1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <School size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Bạn chưa được phân công lớp phụ trách.</p>
              <p className="text-sm text-secondary mt-1">
                Liên hệ phòng đào tạo để được phân công chủ nhiệm lớp.
              </p>
            </div>
          }
          renderRow={(c, _i, stt) => (
            <Row key={c.id}>
              {stt}
              <Cell className="font-medium">{c.name}</Cell>
              <Cell>{c.major_name ?? "—"}</Cell>
              <Cell>{c.cohort ?? "—"}</Cell>
              <NumCell>{c.student_count ?? 0}</NumCell>
              <Cell className="text-right">
                <Link to={`/advisor/classes/${c.id}/students`}>
                  <Button size="sm" variant="secondary">
                    Xem sinh viên →
                  </Button>
                </Link>
              </Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
