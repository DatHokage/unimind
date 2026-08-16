/** Nhãn thứ theo quy ước lưu weekday 2..8 (2 = Thứ 2 ... 8 = Chủ nhật). */
export const WEEKDAY_LABELS = { 2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7", 8: "CN" };

export const WEEKDAYS = [2, 3, 4, 5, 6, 7, 8];

/** Số tiết tối đa trong ngày — 15 tiết (sáng / chiều / tối). */
export const PERIODS = 15;

/** Khung giờ từng tiết theo khung giờ của nhà trường. */
export const PERIOD_TIMES = {
  1: { start: "6:45", end: "7:35" },
  2: { start: "7:40", end: "8:30" },
  3: { start: "8:40", end: "9:30" },
  4: { start: "9:40", end: "10:30" },
  5: { start: "10:35", end: "11:25" },
  6: { start: "13:00", end: "13:50" },
  7: { start: "13:55", end: "14:45" },
  8: { start: "14:55", end: "15:45" },
  9: { start: "15:55", end: "16:45" },
  10: { start: "16:50", end: "17:40" },
  11: { start: "18:15", end: "19:05" },
  12: { start: "19:10", end: "20:00" },
  13: { start: "20:05", end: "20:55" },
  14: { start: "21:10", end: "22:00" },
  15: { start: "21:20", end: "22:10" },
};

/** "tiết 4–6" → "9:40–11:25"; trả "" nếu ngoài khung giờ đã biết. */
export function fmtPeriodRange(startPeriod, endPeriod) {
  const a = PERIOD_TIMES[startPeriod]?.start;
  const b = PERIOD_TIMES[endPeriod]?.end;
  return a && b ? `${a}–${b}` : "";
}

/** [{"weekday":3,"start_period":4,"end_period":6,"room":"B201"}] → "Thứ 3 tiết 4–6 · 9:40–11:25 (B201)" */
export function fmtSchedule(schedule = []) {
  if (!schedule?.length) return "—";
  return schedule
    .map((s) => {
      const range = fmtPeriodRange(s.start_period, s.end_period);
      return `${WEEKDAY_LABELS[s.weekday] ?? `T${s.weekday}`} tiết ${s.start_period}–${s.end_period}${range ? ` · ${range}` : ""}${s.room ? ` (${s.room})` : ""}`;
    })
    .join("; ");
}

export function fmtTerm(year, term) {
  return year ? `${year}-T${term}` : "—";
}

export function fmtScore(v) {
  return v == null ? "—" : Number(v).toFixed(1);
}

export function fmtDate(d) {
  if (!d) return "—";
  const [y, m, day] = String(d).slice(0, 10).split("-");
  return `${day}/${m}/${y}`;
}
