"""Adapters between Django models and the pure engine."""
from apps.placements.models import Offer

from .engine import Config, DriveFacts, FlagFacts, OfferFacts, StudentFacts, category_for, evaluate
from .models import PolicyConfig, PolicyFlag


def load_config() -> Config:
    c = PolicyConfig.current()
    return Config(a_plus_min=c.a_plus_min_lpa, a_min=c.a_min_lpa, b_min=c.b_min_lpa,
                  b_multiplier=c.b_switch_multiplier, enforce_switching=c.enforce_switching)


def student_facts(s):
    return StudentFacts(s.registration_status, s.eligibility_status, s.course, s.cgpa, s.backlogs)


def drive_facts(d):
    return DriveFacts(d.company_id, d.offer_type, d.ctc_lpa, tuple(d.eligible_courses), d.min_cgpa, d.max_backlogs)


def offer_facts(student, exclude_offer_id=None, exclude_drive_id=None):
    qs = Offer.objects.filter(student=student)
    if exclude_offer_id:
        qs = qs.exclude(pk=exclude_offer_id)
    if exclude_drive_id:
        qs = qs.exclude(drive_id=exclude_drive_id)
    return [OfferFacts(o.company_id, o.offer_type, o.ctc_lpa, o.acceptance) for o in qs]


def flag_facts(student):
    return [FlagFacts(f.rule_code, f.explanation)
            for f in PolicyFlag.objects.filter(student=student, status=PolicyFlag.Status.OPEN, drives_remaining__gt=0)]


def evaluate_for(student, drive, exclude_offer_id=None):
    """An offer that came from this same drive is the outcome of it, not a reason to block it."""
    return evaluate(student_facts(student), drive_facts(drive), offer_facts(student, exclude_offer_id, drive.pk),
                    flag_facts(student), load_config())


def current_category(student):
    cfg = load_config()
    ctcs = [o.ctc_lpa for o in Offer.objects.filter(student=student, acceptance="accepted", offer_type__in=["F", "IF"])
            if o.ctc_lpa is not None]
    return category_for(max(ctcs), cfg) if ctcs else None


def placement_status(student) -> str:
    """Derived from accepted offers, never typed by hand."""
    types = set(Offer.objects.filter(student=student, acceptance="accepted").values_list("offer_type", flat=True))
    if not types:
        return "unplaced"
    if "IF" in types or {"I", "F"} <= types:
        return "internship_plus_fte"
    return "internship_only" if "I" in types else "fte_only"
