import {
  CalendarDays,
  Table,
  ClipboardList,
  Award,
  Sparkles,
  MessageCircle,
  BookOpen,
  NotebookPen,
  LayoutDashboard,
  Users,
  User,
  BookMarked,
  Library,
  Presentation,
  PenLine,
  BarChart,
  School,
} from "lucide-react";

/**
 * Menu sidebar theo từng role — frontend.md §5.2.
 * Định nghĩa tập trung tại đây; Sidebar chỉ việc render, không hardcode menu.
 */
export const MENU = {
  student: [
    {
      title: "Học tập",
      items: [
        { to: "/student", icon: LayoutDashboard, label: "Tổng quan", end: true },
        { to: "/student/schedule", icon: Table, label: "Thời khóa biểu" },
        { to: "/student/register", icon: CalendarDays, label: "Đăng ký học phần" },
        { to: "/student/enrollments", icon: ClipboardList, label: "Đăng ký của tôi" },
        { to: "/student/grades", icon: Award, label: "Bảng điểm" },
      ],
    },
    {
      title: "Trợ lý AI",
      items: [
        // Route riêng — AI chỉ phân tích khi người dùng nhấn nút "Nhận tư vấn"
        { to: "/student/advice", icon: Sparkles, label: "Tư vấn đăng ký" },
        { to: "/student/chat", icon: MessageCircle, label: "Hỏi đáp quy chế" },
      ],
    },
  ],
  lecturer: [
    {
      title: "Giảng dạy",
      items: [
        { to: "/lecturer", icon: BookOpen, label: "Lớp học phần của tôi", end: true },
        { to: "/lecturer/gradebook/select", icon: NotebookPen, label: "Nhập điểm quá trình" },
      ],
    },
  ],
  training_office: [
    {
      title: "Quản lý",
      items: [
        { to: "/office/students", icon: Users, label: "Sinh viên" },
        { to: "/office/lecturers", icon: User, label: "Giảng viên" },
        { to: "/office/majors", icon: BookMarked, label: "Ngành học" },
        { to: "/office/homerooms", icon: School, label: "Lớp hành chính" },
        { to: "/office/courses", icon: Library, label: "Học phần" },
        { to: "/office/course-classes", icon: Presentation, label: "Lớp học phần" },
        { to: "/office/exam-grades", icon: PenLine, label: "Nhập điểm thi" },
      ],
    },
    {
      title: "Thống kê",
      items: [
        { to: "/office", icon: BarChart, label: "Kết quả học tập", end: true },
      ],
    },
  ],
  advisor: [
    {
      title: "Cố vấn",
      items: [
        { to: "/advisor", icon: School, label: "Lớp phụ trách", end: true },
        { to: "/advisor/results", icon: BarChart, label: "Kết quả sinh viên" },
      ],
    },
  ],
};
