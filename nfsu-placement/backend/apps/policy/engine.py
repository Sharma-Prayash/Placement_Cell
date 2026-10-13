"""Policy rule engine: a pure function with no database access.

    evaluate(student, drive, offers, flags, cfg) -> Verdict

HARD rules (always BLOCK):
  * registration and company-specific eligibility (course, CGPA, backlogs)
  * offer-type rules agreed by the team:
      - holds Internship-only (I)  -> cannot take another I; may take F or I+F
      - holds FTE-only (F)         -> cannot take another F; may take I
                                      (F student -> I+F drive is ambiguous: FLAG for review)
      - holds Internship+FTE (I+F) -> cannot take I, F or I+F at another organisation

ADVISORY rules (FLAG, shown to recruiters and staff; recruiters decide):
  * category switching (A+, A, B 1.5x, C) and absenteeism exclusions
  * set cfg.enforce_switching = True to make switching rules BLOCK instead

Only accepted offers count as "held". Pending offers are reported as info.
"""
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Optional

ALLOW, FLAG, BLOCK = "ALLOW", "FLAG", "BLOCK"
I, F, IF = "I", "F", "IF"
CATEGORY_RANK = {"C": 0, "B": 1, "A": 2, "A+": 3}


@dataclass(frozen=True)
class Config:
    a_plus_min: Decimal = Decimal("16")
    a_min: Decimal = Decimal("10")
    b_min: Decimal = Decimal("6")
    b_multiplier: Decimal = Decimal("1.5")
    enforce_switching: bool = False


@dataclass(frozen=True)
class StudentFacts:
    registration_status: str
    eligibility_status: str
    course: str
    cgpa: Decimal
    backlogs: int


@dataclass(frozen=True)
class DriveFacts:
    company_id: int
    offer_type: str
    ctc_lpa: Optional[Decimal]
    eligible_courses: tuple
    min_cgpa: Decimal = Decimal("0")
    max_backlogs: int = 0


@dataclass(frozen=True)
class OfferFacts:
    company_id: int
    offer_type: str
    ctc_lpa: Optional[Decimal]
    acceptance: str  # pending / accepted / declined / expired


@dataclass(frozen=True)
class FlagFacts:
    rule_code: str
    explanation: str


@dataclass
class Reason:
    code: str
    severity: str  # block / flag / info
    message: str


@dataclass
class Verdict:
    decision: str
    reasons: list = field(default_factory=list)
    current_category: Optional[str] = None
    drive_category: Optional[str] = None
    held_types: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def category_for(ctc_lpa, cfg: Config) -> Optional[str]:
    """Half-open bands: A+ >= 16, A in [10, 16), B in [6, 10), C < 6. No CTC -> no category."""
    if ctc_lpa is None:
        return None
    ctc = Decimal(str(ctc_lpa))
    if ctc >= cfg.a_plus_min:
        return "A+"
    if ctc >= cfg.a_min:
        return "A"
    if ctc >= cfg.b_min:
        return "B"
    return "C"


def _offer_type_rules(drive: DriveFacts, held: list) -> list:
    reasons = []
    held_types = {o.offer_type for o in held}
    for o in held:
        if o.offer_type == IF and o.company_id != drive.company_id:
            reasons.append(Reason("OFFER_TYPE_IF_LOCK", "block",
                                  "Holds an accepted Internship + FTE offer; cannot take part in I, F or I+F drives at another organisation."))
            return reasons
    if I in held_types and drive.offer_type == I:
        reasons.append(Reason("OFFER_TYPE_I_REPEAT", "block",
                              "Holds an accepted internship-only offer; cannot apply for another internship-only role. FTE and I+F roles are open."))
    if F in held_types and drive.offer_type == F:
        reasons.append(Reason("OFFER_TYPE_F_REPEAT", "block",
                              "Holds an accepted FTE-only offer; cannot apply for another FTE-only role. Internship roles are open."))
    if F in held_types and drive.offer_type == IF:
        reasons.append(Reason("OFFER_TYPE_F_TO_IF", "flag",
                              "Holds an FTE-only offer and this drive is Internship + FTE; the agreed rules do not cover this case, so the Placement Cell should review it."))
    return reasons


