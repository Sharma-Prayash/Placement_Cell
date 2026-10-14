"""Attack-resistance tests. Each maps to a row of the security table in docs/SECURITY.md."""
import io
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.approvals.models import ChangeRequest
from apps.audit.models import AuditLog
from apps.audit.services import verify_chain
from apps.bulletin.models import Post
from apps.placements.models import Application, Offer
from apps.students.models import Student

from . import factories as f


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class AuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = f.user("admin1", Role.ADMIN)

    def test_password_hash_is_argon2_and_never_returned(self):
        self.assertTrue(self.admin.password.startswith("argon2"))
        c = APIClient()
        step1 = c.post("/api/auth/login", {"username": "admin1", "password": f.PASSWORD}, format="json")
        r = c.post("/api/auth/login/verify", {"code": f.emailed_code()}, format="json")
        self.assertEqual(r.status_code, 200)
        for body in (step1.content.decode(), r.content.decode()):
            self.assertNotIn("password", body)
            self.assertNotIn("argon2", body)

    def test_brute_force_locks_account(self):
        c = APIClient()
        for _ in range(5):
            c.post("/api/auth/login", {"username": "admin1", "password": "wrong-password"}, format="json")
        r = c.post("/api/auth/login", {"username": "admin1", "password": f.PASSWORD}, format="json")
        self.assertEqual(r.status_code, 401, "correct password must be refused while locked")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_locked)

    def test_session_cookie_is_httponly_and_dead_after_logout(self):
        c = APIClient()
        self.assertEqual(f.sign_in(c, "admin1").status_code, 200)
        cookie = c.cookies["sessionid"]
        self.assertTrue(cookie["httponly"])
        old = cookie.value
        self.assertEqual(c.get("/api/auth/me").status_code, 200)  # signed in before logout
        c.post("/api/auth/logout")
        replay = APIClient()
        replay.cookies["sessionid"] = old
        self.assertEqual(replay.get("/api/auth/me").status_code, 403)

    def test_login_requires_csrf_token(self):
        c = APIClient(enforce_csrf_checks=True)
        r = c.post("/api/auth/login", {"username": "admin1", "password": f.PASSWORD}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_authenticator_app_users_confirm_with_their_app(self):
        import pyotp
        self.admin.mfa_secret = pyotp.random_base32()
        self.admin.mfa_enabled = True
        self.admin.save()
        c = APIClient()
        r = c.post("/api/auth/login", {"username": "admin1", "password": f.PASSWORD}, format="json")
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["channel"], "totp")
        self.assertEqual(len(mail.outbox), 0)  # no email when an app is enrolled
        self.assertEqual(c.get("/api/auth/me").status_code, 403)
        r = c.post("/api/auth/login/verify", {"code": pyotp.TOTP(self.admin.mfa_secret).now()}, format="json")
        self.assertEqual(r.status_code, 200)


