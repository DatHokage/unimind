import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { School } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { name: "", major_id: "", cohort: "", advisor_id: "" };

export default function OfficeHomeroomsPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [homerooms, setHomerooms] = useState([]);
  const [majors, setMajors] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async () => {
    const [h, m, l] = await Promise.all([
      api.get("/homeroom-classes"),
      api.get("/majors"),
      api.get("/lecturers"),
    ]);
    setHomerooms(h.data);
    setMajors(m.data);
    setLecturers(l.data);
  };

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.post("/homeroom-classes", {
        name: form.name.trim(),
        major_id: form.major_id ? Number(form.major_id) : null,
        cohort: form.cohort ? Number(form.cohort) : null,
        advisor_id: form.advisor_id ? Number(form.advisor_id) : null,
      });
      setSuccess(`Đã tạo lớp hành chính ${form.name}`);
      setForm(EMPTY);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{homerooms.length} lớp hành chính</p>
      {error && (
        <Alert kind="error" onClose={() => setError("")}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert kind="success" onClose={() => setSuccess("")}>
          {success}
        </Alert>
      )}

      {showForm && (
        <Card
          title="Thêm lớp hành chính"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Tên lớp</label>
              <input className={INPUT_CLS} placeholder="VD: CNTT3-K13" value={form.name} onChange={set("name")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Khóa</label>
              <input className={INPUT_CLS} type="number" placeholder="VD: 2024" value={form.cohort} onChange={set("cohort")} />
            </div>
            <div>
              <label className={LABEL_CLS}>Ngành</label>
              <select className={INPUT_CLS} value={form.major_id} onChange={set("major_id")}>
                <option value="">— Chọn ngành —</option>
                {majors.map((m) => (
                  <option key={m.id} value={m.id}>{m.code} — {m.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Cố vấn (giảng viên)</label>
              <select className={INPUT_CLS} value={form.advisor_id} onChange={set("advisor_id")}>
                <option value="">— Chọn giảng viên —</option>
                {lecturers.map((l) => (
                  <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <Button type="submit">Tạo lớp</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "name", label: "Tên lớp" },
            { key: "major", label: "Ngành" },
            { key: "cohort", label: "Khóa" },
            { key: "advisor", label: "Cố vấn" },
            { key: "count", label: "Số SV", align: "right" },
          ]}
          rows={homerooms}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <School size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có lớp hành chính nào.</p>
              <p className="text-sm text-secondary mt-1">
                Bấm “Thêm lớp” ở góc trên bên phải để tạo lớp đầu tiên.
              </p>
            </div>
          }
          renderRow={(h) => (
            <Row key={h.id}>
              <Cell className="font-medium">{h.name}</Cell>
              <Cell>{h.major_name ?? "—"}</Cell>
              <Cell>{h.cohort ?? "—"}</Cell>
              <Cell>{h.advisor_name ?? "—"}</Cell>
              <NumCell>{h.student_count ?? 0}</NumCell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
