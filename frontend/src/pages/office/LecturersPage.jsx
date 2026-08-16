import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { User } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Badge, Spinner, Alert, Button } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { code: "", name: "", department: "", account: "", password: "", role: "lecturer" };

export default function OfficeLecturersPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [lecturers, setLecturers] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = async () => {
    const { data } = await api.get("/lecturers");
    setLecturers(data);
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
    const body = {
      code: form.code.trim(),
      name: form.name.trim(),
      department: form.department.trim() || null,
    };
    if (form.account.trim()) {
      body.account = { username: form.account.trim(), password: form.password, role: form.role };
    }
    try {
      await api.post("/lecturers", body);
      setSuccess(`Đã tạo giảng viên ${body.code}${body.account ? ` + tài khoản (${form.role})` : ""}`);
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
      <p className="text-sm text-secondary num">{lecturers.length} giảng viên</p>
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
          title="Thêm giảng viên mới"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Mã GV</label>
              <input className={INPUT_CLS} placeholder="VD: GV003" value={form.code} onChange={set("code")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Họ tên</label>
              <input className={INPUT_CLS} value={form.name} onChange={set("name")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Khoa / Bộ môn</label>
              <input className={INPUT_CLS} value={form.department} onChange={set("department")} />
            </div>
            <div>
              <label className={LABEL_CLS}>Loại tài khoản</label>
              <select className={INPUT_CLS} value={form.role} onChange={set("role")}>
                <option value="lecturer">Giảng viên</option>
                <option value="advisor">Cố vấn học tập</option>
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Tài khoản đăng nhập (tùy chọn)</label>
              <input className={INPUT_CLS} value={form.account} onChange={set("account")} />
            </div>
            <div>
              <label className={LABEL_CLS}>Mật khẩu</label>
              <input className={INPUT_CLS} type="password" placeholder="≥ 6 ký tự" value={form.password} onChange={set("password")} />
            </div>
            <div className="md:col-span-2">
              <Button type="submit">Tạo giảng viên</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã GV" },
            { key: "name", label: "Họ tên" },
            { key: "department", label: "Khoa / Bộ môn" },
          ]}
          rows={lecturers}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <User size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">Chưa có giảng viên nào.</p>
              <p className="text-sm text-secondary mt-1">
                Bấm “Thêm giảng viên” ở góc trên bên phải để tạo hồ sơ đầu tiên.
              </p>
            </div>
          }
          renderRow={(l) => (
            <Row key={l.id}>
              <Cell className="font-medium">{l.code}</Cell>
              <Cell>{l.name}</Cell>
              <Cell>
                {l.department ? <Badge tone="info">{l.department}</Badge> : "—"}
              </Cell>
            </Row>
          )}
        />
      </Card>
    </div>
  );
}
