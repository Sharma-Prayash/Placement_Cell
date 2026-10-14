"""Adding recruiters: both onboarding paths, who may approve, duplicates, and activation links."""
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.approvals.models import ChangeRequest
from apps.audit.models import AuditLog
from apps.recruiters.models import Company, Recruiter, RecruiterRequest

from . import factories as f

NEW = {"company_name": "Rann Security", "website": "https://rann.example", "contact_name": "Asha Rao",
       "contact_email": "asha@rann.example"}


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def propose(user, data=NEW):
    return client_for(user).post("/api/staff/changes", {"entity": "recruiter", "action": "create", "data": data,
                                                        "reason": "Signed MoU for the 2026-27 session"}, format="json")


class AddRecruiterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = f.user("admin-a", Role.ADMIN)
        self.officer = f.user("officer-a", Role.OFFICER)
        self.coord = f.user("coord-a", Role.COORDINATOR, coordinator_course="MSC_CS")

    def test_admin_adds_recruiter_and_an_officer_approves(self):
        r = propose(self.admin)
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Recruiter.objects.exists())  # nothing exists until a second person approves
        listed = client_for(self.officer).get("/api/staff/changes?status=pending").json()
        self.assertTrue(listed[0]["can_approve"])  # the officer sees the admin's proposal
        r = client_for(self.officer).post(f"/api/staff/changes/{r.json()['id']}/approve", {"note": "MoU checked"}, format="json")
        self.assertEqual(r.status_code, 200)
        rec = Recruiter.objects.get()
        self.assertEqual(rec.company.name, "Rann Security")
        self.assertFalse(rec.user.has_usable_password())  # no password is ever set or emailed
        self.assertIn(rec.recruiter_code, mail.outbox[-1].body)
        self.assertIn("/activate?uid=", mail.outbox[-1].body)
        self.assertEqual(mail.outbox[-1].to, ["asha@rann.example"])

    def test_officer_adds_and_an_admin_approves(self):
        cr = propose(self.officer).json()
        self.assertEqual(client_for(self.admin).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "ok"}, format="json").status_code, 200)
        self.assertTrue(Recruiter.objects.exists())

    def test_nobody_approves_their_own_proposal(self):
        cr = propose(self.admin).json()
        r = client_for(self.admin).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "self"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Recruiter.objects.exists())

    def test_coordinators_students_and_recruiters_cannot_add_or_approve(self):
        cr = propose(self.officer).json()
        r = client_for(self.coord).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "x"}, format="json")
        self.assertEqual(r.status_code, 403)
        s = f.student()
        _, rec_user = f.company_with_recruiter("Acme")
        for user in (s.user, rec_user):
            self.assertEqual(propose(user).status_code, 403)
            self.assertEqual(client_for(user).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "x"}, format="json").status_code, 403)
        self.assertFalse(Recruiter.objects.filter(company__name="Rann Security").exists())

    def test_officer_still_cannot_approve_student_changes(self):
        s = f.student()
        cr = client_for(self.admin).post("/api/staff/changes", {"entity": "student", "action": "update", "entity_id": s.pk,
                                                                "data": {"cgpa": "9.9"}, "reason": "Marks corrected"}, format="json").json()
        r = client_for(self.officer).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_duplicate_email_is_refused_at_proposal(self):
        User.objects.filter(pk=f.user("someone", Role.OFFICER).pk).update(email="ASHA@rann.example")  # case differs
        r = propose(self.admin)
        self.assertEqual(r.status_code, 400)
        self.assertIn("contact_email", r.json())
        self.assertFalse(ChangeRequest.objects.exists())

    def test_existing_company_is_reused_whatever_the_capitalisation(self):
        Company.objects.create(name="Rann Security")
        cr = propose(self.admin, {**NEW, "company_name": "rann security"}).json()
        client_for(self.officer).post(f"/api/staff/changes/{cr['id']}/approve", {"note": "ok"}, format="json")
        self.assertEqual(Company.objects.filter(name__iexact="rann security").count(), 1)


class PublicRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = f.user("admin-b", Role.ADMIN)

    def request(self, email="hr@kutch.example"):
        return RecruiterRequest.objects.create(company_name="Kutch Cloud", contact_name="HR", contact_email=email,
                                               roles_offered="SDE", offer_types="F", eligible_courses=["MSC_CS"])

    def test_admin_verifies_public_request(self):
        req = self.request()
        r = client_for(self.admin).post(f"/api/staff/recruiter-requests/{req.pk}/verify")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Recruiter.objects.filter(recruiter_code=r.json()["recruiter_code"], source_request=req).exists())

    def test_verify_with_an_email_already_in_use_changes_nothing(self):
        User.objects.filter(pk=f.user("taken", Role.STUDENT).pk).update(email="hr@kutch.example")
        req = self.request()
        r = client_for(self.admin).post(f"/api/staff/recruiter-requests/{req.pk}/verify")
        self.assertEqual(r.status_code, 400)
        req.refresh_from_db()
        self.assertEqual(req.status, "new")  # rolled back: still waiting for a decision
        self.assertFalse(Recruiter.objects.exists())


class RecruiterAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.officer = f.user("officer-c", Role.OFFICER)
        self.company, self.rec_user = f.company_with_recruiter("Gir")
        self.rec_user.set_unusable_password()
        self.rec_user.save()
        self.rec = Recruiter.objects.get(user=self.rec_user)

    def test_staff_list_shows_activation_state(self):
        rows = client_for(self.officer).get("/api/staff/recruiters").json()
        row = next(x for x in rows if x["recruiter_code"] == self.rec.recruiter_code)
        self.assertFalse(row["activated"])
        self.assertEqual(row["company"], "Gir")

    def test_only_admin_and_officer_see_the_list(self):
        coord = f.user("coord-c", Role.COORDINATOR, coordinator_course="MSC_CS")
        for user in (coord, f.student().user, self.rec_user):
            self.assertEqual(client_for(user).get("/api/staff/recruiters").status_code, 403)
            self.assertEqual(client_for(user).post(f"/api/staff/recruiters/{self.rec.pk}/resend-activation").status_code, 403)
        self.assertEqual(APIClient().get("/api/staff/recruiters").status_code, 403)

    def test_resend_activation_link(self):
        c = client_for(self.officer)
        r = c.post(f"/api/staff/recruiters/{self.rec.pk}/resend-activation")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/activate?uid=", mail.outbox[-1].body)
        self.assertEqual(mail.outbox[-1].to, [self.rec_user.email])
        self.assertTrue(AuditLog.objects.filter(action="recruiter.activation_resent").exists())
        codes = [c.post(f"/api/staff/recruiters/{self.rec.pk}/resend-activation").status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_no_resend_once_activated_and_unknown_ids_are_404(self):
        self.rec_user.set_password(f.PASSWORD)
        self.rec_user.save()
        c = client_for(self.officer)
        self.assertEqual(c.post(f"/api/staff/recruiters/{self.rec.pk}/resend-activation").status_code, 400)
        self.assertEqual(c.post("/api/staff/recruiters/99999/resend-activation").status_code, 404)
