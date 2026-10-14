"""Email second factor at sign-in, and rate limiting that cannot be dodged. Rows in docs/SECURITY.md point here."""
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import LoginChallenge, Role
from apps.audit.models import AuditLog

from . import factories as f


def password_step(client, username):
    return client.post("/api/auth/login", {"username": username, "password": f.PASSWORD}, format="json")


def code_step(client, code):
    return client.post("/api/auth/login/verify", {"code": code}, format="json")


def wrong(code):
    return f"{(int(code) + 1) % 10**6:06d}"


class EmailCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.s = f.student()
        self.s.user.email = "personal@gmail.example"  # the account email is NOT the official one for students
        self.s.user.save()
        self.officer = f.user("officer1", Role.OFFICER)

    def test_password_alone_does_not_sign_in_and_code_goes_to_official_email(self):
        c = APIClient()
        r = password_step(c, self.s.user.username)
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertEqual(body["channel"], "email")
        self.assertEqual(c.get("/api/auth/me").status_code, 403)  # not signed in yet
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.s.email])  # the student record's email, which students cannot edit
        self.assertNotIn(self.s.email, body["sent_to"])  # masked in the response
        code = f.emailed_code()
        self.assertNotIn(code, r.content.decode())
        r = code_step(c, code)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/auth/me").json()["username"], self.s.user.username)

    def test_staff_code_goes_to_account_email(self):
        password_step(APIClient(), "officer1")
        self.assertEqual(mail.outbox[-1].to, [self.officer.email])

    def test_code_is_never_stored_or_logged(self):
        password_step(APIClient(), "officer1")
        code = f.emailed_code()
        ch = LoginChallenge.objects.get(user=self.officer)
        self.assertNotIn(code, ch.code_hash)
        self.assertEqual(len(ch.code_hash), 64)
        for row in AuditLog.objects.all():
            self.assertNotIn(code, f"{row.before} {row.after} {row.action}")

    def test_code_is_single_use(self):
        c = APIClient()
        password_step(c, "officer1")
        code = f.emailed_code()
        self.assertEqual(code_step(c, code).status_code, 200)
        c.post("/api/auth/logout")
        self.assertEqual(code_step(c, code).status_code, 400)

    def test_code_only_works_in_the_session_that_entered_the_password(self):
        password_step(APIClient(), "officer1")
        attacker = APIClient()
        r = code_step(attacker, f.emailed_code())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(attacker.get("/api/auth/me").status_code, 403)

    def test_expired_code_is_refused(self):
        c = APIClient()
        password_step(c, "officer1")
        LoginChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(code_step(c, f.emailed_code()).status_code, 400)

    def test_wrong_codes_burn_the_code_and_count_toward_lockout(self):
        c = APIClient()
        password_step(c, "officer1")
        code = f.emailed_code()
        statuses = [code_step(c, wrong(code)).status_code for _ in range(5)]
        self.assertEqual(statuses, [401] * 5)
        self.assertEqual(code_step(c, code).status_code, 400)  # the right code no longer works
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.is_locked)  # 5 wrong codes = 5 failures = locked
        self.assertTrue(AuditLog.objects.filter(action="auth.mfa_failed").exists())

    def test_new_code_cancels_the_old_one_and_resend_is_limited(self):
        c = APIClient()
        password_step(c, "officer1")
        first = f.emailed_code()
        r = c.post("/api/auth/login/resend")
        self.assertEqual(r.status_code, 202)
        second = f.emailed_code()
        self.assertEqual(c.post("/api/auth/login/resend").status_code, 429)  # within the 60 s gap
        self.assertIn("Retry-After", c.post("/api/auth/login/resend"))
        if first != second:
            self.assertEqual(code_step(c, first).status_code, 401)
        self.assertEqual(code_step(c, second).status_code, 200)

    @override_settings(MFA_CODES_PER_HOUR=3)
    def test_codes_per_account_are_capped_even_with_the_password(self):
        codes = [password_step(APIClient(), "officer1").status_code for _ in range(4)]
        self.assertEqual(codes, [202, 202, 202, 429])
        self.assertEqual(len(mail.outbox), 3)

    def test_verify_and_resend_require_csrf(self):
        c = APIClient(enforce_csrf_checks=True)
        self.assertEqual(c.post("/api/auth/login/verify", {"code": "123456"}, format="json").status_code, 403)
        self.assertEqual(c.post("/api/auth/login/resend").status_code, 403)

    def test_mail_failure_leaves_no_live_code(self):
        with mock.patch("apps.accounts.mfa.send_mail", side_effect=OSError("smtp down")):
            r = password_step(APIClient(), "officer1")
        self.assertEqual(r.status_code, 503)
        self.assertFalse(LoginChallenge.objects.filter(user=self.officer, consumed_at__isnull=True).exists())

    @override_settings(MFA_REQUIRED_ROLES={"admin", "officer", "coordinator", "recruiter"})
    def test_roles_outside_the_setting_sign_in_with_password_only(self):
        c = APIClient()
        r = password_step(c, self.s.user.username)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class RateLimitHardeningTests(TestCase):
    def setUp(self):
        cache.clear()
        f.user("admin1", Role.ADMIN)

    def test_spoofed_x_real_ip_is_ignored_from_untrusted_peers(self):
        c = APIClient()
        codes = [c.post("/api/auth/login", {"username": f"nobody{i}", "password": "x"}, format="json",
                        HTTP_X_REAL_IP=f"203.0.113.{i}").status_code for i in range(22)]
        self.assertEqual(codes[:20], [401] * 20)
        self.assertTrue(all(code == 429 for code in codes[20:]), "a fresh fake header must not reset the limit")

    @override_settings(TRUSTED_PROXIES={"127.0.0.1"})
    def test_x_real_ip_is_honoured_only_from_the_trusted_proxy(self):
        c = APIClient()
        for i in range(20):
            c.post("/api/auth/login", {"username": f"u{i}", "password": "x"}, format="json", HTTP_X_REAL_IP="198.51.100.7")
        blocked = c.post("/api/auth/login", {"username": "u", "password": "x"}, format="json", HTTP_X_REAL_IP="198.51.100.7")
        other = c.post("/api/auth/login", {"username": "u", "password": "x"}, format="json", HTTP_X_REAL_IP="198.51.100.8")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(other.status_code, 401)  # a different real client has its own bucket

    @override_settings(TRUSTED_PROXIES={"127.0.0.1"})
    def test_one_account_is_limited_across_many_ips(self):
        codes = [APIClient().post("/api/auth/login", {"username": "admin1", "password": "wrong"}, format="json",
                                  HTTP_X_REAL_IP=f"198.51.100.{i}").status_code for i in range(12)]
        self.assertEqual(codes[-1], 429)

    def test_public_endpoints_are_rate_limited_with_retry_after(self):
        c = APIClient()
        for path in ("/api/public/stats", "/api/public/bulletin"):
            last = [c.get(path) for _ in range(61)][-1]
            self.assertEqual(last.status_code, 429, path)
            self.assertEqual(last["Retry-After"], "60")

    def test_cache_keys_never_contain_the_identifier(self):
        from core.ratelimit import _key
        key = _key("recruit_email:hr@company.example")
        self.assertNotIn("hr@company.example", key)
        self.assertTrue(key.startswith("rl:recruit_email:"))
