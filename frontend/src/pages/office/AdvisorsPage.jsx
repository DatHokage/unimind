import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search, User } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Badge, Card, DataTable, Cell, Row, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";
import { fmtDate } from "../../utils/format";

const EMPTY = { code: "", name: "", dob: "", account: "", password: "" };
const PAGE_SIZE = 10;

/**
 * Quản lý cố vấn học tập — hồ sơ RIÊNG, không gộp với giảng viên
 * (cố vấn hỗ trợ sinh viên, không giảng dạy). CRUD qua /advisors.
 */
export default function OfficeAdvisorsPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [advisors, setAdvisors] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
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
  const load = async (pageNum, q = "") => {
    const id = ++reqId.current;
    const { data } = await api.get("/advisors", {
      params: { page: pageNum, size: PAGE_SIZE, ...(q ? { search: q } : {}) },
    });
    if (id !== reqId.current) return false;
    setAdvisors(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return true;
  };

  useEffect(() => {
    load(0, "")
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Nút "+ Thêm cố vấn" ở header là Link cùng route với state { form: 1 } —
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

  // Tìm kiếm: luôn quay về trang đầu với điều kiện mới
  const applySearch = () => {
    const q = search;
    load(0, q)
      .then((applied) => {
        if (applied) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch).catch((e) => setError(errMsg(e)));

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY);
  };

  // Nạp dữ liệu dòng vào form và mở chế độ sửa
  const startEdit = (a) => {
    setError("");
    setEditing(a);
    setForm({ code: a.code, name: a.name, dob: a.dob ?? "", account: "", password: "" });
    setShowForm(true);
    setConfirmId(null);
  };

  const doDelete = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/advisors/${id}`);
      setSuccess("Đã xóa cố vấn");
      setConfirmId(null);
      await load(page, appliedSearch);
    } catch (err) {
      setError(errMsg(err));
      setConfirmId(null);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const body = { code: form.code.trim(), name: form.name.trim(), dob: form.dob || null };
    try {
      if (editing) {
        await api.put(`/advisors/${editing.id}`, body);
        setSuccess(`Đã cập nhật cố vấn ${body.code}`);
        closeForm();
      } else {
        if (form.account.trim()) {
          // Vai trò cố định: cố vấn học tập — không chọn role như trang giảng viên
          body.account = { username: form.account.trim(), password: form.password, role: "advisor" };
        }
        await api.post("/advisors", body);
        setSuccess(`Đã tạo cố vấn ${body.code}${body.account ? " + tài khoản" : ""}`);
        setForm(EMPTY);
        setShowForm(false);
      }
      await load(page, appliedSearch);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} cố vấn học tập</p>
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
      </div>

      {showForm && (
        <Card
          title={editing ? `Sửa cố vấn ${editing.code}` : "Thêm cố vấn học tập"}
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Mã cố vấn</label>
              <input className={INPUT_CLS} placeholder="VD: DTCCV005" value={form.code} onChange={set("code")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Họ tên</label>
              <input className={INPUT_CLS} value={form.name} onChange={set("name")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Ngày sinh</label>
              <input className={INPUT_CLS} type="date" value={form.dob} onChange={set("dob")} />
            </div>
            {!editing && (
              <>
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
              <Button type="submit">{editing ? "Lưu thay đổi" : "Tạo cố vấn"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã CV" },
            { key: "name", label: "Họ tên" },
            { key: "dob", label: "Ngày sinh" },
            { key: "classes", label: "Lớp phụ trách" },
            { key: "action", label: "" },
          ]}
          rows={advisors}
          sttStart={page * PAGE_SIZE + 1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <User size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy cố vấn khớp "${appliedSearch}".` : "Chưa có cố vấn nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch
                  ? "Thử từ khóa khác hoặc xóa ô tìm kiếm."
                  : "Bấm “Thêm cố vấn” ở góc trên bên phải để tạo hồ sơ đầu tiên."}
              </p>
            </div>
          }
          renderRow={(a, _i, stt) => (
            <Row key={a.id}>
              {stt}
              <Cell className="font-medium">{a.code}</Cell>
              <Cell>{a.name}</Cell>
              <Cell className="num">{fmtDate(a.dob)}</Cell>
              <Cell>
                {a.classes?.length ? (
                  <span className="flex flex-wrap gap-1 max-w-md">
                    {a.classes.map((c) => (
                      <Badge
                        key={c.id}
                        tone="info"
                        title={[c.major_name, c.cohort ? `Khóa ${c.cohort}` : null].filter(Boolean).join(" · ") || undefined}
                      >
                        {c.name}
                      </Badge>
                    ))}
                  </span>
                ) : (
                  <span className="text-secondary">—</span>
                )}
              </Cell>
              <Cell className="text-right">
                {confirmId === a.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => doDelete(a.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => startEdit(a)}>
                      Sửa
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(a.id)}>
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
