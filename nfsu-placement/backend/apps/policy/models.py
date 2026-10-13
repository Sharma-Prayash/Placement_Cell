from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.students.models import Student


class PolicyConfig(models.Model):
    """Single-row table so the Placement Cell can tune thresholds without code changes.

    enforce_switching=False is "advisory mode": category/switching rules are shown to
    recruiters and staff as flags, and recruiters decide. Set it True to turn them into blocks.
    """

    a_plus_min_lpa = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("16"))
    a_min_lpa = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("10"))
    b_min_lpa = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("6"))
    b_switch_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.5"))
    acceptance_hours = models.PositiveSmallIntegerField(default=24)
    absence_exclusion_drives = models.PositiveSmallIntegerField(default=3)
    enforce_switching = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PolicyFlag(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WAIVED = "waived", "Waived"
        CLOSED = "closed", "Closed"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="flags")
    rule_code = models.CharField(max_length=40)
    explanation = models.CharField(max_length=300)
    drives_remaining = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    source_ref = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-created_at"]
