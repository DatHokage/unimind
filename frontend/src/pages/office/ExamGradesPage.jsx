import { useEffect, useState } from "react";
import { Presentation } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS, SELECT_CLS } from "../../utils/forms";
import { fmtTerm, fmtScore } from "../../utils/format";

function ExamScoreCell({ enrollmentId, initial, onSaved }) {
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
      const { data } = await api.put(`/grades/${enrollmentId}/exam`, { score });
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

export default function OfficeExamGradesPage() {
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [selected, setSelected] = useState("");
  const [rows, setRows] = useState([]);
  const [existing, setExisting] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get("/course-classes/all")
      .then(({ data }) => setClasses(data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const selectClass = async (id) => {
    setSelected(id);
    setRows([]);
    setExisting({});
    if (!id) return;
    setError("");
    try {
      const { data } = await api.get(`/course-classes/${id}/enrollments`);
      setRows(data);
      const gradeMaps = await Promise.all(
        data.map((r) =>
          api
            .get(`/grades/student/${r.student_id}`)
            .then(({ data: g }) => g.find((x) => x.enrollment_id === r.id))
            .catch(() => null)
        )
      );
      const ex = {};
      data.forEach((r, i) => {
        const g = gradeMaps[i];
        ex[r.id] = {
          exam: g?.exam_score ?? null,
          process: g?.process_score ?? null,
          total: g?.total_score ?? null,
        };
      });
      setExisting(ex);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary">
        Chỉ phòng đào tạo được nhập điểm thi; điểm tổng kết hệ thống tự tính.
      </p>
      {error && (
        <Alert kind="error" onClose={() => setError("")}>
          {error}
        </Alert>
      )}

      <Card>
        <label className={LABEL_CLS} htmlFor="class-select">
          Chọn lớp học phần
        </label>
        <select
          id="class-select"
          className={`${SELECT_CLS} max-w-md`}
          value={selected}
          onChange={(e) => selectClass(e.target.value)}
        >
          <option value="">— Chọn lớp —</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.course_code} · {fmtTerm(c.year, c.term)} · {c.lecturer_name ?? "chưa có GV"} ({c.enrolled_count}/{c.max_size})
            </option>
          ))}
        </select>
      </Card>

      {selected && (
        <Card title={`Danh sách vào điểm (${rows.length} sinh viên)`} padded={false}>
          <DataTable
            columns={[
              { key: "code", label: "Mã SV" },
              { key: "name", label: "Sinh viên" },
              { key: "process", label: "Điểm quá trình", align: "right" },
              { key: "exam", label: "Điểm thi (0–10)" },
              { key: "total", label: "Tổng kết", align: "right" },
            ]}
            rows={rows}
            sttStart={1}
            empty={
              <div className="flex flex-col items-center py-12 text-center">
                <Presentation size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
                <p className="text-sm font-medium">Lớp chưa có sinh viên nào đăng ký.</p>
                <p className="text-sm text-secondary mt-1">
                  Sinh viên đăng ký sẽ xuất hiện tại đây để vào điểm thi.
                </p>
              </div>
            }
            renderRow={(r, _i, stt) => (
              <Row key={r.id}>
                {stt}
                <Cell className="font-medium">{r.student_code}</Cell>
                <Cell>{r.student_name}</Cell>
                <NumCell>{fmtScore(existing[r.id]?.process)}</NumCell>
                <Cell>
                  <ExamScoreCell
                    enrollmentId={r.id}
                    initial={existing[r.id]?.exam}
                    onSaved={(grade) =>
                      setExisting((ex) => ({
                        ...ex,
                        [r.id]: {
                          ...ex[r.id],
                          exam: grade.exam_score,
                          total: grade.total_score,
                        },
                      }))
                    }
                  />
                </Cell>
                <NumCell className="font-semibold">{fmtScore(existing[r.id]?.total)}</NumCell>
              </Row>
            )}
          />
        </Card>
      )}
    </div>
  );
}
