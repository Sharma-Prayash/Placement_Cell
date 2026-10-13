from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.policy.engine import BLOCK
from apps.policy.services import current_category, evaluate_for, placement_status
from apps.students.models import Student
from apps.students.views import own_student
from core.permissions import COORDINATOR, IsAdminOrOfficer, IsRecruiter, IsStaff, IsStudent

from .models import Application, Drive, Offer, OfferStatusEvent
from .serializers import ApplicationSerializer, DriveSerializer, OfferReadSerializer


# ------------------------------------------------------------------ student
class StudentDrivesView(APIView):
    """Open drives for the student's programme, each with the engine's verdict and reasons."""

    permission_classes = [IsStudent]

    def get(self, request):
        student = own_student(request)
        applied = dict(Application.objects.filter(student=student).values_list("drive_id", "status"))
        out = []
        for d in Drive.objects.filter(status="open", application_deadline__gt=timezone.now()).select_related("company"):
            if student.course not in d.eligible_courses:
                continue
            v = evaluate_for(student, d)
            out.append({**DriveSerializer(d).data, "verdict": v.to_dict(), "application_status": applied.get(d.id)})
        return Response(out)


class StudentApplyView(APIView):
    permission_classes = [IsStudent]

    def post(self, request, drive_id):
        student = own_student(request)
        drive = Drive.objects.filter(pk=drive_id, status="open", application_deadline__gt=timezone.now()).first()
        if not drive:
            raise Http404
        verdict = evaluate_for(student, drive)  # enforced here, server-side, not only in the UI
        if verdict.decision == BLOCK:
            audit.log(request.user, "policy.application_blocked", "drive", drive.pk, after=verdict.to_dict(), request=request)
            return Response({"detail": "You cannot apply to this drive.", "verdict": verdict.to_dict()}, status=403)
        try:
            with transaction.atomic():
                app = Application.objects.create(drive=drive, student=student, policy_decision=verdict.decision,
                                                 policy_reasons=[r.__dict__ for r in verdict.reasons])
                audit.log(request.user, "application.created", "application", app.pk, after={"drive": drive.pk, "decision": verdict.decision}, request=request)
        except IntegrityError:
            raise ValidationError({"detail": "You have already applied to this drive."})
        return Response(ApplicationSerializer(app).data, status=201)


class StudentOffersView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        student = own_student(request)
        return Response({
            "offers": OfferReadSerializer(Offer.objects.filter(student=student).select_related("company"), many=True).data,
            "applications": ApplicationSerializer(Application.objects.filter(student=student).select_related("drive__company"), many=True).data,
        })


class StudentRespondView(APIView):
    """The one write path a student has on an offer: accept or decline before the deadline."""

    permission_classes = [IsStudent]

    def post(self, request, offer_id):
        student = own_student(request)
        decision = request.data.get("decision")
        if decision not in ("accept", "decline"):
            raise ValidationError({"decision": "Choose accept or decline."})
        with transaction.atomic():
            offer = Offer.objects.select_for_update().filter(pk=offer_id, student=student).first()
            if not offer:
                raise Http404  # another student's offer looks exactly like a missing one
            if offer.acceptance != "pending":
                raise ValidationError({"detail": f"This offer is already {offer.acceptance}."})
            if offer.acceptance_deadline < timezone.now():
                offer.acceptance = "expired"
                offer.save(update_fields=["acceptance"])
                raise ValidationError({"detail": "The acceptance deadline has passed, so the offer expired."})
            if decision == "accept" and offer.drive_id:
                verdict = evaluate_for(student, offer.drive, exclude_offer_id=offer.pk)
                hard = [r for r in verdict.reasons if r.severity == "block" and r.code.startswith("OFFER_TYPE")]
                if hard:
                    return Response({"detail": "Accepting this offer would break the offer-type rules.", "verdict": verdict.to_dict()}, status=403)
            new = "accepted" if decision == "accept" else "declined"
            OfferStatusEvent.objects.create(offer=offer, field="acceptance", old_value=offer.acceptance, new_value=new, actor_label=request.user.username)
            offer.acceptance = new
            offer.save(update_fields=["acceptance"])
            audit.log(request.user, f"offer.{new}", "offer", offer.pk, before={"acceptance": "pending"}, after={"acceptance": new}, request=request)
        return Response(OfferReadSerializer(offer).data)


# ------------------------------------------------------------------ staff
class StaffDrivesView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        return Response(DriveSerializer(Drive.objects.select_related("company"), many=True).data)

    def post(self, request):
        if request.user.role == COORDINATOR:
            return Response({"detail": "Coordinators cannot create drives."}, status=403)
        s = DriveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.save(created_by=request.user)
        audit.log(request.user, "drive.created", "drive", d.pk, after=s.data, request=request)
        return Response(DriveSerializer(d).data, status=201)


class StaffOffersView(APIView):
    permission_classes = [IsStaff]

    def get(self, request):
        qs = Offer.objects.select_related("company", "student")
        if request.user.role == COORDINATOR:
            qs = qs.filter(student__course=request.user.coordinator_course)
        data = []
        for o in qs[:500]:
            row = OfferReadSerializer(o).data
            row.update(student_name=o.student.name, placement_id=o.student.placement_id, student_id=o.student_id, course=o.student.course)
            data.append(row)
        return Response(data)


