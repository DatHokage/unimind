import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ListFilter, Presentation, Search } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { CourseClassRow } from "../../components/domain/CourseClassRow";
import { WEEKDAYS, WEEKDAY_LABELS, BLOCK_OPTIONS, TIME_BLOCKS, fmtSessionNote } from "../../utils/format";
import { INPUT_CLS, INPUT_FILTER_CLS, LABEL_CLS, SELECT_CLS } from "../../utils/forms";

// Năm/kỳ mặc định lấy từ /course-classes/current-term sau khi tải trang
const BASE_FORM = { course_id: "", lecturer_id: "", term: 1, year: 2026, max_size: 40, status: "open", weekday: 2, block: "morning", room: "" };
const EMPTY_FILTERS = { year: "", term: "", status: "", course_id: "", lecturer_id: "" };
const PAGE_SIZE = 10;

// Options cho dropdown thứ/khối giờ — dùng chung form chính + panel ghi đè buổi
const WEEKDAY_OPTS = WEEKDAYS.map((wd) => ({ value: wd, label: WEEKDAY_LABELS[wd] }));

/** Render mảng {value,label} thành các <option> — chọn bằng cách bọc trong <select>. */
const Options = ({ opts }) =>
  opts.map((o) => (
    <option key={o.value} value={o.value}>
      {o.label}
    </option>
  ));

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
  // Kỳ hiện tại của hệ thống — mặc định cho form mở lớp mới
  const [currentTerm, setCurrentTerm] = useState(null);
  const [search, setSearch] = useState(""); // nội dung ô nhập
  const [appliedSearch, setAppliedSearch] = useState(""); // từ khóa đang áp dụng cho danh sách hiện tại
  const [filters, setFilters] = useState(EMPTY_FILTERS); // nội dung các ô lọc
  const [applied, setApplied] = useState(EMPTY_FILTERS); // bộ lọc đang áp dụng cho danh sách hiện tại
  const [form, setForm] = useState(BASE_FORM);
  const [showForm, setShowForm] = useState(() => location.state?.form === 1);
  // Dòng đang sửa — null = chế độ mở lớp mới
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // Hành động đang chờ xác nhận: { id, kind: "close" | "complete" }
  const [confirm, setConfirm] = useState(null);
  // Chỉnh TỪNG buổi khi sửa lớp: seq đang mở panel + nội dung ghi đè
  const [sessEdit, setSessEdit] = useState(null);
  const emptySessForm = { action: "moved", weekday: 2, block: "morning", room: "" };
  const [sessForm, setSessForm] = useState(emptySessForm);
  const [sessBusy, setSessBusy] = useState(false);
  // Neo cuộn tới form sửa/mở lớp
  const formRef = useRef(null);
  // id của form đã cuộn tới (editing?.id hoặc "new") — để saveSession cập nhật
  // editing (cùng id, object mới) không làm effect chạy lại → không bị kéo lên
  // đầu form sau mỗi lần "Lưu buổi"
  const scrolledFor = useRef(null);
  // Tăng dần mỗi lần gọi API — response của request cũ về sau bị bỏ qua
  const reqId = useRef(0);

  // Mở form (nút Sửa hoặc "+ Mở lớp mới") → cuộn lên đầu form để thao tác ngay
  useEffect(() => {
    if (!showForm) {
      scrolledFor.current = null;
      return;
    }
    const key = editing?.id ?? "new";
    if (scrolledFor.current !== key) {
      scrolledFor.current = key;
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [showForm, editing]);

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
    api
      .get("/course-classes/current-term")
      .then(({ data }) => setCurrentTerm(data))
      .catch(() => {});
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
      setForm(emptyForm());
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

  const emptyForm = () => ({
    ...BASE_FORM,
    year: currentTerm?.year ?? BASE_FORM.year,
    term: currentTerm?.term ?? BASE_FORM.term,
  });

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
    setSessEdit(null);
    setForm(BASE_FORM);
  };

  // Nạp dữ liệu dòng vào form và mở chế độ sửa
  const startEdit = (c) => {
    setError("");
    setEditing(c);
    setSessEdit(null);
    setForm({
      course_id: c.course_id,
      lecturer_id: c.lecturer_id ?? "",
      term: c.term,
      year: c.year,
      max_size: c.max_size,
      status: c.status,
      weekday: c.weekday,
      block: c.block,
      room: c.room ?? "",
    });
    setShowForm(true);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    // Lịch cố định: thứ + khối giờ + phòng (không đổi suốt khóa học)
    const slot = {
      weekday: Number(form.weekday),
      block: form.block,
      room: form.room.trim() || null,
    };
    try {
      if (editing) {
        await api.patch(`/course-classes/${editing.id}`, {
          lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : null,
          max_size: Number(form.max_size),
          status: form.status,
          ...slot,
        });
        setSuccess(`Đã cập nhật lớp ${editing.code}`);
        closeForm();
      } else {
        await api.post("/course-classes", {
          course_id: Number(form.course_id),
          lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : null,
          term: Number(form.term),
          year: Number(form.year),
          max_size: Number(form.max_size),
          status: form.status,
          ...slot,
        });
        setSuccess("Đã mở lớp học phần mới");
        setForm(BASE_FORM);
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

  // CLOSED → COMPLETED: backend kiểm tra đủ điểm trước khi chấp nhận
  const completeClass = async (c) => {
    setError("");
    setSuccess("");
    try {
      await api.post(`/course-classes/${c.id}/complete`);
      setSuccess(`Đã chuyển lớp ${c.code} sang HOÀN THÀNH — lớp chỉ còn tra cứu`);
      await load(page, appliedSearch, applied);
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const setF = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  // Cụm xác nhận 2 bước cho hành động khó đảo ngược (đóng lớp / hoàn thành lớp):
  // lần 1 hiện nút hành động, bấm mới chuyển "Chắc chắn … + Hủy", bấm lần 2 mới chạy.
  const confirmOr = (c, kind, { label, confirmLabel, danger = false, onConfirm }) =>
    confirm?.id === c.id && confirm.kind === kind ? (
      <span className="inline-flex gap-2">
        <Button
          size="sm"
          variant={danger ? "danger" : "primary"}
          onClick={() => {
            setConfirm(null);
            onConfirm();
          }}
        >
          {confirmLabel}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirm(null)}>
          Hủy
        </Button>
      </span>
    ) : (
      <Button
        size="sm"
        variant={danger ? "danger" : "primary"}
        onClick={() => setConfirm({ id: c.id, kind })}
      >
        {label}
      </Button>
    );

  const hasFilter = appliedSearch || Object.values(applied).some(Boolean);

  // Học phần đang chọn trong form → sinh danh sách buổi (1 tín chỉ = 3 buổi)
  const formCourse = courses.find((c) => c.id === Number(form.course_id));

  // Mở panel ghi đè cho 1 buổi (chỉ khi đang sửa lớp có sẵn)
  const openSession = (seq, ov) => {
    setSessEdit(seq);
    if (ov) {
      setSessForm({
        action: ov.action,
        weekday: ov.weekday ?? 2,
        block: ov.block ?? "morning",
        room: ov.room ?? "",
      });
    } else {
      setSessForm(emptySessForm);
    }
  };

  // Lưu ghi đè 1 buổi — gọi API ngay (không chờ nút Lưu của form)
  const saveSession = async () => {
    setError("");
    setSessBusy(true);
    try {
      let out;
      if (sessForm.action === "normal") {
        out = await api.delete(`/course-classes/${editing.id}/sessions/${sessEdit}`);
      } else {
        const body = { action: sessForm.action };
        if (sessForm.action === "moved") {
          body.weekday = Number(sessForm.weekday);
          body.block = sessForm.block;
          body.room = sessForm.room.trim() || null;
        }
        out = await api.put(`/course-classes/${editing.id}/sessions/${sessEdit}`, body);
      }
      setEditing(out.data); // response chứa session_overrides mới nhất
      setClasses((cs) => cs.map((c) => (c.id === out.data.id ? out.data : c)));
      setSuccess(`Đã cập nhật lịch buổi ${sessEdit} của lớp ${out.data.code}`);
      setSessEdit(null);
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setSessBusy(false);
    }
  };

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
        <input className={`${INPUT_FILTER_CLS} w-16`} type="number" placeholder="Năm" value={filters.year} onChange={setF("year")} />
        <input className={`${INPUT_FILTER_CLS} w-16`} type="number" placeholder="Kỳ" value={filters.term} onChange={setF("term")} />
        <select className={`${SELECT_CLS} w-40`} value={filters.status} onChange={setF("status")}>
          <option value="">Mọi trạng thái</option>
          <option value="open">Mở đăng ký</option>
          <option value="closed">Đóng</option>
          <option value="completed">Hoàn thành</option>
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
        <div ref={formRef} className="scroll-mt-20">
          <Card
          title={
            editing
              ? `Sửa lớp ${editing.code} · HK${editing.term}/${editing.year}`
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
              <input className={`${INPUT_CLS} w-20`} type="number" min="1" max="3" value={form.term} onChange={set("term")} required disabled={!!editing} />
            </div>
            <div>
              <label className={LABEL_CLS}>Năm</label>
              <input className={`${INPUT_CLS} w-20`} type="number" value={form.year} onChange={set("year")} required disabled={!!editing} />
            </div>
            <div>
              <label className={LABEL_CLS}>Sĩ số tối đa</label>
              <input className={INPUT_CLS} type="number" min="1" value={form.max_size} onChange={set("max_size")} required />
            </div>

            {/* Lịch cố định: 1 buổi/tuần × (số tín chỉ × 3) tuần trong cùng phòng */}
            <div className="md:col-span-3">
              <div className="text-sm font-medium mb-1.5">Lịch học cố định (1 buổi/tuần)</div>
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className={`${SELECT_CLS} w-32`}
                  value={form.weekday}
                  onChange={set("weekday")}
                  required
                >
                  <Options opts={WEEKDAY_OPTS} />
                </select>
                <select
                  className={`${SELECT_CLS} w-52`}
                  value={form.block}
                  onChange={set("block")}
                  required
                >
                  <Options opts={BLOCK_OPTIONS} />
                </select>
                <input
                  className={`${INPUT_CLS} w-36`}
                  placeholder="Phòng (VD: B201)"
                  value={form.room}
                  onChange={set("room")}
                />
              </div>
              <p className="text-xs text-secondary mt-1.5">
                Buổi học chiếm trọn khối giờ và giữ nguyên phòng trong suốt khóa. Trùng phòng hoặc trùng giảng viên
                cùng thứ/khối sẽ bị hệ thống từ chối.
              </p>

              {/* Toàn bộ buổi học của lớp — sinh từ lịch cố định phía trên.
                  Khi sửa lớp: bấm vào từng buổi để dời/nghỉ riêng (trường hợp đặc biệt). */}
              {formCourse?.credits ? (
                <div className="mt-3">
                  <div className="text-xs text-secondary mb-1.5">
                    <b className="text-primary num">{formCourse.credits * 3} buổi</b> · mỗi tuần 1 buổi ·{" "}
                    {WEEKDAY_LABELS[form.weekday]} · {TIME_BLOCKS[form.block]?.label} · {form.room || "chưa có phòng"}
                    {editing
                      ? " — bấm vào buổi để dời/nghỉ riêng; đổi lịch phía trên sẽ chuyển cả lớp"
                      : " — đổi lịch phía trên sẽ chuyển toàn bộ các buổi này"}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {Array.from({ length: formCourse.credits * 3 }, (_, i) => {
                      const seq = i + 1;
                      const ov = editing?.session_overrides?.find((o) => o.seq === seq);
                      const style = !ov
                        ? "bg-app border-border hover:border-primary"
                        : ov.action === "moved"
                          ? "border-primary bg-primary-soft"
                          : "border-danger/40 bg-danger/10 line-through opacity-70";
                      return editing ? (
                        <button
                          key={seq}
                          type="button"
                          onClick={() => openSession(seq, ov)}
                          title={ov ? fmtSessionNote(ov) : "Bấm để dời/nghỉ buổi này"}
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs num cursor-pointer transition-colors ${style}`}
                        >
                          Buổi {seq}
                          {ov && (ov.action === "moved" ? " ↗" : " ✕")}
                        </button>
                      ) : (
                        <span
                          key={seq}
                          className="inline-flex items-center rounded-md bg-app border border-border px-2 py-0.5 text-xs num"
                        >
                          Buổi {seq}
                        </span>
                      );
                    })}
                  </div>

                  {/* Panel ghi đè cho buổi đang chọn */}
                  {sessEdit != null && editing && (
                    <div className="mt-2 bg-app border border-border rounded-lg p-3 space-y-2 max-w-md">
                      <div className="text-sm font-medium">Buổi {sessEdit}</div>
                      <div className="flex flex-wrap items-center gap-2">
                        <select
                          className={`${SELECT_CLS} w-56`}
                          value={sessForm.action}
                          onChange={(e) => setSessForm((s) => ({ ...s, action: e.target.value }))}
                        >
                          <option value="normal">Học bình thường (bỏ ghi đè)</option>
                          <option value="moved">Dời sang slot khác</option>
                          <option value="cancelled">Nghỉ buổi này</option>
                        </select>
                      </div>
                      {sessForm.action === "moved" && (
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            className={`${SELECT_CLS} w-32`}
                            value={sessForm.weekday}
                            onChange={(e) => setSessForm((s) => ({ ...s, weekday: e.target.value }))}
                          >
                            <Options opts={WEEKDAY_OPTS} />
                          </select>
                          <select
                            className={`${SELECT_CLS} w-52`}
                            value={sessForm.block}
                            onChange={(e) => setSessForm((s) => ({ ...s, block: e.target.value }))}
                          >
                            <Options opts={BLOCK_OPTIONS} />
                          </select>
                          <input
                            className={`${INPUT_CLS} w-32`}
                            placeholder="Phòng bù"
                            value={sessForm.room}
                            onChange={(e) => setSessForm((s) => ({ ...s, room: e.target.value }))}
                          />
                        </div>
                      )}
                      <div className="flex gap-2">
                        <Button size="sm" onClick={saveSession} disabled={sessBusy}>
                          {sessBusy ? "Đang lưu…" : "Lưu buổi"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setSessEdit(null)}>
                          Đóng
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            <div className="md:col-span-3">
              <Button type="submit">{editing ? "Lưu thay đổi" : "Mở lớp"}</Button>
            </div>
          </form>
          </Card>
        </div>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã lớp" },
            { key: "name", label: "Học phần" },
            { key: "credits", label: "TC", align: "right" },
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
                  <Link to={`/office/course-classes/${c.id}/students`}>
                    <Button size="sm" variant="secondary">
                      Sinh viên
                    </Button>
                  </Link>
                  {c.status !== "completed" && (
                    <Button size="sm" variant="secondary" onClick={() => startEdit(c)}>
                      Sửa
                    </Button>
                  )}
                  {c.status === "open" &&
                    confirmOr(c, "close", {
                      label: "Đóng lớp",
                      confirmLabel: "Chắc chắn đóng",
                      danger: true,
                      onConfirm: () => toggleStatus(c),
                    })}
                  {c.status === "closed" && (
                    <>
                      <Button size="sm" variant="secondary" onClick={() => toggleStatus(c)}>
                        Mở lại
                      </Button>
                      {confirmOr(c, "complete", {
                        label: "Hoàn thành",
                        confirmLabel: "Chắc chắn hoàn thành",
                        onConfirm: () => completeClass(c),
                      })}
                    </>
                  )}
                </span>
              </Cell>
            </CourseClassRow>
          )}
        />
        <Pagination page={page} totalPages={totalPages} onPageChange={goPage} />
      </Card>
    </div>
  );
}
