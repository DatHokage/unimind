import { Plus } from "lucide-react";

/**
 * Tiêu đề + hành động chính của từng trang — frontend.md §6.
 * Header tự tra theo pathname; action render bên phải header
 * (VD "+ Mở lớp mới", "Nhận tư vấn AI").
 */
export const PAGE_META = {
  "/student": { title: "Tổng quan" },
  "/student/schedule": { title: "Thời khóa biểu" },
  "/student/register": { title: "Đăng ký học phần" },
  "/student/advice": { title: "Tư vấn đăng ký" },
  "/student/enrollments": { title: "Đăng ký của tôi" },
  "/student/grades": { title: "Bảng điểm" },
  "/student/chat": { title: "Hỏi đáp quy chế" },

  "/lecturer": { title: "Lớp học phần của tôi" },
  "/lecturer/gradebook": { title: "Sổ điểm quá trình" },

  "/advisor": { title: "Lớp phụ trách" },
  "/advisor/results": { title: "Kết quả sinh viên" },

  "/office": { title: "Kết quả học tập" },
  "/office/students": {
    title: "Sinh viên",
    action: { label: "Thêm sinh viên", to: "/office/students", state: { form: 1 } },
  },
  "/office/lecturers": {
    title: "Giảng viên",
    action: { label: "Thêm giảng viên", to: "/office/lecturers", state: { form: 1 } },
  },
  "/office/majors": {
    title: "Ngành học",
    action: { label: "Thêm ngành", to: "/office/majors", state: { form: 1 } },
  },
  "/office/homerooms": {
    title: "Lớp hành chính",
    action: { label: "Thêm lớp", to: "/office/homerooms", state: { form: 1 } },
  },
  "/office/courses": {
    title: "Học phần",
    action: { label: "Thêm học phần", to: "/office/courses", state: { form: 1 } },
  },
  "/office/course-classes": {
    title: "Lớp học phần",
    action: { label: "Mở lớp mới", to: "/office/course-classes", state: { form: 1 } },
  },
  "/office/exam-grades": { title: "Nhập điểm thi" },
};

/** Icon mặc định cho nút hành động chính của header (nút "+ ..."). */
export const ACTION_ICON = Plus;

/**
 * Tra meta theo pathname. Route động (gradebook/:id, students/:id...)
 * khớp theo prefix 2 đoạn đầu.
 */
export function getPageMeta(pathname) {
  if (PAGE_META[pathname]) return PAGE_META[pathname];
  const parts = pathname.split("/").filter(Boolean); // ["lecturer","gradebook","12"]
  const key = `/${parts.slice(0, 2).join("/")}`;
  return PAGE_META[key] ?? { title: "" };
}
