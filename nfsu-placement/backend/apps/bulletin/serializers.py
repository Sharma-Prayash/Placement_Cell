from rest_framework import serializers

from core.sanitize import clean_html, clean_text

from .models import Post


class PostWriteSerializer(serializers.ModelSerializer):
    meeting_url = serializers.URLField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Post
        fields = ["kind", "title", "body", "drive", "starts_at", "ends_at", "meeting_url", "visibility", "pinned"]

    def validate_title(self, v):
        return clean_text(v)

    def validate_body(self, v):
        return clean_html(v)

    def validate_meeting_url(self, v):
        if v and not v.startswith("https://"):
            raise serializers.ValidationError("Meeting links must start with https://")
        return v

    def validate(self, a):
        if a.get("kind") in ("ppt", "test", "interview"):
            if not a.get("starts_at") or not a.get("ends_at"):
                raise serializers.ValidationError({"starts_at": "Talks, tests and interviews need a start and end time."})
            if a["ends_at"] <= a["starts_at"]:
                raise serializers.ValidationError({"ends_at": "The end time must be after the start time."})
        return a


class PostReadSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    has_meeting_link = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "kind", "title", "body", "drive", "company_name", "starts_at", "ends_at", "visibility", "pinned",
                  "status", "author_name", "has_meeting_link", "created_at"]

    def get_author_name(self, obj):
        if obj.author.role == "recruiter" and hasattr(obj.author, "recruiter"):
            return obj.author.recruiter.company.name
        return "NFSU Placement Cell"

    def get_company_name(self, obj):
        return obj.drive.company.name if obj.drive_id else None

    def get_has_meeting_link(self, obj):
        return bool(obj.meeting_url)


class PublicPostSerializer(serializers.ModelSerializer):
    """Public bulletin: what and when, nothing internal."""

    class Meta:
        model = Post
        fields = ["id", "kind", "title", "body", "starts_at", "ends_at", "pinned", "created_at"]
