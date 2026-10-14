from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.placements.models import Application
from apps.policy.engine import BLOCK
from apps.policy.services import evaluate_for
from apps.students.views import own_student
from core.permissions import ADMIN, OFFICER, RECRUITER, IsAdminOrOfficer, IsAnyMember, IsStudent
from core.ratelimit import ratelimit

from .models import Attendance, Post
from .serializers import PostReadSerializer, PostWriteSerializer, PublicPostSerializer


def _visible_now():
    now = timezone.now()
    return Post.objects.filter(status="approved").filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now - timedelta(days=30)))


class PublicBulletinView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @ratelimit("public_bulletin", limit=60, window_seconds=60)
    def get(self, request):
        qs = _visible_now().filter(visibility="public")[:30]
        return Response(PublicPostSerializer(qs, many=True).data)


class BulletinView(APIView):
    permission_classes = [IsAnyMember]

    def get(self, request):
        u = request.user
        qs = _visible_now().select_related("author", "drive__company")
        if u.role == RECRUITER:
            mine = Post.objects.filter(author=u).exclude(status="approved")
            qs = (qs | mine).distinct()
        data = PostReadSerializer(qs[:100], many=True).data
        if u.role == "student":
            att = dict(Attendance.objects.filter(student=u.student, post_id__in=[p["id"] for p in data]).values_list("post_id", "status"))
            applied = set(Application.objects.filter(student=u.student).values_list("drive_id", flat=True))
            for p in data:
                p["my_attendance"] = att.get(p["id"])
                p["expected_to_attend"] = p["drive"] in applied
        return Response(data)

    def post(self, request):
        u = request.user
        if u.role not in (ADMIN, OFFICER, RECRUITER):
            return Response({"detail": "Only the Placement Cell and recruiters can post to the bulletin."}, status=403)
        s = PostWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        if u.role == RECRUITER:
            drive = s.validated_data.get("drive")
            if s.validated_data["kind"] not in ("ppt", "test", "interview"):
                raise ValidationError({"kind": "Recruiters can post talks, tests and interviews."})
            if not drive or drive.company_id != u.recruiter.company_id:
                raise ValidationError({"drive": "Pick one of your company's drives."})
            post = s.save(author=u, status="pending", pinned=False, visibility="members")
        else:
            post = s.save(author=u, status="approved", reviewed_by=u)
        audit.log(u, "bulletin.posted", "post", post.pk, after={"title": post.title, "status": post.status}, request=request)
        return Response(PostReadSerializer(post).data, status=201)


class BulletinModerationView(APIView):
    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        return Response(PostReadSerializer(Post.objects.filter(status="pending").select_related("author", "drive__company"), many=True).data)

    def post(self, request, pk, decision):
        post = Post.objects.filter(pk=pk, status="pending").first()
        if not post or decision not in ("approve", "reject"):
            raise Http404
        post.status = "approved" if decision == "approve" else "rejected"
        post.reviewed_by = request.user
        post.save(update_fields=["status", "reviewed_by"])
        audit.log(request.user, f"bulletin.{post.status}", "post", post.pk, request=request)
        return Response(PostReadSerializer(post).data)


class JoinEventView(APIView):
    """The only way to obtain a meeting link. Checks eligibility and the time window,
    records attendance, then returns the link."""

    permission_classes = [IsStudent]

    def post(self, request, pk):
        student = own_student(request)
        post = Post.objects.filter(pk=pk, status="approved").select_related("drive").first()
        if not post or not post.meeting_url:
            raise Http404
        now = timezone.now()
        if post.starts_at and now < post.starts_at - timedelta(minutes=15):
            return Response({"detail": "The link opens 15 minutes before the start time."}, status=403)
        if post.ends_at and now > post.ends_at:
            return Response({"detail": "This event has ended."}, status=403)
        if post.drive_id:
            if not Application.objects.filter(drive=post.drive, student=student).exclude(status="withdrawn").exists():
                if evaluate_for(student, post.drive).decision == BLOCK:
                    return Response({"detail": "You are not eligible for this company's drive."}, status=403)
        if post.tracks_attendance:
            try:
                with transaction.atomic():
                    Attendance.objects.create(post=post, student=student, joined_at=now, status="present")
            except IntegrityError:
                pass
        audit.log(request.user, "event.joined", "post", post.pk, request=request)
        return Response({"meeting_url": post.meeting_url})


class AttendanceListView(APIView):
    permission_classes = [IsAdminOrOfficer]

    def get(self, request, pk):
        rows = Attendance.objects.filter(post_id=pk).select_related("student")
        return Response([{"id": a.pk, "placement_id": a.student.placement_id, "name": a.student.name, "status": a.status,
                          "joined_at": a.joined_at, "excuse_reason": a.excuse_reason} for a in rows])
