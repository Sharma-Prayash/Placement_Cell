import csv
import io
import secrets

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.placements.models import Application
from core.permissions import ADMIN, COORDINATOR, OFFICER, RECRUITER, IsStaff, IsStaffOrRecruiter, IsStudent
from core.ratelimit import hit, too_many

from .models import Student
from .serializers import SELF_EDITABLE, StaffStudentReadSerializer, StudentSelfSerializer


def own_student(request):
    """The logged-in student's record, always resolved from the session, never from the URL."""
    try:
        return request.user.student
    except Student.DoesNotExist:
        raise Http404


def staff_queryset(user):
    qs = Student.objects.all()
    if user.role == COORDINATOR:
        qs = qs.filter(course=user.coordinator_course)
    return qs


class StudentMeView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response(StudentSelfSerializer(own_student(request)).data)

    def patch(self, request):
        student = own_student(request)
        forbidden = set(request.data.keys()) - SELF_EDITABLE
        if forbidden:
            audit.log(request.user, "security.mass_assignment_blocked", "student", student.pk,
                      after={"fields": sorted(forbidden)}, request=request)
            raise ValidationError({"detail": f"You cannot change these fields: {', '.join(sorted(forbidden))}. "
                                             "Contact the Placement Cell if your record is wrong."})
        before = {k: getattr(student, k) for k in request.data}
        s = StudentSelfSerializer(student, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        audit.log(request.user, "student.self_update", "student", student.pk, before=before, after=dict(request.data), request=request)
        return Response(s.data)


class ResumeUploadView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        student = own_student(request)
        f = request.FILES.get("resume")
        if not f:
            raise ValidationError({"resume": "Attach your resume as a PDF."})
        if f.size > settings.RESUME_MAX_BYTES:
            raise ValidationError({"resume": "The resume must be 2 MB or smaller."})
        head = f.read(5)
        f.seek(0)
        if head != b"%PDF-" or not f.name.lower().endswith(".pdf"):
            raise ValidationError({"resume": "Only PDF files are accepted."})
        settings.PRIVATE_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
        name = secrets.token_hex(16) + ".pdf"
        with open(settings.PRIVATE_MEDIA_ROOT / name, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        old = student.resume_file
        student.resume_file = name
        student.save(update_fields=["resume_file"])
        if old:
            (settings.PRIVATE_MEDIA_ROOT / old).unlink(missing_ok=True)
        audit.log(request.user, "student.resume_uploaded", "student", student.pk, request=request)
        return Response({"detail": "Resume uploaded."})


class ResumeDownloadView(APIView):
    """Staff, or a recruiter for a consenting candidate who applied to one of their drives. Every view is logged."""

    permission_classes = [IsStaffOrRecruiter]

    def get(self, request, placement_id):
        student = Student.objects.filter(placement_id=placement_id, archived_at__isnull=True).first()
        if not student or not student.resume_file:
            raise Http404
        if request.user.role == COORDINATOR and student.course != request.user.coordinator_course:
            raise Http404
        if request.user.role == RECRUITER:
            if not student.consent_share_with_recruiters:
                raise Http404
            if not hit(f"resume:{request.user.pk}", 60, 3600):
                return too_many("Resume view limit reached for this hour.", 3600)
            if not Application.objects.filter(student=student, drive__company=request.user.recruiter.company).exists():
                raise Http404
        audit.log(request.user, "student.resume_viewed", "student", student.pk, request=request)
        resp = FileResponse(open(settings.PRIVATE_MEDIA_ROOT / student.resume_file, "rb"), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{student.placement_id}.pdf"'
        return resp


class StaffStudentListView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = staff_queryset(request.user)
        p = request.query_params
        if p.get("course"):
            qs = qs.filter(course=p["course"])
        if p.get("batch"):
            qs = qs.filter(batch=p["batch"])
        if p.get("registration_status"):
            qs = qs.filter(registration_status=p["registration_status"])
        if p.get("archived") != "1":
            qs = qs.filter(archived_at__isnull=True)
        if p.get("q"):
            q = p["q"][:60]  # passed to the ORM as a bound parameter, never concatenated into SQL
            qs = qs.filter(Q(name__icontains=q) | Q(placement_id__icontains=q) | Q(email__icontains=q))
        rows = StaffStudentReadSerializer(qs[:500], many=True).data
        audit.log(request.user, "student.list_viewed", "student", "", after={"filters": dict(p), "count": len(rows)}, request=request)
        return Response(rows)


class StaffStudentDetailView(APIView):
    permission_classes = [IsStaff]

    def get(self, request, pk):
        student = staff_queryset(request.user).filter(pk=pk).first()
        if not student:
            raise Http404
        audit.log(request.user, "student.viewed", "student", student.pk, request=request)
        return Response(StaffStudentReadSerializer(student).data)


class StaffExportView(APIView):
    """CSV export: role-checked, reason required, row-capped, watermarked and audited."""

    permission_classes = [IsStaff]

    def post(self, request):
        reason = str(request.data.get("reason", "")).strip()
        if len(reason) < 5:
            raise ValidationError({"reason": "Say why you need this export; it is recorded in the audit log."})
        include_contact = bool(request.data.get("include_contact")) and request.user.role in (ADMIN, OFFICER)
        qs = staff_queryset(request.user).filter(archived_at__isnull=True)
        if request.data.get("course"):
            qs = qs.filter(course=request.data["course"])
        qs = qs[: settings.EXPORT_ROW_CAP]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([f"# Exported by {request.user.username} at {timezone.now().isoformat()} — confidential, NFSU Placement Cell"])
        header = ["placement_id", "name", "course", "batch", "registration_status", "eligibility_status", "cgpa", "placement_status"]
        if include_contact:
            header += ["email", "mobile"]
        w.writerow(header)
        from apps.policy.services import placement_status
        count = 0
        for s in qs:
            row = [s.placement_id, s.name, s.course, s.batch, s.registration_status, s.eligibility_status, s.cgpa, placement_status(s)]
            if include_contact:
                row += [s.email, s.mobile]
            # Neutralise spreadsheet formula injection.
            w.writerow(["'" + str(c) if str(c)[:1] in ("=", "+", "-", "@") else c for c in row])
            count += 1
        audit.log(request.user, "student.exported", "student", "", after={"reason": reason, "rows": count, "contact": include_contact}, request=request)
        resp = HttpResponse(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="students_export.csv"'
        return resp
