import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, List, ListFilter, Clock } from "lucide-react";
import api, { errMsg } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import { Card, DataTable, Cell, NumCell, Row, Button, Spinner, Alert, EmptyState } from "../../components/ui";
import { WEEKDAYS, WEEKDAY_LABELS, PERIODS, PERIOD_TIMES, fmtPeriodRange, fmtSchedule, fmtTerm } from "../../utils/format";
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

/** Phân buổi trong ngày: mỗi buổi tối đa 5 tiết. */
const SESSIONS = [
  { key: "morning", label: "Sáng", from: 1, to: 5 },
  { key: "afternoon", label: "Chiều", from: 6, to: 10 },
  { key: "evening", label: "Tối", from: 11, to: 15 },
];

/** Template cột dùng chung cho header và thân lưới: [nhãn buổi][cột tiết][7 thứ]. */
const GRID_COLS = "26px 72px repeat(7, minmax(104px, 1fr))";
const ROW_H = 56; // px — chiều cao mỗi hàng tiết

/** Chỉ số cột grid của 1 thứ (sau cột nhãn buổi + cột tiết). */
const colOf = (wd) => WEEKDAYS.indexOf(wd) + 3;

/** Gom buổi học theo thứ trong tuần: {"2": [{cls, session}, ...]}. */
function groupByWeekday(classes) {
  const days = {};
  for (const cls of classes) {
    for (const s of cls.schedule ?? []) {
      if (!s.weekday || !s.start_period || !s.end_period) continue;
      (days[s.weekday] ??= []).push({ cls, session: s });
    }
  }
  for (const list of Object.values(days)) {
    list.sort((a, b) => a.session.start_period - b.session.start_period);
  }
  return days;
}

/** Khối học phần trong lưới tuần: kéo đúng số tiết start→end, hẹp hơn cột ngày và căn giữa. */
function SessionBlock({ cls, session, classes }) {
  const pal = paletteOf(cls, classes);
  const range = fmtPeriodRange(session.start_period, session.end_period);
  const short = session.end_period - session.start_period < 2; // ≤2 tiết: chỗ chỉ đủ 2 dòng
  return (
    <div
      className={`h-full overflow-hidden rounded-md border-l-[3px] px-2 py-1 text-left ${pal.cell}`}
      title={`${cls.course_code} — ${cls.course_name}${range ? ` · ${range}` : ""}${session.room ? ` · ${session.room}` : ""}`}
    >
      <div className="text-[13px] font-semibold leading-tight truncate">
        {cls.course_code}
        {cls.credits != null && (
          <span className="ml-1 text-[11px] font-normal text-secondary">({cls.credits}TC)</span>
        )}
      </div>
      <div className={`text-xs ${short ? "truncate" : "line-clamp-2"}`}>{cls.course_name}</div>
      {!short && (
        <div className="text-[11px] text-secondary num whitespace-nowrap truncate">
          {range && (
            <span className="inline-flex items-center gap-0.5">
              <Clock size={10} /> {range}
            </span>
          )}
          {session.room ? ` · ${session.room}` : ""}
        </div>
      )}
    </div>
  );
}

/**
 * Bảng theo tuần (desktop) — CSS Grid:
 * - Cột: [Buổi][Tiết][7 thứ]; hàng: header + 3 buổi × 5 tiết.
 * - Khối học phần đặt bằng grid-row động: (2 + start_period) / (3 + end_period)
 *   → chiều cao tự khớp số tiết, không chồng lấn nếu lịch không trùng (backend đã chặn).
 */