def _switching_rules(drive: DriveFacts, held: list, cfg: Config):
    """Return (reasons, current_category, drive_category)."""
    severity = "block" if cfg.enforce_switching else "flag"
    drive_cat = category_for(drive.ctc_lpa, cfg)
    fte_held = [o for o in held if o.offer_type in (F, IF) and o.ctc_lpa is not None]
    if not fte_held:
        return [], None, drive_cat
    best = max(fte_held, key=lambda o: Decimal(str(o.ctc_lpa)))
    best_ctc = Decimal(str(best.ctc_lpa))
    current = category_for(best_ctc, cfg)
    if drive.offer_type == I or drive_cat is None:
        return [], current, drive_cat  # switching rules compare FTE packages only

    new_ctc = Decimal(str(drive.ctc_lpa))
    reasons = []
    if current == "A+":
        reasons.append(Reason("SWITCH_A_PLUS_EXIT", severity,
                              f"Holds an A+ offer ({best_ctc} LPA); under the guideline, A+ students leave the placement process."))
    elif current == "A" and drive_cat != "A+":
        reasons.append(Reason("SWITCH_A_ONLY_TO_A_PLUS", severity,
                              f"Holds an A-category offer ({best_ctc} LPA); switching is allowed only to A+ drives. This drive is {drive_cat}."))
    elif current == "B" and new_ctc < best_ctc * cfg.b_multiplier:
        need = (best_ctc * cfg.b_multiplier).quantize(Decimal("0.01"))
        reasons.append(Reason("SWITCH_B_MULTIPLIER", severity,
                              f"Holds a B-category offer ({best_ctc} LPA); a new package must be at least {need} LPA ({cfg.b_multiplier}×). This drive offers {new_ctc} LPA."))
    elif current == "C" and CATEGORY_RANK[drive_cat] <= CATEGORY_RANK["C"]:
        reasons.append(Reason("SWITCH_C_SAME_CATEGORY", severity,
                              "Holds a C-category offer; only higher-category drives qualify as a switch. This drive is also C."))
    else:
        reasons.append(Reason("SWITCH_OK", "info", f"Switch from {current} ({best_ctc} LPA) to {drive_cat} ({new_ctc} LPA) meets the switching rule."))
    return reasons, current, drive_cat


def evaluate(student: StudentFacts, drive: DriveFacts, offers: list, flags: list, cfg: Config = Config()) -> Verdict:
    reasons = []

    if student.registration_status != "registered":
        reasons.append(Reason("NOT_REGISTERED", "block", "Not registered for the placement session."))
    if student.eligibility_status == "ineligible":
        reasons.append(Reason("INELIGIBLE", "block", "Marked ineligible by the Placement Cell."))
    elif student.eligibility_status == "pending":
        reasons.append(Reason("ELIGIBILITY_PENDING", "flag", "Eligibility verification is still pending."))
    if student.course not in drive.eligible_courses:
        reasons.append(Reason("COURSE_NOT_ELIGIBLE", "block", "This drive is not open to the student's programme."))
    if Decimal(str(student.cgpa)) < Decimal(str(drive.min_cgpa)):
        reasons.append(Reason("CGPA_BELOW_CUTOFF", "block", f"CGPA {student.cgpa} is below the company cut-off of {drive.min_cgpa}."))
    if student.backlogs > drive.max_backlogs:
        reasons.append(Reason("BACKLOGS_ABOVE_LIMIT", "block", f"{student.backlogs} active backlogs; the company allows at most {drive.max_backlogs}."))

    held = [o for o in offers if o.acceptance == "accepted"]
    pending = [o for o in offers if o.acceptance == "pending"]
    reasons += _offer_type_rules(drive, held)
    switch_reasons, current_cat, drive_cat = _switching_rules(drive, held, cfg)
    reasons += switch_reasons

    for fl in flags:
        reasons.append(Reason(fl.rule_code, "flag", fl.explanation))
    if pending:
        reasons.append(Reason("PENDING_OFFER", "info", f"Has {len(pending)} offer(s) awaiting the student's response."))

    severities = {r.severity for r in reasons}
    decision = BLOCK if "block" in severities else FLAG if "flag" in severities else ALLOW
    return Verdict(decision=decision, reasons=reasons, current_category=current_cat,
                   drive_category=drive_cat, held_types=sorted({o.offer_type for o in held}))
