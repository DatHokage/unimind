import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ListFilter, Presentation } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Spinner, Alert, Button } from "../../components/ui";
import { CourseClassRow } from "../../components/domain/CourseClassRow";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { course_id: "", lecturer_id: "", term: 1, year: 2026, max_size: 40, status: "open" };

export default function OfficeCourseClassesPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [courses, setCourses] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [filters, setFilters] = useState({ year: "", term: "", status: "" });
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async (f = filters) => {
    const params = {};
    if (f.year) params.year = Number(f.year);
    if (f.term) params.term = Number(f.term);
    if (f.status) params.status = f.status;
    const [c, co, le] = await Promise.all([
      api.get("/course-classes", { params }),
      api.get("/courses"),
      api.get("/lecturers"),
    ]);
    setClasses(c.data);
    setCourses(co.data);
    setLecturers(le.data);
  };

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.post("/course-classes", {
        course_id: Number(form.course_id),
        lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : null,
        term: Number(form.term),
        year: Number(form.year),
        max_size: Number(form.max_size),
        status: form.status,
      });
      setSuccess("Đã mở lớp học phần mới");
      setForm(EMPTY);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const toggleStatus = async (c) => {
    setError("");
    try {
      await api.patch(`/course-classes/${c.id}`, {
        status: c.status === "open" ? "closed" : "open",
      });
      await load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setF = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{classes.length} lớp học phần</p>
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

      {/* Bộ lọc theo kỳ/trạng thái */}
      <div className="flex flex-wrap items-center gap-2">
        <ListFilter size={15} className="text-secondary" />
        <input className={`${INPUT_CLS} w-24`} type="number" placeholder="Năm" value={filters.year} onChange={setF("year")} />
        <input className={`${INPUT_CLS} w-24`} type="number" placeholder="Kỳ" value={filters.term} onChange={setF("term")} />
        <select className={`${INPUT_CLS} w-36`} value={filters.status} onChange={setF("status")}>
          <option value="">Mọi trạng thái</option>
          <option value="open">Mở đăng ký</option>
          <option value="closed">Đóng</option>
        </select>
        <Button variant="secondary" onClick={() => load().catch((x) => setError(errMsg(x)))}>
          Lọc
        </Button>
      </div>

      {showForm && (
        <Card
          title="Mở lớp học phần mới"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Đóng
            </Button>
          }
        >
          <p className="text-sm text-secondary mb-3">Lịch học có thể bổ sung sau khi mở lớp.</p>
          <form onSubmit={submit} className="grid md:grid-cols-3 gap-3">
            <div>
              <label className={LABEL_CLS}>Học phần</label>
              <select className={INPUT_CLS} value={form.course_id} onChange={set("course_id")} required>
                <option value="">— Chọn học phần —</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Giảng viên</label>
              <select className={INPUT_CLS} value={form.lecturer_id} onChange={set("lecturer_id")}>
                <option value="">— Chọn giảng viên —</option>
                {lecturers.map((l) => (
                  <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Trạng thái</label>
              <select className={INPUT_CLS} value={form.status} onChange={set("status")}>
                <option value="open">Mở đăng ký</option>
                <option value="closed">Đóng</option>
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Kỳ (1–3)</label>
              <input className={INPUT_CLS} type="number" min="1" max="3" value={form.term} onChange={set("term")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Năm</label>
              <input className={INPUT_CLS} type="number" value={form.year} onChange={set("year")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Sĩ số tối đa</label>
              <input className={INPUT_CLS} type="number" min="1" value={form.max_size} onChange={set("max_size")} required />
            </div>
            <div className="md:col-span-3">
              <Button type="submit">Mở lớp</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Học phần" },
            { key: "term", label: "Kỳ" },
            { key: "schedule", label: "Lịch" },
            { key: "lecturer", label: "GV" },
            { key: "size", label: "Sĩ số", align: "right" },
            { key: "status", label: "Trạng thái" },
            { key: "action", label: "" },
          ]}
          rows={classes}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Presentation size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có lớp học phần nào khớp bộ lọc.</p>
              <p className="text-sm text-secondary mt-1">
                Đổi điều kiện lọc hoặc bấm “Mở lớp mới” ở góc trên bên phải.
              </p>
            </div>
          }
          renderRow={(c) => (
            <CourseClassRow key={c.id} cls={c} showLecturer>
              <Cell className="text-right">
                <Button
                  size="sm"
                  variant={c.status === "open" ? "danger" : "secondary"}
                  onClick={() => toggleStatus(c)}
                >
                  {c.status === "open" ? "Đóng lớp" : "Mở lớp"}
                </Button>
              </Cell>
            </CourseClassRow>
          )}
        />
      </Card>
    </div>
  );
}
