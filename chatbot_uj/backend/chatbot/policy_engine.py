"""
Authoritative Policy Engine Service for NFSU Placement Management System.
Evaluates student eligibility deterministically without LLM hallucination.
Returns authoritative outcomes: ALLOW, BLOCK, MANUAL_REVIEW.
"""

from typing import Dict, Any, Optional


class PolicyEngineService:
    """
    Authoritative policy evaluation engine.
    Rules are strictly enforced server-side; the LLM only translates the returned
    decision into accessible prose and cannot override these rules.
    """

    OUTCOME_ALLOW = "ALLOW"
    OUTCOME_BLOCK = "BLOCK"
    OUTCOME_MANUAL_REVIEW = "MANUAL_REVIEW"

    # Default institutional threshold rules
    MIN_ATTENDANCE_PCT = 75.0
    MAX_ACTIVE_BACKLOGS = 0

    @classmethod
    def evaluate_student_eligibility(
        cls,
        student_profile: Dict[str, Any],
        opportunity: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates student placement eligibility.
        Decision outcomes:
        - ALLOW: Student meets all verified criteria.
        - BLOCK: Student violates hard institutional rules (e.g., active backlogs, low CGPA, attendance).
        - MANUAL_REVIEW: Student has existing offer needing CTC multiplier waiver or disciplinary clearance.
        """
        reasons = []
        is_blocked = False
        needs_review = False

        cgpa = float(student_profile.get('cgpa', 0.0))
        active_backlogs = int(student_profile.get('active_backlogs', 0))
        attendance_pct = float(student_profile.get('attendance_pct', 100.0))
        disciplinary_flag = bool(student_profile.get('disciplinary_flag', False))
        existing_offer_ctc = student_profile.get('existing_offer_ctc')  # in LPA, or None

        # 1. Hard Disciplinary Check
        if disciplinary_flag:
            is_blocked = True
            reasons.append("Active disciplinary proceeding on institutional record. Placement clearance blocked.")

        # 2. Active Backlog Check
        if active_backlogs > cls.MAX_ACTIVE_BACKLOGS:
            is_blocked = True
            reasons.append(f"Student has {active_backlogs} active backlog(s). Zero backlogs required for drive participation.")

        # 3. Attendance Check
        if attendance_pct < cls.MIN_ATTENDANCE_PCT:
            is_blocked = True
            reasons.append(f"Academic attendance is {attendance_pct:.1f}%, which is below the mandatory {cls.MIN_ATTENDANCE_PCT}% threshold.")

        # 4. Opportunity-Specific CGPA Cutoff
        target_cutoff = 6.5  # default baseline
        target_ctc = 0.0
        company_name = "General Placement Drive"
        if opportunity:
            target_cutoff = float(opportunity.get('min_cgpa', 6.5))
            target_ctc = float(opportunity.get('ctc_lpa', 0.0))
            company_name = opportunity.get('company_name', 'Recruiter')

        if cgpa < target_cutoff:
            is_blocked = True
            reasons.append(f"Current CGPA ({cgpa:.2f}) does not meet {company_name}'s minimum cutoff of {target_cutoff:.2f}.")

        # 5. One-Student-One-Job Policy Check
        if existing_offer_ctc:
            existing_val = float(existing_offer_ctc)
            # If target opportunity CTC is less than 1.5x existing offer CTC:
            if target_ctc and target_ctc < (existing_val * 1.5):
                is_blocked = True
                reasons.append(
                    f"Student already holds an offer of {existing_val:.1f} LPA. Under NFSU's One-Student-One-Job policy, "
                    f"you may only apply for Dream/Super-Dream offers >= {existing_val * 1.5:.1f} LPA (target is {target_ctc:.1f} LPA)."
                )
            else:
                needs_review = True
                reasons.append(
                    f"Student already holds an offer of {existing_val:.1f} LPA. Application for upgrade requires "
                    f"CDC committee approval (Manual Review)."
                )

        # Final outcome determination
        if is_blocked:
            decision = cls.OUTCOME_BLOCK
        elif needs_review:
            decision = cls.OUTCOME_MANUAL_REVIEW
        else:
            decision = cls.OUTCOME_ALLOW
            reasons.append(f"Student satisfies all academic ({cgpa:.2f} CGPA), attendance ({attendance_pct:.1f}%), and disciplinary criteria.")

        return {
            "decision": decision,
            "reasons": reasons,
            "student_summary": {
                "enrollment_number": student_profile.get("enrollment_number", "N/A"),
                "student_name": student_profile.get("student_name", "Student"),
                "degree_program": student_profile.get("degree_program", "Cybersecurity / Computer Science"),
                "cgpa": cgpa,
                "attendance_pct": attendance_pct,
                "active_backlogs": active_backlogs,
                "has_existing_offer": bool(existing_offer_ctc),
                "existing_offer_ctc": existing_offer_ctc,
            },
            "evaluated_opportunity": company_name
        }
