"""Demo data: staff, recruiters, 60 students across the five programmes, drives, offers, bulletin.
All data is fictional. Every account uses SEED_PASSWORD from .env."""
import os
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import COURSE_CODES, Role, User
from apps.audit import services as audit
from apps.bulletin.models import Post
from apps.placements.models import Application, Drive, Offer
from apps.placements.serializers import acceptance_deadline
from apps.policy.models import PolicyConfig
from apps.policy.services import evaluate_for
from apps.recruiters.models import Company, Recruiter, RecruiterRequest
from apps.students.models import Student

FIRST = ["Aarav", "Diya", "Kabir", "Ananya", "Vivaan", "Ishita", "Arjun", "Meera", "Rohan", "Saanvi", "Kunal", "Priya",
         "Dev", "Nisha", "Yash", "Tanvi", "Aditya", "Riya", "Harsh", "Pooja"]
LAST = ["Patel", "Shah", "Mehta", "Desai", "Joshi", "Iyer", "Rao", "Singh", "Verma", "Nair", "Kulkarni", "Trivedi"]
SKILLS = {
    "MTECH_CS": ["Java", "Distributed systems", "Go", "Kubernetes", "DSA"],
    "MTECH_AIDS": ["Python", "PyTorch", "NLP", "SQL", "MLOps"],
    "BTECH_MTECH_CSE": ["C++", "React", "Node.js", "DSA", "System design"],
    "MSC_CS": ["Python", "Django", "SQL", "Linux", "DSA"],
    "MSC_DFIS": ["Digital forensics", "Malware analysis", "SIEM", "Network security", "Python"],
}
ABBR = {"MTECH_CS": "MCS", "MTECH_AIDS": "MAI", "BTECH_MTECH_CSE": "BMC", "MSC_CS": "SCS", "MSC_DFIS": "DFIS"}
COMPANIES = [  # name, website, drives: (title, type, ctc, stipend, courses)
    ("Kavach Cyber Labs", "https://example.com/kavach", [("Security Analyst", "F", "18", None, ["MSC_DFIS", "MTECH_CS"])]),
    ("Sabarmati Analytics", "https://example.com/sabarmati", [("Data Scientist", "IF", "12", 40000, ["MTECH_AIDS", "MSC_CS", "BTECH_MTECH_CSE"])]),
    ("Narmada Systems", "https://example.com/narmada", [("Software Engineer", "F", "8", None, COURSE_CODES),
                                                        ("Summer Intern", "I", None, 25000, COURSE_CODES)]),
    ("Gir Forensics", "https://example.com/gir", [("Forensic Associate", "F", "5", None, ["MSC_DFIS"])]),
    ("Kutch Cloud", "https://example.com/kutch", [("Cloud Engineer", "F", "14", None, ["MTECH_CS", "BTECH_MTECH_CSE", "MSC_CS"]),
                                                  ("ML Platform Engineer", "F", "21", None, ["MTECH_AIDS", "MTECH_CS"])]),
]


