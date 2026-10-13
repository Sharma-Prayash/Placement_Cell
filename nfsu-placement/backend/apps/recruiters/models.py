from django.conf import settings
from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=150, unique=True)
    website = models.URLField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    show_on_public_page = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RecruiterRequest(models.Model):
    """Lands here from the public "Recruit at NFSU" form. Nothing is trusted until staff verify it."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    company_name = models.CharField(max_length=150)
    website = models.URLField(blank=True)
    contact_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    roles_offered = models.CharField(max_length=300)
    offer_types = models.CharField(max_length=10)  # e.g. "I,F,IF"
    ctc_range = models.CharField(max_length=60, blank=True)
    stipend_range = models.CharField(max_length=60, blank=True)
    eligible_courses = models.JSONField(default=list)
    expected_dates = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Recruiter(models.Model):
    recruiter_code = models.CharField(max_length=20, unique=True)  # this is the login ID
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="recruiters")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruiter")
    contact_name = models.CharField(max_length=120)
    source_request = models.ForeignKey(RecruiterRequest, null=True, blank=True, on_delete=models.SET_NULL)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recruiter_code} ({self.company})"
