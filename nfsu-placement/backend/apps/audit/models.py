from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only, hash-chained record of sensitive reads and every write.

    Each row stores the hash of the previous row; editing or deleting any row breaks
    the chain, which `python manage.py verify_audit_chain` reports.
    In PostgreSQL, also REVOKE UPDATE, DELETE on this table from the app role
    (see docs/SECURITY.md).
    """

    ts = models.DateTimeField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=150)  # survives even if the user is deactivated; "system" for jobs
    role = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=60)
    entity = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True)
    prev_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["entity", "entity_id"]), models.Index(fields=["action"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Audit records are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit records cannot be deleted.")
