import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { Library } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Badge, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { code: "", name: "", credits: 3, counted_in_gpa: true, prerequisite_course_ids: [] };

export default function OfficeCoursesPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [courses, setCourses] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  // Dòng đang sửa — null = chế độ thêm mới
  const [editing, setEditing] = useState(null);
  // id dòng đang chờ xác nhận xóa
  const [confirmId, setConfirmId] = useState(null);
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

  // Nút "+ Thêm học phần" ở header là Link cùng route với state { form: 1 } —
  // bấm khi đang ở sẵn trang này không remount component nên phải theo dõi
  // location.key để mở form (location.key đổi mới sau mỗi lần điều hướng).
  useEffect(() => {
    if (location.state?.form === 1) {
      setEditing(null);
      setConfirmId(null);
      setForm(EMPTY);
      setShowForm(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY);
  };

  // Nạp dữ liệu dòng vào form và mở chế độ sửa
  const startEdit = (c) => {
    setError("");
    setEditing(c);
    setForm({
      code: c.code,
      name: c.name,
      credits: c.credits,
      counted_in_gpa: c.counted_in_gpa,
      prerequisite_course_ids: (c.prerequisites ?? []).map((p) => p.id),
    });
    setShowForm(true);
    setConfirmId(null);
  };

  const doDelete = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/courses/${id}`);
      setSuccess("Đã xóa học phần");
      setConfirmId(null);
      await load();
    } catch (err) {
      setError(errMsg(err));
      setConfirmId(null);
    }
  };

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
    const body = {
      name: form.name.trim(),
      credits: Number(form.credits),
      counted_in_gpa: form.counted_in_gpa,
      prerequisite_course_ids: form.prerequisite_course_ids,
    };
    try {
      if (editing) {
        await api.put(`/courses/${editing.id}`, body);
        setSuccess(`Đã cập nhật học phần ${editing.code}`);
        closeForm();
      } else {
        await api.post("/courses", { ...body, code: form.code.trim() });
        setSuccess(`Đã tạo học phần ${form.code}`);
        setForm(EMPTY);
        setShowForm(false);
      }
      await load();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  // Danh sách checkbox tiên quyết — khi sửa thì loại chính học phần đang sửa
  const prereqOptions = editing ? courses.filter((c) => c.id !== editing.id) : courses;

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
          title={editing ? `Sửa học phần ${editing.code}` : "Thêm học phần mới"}
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="space-y-3">
            <div className="grid md:grid-cols-3 gap-3">
              <div>
                <label className={LABEL_CLS}>Mã HP</label>
                <input
                  className={INPUT_CLS}
                  placeholder="VD: MMT"
                  value={form.code}
                  onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                  required
                  disabled={!!editing}
                />
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
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.counted_in_gpa}
                onChange={(e) => setForm((f) => ({ ...f, counted_in_gpa: e.target.checked }))}
              />
              Tính vào GPA tích lũy
            </label>
            <div>
              <div className="text-sm font-medium mb-1.5">Học phần tiên quyết (chọn nhiều)</div>
              <div className="flex flex-wrap gap-2">
                {prereqOptions.map((c) => (
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
                {prereqOptions.length === 0 && (
                  <span className="text-xs text-secondary">Chưa có học phần nào để chọn.</span>
                )}
              </div>
            </div>
            <Button type="submit">{editing ? "Lưu thay đổi" : "Tạo học phần"}</Button>
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
            { key: "action", label: "" },
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
              <Cell className="text-right">
                {confirmId === c.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => doDelete(c.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => startEdit(c)}>
                      Sửa
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(c.id)}>
                      Xóa
                    </Button>
                  </span>
                )}
              </Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
