import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ListFilter, Search, User } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Badge, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { code: "", name: "", department: "", account: "", password: "", role: "lecturer" };
const PAGE_SIZE = 10;

export default function OfficeLecturersPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [lecturers, setLecturers] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
  const [appliedDept, setAppliedDept] = useState(""); // khoa/bộ môn đang áp dụng
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  // Dòng đang sửa — null = chế độ thêm mới
  const [editing, setEditing] = useState(null);
  // id dòng đang chờ xác nhận xóa
  const [confirmId, setConfirmId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // Tăng dần mỗi lần gọi API — response của request cũ về sau bị bỏ qua
  const reqId = useRef(0);

  // Server-side pagination: chỉ tải đúng các bản ghi của trang hiện tại, không filter/slice ở frontend.
  // Trả về true nếu response được áp dụng (false = request cũ bị bỏ qua).
  const load = async (pageNum, q = "", dept = "") => {
    const id = ++reqId.current;
    const { data } = await api.get("/lecturers", {
      params: { page: pageNum, size: PAGE_SIZE, ...(q ? { search: q } : {}), ...(dept ? { department: dept } : {}) },
    });
    if (id !== reqId.current) return false;
    setLecturers(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return true;
  };

  useEffect(() => {
    load(0, "", "")
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // Khoa/bộ môn đang có trong danh sách — dữ liệu thật từ CSDL, không tự bịa
  const departments = useMemo(
    () => [...new Set(lecturers.map((l) => l.department).filter(Boolean))].sort(),
    [lecturers]
  );

  // Tìm kiếm/lọc: luôn quay về trang đầu với điều kiện mới
  const applySearch = () => {
    const q = search;
    load(0, q, appliedDept)
      .then((applied) => {
        if (applied) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const applyDept = (e) => {
    const dept = e.target.value;
    setAppliedDept(dept);
    load(0, appliedSearch, dept).catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch, appliedDept).catch((e) => setError(errMsg(e)));

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
      await load(page, appliedSearch, appliedDept);
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
      await load(page, appliedSearch, appliedDept);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} giảng viên</p>
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

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none"
          />
          <input
            className={`${INPUT_CLS} pl-9 w-72 max-w-full`}
            placeholder="Tìm theo mã hoặc tên…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applySearch()}
          />
        </div>
        <Button variant="secondary" onClick={applySearch}>
          Tìm
        </Button>
        <ListFilter size={15} className="text-secondary ml-2" />
        <select className={`${INPUT_CLS} w-48`} value={appliedDept} onChange={applyDept}>
          <option value="">Mọi khoa/bộ môn</option>
          {departments.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
      </div>

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
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy giảng viên khớp "${appliedSearch}".` : "Chưa có giảng viên nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch
                  ? "Thử từ khóa khác hoặc xóa ô tìm kiếm."
                  : "Bấm “Thêm giảng viên” ở góc trên bên phải để tạo hồ sơ đầu tiên."}
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
        <Pagination page={page} totalPages={totalPages} onPageChange={goPage} />
      </Card>
    </div>
  );
}
