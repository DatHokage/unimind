/** Nhãn thứ theo quy ước lưu weekday 2..8 (2 = Thứ 2 ... 8 = Chủ nhật). */
export const WEEKDAY_LABELS = { 2: "Thứ 2", 3: "Thứ 3", 4: "Thứ 4", 5: "Thứ 5", 6: "Thứ 6", 7: "Thứ 7", 8: "CN" };

export const WEEKDAYS = [2, 3, 4, 5, 6, 7, 8];

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

/**
 * Khối giờ chuẩn của nhà trường: mỗi buổi chiếm trọn 5 tiết liên tiếp
 * (sáng tiết 1–5, chiều 6–10, tối 11–15). Lịch lớp = thứ + khối + phòng cố định.
 */
export const TIME_BLOCKS = {
  morning: { label: "Sáng", from: 1, to: 5 },
  afternoon: { label: "Chiều", from: 6, to: 10 },
  evening: { label: "Tối", from: 11, to: 15 },
};

/** Options cho dropdown chọn khối giờ. */
export const BLOCK_OPTIONS = Object.entries(TIME_BLOCKS).map(([value, b]) => ({
  value,
  label: `${b.label} (tiết ${b.from}–${b.to})`,
}));

/** Lớp có lịch cố định 1 buổi/tuần → "Thứ 3 · Sáng tiết 1–5 · 6:45–11:25 · B201". */
export function fmtSlot(cc) {
  const wd = WEEKDAY_LABELS[cc?.weekday];
  const block = TIME_BLOCKS[cc?.block];
  if (!wd || !block) return "—";
  const range = fmtPeriodRange(block.from, block.to);
  return [
    wd,
    `${block.label} tiết ${block.from}–${block.to}`,
    ...(range ? [range] : []),
    ...(cc.room ? [cc.room] : []),
  ].join(" · ");
}

/** Ghi đè 1 buổi → "Buổi 3 → Thứ 6 · Chiều · P999" hoặc "Buổi 3 nghỉ". */
export function fmtSessionNote(ov) {
  if (!ov) return "";
  if (ov.action !== "moved") return `Buổi ${ov.seq} nghỉ`;
  const block = TIME_BLOCKS[ov.block];
  return [
    `Buổi ${ov.seq} dời →`,
    WEEKDAY_LABELS[ov.weekday] ?? "?",
    block?.label ?? "",
    ...(ov.room ? [ov.room] : []),
  ]
    .filter(Boolean)
    .join(" ");
}

/**
 * Trạng thái ghi đè buổi học → nhãn + tone Badge. Từ vựng duy nhất cho
 * "nghỉ"/"dời" khớp fmtSessionNote — ThTKB sinh viên và lịch admin cùng đọc ở đây.
 */
export const SESSION_STATUS = {
  cancelled: { label: "Nghỉ", tone: "danger" },
  moved: { label: "Dời lịch", tone: "warning" },
};

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
