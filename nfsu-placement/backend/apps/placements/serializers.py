from datetime import timedelta

from rest_framework import serializers

from apps.accounts.models import COURSE_CODES
from apps.policy.models import PolicyConfig

from .models import Application, Drive, Offer


class DriveSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    category = serializers.SerializerMethodField()

    class Meta:
        model = Drive
        fields = ["id", "company", "company_name", "title", "offer_type", "ctc_lpa", "stipend_amount", "stipend_period",
                  "eligible_courses", "min_cgpa", "max_backlogs", "application_deadline", "company_acceptance_hours",
                  "status", "category"]
        read_only_fields = ["status"]

    def get_category(self, obj):
        from apps.policy.services import category_for, load_config
        return category_for(obj.ctc_lpa, load_config())

    def validate_eligible_courses(self, v):
        if not v or any(c not in COURSE_CODES for c in v):
            raise serializers.ValidationError("List one or more of the five programme codes.")
        return v

    def validate(self, a):
        t = a.get("offer_type", getattr(self.instance, "offer_type", None))
        if t in ("F", "IF") and a.get("ctc_lpa") is None:
            raise serializers.ValidationError({"ctc_lpa": "FTE and I+F drives need an annual CTC in LPA."})
        if t in ("I", "IF") and a.get("stipend_amount") and not a.get("stipend_period"):
            raise serializers.ValidationError({"stipend_period": "Say whether the stipend is per month or total."})
        return a


class OfferWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = ["student", "drive", "company", "offer_type", "ctc_lpa", "stipend_amount", "stipend_period",
                  "ppo_status", "offer_date", "source", "noc_status"]

    def validate(self, a):
        if a["offer_type"] in ("F", "IF") and a.get("ctc_lpa") is None:
            raise serializers.ValidationError({"ctc_lpa": "FTE and I+F offers need an annual CTC in LPA."})
        if a["offer_type"] == "I" and a.get("ctc_lpa") is not None:
            raise serializers.ValidationError({"ctc_lpa": "Internship-only offers record a stipend, not a CTC."})
        if a.get("drive") and a["drive"].company_id != a["company"].id:
            raise serializers.ValidationError({"drive": "The drive belongs to a different company."})
        if a.get("source") == "on_campus" and not a.get("drive"):
            raise serializers.ValidationError({"drive": "On-campus offers must reference a drive."})
        return a


def acceptance_deadline(offer_date, drive):
    """24 hours or the company's stated timeline, whichever is earlier."""
    hours = PolicyConfig.current().acceptance_hours
    if drive and drive.company_acceptance_hours:
        hours = min(hours, drive.company_acceptance_hours)
    return offer_date + timedelta(hours=hours)


class OfferUpdateSerializer(serializers.Serializer):
    acceptance = serializers.ChoiceField(choices=Offer.Acceptance.choices, required=False)
    joining_status = serializers.ChoiceField(choices=Offer.Joining.choices, required=False)
    ppo_status = serializers.ChoiceField(choices=Offer.PPO.choices, required=False)
    noc_status = serializers.ChoiceField(choices=Offer.NOC.choices, required=False)


class OfferReadSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    category = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = ["id", "company_name", "drive", "offer_type", "ctc_lpa", "stipend_amount", "stipend_period",
                  "ppo_status", "acceptance", "joining_status", "offer_date", "acceptance_deadline", "source",
                  "noc_status", "category"]

    def get_category(self, obj):
        from apps.policy.services import category_for, load_config
        return category_for(obj.ctc_lpa, load_config()) if obj.offer_type != "I" else None


class ApplicationSerializer(serializers.ModelSerializer):
    drive_title = serializers.CharField(source="drive.title", read_only=True)
    company_name = serializers.CharField(source="drive.company.name", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "drive", "drive_title", "company_name", "status", "policy_decision", "policy_reasons", "applied_at"]
