import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, ChevronLeft, ChevronRight, List, ListFilter } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Badge, Card, DataTable, Cell, NumCell, Row, Button, Spinner, Alert, EmptyState } from "../../components/ui";
import { WEEKDAYS, WEEKDAY_LABELS, PERIOD_TIMES, TIME_BLOCKS, SESSION_STATUS, fmtSlot, fmtTerm } from "../../utils/format";
import { INPUT_CLS } from "../../utils/forms";

/** Bảng màu nhất quán cho từng lớp học phần trong lưới (đủ 9 lớp/kỳ). */
const CLASS_PALETTES = [
  { cell: "border-primary bg-primary-soft", dot: "bg-primary" },
  { cell: "border-success bg-success/10", dot: "bg-success" },
  { cell: "border-warning bg-warning/10", dot: "bg-warning" },
  { cell: "border-[#7C3AED] bg-[#7C3AED]/10", dot: "bg-[#7C3AED]" },
  { cell: "border-[#0891B2] bg-[#0891B2]/10", dot: "bg-[#0891B2]" },
  { cell: "border-[#DB2777] bg-[#DB2777]/10", dot: "bg-[#DB2777]" },
  { cell: "border-[#D97706] bg-[#D97706]/10", dot: "bg-[#D97706]" },
  { cell: "border-[#059669] bg-[#059669]/10", dot: "bg-[#059669]" },
  { cell: "border-[#4B5563] bg-[#4B5563]/10", dot: "bg-[#4B5563]" },
];

/** Gán màu ổn định theo thứ tự xuất hiện của lớp trong danh sách. */
function paletteOf(cls, classes) {
  const idx = classes.findIndex((c) => c.course_class_id === cls.course_class_id);
  return CLASS_PALETTES[(idx >= 0 ? idx : 0) % CLASS_PALETTES.length];
}

// ---------- Tiện ích ngày (ISO yyyy-mm-dd ↔ Date địa phương) ----------

const isoOf = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const parseISO = (s) => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
};

const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

/** Vị trí trong tuần theo thứ Việt Nam (thứ Hai = 0 … Chủ Nhật = 6). */
const mondayIndex = (d) => (d.getDay() + 6) % 7;

