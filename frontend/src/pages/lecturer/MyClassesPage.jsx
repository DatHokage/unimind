import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Spinner, Alert, Button } from "../../components/ui";
import { CourseClassRow } from "../../components/domain/CourseClassRow";

export default function LecturerMyClassesPage() {
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/course-classes/mine")
      .then(({ data }) => setClasses(data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary">
        Các lớp học phần bạn được phân công giảng dạy.
      </p>
      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Học phần" },
            { key: "term", label: "Kỳ" },
            { key: "schedule", label: "Lịch học" },
            { key: "size", label: "Sĩ số", align: "right" },
            { key: "status", label: "Trạng thái" },
            { key: "action", label: "" },
          ]}
          rows={classes}
          sttStart={1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <BookOpen size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Bạn chưa được phân công lớp học phần nào.</p>
              <p className="text-sm text-secondary mt-1">
                Liên hệ phòng đào tạo để được phân công giảng dạy.
              </p>
            </div>
          }
          renderRow={(c, _i, stt) => (
            <CourseClassRow key={c.id} cls={c} stt={stt}>
              <Cell className="text-right">
                <Link to={`/lecturer/gradebook/${c.id}`}>
                  <Button size="sm" variant="secondary">
                    Sổ điểm quá trình →
                  </Button>
                </Link>
              </Cell>
            </CourseClassRow>
          )}
        />
      </Card>
    </div>
  );
}
