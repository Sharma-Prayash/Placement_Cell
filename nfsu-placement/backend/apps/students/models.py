from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from apps.accounts.models import COURSES
from core.fields import EncryptedTextField, blind_index

placement_id_validator = RegexValidator(r"^[A-Z0-9-]{4,20}$", "Placement ID must be 4–20 characters: capital letters, digits or hyphens.")
mobile_validator = RegexValidator(r"^\+?[0-9]{10,13}$", "Enter a 10–13 digit mobile number.")
batch_validator = RegexValidator(r"^20\d{2}-\d{2}$", "Batch must look like 2025-27.")


class Student(models.Model):
    class Registration(models.TextChoices):
        REGISTERED = "registered", "Registered"
        DEREGISTERED = "deregistered", "Deregistered"
        NOT_REGISTERED = "not_registered", "Not registered"

    class Eligibility(models.TextChoices):
        ELIGIBLE = "eligible", "Eligible"
        INELIGIBLE = "ineligible", "Ineligible"
        PENDING = "pending", "Pending verification"

    placement_id = models.CharField(max_length=20, unique=True, validators=[placement_id_validator])
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="student")
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    mobile = EncryptedTextField(validators=[mobile_validator])
    mobile_index = models.CharField(max_length=64, unique=True, editable=False)
    course = models.CharField(max_length=20, choices=COURSES)
    batch = models.CharField(max_length=7, validators=[batch_validator])
    registration_status = models.CharField(max_length=20, choices=Registration.choices, default=Registration.NOT_REGISTERED)
    eligibility_status = models.CharField(max_length=20, choices=Eligibility.choices, default=Eligibility.PENDING)

    # Academic statistics shown to recruiters so they can filter and decide.
    cgpa = models.DecimalField(max_digits=4, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(10)])
    backlogs = models.PositiveSmallIntegerField(default=0)
    tenth_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    twelfth_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    skills = models.CharField(max_length=300, blank=True, help_text="Comma-separated")

    resume_file = models.CharField(max_length=80, blank=True, editable=False)  # random filename in PRIVATE_MEDIA_ROOT
    consent_share_with_recruiters = models.BooleanField(default=False)
    consent_public_listing = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "batch", "name"]
        indexes = [models.Index(fields=["course", "batch"])]

    def save(self, *args, **kwargs):
        if self.mobile:
            self.mobile_index = blind_index(self.mobile)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.placement_id} {self.name}"