class Command(BaseCommand):
    help = "Load fictional demo data (refuses to run if students already exist unless --reset)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first (local SQLite only)")

    def handle(self, *args, **opts):
        password = os.environ.get("SEED_PASSWORD")
        if not password:
            raise CommandError("Set SEED_PASSWORD in backend/.env first.")
        if Student.objects.exists() and not opts["reset"]:
            raise CommandError("Data already exists. Use --reset to wipe and reseed (local database only).")
        random.seed(2627)
        with transaction.atomic():
            if opts["reset"]:
                from django.db import connection
                if connection.vendor != "sqlite":
                    raise CommandError("--reset is only allowed on the local SQLite database.")
                for m in (Post, Application, Offer, Drive, Recruiter, RecruiterRequest, Company, Student):
                    m.objects.all().delete()
                User.objects.all().delete()
                from apps.audit.models import AuditLog
                AuditLog.objects.all()._raw_delete(AuditLog.objects.db)  # local reset only
            self._seed(password)
        call_command("load_knowledge", stdout=self.stdout)  # interview-prep question bank for the assistant
        self.stdout.write(self.style.SUCCESS("Demo data loaded. Accounts (password = SEED_PASSWORD from .env):"))
        for u in User.objects.exclude(role=Role.STUDENT).order_by("role"):
            self.stdout.write(f"  {u.role:<12} {u.username}")
        self.stdout.write("  student      any Placement ID, e.g. " + ", ".join(Student.objects.values_list("placement_id", flat=True)[:3]))

    def _user(self, username, role, password, **extra):
        u = User.objects.create(username=username, role=role, email=f"{username.lower()}@nfsu.local", **extra)
        u.set_password(password)
        u.save()
        return u

    def _seed(self, password):
        PolicyConfig.current()
        admin1 = self._user("admin.mehta", Role.ADMIN, password, first_name="R. Mehta")
        self._user("admin.shah", Role.ADMIN, password, first_name="K. Shah")
        self._user("officer.desai", Role.OFFICER, password, first_name="P. Desai")
        self._user("coord.dfis", Role.COORDINATOR, password, first_name="DFIS Coordinator", coordinator_course="MSC_DFIS")
        self._user("coord.aids", Role.COORDINATOR, password, first_name="AIDS Coordinator", coordinator_course="MTECH_AIDS")

        now = timezone.now()
        students = []
        n = 0
        for course in COURSE_CODES:
            for i in range(12):
                n += 1
                name = f"{random.choice(FIRST)} {random.choice(LAST)}"
                s = Student.objects.create(
                    placement_id=f"NFSU26-{ABBR[course]}-{i + 1:03d}",
                    name=name, email=f"student{n}@students.nfsu.local", mobile=f"98{random.randint(10000000, 99999999)}",
                    course=course, batch="2025-27" if course != "BTECH_MTECH_CSE" else "2022-27",
                    registration_status="registered" if i < 11 else "not_registered",
                    eligibility_status="eligible" if i < 10 else ("pending" if i == 10 else "ineligible"),
                    cgpa=Decimal(str(round(random.uniform(6.2, 9.6), 2))), backlogs=0 if random.random() > 0.15 else 1,
                    tenth_percent=Decimal(str(round(random.uniform(70, 97), 2))), twelfth_percent=Decimal(str(round(random.uniform(65, 96), 2))),
                    skills=", ".join(random.sample(SKILLS[course], 3)),
                    consent_share_with_recruiters=i < 10, consent_public_listing=i % 3 == 0,
                )
                u = self._user(s.placement_id, Role.STUDENT, password, first_name=name)
                s.user = u
                s.save(update_fields=["user"])
                students.append(s)

        drives = []
        for idx, (cname, site, dlist) in enumerate(COMPANIES):
            company = Company.objects.create(name=cname, website=site, verified_at=now)
            ru = self._user(f"REC-DEMO{idx + 1}", Role.RECRUITER, password, first_name=f"HR, {cname}")
            Recruiter.objects.create(recruiter_code=ru.username, company=company, user=ru, contact_name=f"HR, {cname}", activated_at=now)
            for title, typ, ctc, stipend, courses in dlist:
                drives.append(Drive.objects.create(
                    company=company, title=title, offer_type=typ, ctc_lpa=Decimal(ctc) if ctc else None,
                    stipend_amount=stipend, stipend_period="month" if stipend else "", eligible_courses=courses,
                    min_cgpa=Decimal("6.5"), max_backlogs=0, application_deadline=now + timedelta(days=random.randint(3, 20)),
                    company_acceptance_hours=12 if typ == "F" and ctc and Decimal(ctc) > 15 else None, created_by=admin1,
                ))

        # Applications: every eligible student applies to a couple of drives open to them.
        for s in students:
            open_to = [d for d in drives if s.course in d.eligible_courses]
            for d in random.sample(open_to, min(2, len(open_to))):
                v = evaluate_for(s, d)
                if v.decision != "BLOCK":
                    Application.objects.create(drive=d, student=s, policy_decision=v.decision,
                                               policy_reasons=[r.__dict__ for r in v.reasons])

        # Accepted offers for some students so stats and switching rules have something to show.
        placed = 0
        for app in Application.objects.select_related("drive", "student").order_by("?"):
            if placed >= 26:
                break
            if Offer.objects.filter(student=app.student).exists():
                continue
            d = app.drive
            od = now - timedelta(days=random.randint(5, 40))
            Offer.objects.create(
                student=app.student, drive=d, company=d.company, offer_type=d.offer_type, ctc_lpa=d.ctc_lpa,
                stipend_amount=d.stipend_amount, stipend_period=d.stipend_period,
                ppo_status="pending" if d.offer_type == "IF" else "na", acceptance="accepted",
                joining_status=random.choice(["pending", "joined"]), offer_date=od,
                acceptance_deadline=acceptance_deadline(od, d),
            )
            app.status = "selected"
            app.save(update_fields=["status"])
            placed += 1
        # One fresh pending offer to demo the acceptance deadline.
        fresh = next(s for s in students if not Offer.objects.filter(student=s).exists() and s.registration_status == "registered")
        d = next(x for x in drives if fresh.course in x.eligible_courses and x.offer_type == "F")
        Offer.objects.create(student=fresh, drive=d, company=d.company, offer_type="F", ctc_lpa=d.ctc_lpa, offer_date=now,
                             acceptance_deadline=acceptance_deadline(now, d))
        Application.objects.get_or_create(drive=d, student=fresh, defaults={"policy_decision": "ALLOW", "status": "selected"})

        Post.objects.create(kind="update", title="Placement session 2026–27 registration is open",
                            body="<p>Register through the student portal before 31 October.</p>", visibility="public",
                            pinned=True, status="approved", author=admin1, reviewed_by=admin1)
        Post.objects.create(kind="cell_event", title="Resume-writing workshop", body="<p>Seminar hall, Block B.</p>",
                            starts_at=now + timedelta(days=4), ends_at=now + timedelta(days=4, hours=2),
                            visibility="public", status="approved", author=admin1, reviewed_by=admin1)
        k_drive = drives[0]
        Post.objects.create(kind="ppt", title=f"{k_drive.company.name} pre-placement talk", drive=k_drive,
                            body="<p>Role overview and Q&amp;A with the security team.</p>",
                            starts_at=now - timedelta(minutes=5), ends_at=now + timedelta(hours=1),
                            meeting_url="https://meet.example.com/kavach-ppt", visibility="members", status="approved",
                            author=k_drive.company.recruiters.first().user, reviewed_by=admin1)
        Post.objects.create(kind="ppt", title="Kutch Cloud pre-placement talk", drive=drives[-1],
                            starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=1),
                            meeting_url="https://meet.example.com/kutch-ppt", status="pending",
                            author=drives[-1].company.recruiters.first().user)
        RecruiterRequest.objects.create(company_name="Dholavira Data Pvt Ltd", website="https://example.com/dholavira",
                                        contact_name="A. Kapoor", contact_email="hr@dholavira.example.com",
                                        roles_offered="Data Engineer", offer_types="F", ctc_range="9-11 LPA",
                                        eligible_courses=["MTECH_AIDS", "MSC_CS"])
        audit.log(None, "seed.loaded", "system", "", after={"students": len(students), "drives": len(drives)})
