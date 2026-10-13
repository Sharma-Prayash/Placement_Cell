from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from core.permissions import IsAdminOrOfficer, IsAnyMember
from core.ratelimit import client_ip, hit
from core.sanitize import clean_text

from . import llm, service
from .models import AssistantQuery, KnowledgeEntry


class QuestionSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=service.MAX_LEN, trim_whitespace=True,
                                    error_messages={"blank": "Type a question first.", "max_length": "Keep the question under 1,000 characters."})

    def validate_message(self, value):
        value = clean_text(value)
        if not value:
            raise serializers.ValidationError("Type a question first.")
        return value


def _ask(request, user, bucket):
    limit, window = settings.ASSISTANT_RATE_LIMIT
    if not hit(bucket, limit, window):
        return Response({"detail": "You are asking very quickly. Wait a few minutes and try again."}, status=429)
    s = QuestionSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    return Response(service.answer(user, s.validated_data["message"]))


class PublicAssistantView(APIView):
    """Anyone may ask about the process, statistics and interview prep. No session is read here, so a
    personal question from this endpoint always gets "sign in first", even from a signed-in browser."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        return _ask(request, None, f"assistant_ip:{client_ip(request)}")


class AssistantView(APIView):
    """Signed-in members. Students additionally get answers about their own record."""

    permission_classes = [IsAnyMember]

    def post(self, request):
        return _ask(request, request.user, f"assistant_user:{request.user.pk}")


def counts(qs, field):
    return {row[field]: row["n"] for row in qs.values(field).annotate(n=Count("id")).order_by()}


class StaffAssistantView(APIView):
    """Usage and question-bank summary for the Placement Cell. Counts only: questions are never stored."""

    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        recent = AssistantQuery.objects.filter(ts__gte=since)
        kb = KnowledgeEntry.objects.all()
        audit.log(request.user, "assistant.report_viewed", "assistant", "usage", request=request)
        return Response({
            "llm_enabled": llm.is_enabled(),
            "llm_model": settings.GEMINI_MODEL if llm.is_enabled() else None,
            "llm_last": llm.last_status(),
            "window_days": 30,
            "questions": recent.count(),
            "by_intent": counts(recent, "intent"),
            "by_role": counts(recent, "role"),
            "by_status": counts(recent, "status"),
            "unanswered": recent.filter(status="insufficient_evidence").count(),
            "knowledge": {
                "total": kb.count(),
                "by_status": counts(kb, "status"),
                "by_provenance": counts(kb.filter(status="approved"), "provenance"),
                "by_domain": counts(kb.filter(status="approved"), "domain"),
                "companies": sorted(set(kb.filter(status="approved").exclude(company="").values_list("company", flat=True))),
            },
        })
