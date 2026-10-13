from django.conf import settings
from django.db import models

from apps.placements.models import Drive
from apps.students.models import Student
from core.fields import EncryptedTextField


class Post(models.Model):
    """One item on the common bulletin: placement updates, Placement Cell events,
    and pre-placement talks / tests / interviews pushed by an admin or a recruiter.
    Recruiter posts stay pending until the Placement Cell approves them."""

    class Kind(models.TextChoices):
        UPDATE = "update", "Placement update"
        CELL_EVENT = "cell_event", "Placement Cell event"
        PPT = "ppt", "Pre-placement talk"
        TEST = "test", "Test"
        INTERVIEW = "interview", "Interview"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Published"
        REJECTED = "rejected", "Rejected"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Everyone, including public"
        MEMBERS = "members", "Signed-in users only"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True, max_length=5000)  # sanitised on save by the service
    drive = models.ForeignKey(Drive, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    meeting_url = EncryptedTextField(blank=True, default="")  # never returned by list APIs
    visibility = models.CharField(max_length=10, choices=Visibility.choices, default=Visibility.MEMBERS)
    pinned = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="posts")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    attendance_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pinned", "starts_at", "-created_at"]

    @property
    def tracks_attendance(self):
        return self.kind in {self.Kind.PPT, self.Kind.TEST, self.Kind.INTERVIEW} and self.drive_id is not None


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        EXCUSED = "excused", "Excused"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="attendance")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance")
    joined_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices)
    excuse_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "student"], name="one_attendance_per_event")]
