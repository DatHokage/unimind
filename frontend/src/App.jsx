import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import MainLayout from "./layouts/MainLayout";
import LoginPage from "./pages/LoginPage";
import StudentDashboard from "./pages/student/Dashboard";
import SchedulePage from "./pages/student/SchedulePage";
import RegistrationPage from "./pages/student/RegistrationPage";
import MyEnrollmentsPage from "./pages/student/MyEnrollmentsPage";
import GradesPage from "./pages/student/GradesPage";
import RegulationChatPage from "./pages/student/RegulationChatPage";
import LecturerClassesPage from "./pages/lecturer/MyClassesPage";
import GradebookPage from "./pages/lecturer/GradebookPage";
import AdvisorClassesPage from "./pages/advisor/MyClassesPage";
import AdvisorStudentsPage from "./pages/advisor/StudentsPage";
import AdvisorStudentDetailPage from "./pages/advisor/StudentDetailPage";
import OfficeDashboardPage from "./pages/office/DashboardPage";
import StudentsManagePage from "./pages/office/StudentsPage";
import LecturersManagePage from "./pages/office/LecturersPage";
import MajorsManagePage from "./pages/office/MajorsPage";
import HomeroomsManagePage from "./pages/office/HomeroomsPage";
import CoursesManagePage from "./pages/office/CoursesPage";
import CourseClassesManagePage from "./pages/office/CourseClassesPage";
import ExamGradesPage from "./pages/office/ExamGradesPage";

function RequireRole({ roles }) {
  const { token, user } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (!user || !roles.includes(user.role)) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function HomeRedirect() {
  const { token, user } = useAuth();
  if (!token || !user) return <Navigate to="/login" replace />;
  const home = {
    student: "/student",
    lecturer: "/lecturer",
    advisor: "/advisor",
    training_office: "/office",
  }[user.role];
  return <Navigate to={home || "/login"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<HomeRedirect />} />

          <Route path="/student" element={<RequireRole roles={["student"]} />}>
            <Route element={<MainLayout />}>
              <Route index element={<StudentDashboard />} />
              <Route path="schedule" element={<SchedulePage />} />
              <Route path="register" element={<RegistrationPage />} />
              <Route path="advice" element={<RegistrationPage />} />
              <Route path="enrollments" element={<MyEnrollmentsPage />} />
              <Route path="grades" element={<GradesPage />} />
              <Route path="chat" element={<RegulationChatPage />} />
            </Route>
          </Route>

          <Route path="/lecturer" element={<RequireRole roles={["lecturer"]} />}>
            <Route element={<MainLayout />}>
              <Route index element={<LecturerClassesPage />} />
              {/* Không có :courseClassId → trang tự cho chọn lớp rồi vào điểm */}
              <Route path="gradebook/select" element={<GradebookPage />} />
              <Route path="gradebook/:courseClassId" element={<GradebookPage />} />
            </Route>
          </Route>

          <Route path="/advisor" element={<RequireRole roles={["advisor"]} />}>
            <Route element={<MainLayout />}>
              <Route index element={<AdvisorClassesPage />} />
              {/* Kết quả sinh viên: danh sách toàn trường dạng quản lý (xem + tìm kiếm) */}
              <Route path="results" element={<AdvisorStudentsPage officeMode />} />
              <Route path="classes/:classId/students" element={<AdvisorStudentsPage />} />
              <Route path="students/:studentId" element={<AdvisorStudentDetailPage />} />
            </Route>
          </Route>

          <Route path="/office" element={<RequireRole roles={["training_office"]} />}>
            <Route element={<MainLayout />}>
              <Route index element={<OfficeDashboardPage />} />
              <Route path="students" element={<StudentsManagePage />} />
              <Route path="lecturers" element={<LecturersManagePage />} />
              <Route path="majors" element={<MajorsManagePage />} />
              <Route path="homerooms" element={<HomeroomsManagePage />} />
              <Route path="courses" element={<CoursesManagePage />} />
              <Route path="course-classes" element={<CourseClassesManagePage />} />
              <Route path="exam-grades" element={<ExamGradesPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
