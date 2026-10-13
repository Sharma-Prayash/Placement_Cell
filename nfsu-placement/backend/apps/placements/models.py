from django.conf import settings
from django.db import models

from apps.recruiters.models import Company
from apps.students.models import Student


class OfferType(models.TextChoices):
    INTERNSHIP = "I", "Internship only"
    FTE = "F", "FTE only"
    INTERNSHIP_FTE = "IF", "Internship + PPO/FTE"


class StipendPeriod(models.TextChoices):
    MONTH = "month", "per month"
    TOTAL = "total", "total"


class Drive(models.Model):
    """One recruitment opportunity. Category is derived per drive from its CTC, not per company."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="drives")
    title = models.CharField(max_length=150)
    offer_type = models.CharField(max_length=2, choices=OfferType.choices)
    ctc_lpa = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    stipend_amount = models.PositiveIntegerField(null=True, blank=True)
    stipend_period = models.CharField(max_length=10, choices=StipendPeriod.choices, blank=True)
    eligible_courses = models.JSONField(default=list)
    min_cgpa = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    max_backlogs = models.PositiveSmallIntegerField(default=0)
    application_deadline = models.DateTimeField()
    company_acceptance_hours = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Company's own acceptance window, if stated")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-application_deadline"]

    def __str__(self):
        return f"{self.company.name}: {self.title} ({self.offer_type})"


class Application(models.Model):
    """A student applying to a drive makes them a *candidate* for that drive."""

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Not selected"
        SELECTED = "selected", "Selected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    drive = models.ForeignKey(Drive, on_delete=models.CASCADE, related_name="applications")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPLIED)
    policy_decision = models.CharField(max_length=10)
    policy_reasons = models.JSONField(default=list)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["drive", "student"], name="one_application_per_drive")]
        ordering = ["-applied_at"]


class Offer(models.Model):
    """Every offer is its own row, so placement history is never overwritten.
    Status changes are recorded in OfferStatusEvent and the audit log."""

    class PPO(models.TextChoices):
        NA = "na", "Not applicable"
        PENDING = "pending", "Pending"
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    class Acceptance(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    class Joining(models.TextChoices):
        PENDING = "pending", "Pending"
        JOINED = "joined", "Joined"
        NOT_JOINED = "not_joined", "Not joined"

    class Source(models.TextChoices):
        ON = "on_campus", "On campus"
        OFF = "off_campus", "Off campus"

    class NOC(models.TextChoices):
        NA = "na", "Not required"
        REQUIRED = "required", "Required, not submitted"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="offers")
    drive = models.ForeignKey(Drive, null=True, blank=True, on_delete=models.PROTECT, related_name="offers")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="offers")
    offer_type = models.CharField(max_length=2, choices=OfferType.choices)
    ctc_lpa = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    stipend_amount = models.PositiveIntegerField(null=True, blank=True)
    stipend_period = models.CharField(max_length=10, choices=StipendPeriod.choices, blank=True)
    ppo_status = models.CharField(max_length=10, choices=PPO.choices, default=PPO.NA)
    acceptance = models.CharField(max_length=10, choices=Acceptance.choices, default=Acceptance.PENDING)
    joining_status = models.CharField(max_length=12, choices=Joining.choices, default=Joining.PENDING)
    offer_date = models.DateTimeField()
    acceptance_deadline = models.DateTimeField()
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.ON)
    noc_status = models.CharField(max_length=10, choices=NOC.choices, default=NOC.NA)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-offer_date"]


class OfferStatusEvent(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="events")
    field = models.CharField(max_length=30)
    old_value = models.CharField(max_length=30)
    new_value = models.CharField(max_length=30)
    actor_label = models.CharField(max_length=150)
    ts = models.DateTimeField(auto_now_add=True)
