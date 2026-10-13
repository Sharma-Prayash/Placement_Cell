"""Placement statistics. Internal reports see everything; the public view is built from
the same numbers but with small cells suppressed and nothing personal or internal."""
import statistics
from collections import Counter, defaultdict
from decimal import Decimal

from django.conf import settings

from apps.accounts.models import COURSES
from apps.placements.models import Offer
from apps.policy.models import PolicyFlag
from apps.policy.services import category_for, load_config, placement_status
from apps.students.models import Student

COURSE_NAMES = dict(COURSES)


def _money_stats(values):
    vals = [float(v) for v in values]
    if not vals:
        return {"count": 0, "highest": None, "average": None, "median": None}
    return {"count": len(vals), "highest": round(max(vals), 2), "average": round(sum(vals) / len(vals), 2),
            "median": round(statistics.median(vals), 2)}


def internal_report(course=None, batch=None):
    students = Student.objects.filter(archived_at__isnull=True)
    if course:
        students = students.filter(course=course)
    if batch:
        students = students.filter(batch=batch)
    students = list(students)
    ids = [s.id for s in students]
    offers = list(Offer.objects.filter(student_id__in=ids).select_related("company", "student"))
    accepted = [o for o in offers if o.acceptance == "accepted"]
    cfg = load_config()

    status_by_student = {s.id: placement_status(s) for s in students}
    placed_ids = {sid for sid, st in status_by_student.items() if st != "unplaced"}

    by_course = defaultdict(lambda: {"students": 0, "registered": 0, "placed": 0})
    by_batch = defaultdict(lambda: {"students": 0, "placed": 0})
    for s in students:
        c = by_course[s.course]
        c["students"] += 1
        c["registered"] += s.registration_status == "registered"
        c["placed"] += s.id in placed_ids
        b = by_batch[s.batch]
        b["students"] += 1
        b["placed"] += s.id in placed_ids

    company = defaultdict(lambda: {"offers": 0, "accepted": 0, "categories": set(), "ctc": []})
    for o in offers:
        row = company[o.company.name]
        row["offers"] += 1
        row["accepted"] += o.acceptance == "accepted"
        cat = category_for(o.ctc_lpa, cfg) if o.offer_type != "I" else None
        if cat:
            row["categories"].add(cat)
        if o.ctc_lpa is not None:
            row["ctc"].append(float(o.ctc_lpa))

    fte_ctc = [o.ctc_lpa for o in accepted if o.offer_type in ("F", "IF") and o.ctc_lpa is not None]
    monthly_stipends = [o.stipend_amount for o in accepted if o.offer_type in ("I", "IF") and o.stipend_amount and o.stipend_period == "month"]

    return {
        "totals": {
            "students": len(students),
            "registered": sum(s.registration_status == "registered" for s in students),
            "eligible": sum(s.eligibility_status == "eligible" for s in students),
            "ineligible": sum(s.eligibility_status == "ineligible" for s in students),
            "pending_verification": sum(s.eligibility_status == "pending" for s in students),
            "placed_unique_students": len(placed_ids),
            "unplaced": len(students) - len(placed_ids),
            "total_offers": len(offers),
            "accepted_offers": len(accepted),
        },
        "placement_status_counts": dict(Counter(status_by_student.values())),
        "offer_type_counts": dict(Counter(o.offer_type for o in accepted)),
        "fte_ctc_lpa": _money_stats(fte_ctc),
        "internship_stipend_monthly_inr": _money_stats(monthly_stipends),
        "by_course": {k: {**v, "name": COURSE_NAMES.get(k, k)} for k, v in by_course.items()},
        "by_batch": dict(by_batch),
        "by_company": [{"company": k, "offers": v["offers"], "accepted": v["accepted"], "categories": sorted(v["categories"]),
                        "highest_ctc_lpa": max(v["ctc"]) if v["ctc"] else None} for k, v in sorted(company.items())],
        "pending": {
            "offer_acceptance": sum(o.acceptance == "pending" for o in offers),
            "joining": sum(o.acceptance == "accepted" and o.joining_status == "pending" for o in offers),
            "noc_required": sum(o.noc_status == "required" for o in offers),
            "open_policy_flags": PolicyFlag.objects.filter(student_id__in=ids, status="open").count(),
        },
        "eligible_for_further_drives": sum(1 for s in students if status_by_student[s.id] in ("internship_only", "fte_only")
                                           or (status_by_student[s.id] == "unplaced" and s.registration_status == "registered")),
    }


def public_report():
    """Aggregates only. Any figure computed from fewer than PUBLIC_STATS_MIN_CELL students
    is replaced by None ("fewer than K"), so no individual can be singled out."""
    k = settings.PUBLIC_STATS_MIN_CELL
    r = internal_report()

    def suppress(n):
        return n if n >= k else None

    courses = []
    for code, name in COURSES:
        c = r["by_course"].get(code, {"registered": 0, "placed": 0})
        ok = c["registered"] >= k and c["placed"] >= k
        courses.append({"course": name, "registered": suppress(c["registered"]), "placed": c["placed"] if ok else None,
                        "placement_rate": round(100 * c["placed"] / c["registered"]) if ok else None})

    fte = r["fte_ctc_lpa"]
    stip = r["internship_stipend_monthly_inr"]
    return {
        "session": "2026–27",
        "min_cell_size": k,
        "registered_students": suppress(r["totals"]["registered"]),
        "students_placed": suppress(r["totals"]["placed_unique_students"]),
        "offers_made": suppress(r["totals"]["total_offers"]),
        "recruiters": len(r["by_company"]),
        "fte_ctc_lpa": {"highest": fte["highest"], "average": fte["average"], "median": fte["median"]} if fte["count"] >= k else None,
        "internship_stipend_monthly_inr": {"average": stip["average"], "median": stip["median"]} if stip["count"] >= k else None,
        "by_course": courses,
        "past_recruiters": sorted({row["company"] for row in r["by_company"]}),
        "top_packages": _top_packages_with_consent(),
    }


def _top_packages_with_consent(limit=5):
    """Only students who opted in to public listing appear, by first name and course."""
    rows = (Offer.objects.filter(acceptance="accepted", offer_type__in=["F", "IF"], ctc_lpa__isnull=False,
                                 student__consent_public_listing=True)
            .select_related("student", "company").order_by("-ctc_lpa")[:limit])
    return [{"student": o.student.name.split()[0], "course": COURSE_NAMES.get(o.student.course), "company": o.company.name,
             "ctc_lpa": float(o.ctc_lpa)} for o in rows]
