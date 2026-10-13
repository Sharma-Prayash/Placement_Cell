"""Policy rule engine as a case table. Each row: existing accepted offers, new drive, expected decision.
Run: python manage.py test tests"""
from decimal import Decimal as D

from django.test import SimpleTestCase

from apps.policy.engine import ALLOW, BLOCK, FLAG, Config, DriveFacts, FlagFacts, OfferFacts, StudentFacts, category_for, evaluate

OK_STUDENT = StudentFacts("registered", "eligible", "MSC_CS", D("8.0"), 0)
ADVISORY = Config()
ENFORCED = Config(enforce_switching=True)


def drive(t, ctc=None, company=99, courses=("MSC_CS",), min_cgpa="0", max_backlogs=0):
    return DriveFacts(company, t, D(ctc) if ctc else None, courses, D(min_cgpa), max_backlogs)


def held(t, ctc=None, company=1, acceptance="accepted"):
    return OfferFacts(company, t, D(ctc) if ctc else None, acceptance)


class CategoryBoundaries(SimpleTestCase):
    def test_half_open_bands(self):
        cases = [("16", "A+"), ("15.99", "A"), ("10", "A"), ("9.99", "B"), ("6", "B"), ("5.99", "C"), ("0", "C")]
        for ctc, cat in cases:
            with self.subTest(ctc=ctc):
                self.assertEqual(category_for(D(ctc), ADVISORY), cat)

    def test_internship_has_no_category(self):
        self.assertIsNone(category_for(None, ADVISORY))


class OfferTypeRules(SimpleTestCase):
    """Hard rules agreed by the team; always BLOCK regardless of advisory mode."""

    CASES = [
        # (existing offers, new drive, expected, rule code expected in reasons or None)
        ([held("I")], drive("I"), BLOCK, "OFFER_TYPE_I_REPEAT"),
        ([held("I")], drive("F", "8"), ALLOW, None),
        ([held("I")], drive("IF", "12"), ALLOW, None),
        ([held("F", "8")], drive("F", "20"), BLOCK, "OFFER_TYPE_F_REPEAT"),
        ([held("F", "8")], drive("I"), ALLOW, None),
        ([held("F", "8")], drive("IF", "20"), FLAG, "OFFER_TYPE_F_TO_IF"),
        ([held("IF", "12")], drive("I"), BLOCK, "OFFER_TYPE_IF_LOCK"),
        ([held("IF", "12")], drive("F", "30"), BLOCK, "OFFER_TYPE_IF_LOCK"),
        ([held("IF", "12")], drive("IF", "30"), BLOCK, "OFFER_TYPE_IF_LOCK"),
        ([held("I", acceptance="declined")], drive("I"), ALLOW, None),  # declined offers do not count
        ([held("I", acceptance="pending")], drive("I"), ALLOW, None),   # pending is info only
        ([], drive("I"), ALLOW, None),
    ]

    def test_case_table(self):
        for offers, d, expected, code in self.CASES:
            with self.subTest(offers=offers, drive=d):
                v = evaluate(OK_STUDENT, d, offers, [], ADVISORY)
                self.assertEqual(v.decision, expected, v.reasons)
                if code:
                    self.assertIn(code, [r.code for r in v.reasons])

    def test_if_lock_does_not_block_same_company(self):
        v = evaluate(OK_STUDENT, drive("F", "20", company=1), [held("IF", "12", company=1)], [], ADVISORY)
        self.assertNotIn("OFFER_TYPE_IF_LOCK", [r.code for r in v.reasons])


class SwitchingRules(SimpleTestCase):
    CASES = [
        # (existing FTE ctc, new drive ctc, advisory result, enforced result)
        ("18", "25", FLAG, BLOCK),   # A+ exits the process
        ("12", "14", FLAG, BLOCK),   # A -> A not allowed
        ("12", "16", ALLOW, ALLOW),  # A -> A+ allowed
        ("8", "11.99", FLAG, BLOCK), # B needs >= 12.00
        ("8", "12", ALLOW, ALLOW),   # exactly 1.5x passes
        ("4", "5", FLAG, BLOCK),     # C -> C not a higher category
        ("4", "7", ALLOW, ALLOW),    # C -> B allowed
    ]

    def test_case_table(self):
        # Existing and new offers share company 1 so the I+F lock does not fire; this isolates the switching rule.
        for old, new, advisory, enforced in self.CASES:
            for cfg, expected in ((ADVISORY, advisory), (ENFORCED, enforced)):
                with self.subTest(old=old, new=new, enforce=cfg.enforce_switching):
                    v = evaluate(OK_STUDENT, drive("IF", new, company=1), [held("IF", old, company=1)], [], cfg)
                    self.assertEqual(v.decision, expected, [r.message for r in v.reasons])

    def test_internship_drives_skip_switching(self):
        v = evaluate(OK_STUDENT, drive("I"), [held("F", "18")], [], ENFORCED)
        self.assertEqual(v.decision, ALLOW)

    def test_reports_categories_for_recruiters(self):
        v = evaluate(OK_STUDENT, drive("I"), [held("F", "8")], [], ADVISORY)
        self.assertEqual(v.current_category, "B")
        self.assertEqual(v.held_types, ["F"])


class EligibilityRules(SimpleTestCase):
    def test_registration_and_cutoffs(self):
        cases = [
            (StudentFacts("not_registered", "eligible", "MSC_CS", D("8"), 0), drive("F", "8"), "NOT_REGISTERED"),
            (StudentFacts("registered", "ineligible", "MSC_CS", D("8"), 0), drive("F", "8"), "INELIGIBLE"),
            (OK_STUDENT, drive("F", "8", courses=("MSC_DFIS",)), "COURSE_NOT_ELIGIBLE"),
            (OK_STUDENT, drive("F", "8", min_cgpa="8.5"), "CGPA_BELOW_CUTOFF"),
            (StudentFacts("registered", "eligible", "MSC_CS", D("8"), 2), drive("F", "8"), "BACKLOGS_ABOVE_LIMIT"),
        ]
        for st, d, code in cases:
            with self.subTest(code=code):
                v = evaluate(st, d, [], [], ADVISORY)
                self.assertEqual(v.decision, BLOCK)
                self.assertIn(code, [r.code for r in v.reasons])

    def test_pending_eligibility_and_absence_are_flags(self):
        st = StudentFacts("registered", "pending", "MSC_CS", D("8"), 0)
        v = evaluate(st, drive("F", "8"), [], [FlagFacts("ABSENTEEISM", "Missed a talk")], ADVISORY)
        self.assertEqual(v.decision, FLAG)
        self.assertEqual({r.code for r in v.reasons}, {"ELIGIBILITY_PENDING", "ABSENTEEISM"})
