from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from core.permissions import STAFF_ROLES
from core.ratelimit import client_ip, ratelimit

from .models import User

GENERIC_LOGIN_ERROR = "That ID and password combination is not valid, or the account is locked."


def me_payload(user):
    data = {"username": user.username, "name": user.get_full_name() or user.first_name or user.username,
            "role": user.role, "mfa_enabled": user.mfa_enabled, "coordinator_course": user.coordinator_course or None}
    if user.role == "recruiter" and hasattr(user, "recruiter"):
        data["company"] = user.recruiter.company.name
    return data


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    @ratelimit("login", limit=20, window_seconds=300)
    def post(self, request):
        username = str(request.data.get("username", "")).strip()[:150]
        password = str(request.data.get("password", ""))[:256]
        otp = str(request.data.get("otp", "")).strip()[:10]
        user = User.objects.filter(username=username).first()

        if user and user.is_locked:
            audit.log(user, "auth.login_blocked_locked", "user", user.pk, request=request)
            return Response({"detail": GENERIC_LOGIN_ERROR}, status=401)

        auth_user = authenticate(request, username=username, password=password)
        if auth_user is None:
            if user:
                user.failed_attempts += 1
                if user.failed_attempts >= settings.LOGIN_MAX_FAILURES:
                    user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                    user.failed_attempts = 0
                user.save(update_fields=["failed_attempts", "locked_until"])
                audit.log(user, "auth.login_failed", "user", user.pk, request=request)
            return Response({"detail": GENERIC_LOGIN_ERROR}, status=401)

        mfa_required = auth_user.mfa_enabled or (settings.REQUIRE_STAFF_MFA and auth_user.role in STAFF_ROLES | {"recruiter"})
        if mfa_required:
            if not auth_user.mfa_enabled:
                return Response({"detail": "Your role requires two-factor authentication. Ask an administrator to enrol you.",
                                 "mfa_setup_required": True}, status=403)
            if not otp:
                return Response({"detail": "Enter the 6-digit code from your authenticator app.", "otp_required": True}, status=401)
            if not pyotp.TOTP(auth_user.mfa_secret).verify(otp, valid_window=1):
                audit.log(auth_user, "auth.mfa_failed", "user", auth_user.pk, request=request)
                return Response({"detail": "That code is not valid. Check your authenticator app and try again.", "otp_required": True}, status=401)

        login(request, auth_user)  # rotates the session key, preventing session fixation
        auth_user.failed_attempts = 0
        auth_user.locked_until = None
        auth_user.save(update_fields=["failed_attempts", "locked_until"])
        if auth_user.role == "recruiter" and hasattr(auth_user, "recruiter") and not auth_user.recruiter.activated_at:
            auth_user.recruiter.activated_at = timezone.now()
            auth_user.recruiter.save(update_fields=["activated_at"])
        audit.log(auth_user, "auth.login", "user", auth_user.pk, after={"ip": client_ip(request)}, request=request)
        return Response(me_payload(auth_user))


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        audit.log(request.user, "auth.logout", "user", request.user.pk, request=request)
        logout(request)  # flushes the server-side session, so the old cookie stops working
        return Response({"detail": "Signed out."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(me_payload(request.user))


@method_decorator(csrf_protect, name="dispatch")
class ActivateView(APIView):
    """Single-use link for recruiters and students to set their first password."""

    permission_classes = [AllowAny]

    @ratelimit("activate", limit=10, window_seconds=3600)
    def post(self, request):
        try:
            uid = force_str(urlsafe_base64_decode(str(request.data.get("uid", ""))))
            user = User.objects.get(pk=uid)
        except Exception:
            user = None
        token = str(request.data.get("token", ""))
        if user is None or not default_token_generator.check_token(user, token):
            return Response({"detail": "This link is invalid or has already been used. Ask the Placement Cell for a new one."}, status=400)
        password = str(request.data.get("password", ""))
        try:
            password_validation.validate_password(password, user)
        except DjangoValidationError as e:
            return Response({"password": list(e.messages)}, status=400)
        user.set_password(password)  # changes the hash, which invalidates the token (single use)
        user.save()
        audit.log(user, "auth.password_set", "user", user.pk, request=request)
        return Response({"detail": "Password set. You can sign in now.", "username": user.username})


class MfaSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        secret = pyotp.random_base32()
        request.session["pending_mfa_secret"] = secret
        uri = pyotp.TOTP(secret).provisioning_uri(name=request.user.username, issuer_name="NFSU Placement")
        return Response({"otpauth_uri": uri, "secret": secret})


class MfaConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        secret = request.session.get("pending_mfa_secret")
        if not secret or not pyotp.TOTP(secret).verify(str(request.data.get("otp", "")), valid_window=1):
            return Response({"detail": "That code did not match. Scan the QR code again and enter a fresh code."}, status=400)
        request.user.mfa_secret = secret
        request.user.mfa_enabled = True
        request.user.save(update_fields=["mfa_secret", "mfa_enabled"])
        del request.session["pending_mfa_secret"]
        audit.log(request.user, "auth.mfa_enabled", "user", request.user.pk, request=request)
        return Response({"detail": "Two-factor authentication is on."})
