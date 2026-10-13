from rest_framework import serializers

from apps.accounts.models import COURSE_CODES
from apps.policy.services import current_category, placement_status
from core.sanitize import clean_text

from .models import Student

STAFF_EDITABLE = [
    "name", "email", "mobile", "course", "batch", "registration_status", "eligibility_status",
    "cgpa", "backlogs", "tenth_percent", "twelfth_percent", "skills", "remarks",
]


class StaffStudentWriteSerializer(serializers.ModelSerializer):
    """Validates proposals from staff. placement_id is accepted only on create (immutable afterwards)."""

    class Meta:
        model = Student
        fields = ["placement_id"] + STAFF_EDITABLE

    def validate_course(self, v):
        if v not in COURSE_CODES:
            raise serializers.ValidationError("Course must be one of the five programmes.")
        return v

    def validate_remarks(self, v):
        return clean_text(v)

    def validate_skills(self, v):
        return clean_text(v)[:300]

    def validate_name(self, v):
        return clean_text(v)

    def validate(self, attrs):
        if self.instance is not None and "placement_id" in attrs and attrs["placement_id"] != self.instance.placement_id:
            raise serializers.ValidationError({"placement_id": "Placement ID cannot be changed once created."})
        from core.fields import blind_index
        mobile = attrs.get("mobile")
        if mobile:
            dup = Student.objects.filter(mobile_index=blind_index(mobile))
            if self.instance is not None:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError({"mobile": "Another student already uses this mobile number."})
        return attrs


class StaffStudentReadSerializer(serializers.ModelSerializer):
    placement_status = serializers.SerializerMethodField()
    current_category = serializers.SerializerMethodField()
    has_resume = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["id", "placement_id"] + STAFF_EDITABLE + [
            "placement_status", "current_category", "has_resume", "consent_share_with_recruiters",
            "consent_public_listing", "archived_at", "updated_at",
        ]

    def get_placement_status(self, obj):
        return placement_status(obj)

    def get_current_category(self, obj):
        return current_category(obj)

    def get_has_resume(self, obj):
        return bool(obj.resume_file)


class StudentSelfSerializer(serializers.ModelSerializer):
    """What a student sees about themselves. Read-only except the fields in SELF_EDITABLE."""

    placement_status = serializers.SerializerMethodField()
    current_category = serializers.SerializerMethodField()
    has_resume = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ["placement_id", "name", "email", "mobile", "course", "batch", "registration_status",
                  "eligibility_status", "cgpa", "backlogs", "skills", "placement_status", "current_category",
                  "has_resume", "consent_share_with_recruiters", "consent_public_listing"]
        read_only_fields = [f for f in fields if f not in ("skills", "consent_share_with_recruiters", "consent_public_listing")]

    def get_placement_status(self, obj):
        return placement_status(obj)

    def get_current_category(self, obj):
        return current_category(obj)

    def get_has_resume(self, obj):
        return bool(obj.resume_file)

    def validate_skills(self, v):
        return clean_text(v)[:300]


SELF_EDITABLE = {"skills", "consent_share_with_recruiters", "consent_public_listing"}