class StaffEvaluateView(APIView):
    """Dry-run the engine for any student/drive pair (staff tool)."""

    permission_classes = [IsStaff]

    def get(self, request):
        s = Student.objects.filter(pk=request.query_params.get("student")).first()
        d = Drive.objects.filter(pk=request.query_params.get("drive")).first()
        if not s or not d:
            raise Http404
        return Response(evaluate_for(s, d).to_dict())


# ------------------------------------------------------------------ recruiter
def _recruiter_company(request):
    return request.user.recruiter.company


def _decimal(v):
    try:
        return Decimal(v)
    except (InvalidOperation, TypeError):
        raise ValidationError({"detail": "Numeric filters must be numbers."})


def _candidate_row(student, verdict=None, reveal_contact=False):
    row = {
        "placement_id": student.placement_id, "name": student.name, "course": student.course, "batch": student.batch,
        "cgpa": str(student.cgpa), "backlogs": student.backlogs,
        "tenth_percent": str(student.tenth_percent) if student.tenth_percent is not None else None,
        "twelfth_percent": str(student.twelfth_percent) if student.twelfth_percent is not None else None,
        "skills": [s.strip() for s in student.skills.split(",") if s.strip()],
        "placement_status": placement_status(student),
        "current_category": current_category(student),  # band only: never another company's name or exact CTC
        "has_resume": bool(student.resume_file) and student.consent_share_with_recruiters,
        "email": student.email if reveal_contact else None,
        "mobile": student.mobile if reveal_contact else None,
        "contact_masked": not reveal_contact,
    }
    if verdict is not None:
        row["verdict"] = verdict.decision
        row["reasons"] = [{"severity": r.severity, "message": r.message} for r in verdict.reasons if r.severity != "info"]
    return row


def _apply_filters(rows, p):
    if p.get("min_cgpa"):
        rows = [r for r in rows if Decimal(r["cgpa"]) >= _decimal(p["min_cgpa"])]
    if p.get("max_cgpa"):
        rows = [r for r in rows if Decimal(r["cgpa"]) <= _decimal(p["max_cgpa"])]
    if p.get("max_backlogs"):
        rows = [r for r in rows if r["backlogs"] <= int(_decimal(p["max_backlogs"]))]
    if p.get("course"):
        rows = [r for r in rows if r["course"] == p["course"]]
    if p.get("batch"):
        rows = [r for r in rows if r["batch"] == p["batch"]]
    if p.get("skill"):
        needle = p["skill"].lower()[:40]
        rows = [r for r in rows if any(needle in s.lower() for s in r["skills"])]
    if p.get("placement_status"):
        rows = [r for r in rows if r["placement_status"] == p["placement_status"]]
    if p.get("category"):
        want = p["category"]
        rows = [r for r in rows if (r["current_category"] or "none") == want]
    if p.get("verdict"):
        rows = [r for r in rows if r.get("verdict") == p["verdict"]]
    return rows


class RecruiterDrivesView(APIView):
    permission_classes = [IsRecruiter]

    def get(self, request):
        drives = Drive.objects.filter(company=_recruiter_company(request))
        out = []
        for d in drives:
            row = DriveSerializer(d).data
            row["applicant_count"] = d.applications.exclude(status="withdrawn").count()
            out.append(row)
        return Response(out)


class RecruiterCandidatesView(APIView):
    """Candidates (applicants) for one of the recruiter's own drives, with stats and the
    engine's advisory verdict. The recruiter filters and decides."""

    permission_classes = [IsRecruiter]

    def get(self, request, drive_id):
        drive = Drive.objects.filter(pk=drive_id, company=_recruiter_company(request)).first()
        if not drive:
            raise Http404  # another company's drive is indistinguishable from a missing one
        rows = []
        for app in drive.applications.exclude(status="withdrawn").select_related("student"):
            st = app.student
            if st.archived_at:
                continue
            reveal = app.status in ("shortlisted", "selected")
            row = _candidate_row(st, evaluate_for(st, drive), reveal_contact=reveal)
            row.update(application_id=app.pk, application_status=app.status)
            rows.append(row)
        rows = _apply_filters(rows, request.query_params)
        audit.log(request.user, "recruiter.candidates_viewed", "drive", drive.pk, after={"count": len(rows)}, request=request)
        return Response({"drive": DriveSerializer(drive).data, "candidates": rows})


class RecruiterTalentPoolView(APIView):
    """Browse consenting, registered students as statistics. No contact details here."""

    permission_classes = [IsRecruiter]

    def get(self, request):
        qs = Student.objects.filter(consent_share_with_recruiters=True, registration_status="registered",
                                    archived_at__isnull=True)
        rows = _apply_filters([_candidate_row(s) for s in qs], request.query_params)
        for r in rows:
            r["has_resume"] = False  # resumes only open for applicants to the recruiter's own drives
        audit.log(request.user, "recruiter.talent_viewed", "student", "", after={"count": len(rows)}, request=request)
        return Response(rows)


class RecruiterApplicationView(APIView):
    permission_classes = [IsRecruiter]

    def post(self, request, app_id):
        app = Application.objects.select_related("drive").filter(pk=app_id, drive__company=_recruiter_company(request)).first()
        if not app:
            raise Http404
        new = request.data.get("status")
        if new not in ("shortlisted", "rejected", "selected"):
            raise ValidationError({"status": "Choose shortlisted, rejected or selected."})
        old = app.status
        app.status = new
        app.save(update_fields=["status", "updated_at"])
        audit.log(request.user, "application.status_changed", "application", app.pk, before={"status": old}, after={"status": new}, request=request)
        return Response({"id": app.pk, "status": new})
