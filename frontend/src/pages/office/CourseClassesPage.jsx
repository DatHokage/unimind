import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ListFilter, Presentation, Search } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { CourseClassRow } from "../../components/domain/CourseClassRow";
import { INPUT_CLS, LABEL_CLS, SELECT_CLS } from "../../utils/forms";

const EMPTY = { course_id: "", lecturer_id: "", term: 1, year: 2026, max_size: 40, status: "open", schedule: [] };
const EMPTY_FILTERS = { year: "", term: "", status: "", course_id: "", lecturer_id: "" };
const PAGE_SIZE = 10;

const WEEKDAYS = [
  { v: 2, label: "Thứ Hai" },
  { v: 3, label: "Thứ Ba" },
  { v: 4, label: "Thứ Tư" },
  { v: 5, label: "Thứ Năm" },
  { v: 6, label: "Thứ Sáu" },
  { v: 7, label: "Thứ Bảy" },
  { v: 8, label: "Chủ Nhật" },
];

export default function OfficeCourseClassesPage() {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  // Dropdown trong form & bộ lọc: toàn bộ học phần/giảng viên (không phân trang)
  const [courses, setCourses] = useState([]);
  const [lecturers, setLecturers] = useState([]);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
  const [filters, setFilters] = useState(EMPTY_FILTERS); // nội dung các ô lọc
  const [applied, setApplied] = useState(EMPTY_FILTERS); // bộ lọc đang áp dụng cho danh sách hiện tại
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  // Dòng đang sửa — null = chế độ mở lớp mới
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // Tăng dần mỗi lần gọi API — response của request cũ về sau bị bỏ qua
  const reqId = useRef(0);

  // Panel "Quản lý SV": lớp đang mở panel + danh sách đăng ký trong lớp đó
  const [managed, setManaged] = useState(null);
  const [managedRows, setManagedRows] = useState([]);
  const [managedLoading, setManagedLoading] = useState(false);
  const [confirmEnrollId, setConfirmEnrollId] = useState(null);
  // Tìm sinh viên để thêm vào lớp
  const [stuSearch, setStuSearch] = useState("");
  const [stuResults, setStuResults] = useState([]);
  const [pickedStudent, setPickedStudent] = useState("");

  // Server-side pagination: chỉ tải đúng các bản ghi của trang hiện tại, không filter/slice ở frontend.
  // Trả về true nếu response được áp dụng (false = request cũ bị bỏ qua).
  const load = async (pageNum, q = "", f = applied) => {
    const id = ++reqId.current;
    const params = { page: pageNum, size: PAGE_SIZE };
    if (q) params.search = q;
    if (f.year) params.year = Number(f.year);
    if (f.term) params.term = Number(f.term);
    if (f.status) params.status = f.status;
    if (f.course_id) params.course_id = Number(f.course_id);
    if (f.lecturer_id) params.lecturer_id = Number(f.lecturer_id);
    const { data } = await api.get("/course-classes", { params });
    if (id !== reqId.current) return false;
    setClasses(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return true;
  };

  useEffect(() => {
    // Danh mục cho form + bộ lọc: toàn bộ học phần/giảng viên (không phân trang)
    Promise.all([api.get("/courses/all"), api.get("/lecturers/all")])
      .then(([co, le]) => {
        setCourses(co.data);
        setLecturers(le.data);
      })
      .catch((e) => setError(errMsg(e)));
    load(0, "", EMPTY_FILTERS)
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Nút "+ Mở lớp mới" ở header là Link cùng route với state { form: 1 } —
  // bấm khi đang ở sẵn trang này không remount component nên phải theo dõi
  // location.key để mở form (location.key đổi mới sau mỗi lần điều hướng).
  useEffect(() => {
    if (location.state?.form === 1) {
      setEditing(null);
      setForm(EMPTY);
      setShowForm(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  // Tìm kiếm: luôn quay về trang đầu với từ khóa mới
  const applySearch = () => {
    const q = search;
    load(0, q, applied)
      .then((ok) => {
        if (ok) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  // Áp bộ lọc: luôn quay về trang đầu với điều kiện mới
  const applyFilters = () => {
    const f = { ...filters };
    load(0, appliedSearch, f)
      .then((ok) => {
        if (ok) setApplied(f);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch, applied).catch((e) => setError(errMsg(e)));

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
      course_id: c.course_id,
      lecturer_id: c.lecturer_id ?? "",
      term: c.term,
      year: c.year,
      max_size: c.max_size,
      status: c.status,
      schedule: c.schedule ?? [],
    });
    setShowForm(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    try {
      if (editing) {
        await api.patch(`/course-classes/${editing.id}`, {
          lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : null,
          max_size: Number(form.max_size),
          status: form.status,
          schedule: form.schedule.map((s) => ({
            weekday: Number(s.weekday),
            start_period: Number(s.start_period),
            end_period: Number(s.end_period),
            room: s.room?.trim() || null,
          })),
        });
        setSuccess(`Đã cập nhật lớp ${courses.find((c) => c.id === editing.course_id)?.code ?? ""}`);
        closeForm();
      } else {
        await api.post("/course-classes", {
          course_id: Number(form.course_id),
          lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : null,
          term: Number(form.term),
          year: Number(form.year),
          max_size: Number(form.max_size),
          status: form.status,
          schedule: form.schedule.map((s) => ({
            weekday: Number(s.weekday),
            start_period: Number(s.start_period),
            end_period: Number(s.end_period),
            room: s.room?.trim() || null,
          })),
        });
        setSuccess("Đã mở lớp học phần mới");
        setForm(EMPTY);
        setShowForm(false);
      }
      await load(page, appliedSearch, applied);
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
      await load(page, appliedSearch, applied);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  // ---- Quản lý sinh viên trong lớp ----

  const loadManagedRows = async (classId) => {
    const { data } = await api.get(`/course-classes/${classId}/enrollments`);
    setManagedRows(data);
  };

  const openManage = async (c) => {
    setError("");
    setManaged(c);
    setManagedRows([]);
    setStuSearch("");
    setStuResults([]);
    setPickedStudent("");
    setConfirmEnrollId(null);
    setManagedLoading(true);
    try {
      await loadManagedRows(c.id);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setManagedLoading(false);
    }
  };

  const searchStudents = async () => {
    setError("");
    try {
      const { data } = await api.get("/students", {
        params: { page: 0, size: 20, ...(stuSearch.trim() ? { search: stuSearch.trim() } : {}) },
      });
      setStuResults(data.data);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const addStudentToClass = async () => {
    if (!pickedStudent) return;
    setError("");
    setSuccess("");
    try {
      await api.post("/enrollments", {
        course_class_id: managed.id,
        student_id: Number(pickedStudent),
      });
      setSuccess("Đã thêm sinh viên vào lớp");
      setPickedStudent("");
      setStuSearch("");
      setStuResults([]);
      await Promise.all([loadManagedRows(managed.id), load(page, appliedSearch, applied)]);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const removeEnrollment = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.delete(`/enrollments/${id}`);
      setSuccess("Đã xóa sinh viên khỏi lớp");
      setConfirmEnrollId(null);
      await Promise.all([loadManagedRows(managed.id), load(page, appliedSearch, applied)]);
    } catch (err) {
      setError(errMsg(err));
      setConfirmEnrollId(null);
    }
  };

  // ---- Chỉnh lịch học trong form ----

  const setSession = (idx, key, value) =>
    setForm((f) => ({
      ...f,
      schedule: f.schedule.map((s, i) => (i === idx ? { ...s, [key]: value } : s)),
    }));

  const addSession = () =>
    setForm((f) => ({
      ...f,
      schedule: [...f.schedule, { weekday: 2, start_period: 1, end_period: 3, room: "" }],
    }));

  const removeSession = (idx) =>
    setForm((f) => ({ ...f, schedule: f.schedule.filter((_, i) => i !== idx) }));

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setF = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  const hasFilter = appliedSearch || Object.values(applied).some(Boolean);

  if (loading) return <Spinner />;

  return (
    <div className="space-y-4">
      <p className="text-sm text-secondary num">{totalElements} lớp học phần</p>
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
            placeholder="Tìm theo mã/tên học phần, giảng viên…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && applySearch()}
          />
        </div>
        <Button variant="secondary" onClick={applySearch}>
          Tìm
        </Button>
        <ListFilter size={15} className="text-secondary ml-2" />
        <input className={`${INPUT_CLS} w-24`} type="number" placeholder="Năm" value={filters.year} onChange={setF("year")} />
        <input className={`${INPUT_CLS} w-24`} type="number" placeholder="Kỳ" value={filters.term} onChange={setF("term")} />
        <select className={`${SELECT_CLS} w-36`} value={filters.status} onChange={setF("status")}>
          <option value="">Mọi trạng thái</option>
          <option value="open">Mở đăng ký</option>
          <option value="closed">Đóng</option>
        </select>
        <select className={`${SELECT_CLS} w-56`} value={filters.course_id} onChange={setF("course_id")}>
          <option value="">Mọi học phần</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
          ))}
        </select>
        <select className={`${SELECT_CLS} w-56`} value={filters.lecturer_id} onChange={setF("lecturer_id")}>
          <option value="">Mọi giảng viên</option>
          {lecturers.map((l) => (
            <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
          ))}
        </select>
        <Button variant="secondary" onClick={applyFilters}>
          Lọc
        </Button>
      </div>

      {showForm && (
        <Card
          title={
            editing
              ? `Sửa lớp ${courses.find((c) => c.id === editing.course_id)?.code ?? ""} · HK${editing.term}/${editing.year}`
              : "Mở lớp học phần mới"
          }
          actions={
            <Button variant="ghost" size="sm" onClick={closeForm}>
              Đóng
            </Button>
          }
        >
          <form onSubmit={submit} className="grid md:grid-cols-3 gap-3">
            <div>
              <label className={LABEL_CLS}>Học phần</label>
              <select className={SELECT_CLS} value={form.course_id} onChange={set("course_id")} required disabled={!!editing}>
                <option value="">— Chọn học phần —</option>
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Giảng viên</label>
              <select className={SELECT_CLS} value={form.lecturer_id} onChange={set("lecturer_id")}>
                <option value="">— Chọn giảng viên —</option>
                {lecturers.map((l) => (
                  <option key={l.id} value={l.id}>{l.code} — {l.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Trạng thái</label>
              <select className={SELECT_CLS} value={form.status} onChange={set("status")}>
                <option value="open">Mở đăng ký</option>
                <option value="closed">Đóng</option>
              </select>
            </div>
            <div>
              <label className={LABEL_CLS}>Kỳ (1–3)</label>
              <input className={INPUT_CLS} type="number" min="1" max="3" value={form.term} onChange={set("term")} required disabled={!!editing} />
            </div>
            <div>
              <label className={LABEL_CLS}>Năm</label>
              <input className={INPUT_CLS} type="number" value={form.year} onChange={set("year")} required disabled={!!editing} />
            </div>
            <div>
              <label className={LABEL_CLS}>Sĩ số tối đa</label>
              <input className={INPUT_CLS} type="number" min="1" value={form.max_size} onChange={set("max_size")} required />
            </div>

            {/* Lịch học */}
            <div className="md:col-span-3">
              <div className="text-sm font-medium mb-1.5">Lịch học</div>
              <div className="space-y-2">
                {form.schedule.map((s, i) => (
                  <div key={i} className="flex flex-wrap items-center gap-2">
                    <select
                      className={`${SELECT_CLS} w-32`}
                      value={s.weekday}
                      onChange={(e) => setSession(i, "weekday", e.target.value)}
                    >
                      {WEEKDAYS.map((w) => (
                        <option key={w.v} value={w.v}>{w.label}</option>
                      ))}
                    </select>
                    <input
                      className={`${INPUT_CLS} w-24`}
                      type="number"
                      min="1"
                      max="15"
                      placeholder="Tiết bắt đầu"
                      value={s.start_period}
                      onChange={(e) => setSession(i, "start_period", e.target.value)}
                      required
                    />
                    <input
                      className={`${INPUT_CLS} w-24`}
                      type="number"
                      min="1"
                      max="15"
                      placeholder="Tiết kết thúc"
                      value={s.end_period}
                      onChange={(e) => setSession(i, "end_period", e.target.value)}
                      required
                    />
                    <input
                      className={`${INPUT_CLS} w-32`}
                      placeholder="Phòng (VD: A1)"
                      value={s.room ?? ""}
                      onChange={(e) => setSession(i, "room", e.target.value)}
                    />
                    <Button variant="ghost" size="sm" onClick={() => removeSession(i)}>
                      Bỏ buổi
                    </Button>
                  </div>
                ))}
                <Button variant="secondary" size="sm" onClick={addSession}>
                  + Thêm buổi học
                </Button>
              </div>
            </div>

            <div className="md:col-span-3">
              <Button type="submit">{editing ? "Lưu thay đổi" : "Mở lớp"}</Button>
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
          sttStart={page * PAGE_SIZE + 1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Presentation size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {hasFilter ? "Không có lớp học phần nào khớp điều kiện." : "Chưa có lớp học phần nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {hasFilter
                  ? "Đổi từ khóa hoặc xóa bộ lọc."
                  : "Bấm “Mở lớp mới” ở góc trên bên phải để mở lớp đầu tiên."}
              </p>
            </div>
          }
          renderRow={(c, _i, stt) => (
            <CourseClassRow key={c.id} cls={c} showLecturer stt={stt}>
              <Cell className="text-right">
                <span className="inline-flex gap-1">
                  <Button size="sm" variant="secondary" onClick={() => startEdit(c)}>
                    Sửa
                  </Button>
                  <Button
                    size="sm"
                    variant={managed?.id === c.id ? "primary" : "ghost"}
                    onClick={() => (managed?.id === c.id ? setManaged(null) : openManage(c))}
                  >
                    Quản lý SV
                  </Button>
                  <Button
                    size="sm"
                    variant={c.status === "open" ? "danger" : "secondary"}
                    onClick={() => toggleStatus(c)}
                  >
                    {c.status === "open" ? "Đóng lớp" : "Mở lớp"}
                  </Button>
                </span>
              </Cell>
            </CourseClassRow>
          )}
        />
        <Pagination page={page} totalPages={totalPages} onPageChange={goPage} />
      </Card>

      {/* Panel quản lý sinh viên của lớp đang chọn */}
      {managed && (
        <Card
          title={`Sinh viên lớp ${managed.course_code} · HK${managed.term}/${managed.year} (${managed.enrolled_count}/${managed.max_size})`}
          actions={
            <Button variant="ghost" size="sm" onClick={() => setManaged(null)}>
              Đóng
            </Button>
          }
          padded={false}
        >
          <div className="p-4 border-b border-border">
            <div className="flex flex-wrap gap-2">
              <div className="relative">
                <Search
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none"
                />
                <input
                  className={`${INPUT_CLS} pl-9 w-72 max-w-full`}
                  placeholder="Tìm theo mã hoặc tên sinh viên…"
                  value={stuSearch}
                  onChange={(e) => setStuSearch(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchStudents()}
                />
              </div>
              <Button variant="secondary" onClick={searchStudents}>
                Tìm
              </Button>
              <select
                className={`${SELECT_CLS} w-72 max-w-full`}
                value={pickedStudent}
                onChange={(e) => setPickedStudent(e.target.value)}
              >
                <option value="">— Chọn sinh viên —</option>
                {stuResults.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </select>
              <Button onClick={addStudentToClass} disabled={!pickedStudent}>
                Thêm vào lớp
              </Button>
            </div>
            <p className="text-xs text-secondary mt-2">
              Hệ thống tự kiểm tra sĩ số, điều kiện tiên quyết và trùng lịch khi thêm.
            </p>
          </div>
          {managedLoading ? (
            <Spinner />
          ) : (
            <DataTable
              columns={[
                { key: "code", label: "Mã SV" },
                { key: "name", label: "Họ tên" },
                { key: "date", label: "Ngày đăng ký" },
                { key: "action", label: "" },
              ]}
              rows={managedRows}
              sttStart={1}
              empty={
                <p className="py-8 text-center text-sm text-secondary">
                  Chưa có sinh viên nào đăng ký lớp này.
                </p>
              }
              renderRow={(r, _i, stt) => (
                <tr key={r.id} className="border-b border-border last:border-0 hover:bg-app/60">
                  {stt}
                  <td className="px-4 py-3 text-sm font-medium">{r.student_code}</td>
                  <td className="px-4 py-3 text-sm">{r.student_name}</td>
                  <td className="px-4 py-3 text-sm num">
                    {r.enrolled_at ? new Date(r.enrolled_at).toLocaleDateString("vi-VN") : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {confirmEnrollId === r.id ? (
                      <span className="inline-flex gap-2">
                        <Button size="sm" variant="danger" onClick={() => removeEnrollment(r.id)}>
                          Chắc chắn xóa
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setConfirmEnrollId(null)}>
                          Giữ lại
                        </Button>
                      </span>
                    ) : (
                      <Button size="sm" variant="danger" onClick={() => setConfirmEnrollId(r.id)}>
                        Xóa khỏi lớp
                      </Button>
                    )}
                  </td>
                </tr>
              )}
            />
          )}
        </Card>
      )}
    </div>
  );
}
