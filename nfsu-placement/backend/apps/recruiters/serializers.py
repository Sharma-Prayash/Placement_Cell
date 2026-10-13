from rest_framework import serializers

from apps.accounts.models import COURSE_CODES
from core.sanitize import clean_text

from .models import RecruiterRequest


def _no_header_injection(value):
    if "\r" in value or "\n" in value:
        raise serializers.ValidationError("Line breaks are not allowed here.")
    return value


class RecruiterInterestSerializer(serializers.ModelSerializer):
    """Public form. Strict lengths and plain text only; a hidden honeypot field catches bots."""

    website_confirm = serializers.CharField(required=False, allow_blank=True, write_only=True)  # honeypot

    class Meta:
        model = RecruiterRequest
        fields = ["company_name", "website", "contact_name", "contact_email", "contact_phone", "roles_offered",
                  "offer_types", "ctc_range", "stipend_range", "eligible_courses", "expected_dates", "notes",
                  "website_confirm"]

    def validate_company_name(self, v):
        return clean_text(_no_header_injection(v))

    def validate_contact_name(self, v):
        return clean_text(_no_header_injection(v))

    def validate_roles_offered(self, v):
        return clean_text(v)

    def validate_notes(self, v):
        return clean_text(v)[:2000]

    def validate_contact_phone(self, v):
        v = v.strip()
        if v and not v.replace("+", "").replace(" ", "").isdigit():
            raise serializers.ValidationError("Use digits only.")
        return v

    def validate_offer_types(self, v):
        parts = {p.strip().upper() for p in v.split(",") if p.strip()}
        if not parts or not parts <= {"I", "F", "IF"}:
            raise serializers.ValidationError("Choose from I, F and IF.")
        return ",".join(sorted(parts))

    def validate_eligible_courses(self, v):
        if not isinstance(v, list) or any(c not in COURSE_CODES for c in v):
            raise serializers.ValidationError("Pick from the five programmes.")
        return v

    def create(self, validated_data):
        validated_data.pop("website_confirm", None)
        return super().create(validated_data)


class RecruiterRequestStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruiterRequest
        fields = "__all__"


class AdminRecruiterSerializer(serializers.Serializer):
    """Placement Cell adds a recruiter directly (goes through maker-checker)."""

    company_name = serializers.CharField(max_length=150)
    website = serializers.URLField(required=False, allow_blank=True)
    contact_name = serializers.CharField(max_length=120)
    contact_email = serializers.EmailField()

    def validate_company_name(self, v):
        return clean_text(_no_header_injection(v))

    def validate_contact_name(self, v):
        return clean_text(_no_header_injection(v))