class AccessControlTests(TestCase):
    def setUp(self):
        self.a = f.student()
        self.b = f.student()
        self.company, self.rec = f.company_with_recruiter()
        self.d = f.drive(self.company)
        self.offer_b = f.accepted_offer(self.b, self.d)

    def test_student_cannot_read_staff_or_other_student_data(self):
        c = client_for(self.a.user)
        self.assertEqual(c.get(f"/api/staff/students/{self.b.pk}").status_code, 403)
        self.assertEqual(c.get("/api/staff/students").status_code, 403)
        me = c.get("/api/student/me").json()
        self.assertEqual(me["placement_id"], self.a.placement_id)

    def test_student_cannot_respond_to_another_students_offer(self):
        r = client_for(self.a.user).post(f"/api/student/offers/{self.offer_b.pk}/respond", {"decision": "decline"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.offer_b.refresh_from_db()
        self.assertEqual(self.offer_b.acceptance, "accepted")

    def test_mass_assignment_of_status_or_package_is_rejected_and_logged(self):
        c = client_for(self.a.user)
        for payload in ({"placement_status": "fte_only"}, {"eligibility_status": "eligible", "skills": "x"},
                        {"cgpa": "10.0"}, {"registration_status": "registered"}):
            with self.subTest(payload=payload):
                r = c.patch("/api/student/me", payload, format="json")
                self.assertEqual(r.status_code, 400)
        self.a.refresh_from_db()
        self.assertEqual(str(self.a.cgpa), "8.00")
        self.assertTrue(AuditLog.objects.filter(action="security.mass_assignment_blocked").exists())

    def test_student_can_edit_only_safe_fields(self):
        r = client_for(self.a.user).patch("/api/student/me", {"skills": "Python, SQL"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_recruiter_cannot_see_other_company_drive_or_masked_contacts(self):
        other_company, other_rec = f.company_with_recruiter("Other")
        Application.objects.create(drive=self.d, student=self.a, policy_decision="ALLOW")
        self.assertEqual(client_for(other_rec).get(f"/api/recruiter/drives/{self.d.pk}/candidates").status_code, 404)
        rows = client_for(self.rec).get(f"/api/recruiter/drives/{self.d.pk}/candidates").json()["candidates"]
        self.assertIsNone(rows[0]["mobile"])
        self.assertIsNone(rows[0]["email"])
        self.assertNotIn("ctc_lpa", rows[0])

    def test_contacts_revealed_after_shortlisting(self):
        app = Application.objects.create(drive=self.d, student=self.a, policy_decision="ALLOW")
        client_for(self.rec).post(f"/api/recruiter/applications/{app.pk}", {"status": "shortlisted"}, format="json")
        row = client_for(self.rec).get(f"/api/recruiter/drives/{self.d.pk}/candidates").json()["candidates"][0]
        self.assertEqual(row["email"], self.a.email)

    def test_talent_pool_excludes_non_consenting_students(self):
        hidden = f.student(consent=False)
        ids = {r["placement_id"] for r in client_for(self.rec).get("/api/recruiter/talent").json()}
        self.assertIn(self.a.placement_id, ids)
        self.assertNotIn(hidden.placement_id, ids)

    def test_anonymous_gets_nothing_private(self):
        c = APIClient()
        for url in ("/api/student/me", "/api/staff/students", "/api/recruiter/talent", "/api/bulletin", "/api/staff/audit"):
            with self.subTest(url=url):
                self.assertIn(c.get(url).status_code, (401, 403))


class InjectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = f.user("admin1", Role.ADMIN)
        f.student()

    def test_sql_injection_in_search_and_login(self):
        c = client_for(self.admin)
        r = c.get("/api/staff/students", {"q": "' OR 1=1 --"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])
        r = APIClient().post("/api/auth/login", {"username": "admin1' OR '1'='1", "password": "x' OR '1'='1"}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_xss_in_bulletin_is_stripped(self):
        r = client_for(self.admin).post("/api/bulletin", {
            "kind": "update", "title": "<img src=x onerror=alert(1)>Hello",
            "body": "<p>ok</p><script>alert(document.cookie)</script><a href='javascript:alert(1)'>x</a>"}, format="json")
        self.assertEqual(r.status_code, 201)
        post = Post.objects.get()
        self.assertNotIn("<script", post.body)
        self.assertNotIn("javascript:", post.body)
        self.assertNotIn("onerror", post.title)

    def test_email_header_injection_rejected(self):
        r = APIClient().post("/api/public/recruit", {
            "company_name": "Evil\r\nBcc: victim@example.com", "contact_name": "X", "contact_email": "a@b.com",
            "roles_offered": "Dev", "offer_types": "F", "eligible_courses": ["MSC_CS"]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_upload_rejects_non_pdf(self):
        s = f.student()
        fake = io.BytesIO(b"<?php system($_GET['c']); ?>")
        fake.name = "resume.pdf"
        r = client_for(s.user).post("/api/student/resume", {"resume": fake}, format="multipart")
        self.assertEqual(r.status_code, 400)


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_public_recruiter_form_limited(self):
        c = APIClient()
        codes = []
        for i in range(8):
            codes.append(c.post("/api/public/recruit", {
                "company_name": f"Co {i}", "contact_name": "HR", "contact_email": f"hr{i}@co.com", "roles_offered": "Dev",
                "offer_types": "F", "eligible_courses": ["MSC_CS"]}, format="json").status_code)
        self.assertEqual(codes[:5], [201] * 5)
        self.assertTrue(all(code == 429 for code in codes[5:]))


class MakerCheckerTests(TestCase):
    def setUp(self):
        self.admin1 = f.user("admin1", Role.ADMIN)
        self.admin2 = f.user("admin2", Role.ADMIN)
        self.coord = f.user("coord", Role.COORDINATOR, coordinator_course="MSC_DFIS")
        self.s = f.student()

    def _propose(self, user, data=None):
        return client_for(user).post("/api/staff/changes", {
            "entity": "student", "action": "update", "entity_id": self.s.pk,
            "data": data or {"eligibility_status": "ineligible"}, "reason": "Failed document verification"}, format="json")

    def test_change_is_not_applied_until_someone_else_approves(self):
        cr = self._propose(self.admin1).json()
        self.s.refresh_from_db()
        self.assertEqual(self.s.eligibility_status, "eligible")
        self.assertEqual(client_for(self.admin1).post(f"/api/staff/changes/{cr['id']}/approve", {}, format="json").status_code, 403)
        self.assertEqual(client_for(self.admin2).post(f"/api/staff/changes/{cr['id']}/approve", {}, format="json").status_code, 200)
        self.s.refresh_from_db()
        self.assertEqual(self.s.eligibility_status, "ineligible")
        actions = list(AuditLog.objects.filter(entity="student").values_list("action", flat=True))
        self.assertIn("change.proposed", actions)
        self.assertIn("change.approved", actions)

    def test_database_constraint_blocks_self_approval(self):
        cr = ChangeRequest.objects.create(entity="student", action="update", entity_id=str(self.s.pk), proposed={},
                                          reason="x", proposer=self.admin1, expires_at=timezone.now() + timedelta(hours=1))
        cr.approver = self.admin1
        with self.assertRaises(IntegrityError), transaction.atomic():
            cr.save()

    def test_coordinator_limited_to_own_course(self):
        cr = self._propose(self.admin1).json()  # student is MSC_CS, coordinator is DFIS
        self.assertEqual(client_for(self.coord).post(f"/api/staff/changes/{cr['id']}/approve", {}, format="json").status_code, 403)

    def test_placement_id_is_immutable(self):
        r = self._propose(self.admin1, {"placement_id": "HACKED-1"})
        self.assertEqual(r.status_code, 400)

    def test_blocked_offer_cannot_be_created_through_any_path(self):
        company, _ = f.company_with_recruiter()
        d1 = f.drive(company, "F", "8")
        f.accepted_offer(self.s, d1)
        other, _ = f.company_with_recruiter("Other")
        d2 = f.drive(other, "F", "30")
        r = client_for(self.admin1).post("/api/staff/changes", {
            "entity": "offer", "action": "create", "data": {
                "student": self.s.pk, "drive": d2.pk, "company": other.pk, "offer_type": "F", "ctc_lpa": "30",
                "offer_date": timezone.now().isoformat(), "source": "on_campus"},
            "reason": "Second FTE offer"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("OFFER_TYPE_F_REPEAT", str(r.json()))
        self.assertEqual(Offer.objects.filter(student=self.s).count(), 1)

    def test_student_apply_blocked_server_side(self):
        company, _ = f.company_with_recruiter()
        f.accepted_offer(self.s, f.drive(company, "I", None))
        other, _ = f.company_with_recruiter("Other")
        d = f.drive(other, "I", None)
        r = client_for(self.s.user).post(f"/api/student/drives/{d.pk}/apply")
        self.assertEqual(r.status_code, 403)
        self.assertIn("OFFER_TYPE_I_REPEAT", str(r.json()))


class AuditTamperTests(TestCase):
    def test_editing_a_row_breaks_the_chain(self):
        from apps.audit import services as audit
        for i in range(4):
            audit.log(None, "test.event", "x", i, after={"i": i})
        self.assertTrue(verify_chain()[0])
        row = AuditLog.objects.order_by("id")[1]
        with self.assertRaises(PermissionError):
            row.save()
        with connection.cursor() as cur:  # simulate an attacker editing the DB directly
            cur.execute("UPDATE audit_auditlog SET action = %s WHERE id = %s", ["test.innocent", row.id])
        ok, bad_id, _ = verify_chain()
        self.assertFalse(ok)
        self.assertEqual(bad_id, row.id)


class EncryptionTests(TestCase):
    def test_mobile_is_ciphertext_in_database(self):
        s = f.student()
        with connection.cursor() as cur:
            cur.execute("SELECT mobile FROM students_student WHERE id = %s", [s.pk])
            raw = cur.fetchone()[0]
        self.assertNotEqual(raw, s.mobile)
        self.assertTrue(raw.startswith("gAAAA"))
        self.assertEqual(Student.objects.get(pk=s.pk).mobile, s.mobile)


class PublicDataTests(TestCase):
    def test_public_stats_suppress_small_cells_and_hold_no_personal_data(self):
        company, _ = f.company_with_recruiter()
        d = f.drive(company, "F", "20")
        s = f.student()
        f.accepted_offer(s, d)
        data = APIClient().get("/api/public/stats").json()
        self.assertIsNone(data["fte_ctc_lpa"], "one placed student must not reveal a package")
        body = str(data)
        self.assertNotIn(s.name, body)
        self.assertNotIn(s.email, body)

    def test_meeting_link_only_from_join_endpoint(self):
        company, rec = f.company_with_recruiter()
        d = f.drive(company)
        s = f.student()
        admin = f.user("admin1", Role.ADMIN)
        now = timezone.now()
        post = Post.objects.create(kind="ppt", title="Talk", drive=d, starts_at=now, ends_at=now + timedelta(hours=1),
                                   meeting_url="https://meet.example.com/secret", status="approved", author=rec, reviewed_by=admin)
        listing = client_for(s.user).get("/api/bulletin").content.decode()
        self.assertNotIn("meet.example.com", listing)
        r = client_for(s.user).post(f"/api/bulletin/{post.pk}/join")
        self.assertEqual(r.json()["meeting_url"], "https://meet.example.com/secret")


class AttendanceJobTests(TestCase):
    def test_only_applicants_are_marked_absent(self):
        from apps.placements.jobs import close_attendance
        from apps.policy.models import PolicyFlag
        company, rec = f.company_with_recruiter()
        d = f.drive(company)
        applicant, bystander, attendee = f.student(), f.student(), f.student()
        for s in (applicant, attendee):
            Application.objects.create(drive=d, student=s, policy_decision="ALLOW")
        now = timezone.now()
        post = Post.objects.create(kind="ppt", title="Talk", drive=d, starts_at=now - timedelta(hours=2), ends_at=now - timedelta(hours=1),
                                   meeting_url="https://meet.example.com/x", status="approved", author=rec)
        post.attendance.create(student=attendee, status="present", joined_at=now - timedelta(hours=2))
        close_attendance()
        flagged = set(PolicyFlag.objects.values_list("student_id", flat=True))
        self.assertEqual(flagged, {applicant.pk})


class SensitiveDataInApprovalsTests(TestCase):
    def test_mobile_never_plaintext_in_change_requests_or_audit(self):
        admin1, admin2 = f.user("a1", Role.ADMIN), f.user("a2", Role.ADMIN)
        s = f.student()
        old_mobile = s.mobile
        r = client_for(admin1).post("/api/staff/changes", {"entity": "student", "action": "update", "entity_id": s.pk,
                                                         "data": {"mobile": "9123456789"}, "reason": "Student changed number"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("9123456789", r.content.decode())
        with connection.cursor() as cur:
            cur.execute("SELECT proposed, before FROM approvals_changerequest")
            raw = " ".join(str(x) for x in cur.fetchone())
        self.assertNotIn("9123456789", raw)
        self.assertNotIn(old_mobile, raw)
        client_for(admin2).post(f"/api/staff/changes/{r.json()['id']}/approve", {}, format="json")
        s.refresh_from_db()
        self.assertEqual(s.mobile, "9123456789")
        audit_dump = " ".join(str(x) for x in AuditLog.objects.values_list("before", "after"))
        self.assertNotIn("9123456789", audit_dump)
        self.assertNotIn(old_mobile, audit_dump)

    def test_update_snapshot_contains_only_changed_fields(self):
        admin1 = f.user("a1", Role.ADMIN)
        s = f.student()
        r = client_for(admin1).post("/api/staff/changes", {"entity": "student", "action": "update", "entity_id": s.pk,
                                                         "data": {"cgpa": "8.5"}, "reason": "Semester result update"}, format="json")
        self.assertEqual(set(r.json()["before"].keys()), {"cgpa"})
