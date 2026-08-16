/**
 * Xếp loại học lực theo GPA hệ 4 — chuẩn Việt Nam (QĐ 43/2007):
 * 3.60–4.00 Xuất sắc · 3.20–3.59 Giỏi · 2.50–3.19 Khá · 2.00–2.49 Trung bình
 * 1.00–1.99 Yếu · dưới 1.00 Kém.
 */
export function classifyGpa4(gpa4) {
  if (gpa4 == null) return { label: "Chưa xếp loại", tone: "neutral" };
  if (gpa4 >= 3.6) return { label: "Xuất sắc", tone: "success" };
  if (gpa4 >= 3.2) return { label: "Giỏi", tone: "info" };
  if (gpa4 >= 2.5) return { label: "Khá", tone: "neutral" };
  if (gpa4 >= 2.0) return { label: "Trung bình", tone: "neutral" };
  if (gpa4 >= 1.0) return { label: "Yếu", tone: "warning" };
  return { label: "Kém", tone: "danger" };
}
