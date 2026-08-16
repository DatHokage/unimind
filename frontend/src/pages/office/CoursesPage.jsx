import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Library } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Badge, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { code: "", name: "", credits: 3, prerequisite_course_ids: [] };

export default function OfficeCoursesPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [courses, setCourses] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async () => {
    const { data } = await api.get("/courses");
    setCourses(data);
  };

  useEffect(() => {
    load()
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, []);

  const togglePrereq = (id) =>
    setForm((f) => ({
      ...f,
      prerequisite_course_ids: f.prerequisite_course_ids.includes(id)
        ? f.prerequisite_course_ids.filter((x) => x !== id)
        : [...f.prerequisite_course_ids, id],
    }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      await api.post("/courses", {
        code: form.code.trim(),
        name: form.name.trim(),
        credits: Number(form.credits),
        prerequisite_course_ids: form.prerequisite_course_ids,
      });
      setSuccess(`Đã tạo học phần ${form.code}`);
      setForm(EMPTY);
      setShowForm(false);
      await load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">
        {courses.length} học phần · học phần tiên quyết được hệ thống kiểm tra tự động khi sinh viên đăng ký.
      </p>
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
          title="Thêm học phần mới"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="space-y-3">
            <div className="grid md:grid-cols-3 gap-3">
              <div>
                <label className={LABEL_CLS}>Mã HP</label>
                <input className={INPUT_CLS} placeholder="VD: MMT" value={form.code} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} required />
              </div>
              <div>
                <label className={LABEL_CLS}>Tên học phần</label>
                <input className={INPUT_CLS} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} required />
              </div>
              <div>
                <label className={LABEL_CLS}>Số tín chỉ</label>
                <input className={INPUT_CLS} type="number" min="1" max="20" value={form.credits} onChange={(e) => setForm((f) => ({ ...f, credits: e.target.value }))} />
              </div>
            </div>
            <div>
              <div className="text-sm font-medium mb-1.5">Học phần tiên quyết (chọn nhiều)</div>
              <div className="flex flex-wrap gap-2">
                {courses.map((c) => (
                  <label
                    key={c.id}
                    className={`flex items-center gap-1.5 text-sm rounded-md border px-2.5 py-1.5 cursor-pointer transition-colors duration-150 ${
                      form.prerequisite_course_ids.includes(c.id)
                        ? "border-primary bg-primary-soft text-primary"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={form.prerequisite_course_ids.includes(c.id)}
                      onChange={() => togglePrereq(c.id)}
                    />
                    {c.code}
                  </label>
                ))}
                {courses.length === 0 && (
                  <span className="text-xs text-secondary">Chưa có học phần nào để chọn.</span>
                )}
              </div>
            </div>
            <Button type="submit">Tạo học phần</Button>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã HP" },
            { key: "name", label: "Tên học phần" },
            { key: "credits", label: "TC", align: "right" },
            { key: "prereq", label: "Tiên quyết" },
          ]}
          rows={courses}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Library size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có học phần nào.</p>
              <p className="text-sm text-secondary mt-1">
                Bấm “Thêm học phần” ở góc trên bên phải để tạo học phần đầu tiên.
              </p>
            </div>
          }
          renderRow={(c) => (
            <Row key={c.id}>
              <Cell className="font-medium">{c.code}</Cell>
              <Cell className="whitespace-normal min-w-40">{c.name}</Cell>
              <NumCell>{c.credits}</NumCell>
              <Cell>
                {c.prerequisites?.length ? (
                  <span className="flex flex-wrap gap-1">
                    {c.prerequisites.map((p) => (
                      <Badge key={p.id} tone="warning">{p.code}</Badge>
                    ))}
                  </span>
                ) : (
                  "—"
                )}
              </Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
