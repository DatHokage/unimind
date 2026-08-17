from app.models.academic import (
    Course,
    CourseClass,
    Enrollment,
    Grade,
    HomeroomClass,
    Prerequisite,
)
from app.models.base import Base, TimestampMixin
from app.models.person import Advisor, Lecturer, Major, Student
from app.models.user import ROLES, User

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "ROLES",
    "Major",
    "Student",
    "Lecturer",
    "Advisor",
    "HomeroomClass",
    "Course",
    "Prerequisite",
    "CourseClass",
    "Enrollment",
    "Grade",
]
