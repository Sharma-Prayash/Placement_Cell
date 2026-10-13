from django.db import models


class KnowledgeEntry(models.Model):
    """One interview-preparation question with a model answer. Only `approved` entries are ever served.

    `provenance` says where the material comes from, and the assistant shows it on every answer:
    official = backed by a standards or vendor document, reported = public interview experiences,
    practice = a realistic practice question written for students.
    """

    class Provenance(models.TextChoices):
        OFFICIAL = "official", "Official source"
        REPORTED = "reported", "Reported experience"
        PRACTICE = "practice", "Practice question"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for review"
        APPROVED = "approved", "Approved"
        REVOKED = "revoked", "Revoked"

    entry_id = models.CharField(max_length=64, unique=True)
    company = models.CharField(max_length=120, blank=True, default="", db_index=True)
    domain = models.CharField(max_length=120, db_index=True)
    role = models.CharField(max_length=120, blank=True, default="")
    topic = models.CharField(max_length=120)
    subtopic = models.CharField(max_length=120, blank=True, default="")
    question = models.TextField()
    answer = models.TextField()
    difficulty = models.CharField(max_length=10, choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], default="medium")
    provenance = models.CharField(max_length=10, choices=Provenance.choices, default=Provenance.PRACTICE)
    source_title = models.CharField(max_length=255, blank=True, default="")
    source_url = models.URLField(max_length=500, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain", "topic", "entry_id"]

    def __str__(self):
        return f"{self.entry_id}: {self.question[:60]}"


class AssistantQuery(models.Model):
    """Usage metadata for one assistant answer. The question text is deliberately NOT stored:
    students type all sorts of things (phone numbers, names), and none of it is needed to run the service."""

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    role = models.CharField(max_length=20)  # "public" for anonymous callers
    intent = models.CharField(max_length=20)
    mode = models.CharField(max_length=20)
    status = models.CharField(max_length=24)
    source_ids = models.JSONField(default=list, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-ts"]
