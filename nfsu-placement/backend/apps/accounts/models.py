from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from core.fields import EncryptedTextField

COURSES = [
    ("MTECH_CS", "M.Tech. Computer Science"),
    ("MTECH_AIDS", "M.Tech. Artificial Intelligence and Data Science"),
    ("BTECH_MTECH_CSE", "B.Tech.–M.Tech. Computer Science and Engineering"),
    ("MSC_CS", "M.Sc. Computer Science"),
    ("MSC_DFIS", "M.Sc. Digital Forensics and Information Security"),
]
COURSE_CODES = [c for c, _ in COURSES]


class Role(models.TextChoices):
    ADMIN = "admin", "Placement Administrator"
    OFFICER = "officer", "Placement Officer"
    COORDINATOR = "coordinator", "Course Coordinator"
    RECRUITER = "recruiter", "Recruiter"
    STUDENT = "student", "Student"


class User(AbstractUser):
    """One account table for every signed-in role.

    `username` is the login ID: the Placement ID for students, the Recruiter ID for
    recruiters, and a staff handle for the Placement Cell. "Public" users have no account.
    "Candidates" are not a role: a candidate is a student with an application to a drive.
    """

    role = models.CharField(max_length=20, choices=Role.choices)
    coordinator_course = models.CharField(max_length=20, choices=COURSES, blank=True)
    mfa_secret = EncryptedTextField(blank=True, default="")
    mfa_enabled = models.BooleanField(default=False)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    REQUIRED_FIELDS = ["email", "role"]

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    @property
    def is_placement_staff(self):
        return self.role in {Role.ADMIN, Role.OFFICER, Role.COORDINATOR}
