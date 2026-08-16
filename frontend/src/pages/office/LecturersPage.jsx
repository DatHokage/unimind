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
  // Dòng đang sửa — null = chế độ thêm mới
  const [editing, setEditing] = useState(null);
  // id dòng đang chờ xác nhận xóa
  const [confirmId, setConfirmId] = useState(null);
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

  // Nút "+ Thêm giảng viên" ở header là Link cùng route với state { form: 1 } —
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
  const startEdit = (l) => {
    setError("");
    setEditing(l);
    setForm({
      code: l.code,
      name: l.name,
      department: l.department ?? "",
      account: "",
      password: "",
      role: "lecturer",
    });
    setShowForm(true);
    setConfirmId(null);
  };

  const doDelete = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/lecturers/${id}`);
      setSuccess("Đã xóa giảng viên");
      setConfirmId(null);
      await load();
    } catch (err) {
      setError(errMsg(err));
      setConfirmId(null);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const body = {
      code: form.code.trim(),
      name: form.name.trim(),
      department: form.department.trim() || null,
    };
    try {
      if (editing) {
        await api.put(`/lecturers/${editing.id}`, body);
        setSuccess(`Đã cập nhật giảng viên ${body.code}`);
        closeForm();
      } else {
        if (form.account.trim()) {
          body.account = { username: form.account.trim(), password: form.password, role: form.role };
        }
        await api.post("/lecturers", body);
        setSuccess(`Đã tạo giảng viên ${body.code}${body.account ? ` + tài khoản (${form.role})` : ""}`);
        setForm(EMPTY);
        setShowForm(false);
      }
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
          title={editing ? `Sửa giảng viên ${editing.code}` : "Thêm giảng viên mới"}
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
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
            {!editing && (
              <>
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
              </>
            )}
            <div className="md:col-span-2">
              <Button type="submit">{editing ? "Lưu thay đổi" : "Tạo giảng viên"}</Button>
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
            { key: "action", label: "" },
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
              <Cell className="text-right">
                {confirmId === l.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => doDelete(l.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => startEdit(l)}>
                      Sửa
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(l.id)}>
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