const fmtDM = (d) => `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;

/** Ô ngày trong lịch tháng: số ngày + các chip buổi học (tối đa 3, còn lại gộp "+n"). */
function MonthCell({ date, inMonth, events, classes, isToday }) {
  const visible = events.slice(0, 3);
  const rest = events.length - visible.length;
  return (
    <div
      className={`min-h-[76px] p-1 ${inMonth ? "bg-surface" : "bg-app/60"} ${isToday ? "ring-1 ring-primary ring-inset" : ""}`}
    >
      <div className="flex items-center justify-between px-0.5">
        <span className={`text-[11px] num font-semibold ${inMonth ? "" : "text-secondary/50"} ${isToday ? "text-primary" : ""}`}>
          {date.getDate()}
        </span>
        {isToday && <span className="text-[9px] font-semibold text-primary">Hôm nay</span>}
      </div>
      <div className="space-y-0.5 mt-0.5">
        {visible.map((s) => {
          const pal = paletteOf(s, classes);
          const cancelled = s.status === "cancelled";
          const st = SESSION_STATUS[s.status];
          return (
            <div
              key={`${s.course_class_id}-${s.seq}`}
              className={`rounded border-l-2 px-1 py-0.5 text-[10px] leading-tight ${pal.cell} ${cancelled ? "opacity-50 line-through" : ""}`}
              title={`${s.course_code} — ${s.course_name} · tiết ${s.start_period}–${s.end_period}${s.room ? ` · ${s.room}` : ""}${
                st ? ` · ${st.label}` : ""
              }`}
            >
              <span className="font-semibold">{s.course_code}</span>{" "}
              <span className="text-secondary num">{PERIOD_TIMES[s.start_period]?.start}</span>
              {s.room && <span className="block truncate text-secondary">{s.room}</span>}
            </div>
          );
        })}
        {rest > 0 && <div className="text-[10px] text-secondary pl-1">+{rest} buổi khác</div>}
      </div>
    </div>
  );
}

/** Lịch theo tháng: điều hướng ‹ ›, ô hôm nay được làm nổi, chip màu theo lớp. */
function MonthGrid({ sessions, classes }) {
  const times = sessions.map((s) => parseISO(s.date).getTime());
  const minTime = times.length ? Math.min(...times) : null;
  const maxTime = times.length ? Math.max(...times) : null;
  const now = new Date();
  // Mặc định mở tháng chứa hôm nay nếu hôm nay nằm trong khoảng có lịch, ngược lại
  // tháng của buổi đầu tiên. Kỳ chưa có ngày học (sessions rỗng) → mở tháng hiện tại
  // thay vì Math.min(...[]) = Infinity → con trỏ NaN.
  const anchor =
    minTime != null && (now.getTime() < minTime || now.getTime() > maxTime)
      ? new Date(minTime)
      : now;
  const [cursor, setCursor] = useState({ y: anchor.getFullYear(), m: anchor.getMonth() });

  const byDate = useMemo(() => {
    const map = {};
    for (const s of sessions) (map[s.date] ??= []).push(s);
    return map;
  }, [sessions]);

  // Lưới luôn đủ 6 hàng × 7 cột bắt đầu từ thứ Hai của tuần chứa ngày 1
  const first = new Date(cursor.y, cursor.m, 1);
  const gridStart = addDays(first, -mondayIndex(first));
  const cells = Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  const todayIso = isoOf(new Date());

  const shift = (delta) =>
    setCursor(({ y, m }) => {
      const next = new Date(y, m + delta, 1);
      return { y: next.getFullYear(), m: next.getMonth() };
    });

  return (
    <Card padded={false}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <Button variant="ghost" size="sm" onClick={() => shift(-1)} aria-label="Tháng trước">
          <ChevronLeft size={16} />
        </Button>
        <h3 className="text-sm font-semibold num">
          Tháng {cursor.m + 1} · {cursor.y}
        </h3>
        <Button variant="ghost" size="sm" onClick={() => shift(1)} aria-label="Tháng sau">
          <ChevronRight size={16} />
        </Button>
      </div>
      <div className="overflow-x-auto">
        <div className="grid min-w-[700px]" style={{ gridTemplateColumns: "repeat(7, minmax(96px, 1fr))" }}>
          {WEEKDAYS.map((wd) => (
            <div key={wd} className="bg-app px-1 py-1.5 text-center text-[11px] font-semibold text-secondary border-b border-border">
              {WEEKDAY_LABELS[wd]}
            </div>
          ))}
          {cells.map((d) => {
            const iso = isoOf(d);
            return (
              <div key={iso} className="border-b border-r border-border last:border-r-0 [&:nth-child(7n)]:border-r-0">
                <MonthCell
                  date={d}
                  inMonth={d.getMonth() === cursor.m}
                  events={byDate[iso] ?? []}
                  classes={classes}
                  isToday={iso === todayIso}
                />
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}

/** Một buổi trong danh sách tuần học — kiểu thẻ giống xem-theo-ngày cũ, kèm trạng thái dời/nghỉ. */
function WeekSessionRow({ s, cls, classes }) {
  const pal = paletteOf(s, classes);
  const cancelled = s.status === "cancelled";
  const moved = s.status === "moved";
  const st = SESSION_STATUS[s.status];
  return (
    <li className={`flex gap-3 ${cancelled ? "opacity-60" : ""}`}>
      <div className="w-14 shrink-0 text-right border-r border-border pr-2 num">
        <div className="text-sm font-semibold leading-tight">{PERIOD_TIMES[s.start_period]?.start ?? "—"}</div>
        <div className="text-[11px] text-secondary leading-tight">{PERIOD_TIMES[s.end_period]?.end ?? ""}</div>
      </div>
      <div className={`min-w-0 flex-1 rounded-md border-l-[3px] px-2.5 py-1.5 ${pal.cell}`}>
        <div className="flex items-center justify-between gap-2">
          <span className={`text-[13px] font-semibold ${cancelled ? "line-through" : ""}`}>
            {s.course_code} — {s.course_name}
          </span>
          {st && <Badge tone={st.tone}>{st.label}</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-secondary">
          <span className="num">tiết {s.start_period}–{s.end_period}</span>
          <span>{WEEKDAY_LABELS[s.weekday]}</span>
          <span>{s.room || "Chưa xếp phòng"}</span>
          {moved && cls && cls.weekday !== s.weekday && (
            <span>(dời từ {WEEKDAY_LABELS[cls.weekday]?.toLowerCase()} {TIME_BLOCKS[cls.block]?.label?.toLowerCase()})</span>
          )}
        </div>
      </div>
    </li>
  );
}

/** Danh sách cả kỳ theo tuần học: "Tuần k · dd/mm – dd/mm" rồi các buổi trong tuần đó. */
function WeekList({ sessions, startDate, classes }) {
  const byWeek = useMemo(() => {
    const map = {};
    for (const s of sessions) (map[s.week] ??= []).push(s);
    return map;
  }, [sessions]);

  const clsById = useMemo(
    () => Object.fromEntries(classes.map((c) => [c.course_class_id, c])),
    [classes]
  );
  const week1Monday = parseISO(startDate); // backend đảm bảo start_date là thứ Hai tuần 1
  const maxWeek = Math.max(...sessions.map((s) => s.week));

  return (
    <div className="space-y-4">
      {Array.from({ length: maxWeek }, (_, i) => i + 1).map((week) => {
        const monday = addDays(week1Monday, (week - 1) * 7);
        const list = byWeek[week] ?? [];
        // Gom theo ngày trong tuần để ra các nhóm "Thứ x · dd/mm"
        const byDay = {};
        for (const s of list) (byDay[s.date] ??= []).push(s);
        return (
          <section key={week} className="bg-surface border border-border rounded-lg shadow-sm">
            <header className="flex items-baseline justify-between px-4 py-2.5 border-b border-border bg-app/40 rounded-t-lg">
              <h3 className="text-sm font-semibold">Tuần {week}</h3>
              <span className="text-xs text-secondary num">
                {fmtDM(monday)} – {fmtDM(addDays(monday, 6))}
              </span>
            </header>
            {list.length === 0 ? (
              <p className="px-4 py-3 text-sm text-secondary">Không có buổi học nào trong tuần này.</p>
            ) : (
              <ol className="space-y-2.5 px-4 py-3">
                {Object.keys(byDay)
                  .sort()
                  .map((dateIso) => {
                    const d = parseISO(dateIso); // parse 1 lần cho cả nhãn thứ + ngày
                    return (
                    <li key={dateIso}>
                      <div className="text-xs font-semibold text-secondary mb-1.5 num">
                        {WEEKDAY_LABELS[WEEKDAYS[mondayIndex(d)]]} · {fmtDM(d)}
                      </div>
                      <ol className="space-y-2.5">
                        {byDay[dateIso].map((s) => (
                          <WeekSessionRow key={`${s.course_class_id}-${s.seq}`} s={s} cls={clsById[s.course_class_id]} classes={classes} />
                        ))}
                      </ol>
                    </li>
                    );
                  })}
              </ol>
            )}
          </section>
        );
      })}
    </div>
  );
}

export default function SchedulePage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState(null);
  const [selected, setSelected] = useState(""); // "year-term" — rỗng = kỳ mới nhất
  const [view, setView] = useState("month"); // month | weeks
  const [error, setError] = useState("");

  useEffect(() => {
    const params = {};
    if (selected) {
      const [year, term] = selected.split("-");
      params.year = Number(year);
      params.term = Number(term);
    }
    setLoading(true);
    setError("");
    api
      .get(`/schedule/student/${user.student_id}`, { params })
      .then(({ data }) => setSchedule(data))
      .catch((e) => setError(errMsg(e)))
      .finally(() => setLoading(false));
  }, [user.student_id, selected]);

  if (loading && !schedule) return <Spinner />;
  if (error && !schedule) return <Alert kind="error">{error}</Alert>;

  const classes = schedule?.classes ?? [];
  const terms = schedule?.terms ?? [];
  const datedSessions = schedule?.sessions ?? []; // có ngày cụ thể (cần academic_term)
  const hasDated = datedSessions.length > 0;
  const totalCredits = classes.reduce((s, c) => s + (c.credits ?? 0), 0);
  // Kỳ đang hiển thị: ưu tiên kỳ người dùng chọn, nếu chưa chọn thì kỳ backend trả về (mới nhất)
  const termValue = selected || (schedule?.year ? `${schedule.year}-${schedule.term}` : "");

  const VIEW_BTN = (key, icon, label) => (
    <Button
      variant={view === key ? "secondary" : "ghost"}
      size="sm"
      onClick={() => setView(key)}
      disabled={!hasDated}
      title={!hasDated ? "Kỳ học chưa có ngày bắt đầu" : undefined}
    >
      {icon}
      {label}
    </Button>
  );

  return (
    <div className="space-y-4">
      {error && (
        <Alert kind="error" onClose={() => setError("")}>
          {error}
        </Alert>
      )}

      {/* Chọn kỳ + chuyển chế độ xem */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListFilter size={15} className="text-secondary" />
          <select
            className={`${INPUT_CLS} w-52`}
            value={termValue}
            onChange={(e) => setSelected(e.target.value)}
            disabled={!terms.length}
          >
            {!terms.length && <option value="">Chưa có kỳ học nào</option>}
            {terms.map((t) => (
              <option key={`${t.year}-${t.term}`} value={`${t.year}-${t.term}`}>
                Năm {t.year} — Học kỳ {t.term}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1">
          {VIEW_BTN("month", <CalendarDays size={14} />, "Theo tháng")}
          {VIEW_BTN("weeks", <List size={14} />, "Theo tuần học")}
        </div>
      </div>

      {loading ? (
        <Spinner />
      ) : classes.length === 0 ? (
        <Card padded={false}>
          <EmptyState
            icon={CalendarDays}
            title="Chưa có lịch học trong kỳ này."
            description="Bạn chưa đăng ký học phần nào cho kỳ đang xem. Đăng ký học phần để xem thời khóa biểu."
            action={
              <Link to="/student/register">
                <Button size="sm">Xem các lớp đang mở →</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          <p className="text-sm text-secondary num">
            {fmtTerm(schedule.year, schedule.term)} · {classes.length} lớp học phần · {totalCredits} tín chỉ
            {hasDated && schedule.start_date && <> · bắt đầu {fmtDM(parseISO(schedule.start_date))}</>}
          </p>

          {/* key theo kỳ: đổi kỳ là remount → MonthGrid chạy lại logic anchor
              (hôm nay nếu trong khoảng lịch, ngược lại buổi đầu) thay vì đứng
              yên ở tháng đang xem của kỳ cũ */}
          {view === "month" ? (
            <MonthGrid key={termValue} sessions={datedSessions} classes={classes} />
          ) : (
            <WeekList sessions={datedSessions} startDate={schedule.start_date} classes={classes} />
          )}

          {/* Chú thích màu theo lớp — nhận diện nhanh khi nhiều buổi trùng màu */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {classes.map((c) => {
              const pal = paletteOf(c, classes);
              return (
                <span key={c.course_class_id} className="inline-flex items-center gap-1.5 text-xs text-secondary">
                  <span className={`w-2 h-2 rounded-full ${pal.dot}`} />
                  {c.course_code}
                  {c.credits != null ? ` (${c.credits}TC)` : ""}
                </span>
              );
            })}
          </div>

          {/* Danh sách lớp chi tiết — luôn kèm, dễ đọc trên mọi kích thước màn hình */}
          <Card padded={false}>
            <DataTable
              columns={[
                { key: "code", label: "Mã HP" },
                { key: "name", label: "Học phần" },
                { key: "credits", label: "TC", align: "right" },
                { key: "schedule", label: "Lịch học" },
                { key: "lecturer", label: "Giảng viên" },
                { key: "room", label: "Phòng" },
              ]}
              rows={classes}
              sttStart={1}
              renderRow={(c, _i, stt) => (
                <Row key={c.course_class_id}>
                  {stt}
                  <Cell className="font-medium">{c.course_code}</Cell>
                  <Cell className="whitespace-normal min-w-40">{c.course_name}</Cell>
                  <NumCell>{c.credits ?? "—"}</NumCell>
                  <Cell className="text-xs whitespace-normal min-w-56">{fmtSlot(c)}</Cell>
                  <Cell>{c.lecturer_name ?? "—"}</Cell>
                  <Cell className="text-xs">{c.room ?? "—"}</Cell>
                </Row>
              )}
            />
          </Card>
        </>
      )}
    </div>
  );
}
