"""Background jobs. Run them on a schedule (cron / Celery beat):
    python manage.py run_jobs
System actions are exempt from maker-checker but every change is audited as actor "system".
"""
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.bulletin.models import Attendance, Post
from apps.policy.models import PolicyConfig, PolicyFlag

from .models import Application, Drive, Offer, OfferStatusEvent


def expire_offers(now=None):
    now = now or timezone.now()
    n = 0
    for offer in Offer.objects.filter(acceptance="pending", acceptance_deadline__lt=now):
        with transaction.atomic():
            OfferStatusEvent.objects.create(offer=offer, field="acceptance", old_value="pending", new_value="expired", actor_label="system")
            offer.acceptance = "expired"
            offer.save(update_fields=["acceptance"])
            audit.log(None, "offer.expired", "offer", offer.pk, before={"acceptance": "pending"}, after={"acceptance": "expired"})
        n += 1
    return n


def close_drives(now=None):
    """Closing a drive counts down absence exclusions for students that drive was open to."""
    now = now or timezone.now()
    n = 0
    for drive in Drive.objects.filter(status="open", application_deadline__lt=now):
        with transaction.atomic():
            drive.status = "closed"
            drive.save(update_fields=["status"])
            for flag in PolicyFlag.objects.filter(status="open", rule_code="ABSENTEEISM", drives_remaining__gt=0,
                                                  student__course__in=drive.eligible_courses):
                flag.drives_remaining -= 1
                if flag.drives_remaining == 0:
                    flag.status = "closed"
                flag.save(update_fields=["drives_remaining", "status"])
            audit.log(None, "drive.closed", "drive", drive.pk)
        n += 1
    return n


def close_attendance(now=None):
    """After an event ends, every *applicant* to that drive without a join record is absent.
    Only applicants are expected; merely eligible students are never flagged."""
    now = now or timezone.now()
    cfg = PolicyConfig.current()
    flagged = 0
    for post in Post.objects.filter(status="approved", attendance_closed=False, ends_at__lt=now, drive__isnull=False,
                                    kind__in=["ppt", "test", "interview"]):
        with transaction.atomic():
            expected = Application.objects.filter(drive=post.drive).exclude(status__in=["withdrawn", "rejected"]).select_related("student")
            present = set(Attendance.objects.filter(post=post).values_list("student_id", flat=True))
            for app in expected:
                if app.student_id in present:
                    continue
                att = Attendance.objects.create(post=post, student=app.student, status="absent")
                PolicyFlag.objects.create(
                    student=app.student, rule_code="ABSENTEEISM", drives_remaining=cfg.absence_exclusion_drives,
                    explanation=f"Absent from '{post.title}' on {post.starts_at:%d %b %Y}; flagged for the next {cfg.absence_exclusion_drives} drives unless excused.",
                    source_ref=f"attendance:{att.pk}",
                )
                flagged += 1
            post.attendance_closed = True
            post.save(update_fields=["attendance_closed"])
            audit.log(None, "event.attendance_closed", "post", post.pk, after={"absent_flagged": flagged})
    return flagged


def run_all():
    return {"offers_expired": expire_offers(), "drives_closed": close_drives(), "absentees_flagged": close_attendance()}
