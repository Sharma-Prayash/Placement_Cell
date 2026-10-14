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
from core.ratelimit import client_ip, hit, ratelimit, too_many

from . import mfa
from .models import LoginChallenge, User

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

    @ratelimit("csrf", limit=60, window_seconds=60)
    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


def _register_failure(user, request, action):
    """Wrong passwords and wrong sign-in codes share one counter, so neither can be guessed past the lockout."""
    user.failed_attempts += 1
    if user.failed_attempts >= settings.LOGIN_MAX_FAILURES:
        user.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        user.failed_attempts = 0
    user.save(update_fields=["failed_attempts", "locked_until"])
    audit.log(user, action, "user", user.pk, request=request)


def _complete_login(request, user, method):
    login(request, user)  # rotates the session key, preventing session fixation
    user.failed_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_attempts", "locked_until"])
    if user.role == "recruiter" and hasattr(user, "recruiter") and not user.recruiter.activated_at:
        user.recruiter.activated_at = timezone.now()
        user.recruiter.save(update_fields=["activated_at"])
    audit.log(user, "auth.login", "user", user.pk, after={"ip": client_ip(request), "second_factor": method}, request=request)
    return Response(me_payload(user))


def _username_key(request):
    return str(request.data.get("username", "")).strip().lower()[:150]


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    """Step 1: password. If the role needs a second factor, a code is emailed and the response says so;
    the session is NOT signed in until step 2 (LoginVerifyView) succeeds."""

    permission_classes = [AllowAny]

    @ratelimit("login_ip", limit=20, window_seconds=300)
    @ratelimit("login_user", limit=10, window_seconds=900, key=_username_key)  # spraying one account from many IPs
    def post(self, request):
        username = str(request.data.get("username", "")).strip()[:150]
        password = str(request.data.get("password", ""))[:256]
        user = User.objects.filter(username=username).first()

        if user and user.is_locked:
            audit.log(user, "auth.login_blocked_locked", "user", user.pk, request=request)
            return Response({"detail": GENERIC_LOGIN_ERROR}, status=401)

        auth_user = authenticate(request, username=username, password=password)
        if auth_user is None:
            if user:
                _register_failure(user, request, "auth.login_failed")
            return Response({"detail": GENERIC_LOGIN_ERROR}, status=401)

        if not mfa.required(auth_user):
            return _complete_login(request, auth_user, "none")
        try:
            challenge = mfa.start(auth_user, client_ip(request))
        except mfa.TooManyCodes:
            return too_many("Too many sign-in codes were sent to this account. Use the latest code or try again in an hour.", 3600)
        except mfa.DeliveryError as exc:
            audit.log(auth_user, "auth.mfa_delivery_failed", "user", auth_user.pk, request=request)
            return Response({"detail": str(exc)}, status=503)
        request.session[mfa.SESSION_KEY] = challenge.pk  # binds the code to this browser session
        audit.log(auth_user, "auth.mfa_code_sent", "user", auth_user.pk, after={"channel": challenge.channel}, request=request)
        return Response(mfa.describe(challenge), status=202)


def _pending(request):
    pk = request.session.get(mfa.SESSION_KEY)
    challenge = LoginChallenge.objects.select_related("user").filter(pk=pk).first() if pk else None
    if challenge is None or not challenge.is_open or not challenge.user.is_active:
        return None
    return challenge


EXPIRED = "This sign-in code has expired or was replaced. Sign in again to get a new one."


@method_decorator(csrf_protect, name="dispatch")
class LoginVerifyView(APIView):
    """Step 2: the 6-digit code from the email (or the authenticator app)."""

    permission_classes = [AllowAny]

    @ratelimit("login_verify", limit=20, window_seconds=300)
    def post(self, request):
        challenge = _pending(request)
        if challenge is None:
            return Response({"detail": EXPIRED, "restart": True}, status=400)
        user = challenge.user
        if user.is_locked:
            return Response({"detail": GENERIC_LOGIN_ERROR, "restart": True}, status=401)
        if not mfa.check(challenge, request.data.get("code", "")):
            _register_failure(user, request, "auth.mfa_failed")
            challenge.refresh_from_db()
            left = max(0, settings.MFA_MAX_ATTEMPTS - challenge.attempts)
            user.refresh_from_db()
            if left == 0 or user.is_locked:
                request.session.pop(mfa.SESSION_KEY, None)
                return Response({"detail": "Too many wrong codes. Sign in again to get a new code.", "restart": True}, status=401)
            return Response({"detail": f"That code is not right. {left} {'try' if left == 1 else 'tries'} left.",
                             "attempts_left": left}, status=401)
        request.session.pop(mfa.SESSION_KEY, None)
        return _complete_login(request, user, challenge.channel)


@method_decorator(csrf_protect, name="dispatch")
class LoginResendView(APIView):
    """Email a fresh code (cancels the old one). Limited per account so the inbox cannot be flooded."""

    permission_classes = [AllowAny]

    def post(self, request):
        challenge = _pending(request)
        if challenge is None:
            return Response({"detail": EXPIRED, "restart": True}, status=400)
        if challenge.channel != LoginChallenge.Channel.EMAIL:
            return Response({"detail": "Your account uses an authenticator app. Enter the code it shows."}, status=400)
        user = challenge.user
        if not hit(f"mfa_resend_gap:{user.pk}", 1, settings.MFA_RESEND_SECONDS):
            return too_many(f"Wait {settings.MFA_RESEND_SECONDS} seconds before asking for another code.", settings.MFA_RESEND_SECONDS)
        try:
            new = mfa.start(user, client_ip(request))
        except mfa.TooManyCodes:
            return too_many("Too many codes requested for this account. Use the latest code or try again in an hour.", 3600)
        except mfa.DeliveryError as exc:
            return Response({"detail": str(exc)}, status=503)
        request.session[mfa.SESSION_KEY] = new.pk
        audit.log(user, "auth.mfa_code_sent", "user", user.pk, after={"channel": new.channel, "resend": True}, request=request)
        return Response(mfa.describe(new), status=202)


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