function ScheduleGrid({ classes }) {
  const blocks = [];
  for (const cls of classes) {
    for (const s of cls.schedule ?? []) {
      if (!s.weekday || !s.start_period || !s.end_period) continue;
      blocks.push({ cls, session: s, key: `${cls.course_class_id}-${s.weekday}-${s.start_period}` });
    }
  }

  return (
    <div className="overflow-x-auto">
      <div
        className="grid min-w-[900px] gap-px border border-border bg-border text-sm"
        style={{
          gridTemplateColumns: GRID_COLS,
          gridTemplateRows: `40px repeat(${PERIODS}, minmax(${ROW_H}px, auto))`,
        }}
      >
        {/* Header */}
        <div className="bg-app px-1 py-2 text-center text-xs font-semibold text-secondary" style={{ gridColumn: "1 / 3" }}>
          Buổi · Tiết
        </div>
        {WEEKDAYS.map((wd, i) => (
          <div key={wd} className="bg-app px-1 py-2 text-center text-xs font-semibold text-secondary" style={{ gridColumn: i + 3 }}>
            {WEEKDAY_LABELS[wd]}
          </div>
        ))}

        {/* Nhãn buổi + dải giờ từng buổi (cột 1) */}
        {SESSIONS.map((ss) => (
          <div
            key={ss.key}
            className="flex flex-col items-center justify-center gap-1 bg-app px-0.5 py-2"
            style={{ gridColumn: 1, gridRow: `${2 + ss.from} / ${3 + ss.to}` }}
          >
            <span className="text-[11px] font-semibold leading-tight text-secondary">
              Buổi
              <br />
              {ss.label.toLowerCase()}
            </span>
            <span className="text-[10px] leading-tight text-secondary num text-center">
              {PERIOD_TIMES[ss.from].start}–{PERIOD_TIMES[ss.to].end}
            </span>
          </div>
        ))}

        {/* Cột tiết: mỗi tiết 1 hàng kèm giờ vào/ra */}
        {Array.from({ length: PERIODS }, (_, i) => i + 1).map((p) => (
          <div key={p} className="flex flex-col items-center justify-center bg-app py-1" style={{ gridColumn: 2, gridRow: 2 + p }}>
            <span className="text-[11px] font-semibold num leading-tight">{p}</span>
            <span className="text-[10px] text-secondary num leading-tight">
              {PERIOD_TIMES[p].start}–{PERIOD_TIMES[p].end}
            </span>
          </div>
        ))}

        {/* Ô nền của lưới: 7 thứ × 15 tiết */}
        {Array.from({ length: PERIODS }, (_, i) => i + 1).map((p) =>
          WEEKDAYS.map((wd, i) => (
            <div key={`${wd}-${p}`} className="bg-surface" style={{ gridColumn: i + 3, gridRow: 2 + p }} />
          ))
        )}

        {/* Khối học phần: grid-row động theo start/end period, căn giữa và hẹp hơn cột ngày */}
        {blocks.map(({ cls, session, key }) => {
          const col = colOf(session.weekday);
          if (!col) return null;
          return (
            <div
              key={key}
              className="my-0.5 w-[86%] max-w-[150px] justify-self-center"
              style={{ gridColumn: col, gridRow: `${2 + session.start_period} / ${3 + session.end_period}` }}
            >
              <SessionBlock cls={cls} session={session} classes={classes} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Xem theo ngày (dễ đọc trên điện thoại): mỗi thứ có lịch là 1 block dọc. */
function DayList({ classes }) {
  const days = groupByWeekday(classes);
  const order = WEEKDAYS.filter((wd) => days[wd]?.length);
  return (
    <div className="space-y-4">
      {order.map((wd) => (
        <section key={wd} className="bg-surface border border-border rounded-lg shadow-sm p-4">
          <h3 className="text-sm font-semibold mb-3">{WEEKDAY_LABELS[wd]}</h3>
          <ol className="space-y-2.5">
            {days[wd].map(({ cls, session }) => {
              const pal = paletteOf(cls, classes);
              const range = fmtPeriodRange(session.start_period, session.end_period);
              return (
                <li key={`${cls.course_class_id}-${session.start_period}`} className="flex gap-3">
                  {/* Cột giờ: giờ vào đậm + giờ ra nhỏ */}
                  <div className="w-14 shrink-0 text-right border-r border-border pr-2 num">
                    <div className="text-sm font-semibold leading-tight">{range ? range.split("–")[0] : "—"}</div>
                    <div className="text-[11px] text-secondary leading-tight">{range ? range.split("–")[1] : ""}</div>
                  </div>
                  <div className={`min-w-0 flex-1 rounded-md border-l-[3px] px-2.5 py-1.5 ${pal.cell}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13px] font-semibold">{cls.course_code}</span>
                      <span className="text-[11px] text-secondary num">tiết {session.start_period}–{session.end_period}</span>
                    </div>
                    <div className="text-xs truncate" title={cls.course_name}>{cls.course_name}</div>
                    <div className="text-xs text-secondary">{session.room || "Chưa xếp phòng"}</div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

export default function SchedulePage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState(null);
  const [selected, setSelected] = useState(""); // "year-term" — rỗng = kỳ mới nhất
  const [view, setView] = useState("grid");
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
  const totalCredits = classes.reduce((s, c) => s + (c.credits ?? 0), 0);
  // Kỳ đang hiển thị: ưu tiên kỳ người dùng chọn, nếu chưa chọn thì kỳ backend trả về (mới nhất)
  const termValue = selected || (schedule?.year ? `${schedule.year}-${schedule.term}` : "");

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
          <Button variant={view === "grid" ? "secondary" : "ghost"} size="sm" onClick={() => setView("grid")}>
            <CalendarDays size={14} />
            Theo tuần
          </Button>
          <Button variant={view === "list" ? "secondary" : "ghost"} size="sm" onClick={() => setView("list")}>
            <List size={14} />
            Theo ngày
          </Button>
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
          </p>

          {view === "grid" ? (
            <Card padded={false}>
              <ScheduleGrid classes={classes} />
            </Card>
          ) : (
            <DayList classes={classes} />
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
                  <Cell className="text-xs whitespace-normal min-w-56">{fmtSchedule(c.schedule)}</Cell>
                  <Cell>{c.lecturer_name ?? "—"}</Cell>
                  <Cell className="text-xs">
                    {[...new Set((c.schedule ?? []).map((s) => s.room).filter(Boolean))].join(", ") || "—"}
                  </Cell>
                </Row>
              )}
            />
          </Card>
        </>
      )}
    </div>
  );
}
