from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Role, User
from apps.placements.models import Drive, Offer
from apps.recruiters.models import Company, Recruiter
from apps.students.models import Student

PASSWORD = "Test-Password-2026!"
_n = [0]


def user(username, role, **extra):
    u = User.objects.create(username=username, role=role, email=f"{username}@t.local", **extra)
    u.set_password(PASSWORD)
    u.save()
    return u


def student(course="MSC_CS", consent=True, **extra):
    _n[0] += 1
    i = _n[0]
    pid = f"T-{i:04d}"
    s = Student.objects.create(placement_id=pid, name=f"Student {i}", email=f"s{i}@t.local", mobile=f"90000{i:05d}",
                               course=course, batch="2025-27", registration_status="registered", eligibility_status="eligible",
                               cgpa=Decimal("8.0"), consent_share_with_recruiters=consent, **extra)
    s.user = user(pid, Role.STUDENT)
    s.save()
    return s


def company_with_recruiter(name="Acme"):
    c = Company.objects.create(name=name)
    u = user(f"REC-{name.upper()}", Role.RECRUITER)
    Recruiter.objects.create(recruiter_code=u.username, company=c, user=u, contact_name="HR")
    return c, u


def drive(company, offer_type="F", ctc="8", courses=("MSC_CS",)):
    return Drive.objects.create(company=company, title="Role", offer_type=offer_type, ctc_lpa=Decimal(ctc) if ctc else None,
                                eligible_courses=list(courses), application_deadline=timezone.now() + timedelta(days=5))


def accepted_offer(s, d):
    now = timezone.now()
    return Offer.objects.create(student=s, drive=d, company=d.company, offer_type=d.offer_type, ctc_lpa=d.ctc_lpa,
                                acceptance="accepted", offer_date=now, acceptance_deadline=now + timedelta(hours=24))
