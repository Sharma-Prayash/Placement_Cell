from django.conf import settings
from django.db import models
from django.db.models import F, Q


class ChangeRequest(models.Model):
    """Maker-checker: admin-side changes to placement records are proposals until a
    different person approves them. The DB constraint makes self-approval impossible
    even if the service layer had a bug."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", "Failed to apply"

    entity = models.CharField(max_length=30)       # student, offer, attendance, flag, recruiter
    action = models.CharField(max_length=20)       # create, update, archive, excuse, waive
    entity_id = models.CharField(max_length=64, blank=True)
    course = models.CharField(max_length=20, blank=True)  # lets coordinators approve their own course only
    before = models.JSONField(null=True, blank=True)
    proposed = models.JSONField()
    reason = models.CharField(max_length=300)
    proposer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="proposals")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approvals")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decision_note = models.CharField(max_length=300, blank=True)
    policy_preview = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(approver__isnull=True) | ~Q(approver=F("proposer")),
                name="proposer_is_not_approver",
            )
        ]
