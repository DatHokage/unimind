import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search, Users } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Badge, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";
import { fmtDate } from "../../utils/format";

const EMPTY = { code: "", name: "", dob: "", major_id: "", class_id: "", account: "", password: "" };
const PAGE_SIZE = 20;

export default function OfficeStudentsPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [students, setStudents] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [majors, setMajors] = useState([]);
  const [homerooms, setHomerooms] = useState([]);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
  const [form, setForm] = useState(EMPTY);
  // Nút "+ Thêm sinh viên" ở header chuyển state { form: 1 } để mở form
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // Tăng dần mỗi lần gọi API — response của request cũ về sau bị bỏ qua
  const reqId = useRef(0);

  // Server-side pagination: chỉ tải đúng các bản ghi của trang hiện tại, không filter/slice ở frontend.
  // Trả về true nếu response được áp dụng (false = request cũ bị bỏ qua).
  const load = async (pageNum, q = "") => {
    const id = ++reqId.current;
    const { data } = await api.get("/students", {
      params: { page: pageNum, size: PAGE_SIZE, ...(q ? { search: q } : {}) },
    });
    if (id !== reqId.current) return false;
    setStudents(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return true;
  };

  useEffect(() => {
    Promise.all([api.get("/majors"), api.get("/homeroom-classes")])
      .then(([m, h]) => {
        setMajors(m.data);
        setHomerooms(h.data);
      })
      .catch((e) => setError(errMsg(e)));
    load(0, "")
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tìm kiếm: luôn quay về trang đầu với từ khóa mới
  const applySearch = () => {
    const q = search;
    load(0, q)
      .then((applied) => {
        if (applied) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch).catch((e) => setError(errMsg(e)));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const body = {
      code: form.code.trim(),
      name: form.name.trim(),
      dob: form.dob || null,
      major_id: form.major_id ? Number(form.major_id) : null,
      class_id: form.class_id ? Number(form.class_id) : null,
    };
    if (form.account.trim()) {
      body.account = { username: form.account.trim(), password: form.password };
    }
    try {
      await api.post("/students", body);
      setSuccess(`Đã tạo sinh viên ${body.code}${body.account ? " + tài khoản" : ""}`);
      setForm(EMPTY);
      setShowForm(false);
      await load(page, appliedSearch);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} sinh viên</p>
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

      <div className="flex gap-2">
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
          title="Thêm sinh viên mới"
          actions={
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Mã SV</label>
              <input className={INPUT_CLS} placeholder="VD: SV004" value={form.code} onChange={set("code")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Họ tên</label>
              <input className={INPUT_CLS} value={form.name} onChange={set("name")} required />
            </div>
            <div>
              <label className={LABEL_CLS}>Ngày sinh</label>
              <input className={INPUT_CLS} type="date" value={form.dob} onChange={set("dob")} />
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
              <label className={LABEL_CLS}>Lớp hành chính</label>
              <select className={INPUT_CLS} value={form.class_id} onChange={set("class_id")}>
                <option value="">— Chọn lớp —</option>
                {homerooms.map((h) => (
                  <option key={h.id} value={h.id}>{h.name}</option>
                ))}
              </select>
            </div>
            <div />
            <div>
              <label className={LABEL_CLS}>Tài khoản đăng nhập (tùy chọn)</label>
              <input className={INPUT_CLS} value={form.account} onChange={set("account")} />
            </div>
            <div>
              <label className={LABEL_CLS}>Mật khẩu</label>
              <input className={INPUT_CLS} type="password" placeholder="≥ 6 ký tự" value={form.password} onChange={set("password")} />
            </div>
            <div className="md:col-span-2">
              <Button type="submit">Tạo sinh viên</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Họ tên" },
            { key: "dob", label: "Ngày sinh" },
            { key: "major", label: "Ngành" },
            { key: "class", label: "Lớp" },
          ]}
          rows={students}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Users size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy sinh viên khớp “${appliedSearch}”.` : "Chưa có sinh viên nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch
                  ? "Thử từ khóa khác hoặc xóa ô tìm kiếm."
                  : "Bấm “Thêm sinh viên” ở góc trên bên phải để tạo hồ sơ đầu tiên."}
              </p>
            </div>
          }
          renderRow={(s) => (
            <Row key={s.id}>
              <Cell className="font-medium">{s.code}</Cell>
              <Cell>{s.name}</Cell>
              <Cell className="num">{fmtDate(s.dob)}</Cell>
              <Cell>{s.major_name ?? "—"}</Cell>
              <Cell>
                {s.class_name ? <Badge tone="info">{s.class_name}</Badge> : "—"}
              </Cell>
            </Row>
          )}
        />
        <Pagination page={page} totalPages={totalPages} onPageChange={goPage} />
      </Card>
    </div>
  );
}
