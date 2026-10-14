from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from core.permissions import IsAdminOrOfficer
from core.ratelimit import client_ip, hit, too_many

from .models import Recruiter, RecruiterRequest
from .serializers import RecruiterInterestSerializer, RecruiterRequestStaffSerializer
from .services import create_recruiter, send_activation

THANKS = {"detail": "Thank you. The Placement Cell will review your request and reply by email."}


@method_decorator(csrf_protect, name="dispatch")
class RecruiterInterestView(APIView):
    """Public "Recruit at NFSU" form. Rate-limited per IP (5/hour) and per email (3/day)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not hit(f"recruit_ip:{client_ip(request)}", 5, 3600):
            return too_many("Too many requests from your network. Try again in an hour.", 3600)
        email = str(request.data.get("contact_email", "")).lower()[:254]
        if email and not hit(f"recruit_email:{email}", 3, 86400):
            return too_many("Too many requests for this email today. Try again tomorrow.", 86400)
        if request.data.get("website_confirm"):
            return Response(THANKS, status=201)  # honeypot filled: pretend success, store nothing
        s = RecruiterInterestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        req = s.save()
        audit.log(None, "recruiter.interest_received", "recruiter_request", req.pk, after={"company": req.company_name}, request=request)
        send_mail(
            subject="New recruiter interest received",  # constant subject: user input never reaches mail headers
            message=(f"Company: {req.company_name}\nContact: {req.contact_name} <{req.contact_email}>\n"
                     f"Roles: {req.roles_offered}\nOffer types: {req.offer_types}\n\n"
                     f"Review it in the Placement Cell console: {settings.FRONTEND_URL}/staff/recruiters"),
            from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[settings.PLACEMENT_CELL_EMAIL], fail_silently=True,
        )
        return Response(THANKS, status=201)


class RecruiterRequestListView(APIView):
    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        qs = RecruiterRequest.objects.all()
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(RecruiterRequestStaffSerializer(qs[:200], many=True).data)


class RecruiterRequestDecisionView(APIView):
    permission_classes = [IsAdminOrOfficer]

    def post(self, request, pk, decision):
        with transaction.atomic():
            req = RecruiterRequest.objects.select_for_update().filter(pk=pk, status="new").first()
            if not req:
                raise Http404
            req.reviewed_by, req.reviewed_at = request.user, timezone.now()
            if decision == "verify":
                req.status = "verified"
                req.save()
                rec = create_recruiter(req.company_name, req.website, req.contact_name, req.contact_email, request.user, source_request=req)
                audit.log(request.user, "recruiter.request_verified", "recruiter_request", req.pk, after={"recruiter_code": rec.recruiter_code}, request=request)
                return Response({"detail": f"Verified. Recruiter ID {rec.recruiter_code} was emailed with an activation link.",
                                 "recruiter_code": rec.recruiter_code})
            if decision == "reject":
                req.status = "rejected"
                req.save()
                audit.log(request.user, "recruiter.request_rejected", "recruiter_request", req.pk, request=request)
                send_mail("Your NFSU recruitment request", "Thank you for your interest. The Placement Cell could not verify this request. "
                          "Reply to this email if you think this is a mistake.", settings.DEFAULT_FROM_EMAIL, [req.contact_email], fail_silently=True)
                return Response({"detail": "Rejected."})
        raise Http404


class RecruiterListView(APIView):
    """Every recruiter account, so the Placement Cell can see who has access and who never activated."""

    permission_classes = [IsAdminOrOfficer]

    def get(self, request):
        rows = Recruiter.objects.select_related("company", "user").order_by("-created_at")[:500]
        return Response([{
            "id": r.pk, "recruiter_code": r.recruiter_code, "company": r.company.name, "contact_name": r.contact_name,
            "email": r.user.email, "is_active": r.user.is_active,
            "activated": r.user.has_usable_password(), "activated_at": r.activated_at, "created_at": r.created_at,
            "source": "public form" if r.source_request_id else "added by staff",
        } for r in rows])


class RecruiterResendActivationView(APIView):
    """Send a fresh single-use activation link to a recruiter who has not set a password yet."""

    permission_classes = [IsAdminOrOfficer]

    def post(self, request, pk):
        rec = Recruiter.objects.select_related("company", "user").filter(pk=pk).first()
        if rec is None:
            raise Http404
        if rec.user.has_usable_password():
            return Response({"detail": "This recruiter has already set a password. They can sign in with their Recruiter ID."}, status=400)
        if not hit(f"activation_resend:{rec.pk}", 3, 3600):
            return too_many("An activation link was sent to this recruiter several times this hour. Try again later.", 3600)
        send_activation(rec)
        audit.log(request.user, "recruiter.activation_resent", "recruiter", rec.pk, after={"code": rec.recruiter_code}, request=request)
        return Response({"detail": f"A new activation link for {rec.recruiter_code} was emailed to the recruiter."})
