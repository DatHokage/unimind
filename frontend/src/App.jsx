import { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Spinner } from "./components/ui";

// Code-splitting theo route: mỗi trang nằm trong chunk riêng, chỉ tải khi điều
// hướng tới → chunk khởi đầu nhỏ (react + router + shell), FCP/TBT tốt hơn.
// react-markdown/remark-gfm (nặng) cũng theo đó rời khỏi bundle đầu vào.
// Shell layout giữ import tĩnh để sidebar/header vẽ được ngay.
import MainLayout from "./layouts/MainLayout";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const StudentDashboard = lazy(() => import("./pages/student/Dashboard"));
const SchedulePage = lazy(() => import("./pages/student/SchedulePage"));
const RegistrationPage = lazy(() => import("./pages/student/RegistrationPage"));
const MyEnrollmentsPage = lazy(() => import("./pages/student/MyEnrollmentsPage"));
const GradesPage = lazy(() => import("./pages/student/GradesPage"));
const RegulationChatPage = lazy(() => import("./pages/student/RegulationChatPage"));
const LecturerClassesPage = lazy(() => import("./pages/lecturer/MyClassesPage"));
const GradebookPage = lazy(() => import("./pages/lecturer/GradebookPage"));
const AdvisorClassesPage = lazy(() => import("./pages/advisor/MyClassesPage"));
const AdvisorStudentsPage = lazy(() => import("./pages/advisor/StudentsPage"));
const AdvisorStudentDetailPage = lazy(() => import("./pages/advisor/StudentDetailPage"));
const AdvisorClassOverviewPage = lazy(() => import("./pages/advisor/ClassOverviewPage"));
const OfficeDashboardPage = lazy(() => import("./pages/office/DashboardPage"));
const StudentsManagePage = lazy(() => import("./pages/office/StudentsPage"));
const LecturersManagePage = lazy(() => import("./pages/office/LecturersPage"));
const AdvisorsManagePage = lazy(() => import("./pages/office/AdvisorsPage"));
const MajorsManagePage = lazy(() => import("./pages/office/MajorsPage"));
const HomeroomsManagePage = lazy(() => import("./pages/office/HomeroomsPage"));
const HomeroomStudentsPage = lazy(() => import("./pages/office/HomeroomStudentsPage"));
const CoursesManagePage = lazy(() => import("./pages/office/CoursesPage"));
const CourseClassesManagePage = lazy(() => import("./pages/office/CourseClassesPage"));
const CourseClassStudentsPage = lazy(() => import("./pages/office/CourseClassStudentsPage"));
const ExamGradesPage = lazy(() => import("./pages/office/ExamGradesPage"));

function PageFallback() {
  return (
    <div className="min-h-screen grid place-items-center">
      <Spinner />
    </div>
  );
}

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
        <Suspense fallback={<PageFallback />}>
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
                <Route path="classes/:classId/students" element={<AdvisorStudentsPage />} />
                <Route path="classes/:classId/overview" element={<AdvisorClassOverviewPage />} />
                <Route path="students/:studentId" element={<AdvisorStudentDetailPage />} />
              </Route>
            </Route>

            <Route path="/office" element={<RequireRole roles={["training_office"]} />}>
              <Route element={<MainLayout />}>
                <Route index element={<OfficeDashboardPage />} />
                <Route path="students" element={<StudentsManagePage />} />
                <Route path="lecturers" element={<LecturersManagePage />} />
                <Route path="advisors" element={<AdvisorsManagePage />} />
                <Route path="majors" element={<MajorsManagePage />} />
                <Route path="homerooms" element={<HomeroomsManagePage />} />
                <Route path="homerooms/:classId/students" element={<HomeroomStudentsPage />} />
                <Route path="courses" element={<CoursesManagePage />} />
                <Route path="course-classes" element={<CourseClassesManagePage />} />
                <Route path="course-classes/:classId/students" element={<CourseClassStudentsPage />} />
                <Route path="exam-grades" element={<ExamGradesPage />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
