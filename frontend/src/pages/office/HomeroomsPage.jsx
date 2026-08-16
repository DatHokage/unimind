import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ListFilter, School, Search } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, NumCell, Row, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS } from "../../utils/forms";

const EMPTY = { name: "", major_id: "", cohort: "", advisor_id: "" };
const PAGE_SIZE = 10;

export default function OfficeHomeroomsPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [homerooms, setHomerooms] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [majors, setMajors] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
  const [appliedMajor, setAppliedMajor] = useState(""); // ngành đang áp dụng
  const [appliedCohort, setAppliedCohort] = useState(""); // khóa đang áp dụng
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
  const load = async (pageNum, q = "", majorId = "", cohort = "") => {
    const id = ++reqId.current;
    const { data } = await api.get("/homeroom-classes", {
      params: {
        page: pageNum,
        size: PAGE_SIZE,
        ...(q ? { search: q } : {}),
        ...(majorId ? { major_id: Number(majorId) } : {}),
        ...(cohort ? { cohort: Number(cohort) } : {}),
      },
    });
    if (id !== reqId.current) return false;
    setHomerooms(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return true;
  };

  useEffect(() => {
    // Danh mục cho form: toàn bộ ngành + giảng viên (không phân trang)
    Promise.all([api.get("/majors/all"), api.get("/lecturers/all")])
      .then(([m, l]) => {
        setMajors(m.data);
        setLecturers(l.data);
      })
      .catch((e) => setError(errMsg(e)));
    load(0, "", "", "")
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Nút "+ Thêm lớp" ở header là Link cùng route với state { form: 1 } —
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

  // Khóa đang có trong danh sách — dữ liệu thật từ CSDL, không tự bịa
  const cohorts = useMemo(
    () => [...new Set(homerooms.map((h) => h.cohort).filter((c) => c != null))].sort(),
    [homerooms]
  );

  // Tìm kiếm/lọc: luôn quay về trang đầu với điều kiện mới
  const applySearch = () => {
    const q = search;
    load(0, q, appliedMajor, appliedCohort)
      .then((applied) => {
        if (applied) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const applyMajor = (e) => {
    const majorId = e.target.value;
    setAppliedMajor(majorId);
    load(0, appliedSearch, majorId, appliedCohort).catch((e) => setError(errMsg(e)));
  };

  const applyCohort = (e) => {
    const cohort = e.target.value;
    setAppliedCohort(cohort);
    load(0, appliedSearch, appliedMajor, cohort).catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch, appliedMajor, appliedCohort).catch((e) => setError(errMsg(e)));

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setForm(EMPTY);
  };

  // Nạp dữ liệu dòng vào form và mở chế độ sửa
  const startEdit = (h) => {
    setError("");
    setEditing(h);
    setForm({
      name: h.name,
      major_id: h.major_id ?? "",
      cohort: h.cohort ?? "",
      advisor_id: h.advisor_id ?? "",
    });
    setShowForm(true);
    setConfirmId(null);
  };

  const doDelete = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/homeroom-classes/${id}`);
      setSuccess("Đã xóa lớp hành chính");
      setConfirmId(null);
      await load(page, appliedSearch, appliedMajor, appliedCohort);
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
      name: form.name.trim(),
      major_id: form.major_id ? Number(form.major_id) : null,
      cohort: form.cohort ? Number(form.cohort) : null,
      advisor_id: form.advisor_id ? Number(form.advisor_id) : null,
    };
    try {
      if (editing) {
        await api.put(`/homeroom-classes/${editing.id}`, body);
        setSuccess(`Đã cập nhật lớp hành chính ${body.name}`);
        closeForm();
      } else {
        await api.post("/homeroom-classes", body);
        setSuccess(`Đã tạo lớp hành chính ${body.name}`);
        setForm(EMPTY);
        setShowForm(false);
      }
      await load(page, appliedSearch, appliedMajor, appliedCohort);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} lớp hành chính</p>
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
            placeholder="Tìm theo tên lớp…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applySearch()}
          />
        </div>
        <Button variant="secondary" onClick={applySearch}>
          Tìm
        </Button>
        <ListFilter size={15} className="text-secondary ml-2" />
        <select className={`${INPUT_CLS} w-56`} value={appliedMajor} onChange={applyMajor}>
          <option value="">Mọi ngành</option>
          {majors.map((m) => (
            <option key={m.id} value={m.id}>{m.code} — {m.name}</option>
          ))}
        </select>
        <select className={`${INPUT_CLS} w-36`} value={appliedCohort} onChange={applyCohort}>
          <option value="">Mọi khóa</option>
          {cohorts.map((c) => (
            <option key={c} value={c}>Khóa {c}</option>
          ))}
        </select>
      </div>

      {showForm && (
        <Card
          title={editing ? `Sửa lớp ${editing.name}` : "Thêm lớp hành chính"}
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
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
              <Button type="submit">{editing ? "Lưu thay đổi" : "Tạo lớp"}</Button>
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
            { key: "action", label: "" },
          ]}
          rows={homerooms}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <School size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy lớp khớp "${appliedSearch}".` : "Chưa có lớp hành chính nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch
                  ? "Thử từ khóa khác hoặc xóa ô tìm kiếm."
                  : "Bấm “Thêm lớp” ở góc trên bên phải để tạo lớp đầu tiên."}
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
              <Cell className="text-right">
                {confirmId === h.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => doDelete(h.id)}>
                      Chắc chắn xóa
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => startEdit(h)}>
                      Sửa
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setConfirmId(h.id)}>
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
