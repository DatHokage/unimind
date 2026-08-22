import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Search, UserPlus, Users } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { Card, DataTable, Cell, Row, Badge, Spinner, Alert, Button, Pagination } from "../../components/ui";
import { INPUT_CLS, LABEL_CLS, SELECT_CLS } from "../../utils/forms";
import { fmtDate } from "../../utils/format";

const EMPTY_NEW = { code: "", name: "", dob: "", major_id: "", account: "", password: "" };
const PAGE_SIZE = 10;

/**
 * Quản lý sinh viên của MỘT lớp hành chính (phòng đào tạo):
 * xem/tìm kiếm/phân trang, thêm SV mới vào lớp, chuyển SV có sẵn vào lớp,
 * tách khỏi lớp và xóa hẳn sinh viên.
 */
export default function HomeroomStudentsPage() {
  const { classId } = useParams();
  const [loading, setLoading] = useState(true);
  const [hc, setHc] = useState(null); // thông tin lớp hiện tại
  const [students, setStudents] = useState([]);
  const [page, setPage] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [totalElements, setTotalElements] = useState(0);
  const [majors, setMajors] = useState([]);
  const [search, setSearch] = useState("");
  const [appliedSearch, setAppliedSearch] = useState("");
  // Card "+ Thêm sinh viên": null = đóng, đang mở thì chọn chế độ "existing" | "new"
  const [addMode, setAddMode] = useState(null);
  // Chế độ "SV có sẵn": kết quả tìm kiếm (đã lọc bỏ SV thuộc lớp này)
  const [pickQuery, setPickQuery] = useState("");
  const [pickResults, setPickResults] = useState(null);
  // Form chế độ "Tạo mới"
  const [form, setForm] = useState(EMPTY_NEW);
  // id sinh viên đang chờ xác nhận tách khỏi lớp
  const [confirmId, setConfirmId] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  // Tăng dần mỗi lần gọi API danh sách — response cũ về sau bị bỏ qua
  const reqId = useRef(0);

  const loadClassInfo = () =>
    api.get(`/homeroom-classes/${classId}`).then(({ data }) => setHc(data));

  // Server-side pagination theo class_id. Trả về data response (null nếu request cũ bị bỏ qua)
  // để caller biết trang vừa load có rỗng hay không.
  const load = async (pageNum = 0, q = "") => {
    const id = ++reqId.current;
    const { data } = await api.get("/students", {
      params: {
        class_id: Number(classId),
        page: pageNum,
        size: PAGE_SIZE,
        ...(q ? { search: q } : {}),
      },
    });
    if (id !== reqId.current) return null;
    setStudents(data.data);
    setPage(data.page);
    setTotalPages(data.totalPages);
    setTotalElements(data.totalElements);
    return data;
  };

  useEffect(() => {
    setLoading(true);
    Promise.all([loadClassInfo(), api.get("/majors/all"), load(0, "")])
      .then(([, m]) => setMajors(m.data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId]);

  // Nạp lại danh sách + số SV của lớp sau mỗi thao tác;
  // nếu trang vừa load rỗng do xóa/tách hết → lùi một trang.
  const reload = async () => {
    loadClassInfo().catch((e) => setError(errMsg(e)));
    try {
      const d = await load(page, appliedSearch);
      if (d && d.data.length === 0 && d.page > 0) await load(d.page - 1, appliedSearch);
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const applySearch = () => {
    const q = search;
    load(0, q)
      .then((d) => {
        if (d) setAppliedSearch(q);
      })
      .catch((e) => setError(errMsg(e)));
  };

  const goPage = (p) => load(p, appliedSearch).catch((e) => setError(errMsg(e)));

  const openAdd = () => {
    setError("");
    setSuccess("");
    setConfirmId(null);
    setForm(EMPTY_NEW);
    setPickQuery("");
    setPickResults(null);
    setAddMode("existing");
  };

  const closeAdd = () => {
    setAddMode(null);
    setForm(EMPTY_NEW);
    setPickResults(null);
    setPickQuery("");
  };

  // Chế độ "SV có sẵn": tìm toàn trường rồi loại những người đã thuộc lớp này
  const searchExisting = async () => {
    setError("");
    try {
      const { data } = await api.get("/students", {
        params: { search: pickQuery.trim() || undefined, size: 10 },
      });
      setPickResults(data.data.filter((s) => s.class_id !== Number(classId)));
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const addExisting = async (s) => {
    setError("");
    setSuccess("");
    try {
      await api.put(`/students/${s.id}`, { class_id: Number(classId) });
      setSuccess(`Đã chuyển ${s.code} — ${s.name} vào lớp`);
      setPickResults((rs) => (rs ? rs.filter((x) => x.id !== s.id) : rs));
      await reload();
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const submitNew = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const body = {
      code: form.code.trim(),
      name: form.name.trim(),
      dob: form.dob || null,
      major_id: form.major_id ? Number(form.major_id) : null,
      class_id: Number(classId),
    };
    try {
      if (form.account.trim()) {
        body.account = { username: form.account.trim(), password: form.password };
      }
      await api.post("/students", body);
      setSuccess(`Đã tạo sinh viên ${body.code} trong lớp`);
      closeAdd();
      await reload();
    } catch (err) {
      setError(errMsg(err));
    }
  };

  const removeFromClass = async (id) => {
    setError("");
    setSuccess("");
    try {
      await api.put(`/students/${id}`, { class_id: null });
      setSuccess("Đã tách sinh viên khỏi lớp");
      setConfirmId(null);
      await reload();
    } catch (err) {
      setError(errMsg(err));
      setConfirmId(null);
    }
  };

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (loading) return <Spinner />;

  const metaParts = [
    hc?.cohort != null ? `Khóa ${hc.cohort}` : null,
    hc?.major_name,
    hc?.advisor_name ? `Cố vấn ${hc.advisor_name}` : null,
  ].filter(Boolean);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            to="/office/homerooms"
            className="inline-flex items-center gap-1 text-sm text-secondary hover:text-primary transition-colors duration-150"
          >
            <ArrowLeft size={14} /> Về danh sách lớp
          </Link>
          <h2 className="text-lg font-semibold mt-1">{hc?.name ?? `Lớp #${classId}`}</h2>
        </div>
        <Button onClick={openAdd}>
          <UserPlus size={15} /> Thêm sinh viên
        </Button>
      </div>

      <p className="text-sm text-secondary num">
        {[...metaParts, `${totalElements} sinh viên`].join(" · ")}
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

      {addMode && (
        <Card
          title={`Thêm sinh viên vào lớp ${hc?.name ?? ""}`}
          actions={
            <Button variant="ghost" size="sm" onClick={closeAdd}>
              Đóng
            </Button>
          }
        >
          <div className="flex gap-2 mb-4">
            <Button size="sm" variant={addMode === "existing" ? "primary" : "secondary"} onClick={() => setAddMode("existing")}>
              Chọn từ sinh viên có sẵn
            </Button>
            <Button size="sm" variant={addMode === "new" ? "primary" : "secondary"} onClick={() => setAddMode("new")}>
              Tạo mới
            </Button>
          </div>

          {addMode === "existing" ? (
            <div className="space-y-3">
              <div className="flex gap-2">
                <input
                  className={`${INPUT_CLS} w-72 max-w-full`}
                  placeholder="Tìm mã/tên sinh viên toàn trường…"
                  value={pickQuery}
                  onChange={(e) => setPickQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchExisting()}
                />
                <Button variant="secondary" onClick={searchExisting}>
                  Tìm
                </Button>
              </div>
              {pickResults !== null && (
                pickResults.length === 0 ? (
                  <p className="text-sm text-secondary">Không còn sinh viên nào khớp ngoài lớp này.</p>
                ) : (
                  <ul className="divide-y divide-border border border-border rounded-lg">
                    {pickResults.map((s) => (
                      <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
                        <span className="text-sm">
                          <span className="font-medium num">{s.code}</span> — {s.name}
                          {s.class_name ? (
                            <Badge tone="info" className="ml-2">hiện ở: {s.class_name}</Badge>
                          ) : (
                            <span className="text-secondary ml-2">chưa có lớp</span>
                          )}
                        </span>
                        <Button size="sm" onClick={() => addExisting(s)}>
                          Thêm vào lớp
                        </Button>
                      </li>
                    ))}
                  </ul>
                )
              )}
            </div>
          ) : (
            <form onSubmit={submitNew} className="grid md:grid-cols-2 gap-3">
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
                <select className={SELECT_CLS} value={form.major_id} onChange={set("major_id")}>
                  <option value="">— Chọn ngành —</option>
                  {majors.map((m) => (
                    <option key={m.id} value={m.id}>{m.code} — {m.name}</option>
                  ))}
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
                <Button type="submit">Tạo sinh viên</Button>
              </div>
            </form>
          )}
        </Card>
      )}

      <Card padded={false}>
        <DataTable
          columns={[
            { key: "code", label: "Mã SV" },
            { key: "name", label: "Họ tên" },
            { key: "dob", label: "Ngày sinh" },
            { key: "major", label: "Ngành" },
            { key: "action", label: "" },
          ]}
          rows={students}
          sttStart={page * PAGE_SIZE + 1}
          empty={
            <div className="flex flex-col items-center py-12 text-center">
              <Users size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
              <p className="text-sm font-medium">
                {appliedSearch ? `Không tìm thấy sinh viên khớp "${appliedSearch}" trong lớp.` : "Lớp chưa có sinh viên nào."}
              </p>
              <p className="text-sm text-secondary mt-1">
                {appliedSearch ? "Thử từ khóa khác hoặc xóa ô tìm kiếm." : "Bấm “Thêm sinh viên” để bổ sung."}
              </p>
            </div>
          }
          renderRow={(s, _i, stt) => (
            <Row key={s.id}>
              {stt}
              <Cell className="font-medium num">{s.code}</Cell>
              <Cell>{s.name}</Cell>
              <Cell className="num">{fmtDate(s.dob)}</Cell>
              <Cell>{s.major_name ?? "—"}</Cell>
              <Cell className="text-right">
                {confirmId === s.id ? (
                  <span className="inline-flex gap-2">
                    <Button size="sm" variant="danger" onClick={() => removeFromClass(s.id)}>
                      Chắc chắn tách
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                      Giữ lại
                    </Button>
                  </span>
                ) : (
                  <span className="inline-flex gap-1">
                    <Button size="sm" variant="secondary" onClick={() => setConfirmId(s.id)}>
                      Tách khỏi lớp
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
