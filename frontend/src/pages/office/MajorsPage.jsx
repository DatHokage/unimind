import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { BookMarked, Search } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { code: "", name: "" };
const PAGE_SIZE = 10;

export default function OfficeMajorsPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [majors, setMajors] = useState([]);
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
    const { data } = await api.get("/majors", {
      params: { page: pageNum, size: PAGE_SIZE, ...(q ? { search: q } : {}) },
    });
    if (id !== reqId.current) return false;
    setMajors(data.data);
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

  // Nút "+ Thêm ngành" ở header là Link cùng route với state { form: 1 } —
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

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY);
  };

  // Nạp dữ liệu dòng vào form và mở chế độ sửa
  const startEdit = (m) => {
    setError("");
    setEditing(m);
    setForm({ code: m.code, name: m.name });
    setShowForm(true);
    setConfirmId(null);
  };

  const doDelete = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/majors/${id}`);
      setSuccess("Đã xóa ngành học");
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
    try {
      if (editing) {
        // Mã ngành không đổi sau khi tạo — chỉ sửa tên
        await api.put(`/majors/${editing.id}`, { name: form.name.trim() });
        setSuccess(`Đã cập nhật ngành ${editing.code}`);
        closeForm();
      } else {
        await api.post("/majors", { code: form.code.trim(), name: form.name.trim() });
        setSuccess(`Đã tạo ngành ${form.code}`);
        setForm(EMPTY);
        setShowForm(false);
      }
      await load(page, appliedSearch);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} ngành học</p>
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
            placeholder="Tìm theo mã hoặc tên ngành…"
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
          title={editing ? `Sửa ngành ${editing.code}` : "Thêm ngành học mới"}
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Mã ngành</label>
              <input
                className={INPUT_CLS}
                placeholder="VD: CNTT"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                required
                disabled={!!editing}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>Tên ngành</label>
              <input
                className={INPUT_CLS}
                placeholder="VD: Công nghệ thông tin"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                required
              />
            </div>
            <div className="md:col-span-2">
              <Button type="submit">{editing ? "Lưu thay đổi" : "Tạo ngành"}</Button>
            </div>
          </form>
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã ngành" },
            { key: "name", label: "Tên ngành" },
            { key: "action", label: "" },
          ]}
          rows={majors}
          sttStart={page * PAGE_SIZE + 1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <BookMarked size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy ngành học khớp "${appliedSearch}".` : "Chưa có ngành học nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch
                  ? "Thử từ khóa khác hoặc xóa ô tìm kiếm."
                  : "Bấm “Thêm ngành” ở góc trên bên phải để tạo ngành đầu tiên."}
              </p>
            </div>
          }
          renderRow={(m, _i, stt) => (
            <Row key={m.id}>
              {stt}
              <Cell className="font-medium">{m.code}</Cell>
              <Cell>{m.name}</Cell>
              <Cell className="text-right">
                {confirmId === m.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => doDelete(m.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => startEdit(m)}>
                      Sửa
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(m.id)}>
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
