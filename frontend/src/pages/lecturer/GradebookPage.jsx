import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { NotebookPen } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Spinner, Alert, Button } from "../../components/ui";
import { CourseClassRow } from "../../components/domain/CourseClassRow";
import { fmtTerm, fmtScore } from "../../utils/format";

function ScoreCell({ enrollmentId, initial, onSaved }) {
  const [value, setValue] = useState(initial ?? "");
  const [state, setState] = useState("idle"); // idle | saving | saved | error
  const [msg, setMsg] = useState("");

  useEffect(() => setValue(initial ?? ""), [initial]);

  const save = async () => {
    if (value === "") return;
    const score = Number(value);
    if (Number.isNaN(score) || score < 0 || score > 10) {
      setState("error");
      setMsg("Điểm phải từ 0 đến 10");
      return;
    }
    setState("saving");
    try {
      const { data } = await api.put(`/grades/${enrollmentId}/process`, { score });
      setState("saved");
      setMsg("");
      onSaved?.(data);
    } catch (e) {
      setState("error");
      setMsg(errMsg(e));
    }
  };

  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        step="0.1"
        min="0"
        max="10"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setState("idle");
        }}
        className="w-20 border border-border rounded-lg px-2 py-1 text-sm num bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
      />
      <Button size="sm" onClick={save} disabled={state === "saving"}>
        {state === "saving" ? "Đang lưu…" : "Lưu điểm"}
      </Button>
      {state === "saved" && <span className="text-xs text-success">✓ đã lưu</span>}
      {state === "error" && <span className="text-xs text-danger">{msg}</span>}
    </div>
  );
}

/**
 * Sổ điểm quá trình. Có :courseClassId → vào điểm luôn;
 * không (route /gradebook/select) → chọn lớp trong danh sách lớp của mình.
 */
export default function GradebookPage() {
  const { courseClassId } = useParams();

  if (!courseClassId) return <SelectClassScreen />;
  return <GradebookScreen key={courseClassId} courseClassId={courseClassId} />;
}

function SelectClassScreen() {
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
        Chọn lớp học phần để vào điểm quá trình.
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
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <NotebookPen size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Bạn chưa được phân công lớp học phần nào.</p>
              <p className="text-sm text-secondary mt-1">
                Liên hệ phòng đào tạo để được phân công giảng dạy.
              </p>
            </div>
          }
          renderRow={(c) => (
            <CourseClassRow key={c.id} cls={c}>
              <Cell className="text-right">
                <Link to={`/lecturer/gradebook/${c.id}`}>
                  <Button size="sm" variant="secondary">
                    Vào điểm →
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

function GradebookScreen({ courseClassId }) {
  const [loading, setLoading] = useState(true);
  const [cls, setCls] = useState(null);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  // enrollment_id -> { process, total } lấy từ bảng điểm từng SV
  const [existing, setExisting] = useState({});

  const load = useCallback(async () => {
    const [c, en] = await Promise.all([
      api.get(`/course-classes/${courseClassId}`),
      api.get(`/course-classes/${courseClassId}/enrollments`),
    ]);
    setCls(c.data);
    setRows(en.data);

    // Lấy điểm hiện có của từng sinh viên (song song) để điền ô nhập liệu
    const gradeMaps = await Promise.all(
      en.data.map((r) =>
        api
          .get(`/grades/student/${r.student_id}`)
          .then(({ data }) => data.find((g) => g.enrollment_id === r.id))
          .catch(() => null)
      )
    );
    const ex = {};
    en.data.forEach((r, i) => {
      const g = gradeMaps[i];
      ex[r.id] = {
        process: g?.process_score ?? null,
        total: g?.total_score ?? null,
      };
    });
    setExisting(ex);
  }, [courseClassId]);

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [load]);

  if (loading) return <Spinner />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <div className="space-y-4">
      {/* §6 — breadcrumb mỏng khi vào sâu */}
      <nav className="text-sm text-secondary">
        <Link to="/lecturer" className="hover:text-primary">
          Lớp học phần của tôi
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-primary">Sổ điểm {cls?.course_code}</span>
      </nav>

      <div>
        <h2 className="text-lg font-semibold">{cls?.course_name}</h2>
        <p className="text-sm text-secondary mt-0.5 num">
          {fmtTerm(cls?.year, cls?.term)} · {rows.length} sinh viên
        </p>
      </div>

      <Alert kind="info">
        Chỉ giảng viên dạy lớp này được nhập điểm quá trình. Điểm thi do phòng đào tạo nhập;
        điểm tổng kết hệ thống tự tính = (quá trình + thi) / 2.
      </Alert>

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Sinh viên" },
            { key: "process", label: "Điểm quá trình (0–10)" },
            { key: "total", label: "Tổng kết gần nhất", align: "right" },
          ]}
          rows={rows}
          empty={
            <div className="py-12 text-center">
              <p className="text-sm font-medium">Lớp chưa có sinh viên nào đăng ký.</p>
              <p className="text-sm text-secondary mt-1">
                Sinh viên đăng ký sẽ xuất hiện tại đây để vào điểm.
              </p>
            </div>
          }
          renderRow={(r) => (
            <Row key={r.id}>
              <Cell className="font-medium">{r.student_code}</Cell>
              <Cell>{r.student_name}</Cell>
              <Cell>
                <ScoreCell
                  enrollmentId={r.id}
                  initial={existing[r.id]?.process}
                  onSaved={(grade) =>
                    setExisting((ex) => ({
                      ...ex,
                      [r.id]: { ...ex[r.id], process: grade.process_score, total: grade.total_score },
                    }))
                  }
                />
              </Cell>
              <NumCell className="font-semibold">
                {fmtScore(existing[r.id]?.total)}
              </NumCell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
