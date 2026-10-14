"""Second sign-in factor: a one-time code emailed to the user's official address, or an authenticator app.

Properties this module guarantees (each has a test in tests/test_mfa.py):
- The code goes only to the official address on record: the student record's email for students (students
  cannot edit it; changes go through maker-checker), and the account email for staff and recruiters.
- Only an HMAC of the code, keyed with SECRET_KEY, is stored. The code never appears in a response, log or audit row.
- A code is single use, expires after MFA_CODE_TTL_MINUTES, allows MFA_MAX_ATTEMPTS guesses, and works only in the
  browser session that entered the correct password. Issuing a new code cancels the previous one.
- Every wrong code also counts toward the account lockout, the same as a wrong password.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

import pyotp
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from core.ratelimit import hit

from .models import LoginChallenge, User

SESSION_KEY = "mfa_pending"


def required(user: User) -> bool:
    return user.mfa_enabled or user.role in settings.MFA_REQUIRED_ROLES


def official_email(user: User) -> str:
    if user.role == "student":
        student = getattr(user, "student", None)
        return student.email if student else ""
    return user.email


def masked(email: str) -> str:
    local, _, domain = email.partition("@")
    shown = local[0] + "•" * max(1, len(local) - 2) + (local[-1] if len(local) > 1 else "")
    return f"{shown}@{domain}"


def _digest(challenge_id: int, code: str) -> str:
    msg = f"login-code:{challenge_id}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


class DeliveryError(Exception):
    pass


class TooManyCodes(Exception):
    """More than MFA_CODES_PER_HOUR codes for one account: stops anyone holding the password from flooding the inbox."""


def start(user: User, ip: str) -> LoginChallenge:
    """Cancel any open challenge for the user and issue a new one (emailing a code unless they use an app)."""
    now = timezone.now()
    if not user.mfa_enabled and not hit(f"mfa_codes_hour:{user.pk}", settings.MFA_CODES_PER_HOUR, 3600):
        raise TooManyCodes  # checked first, so the code already sent stays usable
    LoginChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    ttl = timedelta(minutes=settings.MFA_CODE_TTL_MINUTES)
    if user.mfa_enabled:
        return LoginChallenge.objects.create(user=user, channel=LoginChallenge.Channel.TOTP, expires_at=now + ttl)

    to = official_email(user)
    if not to:
        raise DeliveryError("No official email address is on record for this account. Contact the Placement Cell.")
    challenge = LoginChallenge.objects.create(user=user, channel=LoginChallenge.Channel.EMAIL, expires_at=now + ttl)
    code = f"{secrets.randbelow(10**6):06d}"
    challenge.code_hash = _digest(challenge.pk, code)
    challenge.save(update_fields=["code_hash"])
    when = timezone.localtime(now).strftime("%d %b %Y, %I:%M %p")
    try:
        send_mail(
            subject="Your NFSU placement portal sign-in code",  # constant: nothing user-typed reaches mail headers
            message=(f"Your sign-in code is {code}\n\n"
                     f"It expires in {settings.MFA_CODE_TTL_MINUTES} minutes and works once.\n"
                     f"Requested for {user.username} on {when} from {ip}.\n\n"
                     "If you did not just enter your password, do not share this code. Someone may know your password: "
                     "change it and tell the Placement Cell.\n\nNFSU Training and Placement Cell"),
            from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[to], fail_silently=False,
        )
    except Exception as exc:  # SMTP down or misconfigured: do not leave a live code behind
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
        raise DeliveryError("We could not send the sign-in code. Try again in a few minutes.") from exc
    return challenge


def check(challenge: LoginChallenge, code: str) -> bool:
    """Count the attempt, then compare in constant time. A used, expired or exhausted challenge never passes."""
    if not challenge.is_open or challenge.attempts >= settings.MFA_MAX_ATTEMPTS:
        return False
    challenge.attempts += 1
    challenge.save(update_fields=["attempts"])
    code = "".join(ch for ch in str(code) if ch.isdigit())[:6]
    if len(code) != 6:
        return False
    if challenge.channel == LoginChallenge.Channel.TOTP:
        ok = pyotp.TOTP(challenge.user.mfa_secret).verify(code, valid_window=1)
    else:
        ok = hmac.compare_digest(challenge.code_hash, _digest(challenge.pk, code))
    if ok:
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=["consumed_at"])
    return ok


def describe(challenge: LoginChallenge) -> dict:
    """What the login screen needs to show. Never includes the code."""
    data = {"mfa_required": True, "channel": challenge.channel,
            "expires_in": max(0, int((challenge.expires_at - timezone.now()).total_seconds())),
            "attempts_left": max(0, settings.MFA_MAX_ATTEMPTS - challenge.attempts)}
    if challenge.channel == LoginChallenge.Channel.EMAIL:
        data["sent_to"] = masked(official_email(challenge.user))
        data["resend_after"] = settings.MFA_RESEND_SECONDS
    return data
