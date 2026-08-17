from app.schemas.advisor import AdvisorCreate, AdvisorOut, AdvisorPage, AdvisorUpdate
from app.schemas.ai import (
    CourseAdviceRequest,
    CourseAdviceResponse,
    RegulationChatRequest,
    StudySummaryRequest,
    StudySummaryResponse,
)
from app.schemas.auth import LoginResponse, UserInfo
from app.schemas.course import CourseBrief, CourseCreate, CourseOut
from app.schemas.course_class import (
    CourseClassCreate,
    CourseClassOut,
    CourseClassUpdate,
    ScheduleSession,
)
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut
from app.schemas.grade import GradeOut, ScoreUpdate, StudentGradeOut
from app.schemas.homeroom_class import HomeroomClassCreate, HomeroomClassOut
from app.schemas.lecturer import LecturerAccountCreate, LecturerCreate, LecturerOut
from app.schemas.major import MajorCreate, MajorOut
from app.schemas.stats import AcademicResultRow, PopularCourseRow
from app.schemas.student import AccountCreate, StudentCreate, StudentOut, StudentPage, StudentUpdate
