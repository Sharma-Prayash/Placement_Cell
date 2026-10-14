import secrets

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.audit import services as audit

from .models import Company, Recruiter


def _new_code():
    while True:
        code = "REC-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        if not User.objects.filter(username=code).exists():
            return code


def activation_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL}/activate?uid={uid}&token={token}"


def ensure_email_free(email):
    """One account per email: a second recruiter login for the same person is a takeover risk and a data mix-up."""
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"contact_email": "An account already uses this email. Check the recruiter list "
                                                "and resend that recruiter's activation link instead."})


def create_recruiter(company_name, website, contact_name, email, actor, source_request=None):
    """Creates company (if new), recruiter account with no usable password, and mails a
    single-use activation link. A password is never emailed."""
    with transaction.atomic():
        ensure_email_free(email)
        company = Company.objects.filter(name__iexact=company_name.strip()).first()  # "kavach" reuses "Kavach"
        if company is None:
            company = Company.objects.create(name=company_name.strip(), website=website or "")
        if not company.verified_at:
            company.verified_at = timezone.now()
            company.save(update_fields=["verified_at"])
        code = _new_code()
        user = User.objects.create(username=code, email=email, role=Role.RECRUITER, first_name=contact_name[:150])
        user.set_unusable_password()
        user.save()
        rec = Recruiter.objects.create(recruiter_code=code, company=company, user=user, contact_name=contact_name,
                                       source_request=source_request)
        audit.log(actor, "recruiter.created", "recruiter", rec.pk, after={"code": code, "company": company.name})
    send_activation(rec)
    return rec


def send_activation(rec):
    """(Re)send the Recruiter ID and a fresh single-use link. Earlier links stay single use and expire in 24 hours."""
    send_mail(
        subject="Your NFSU Placement Cell recruiter account",
        message=(f"Hello {rec.contact_name},\n\nThe NFSU Placement Cell has verified {rec.company.name}.\n"
                 f"Your Recruiter ID is {rec.recruiter_code}.\n\nSet your password within 24 hours using this single-use link:\n"
                 f"{activation_link(rec.user)}\n\nAfter setting it, sign in with your Recruiter ID; a one-time code is then "
                 "emailed to this address.\n\nIf you did not expect this email, ignore it."),
        from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[rec.user.email], fail_silently=True,
    )
