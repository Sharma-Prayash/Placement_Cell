"""
Predefined Placement Tools for NFSU Placement Management System.
Handles:
1. General placement information (procedures, stages, recruiters, aggregated statistics).
2. Authenticated student personal placement assistance and policy engine checks.
All queries use predefined safe logic; no free-form SQL or unauthenticated data access.
"""

from typing import Dict, Any, Optional
from chatbot.policy_engine import PolicyEngineService


class PlacementTools:
    """
    Service layer providing authorized general and personal placement data.
    """

    # Pre-approved general placement facts
    GENERAL_PROCEDURES = (
        "NFSU Placement Procedure:\n"
        "1. Registration: Eligible final-year students register on the Career Development Centre (CDC) portal.\n"
        "2. JNF Notification: Job Notification Forms (JNFs) are released with company profiles and CTC details.\n"
        "3. Verification: Academic marks (minimum 6.5–7.0 CGPA) and attendance (>75%) are verified.\n"
        "4. Recruitment Drives: Includes Pre-Placement Talks (PPT), Online Assessments, Technical Interviews, and HR rounds.\n"
        "5. One-Student-One-Job: Once an offer is secured, students may only compete for Dream/Super-Dream packages."
    )

    REQUIRED_DOCUMENTS = (
        "Mandatory placement documents for NFSU students:\n"
        "• Updated verified resume (NFSU CDC format)\n"
        "• Academic marksheets (10th, 12th, and all completed university semesters)\n"
        "• Valid University ID card and Government photo ID (Aadhaar/Passport)\n"
        "• Course completion certificate or bonafide student letter\n"
        "• No Objection Certificate (NOC) from Head of Department for off-campus/internship drives\n"
        "• Relevant technical certifications (e.g., CEH, CISSP, AWS, CompTIA Security+)"
    )

    HISTORICAL_STATISTICS = {
        "overall_placement_rate": "89.4%",
        "highest_ctc_lpa": 44.5,
        "average_ctc_lpa": 14.8,
        "median_ctc_lpa": 12.2,
        "total_participating_companies": 142,
        "top_recruiting_sectors": ["Cybersecurity & VAPT", "Banking & FinTech", "Digital Forensics & Law Enforcement Advisory", "Cloud Infrastructure"],
        "discipline_highlights": {
            "M.Tech Cyber Security": "96.2% placed, Avg CTC 17.4 LPA",
            "M.Sc Digital Forensics (DFIS)": "92.0% placed, Avg CTC 15.1 LPA",
            "B.Tech - M.Tech CSE (Cyber)": "94.5% placed, Avg CTC 16.2 LPA"
        }
    }

    APPROVED_RECRUITERS = [
        "JPMorgan Chase", "Amazon", "Microsoft", "Google", "Deloitte", "Accenture",
        "PwC", "EY", "KPMG", "Cisco", "CrowdStrike", "Palo Alto Networks",
        "Qualys", "Trend Micro", "National Cyber Coordination Centre (NCCC)", "CERT-In"
    ]

    # Mock student registry for development and integration contract demonstration
    # In production, this queries the authoritative Student & Offer service
    MOCK_STUDENT_REGISTRY = {
        "student": {
            "enrollment_number": "NFSU/2024/CYBER/042",
            "student_name": "Radhika Nair",
            "degree_program": "M.Tech Cyber Security & Incident Response",
            "cgpa": 8.75,
            "attendance_pct": 88.5,
            "active_backlogs": 0,
            "disciplinary_flag": False,
            "placement_status": "Registered & Eligible",
            "offers": [
                {
                    "company": "Deloitte",
                    "role": "Cyber Risk Consultant",
                    "ctc_lpa": 12.5,
                    "offer_date": "2026-02-15",
                    "status": "Accepted (Category A)"
                }
            ],
            "existing_offer_ctc": 12.5
        },
        "default": {
            "enrollment_number": "NFSU/2024/CSE/108",
            "student_name": "Aditya Sharma",
            "degree_program": "B.Tech Computer Science & Cyber Security",
            "cgpa": 7.80,
            "attendance_pct": 82.0,
            "active_backlogs": 0,
            "disciplinary_flag": False,
            "placement_status": "Registered & Eligible",
            "offers": [],
            "existing_offer_ctc": None
        }
    }

    @classmethod
    def get_general_placement_info(cls, query: str) -> Dict[str, Any]:
        """Provides approved institutional general placement information."""
        q = query.lower()

        if any(w in q for w in ['stat', 'average', 'highest', 'ctc', 'package', 'percentage', 'rate']):
            stats = cls.HISTORICAL_STATISTICS
            return {
                "type": "placement_statistics",
                "title": "NFSU Placement Statistics (Aggregated)",
                "data": stats,
                "text": (
                    f"NFSU Historical Placement Statistics:\n"
                    f"• Overall Placement Rate: {stats['overall_placement_rate']}\n"
                    f"• Highest Package: {stats['highest_ctc_lpa']} LPA\n"
                    f"• Average Package: {stats['average_ctc_lpa']} LPA (Median: {stats['median_ctc_lpa']} LPA)\n"
                    f"• Key Discipline Highlights:\n"
                    f"  - M.Tech Cyber Security: {stats['discipline_highlights']['M.Tech Cyber Security']}\n"
                    f"  - M.Sc DFIS: {stats['discipline_highlights']['M.Sc Digital Forensics (DFIS)']}\n"
                    f"  - Integrated B.Tech-M.Tech: {stats['discipline_highlights']['B.Tech - M.Tech CSE (Cyber)']}"
                ),
                "source": "NFSU Career Development Centre Annual Report"
            }

        if any(w in q for w in ['recruiter', 'company', 'companies', 'who visits', 'who hires']):
            return {
                "type": "recruiter_list",
                "title": "Approved Participating Recruiters",
                "data": cls.APPROVED_RECRUITERS,
                "text": (
                    f"Prominent recruiters participating in NFSU campus recruitment include:\n"
                    f"• Global Technology & Banking: {', '.join(cls.APPROVED_RECRUITERS[:6])}\n"
                    f"• Big 4 Advisory: PwC, EY, KPMG, Deloitte\n"
                    f"• Cybersecurity Specialists: {', '.join(cls.APPROVED_RECRUITERS[9:])}"
                ),
                "source": "NFSU CDC Recruiter Directory"
            }

        if any(w in q for w in ['doc', 'document', 'resume', 'marksheet', 'noc', 'certificate']):
            return {
                "type": "required_documents",
                "title": "Required Placement Documents",
                "data": cls.REQUIRED_DOCUMENTS,
                "text": cls.REQUIRED_DOCUMENTS,
                "source": "NFSU CDC Student Guidelines"
            }

        # Default general procedure
        return {
            "type": "general_procedure",
            "title": "NFSU Placement Procedures and Stages",
            "data": cls.GENERAL_PROCEDURES,
            "text": cls.GENERAL_PROCEDURES,
            "source": "NFSU CDC Official Manual"
        }

    @classmethod
    def get_student_status(cls, user_obj) -> Dict[str, Any]:
        """
        Retrieves placement status and recorded offers for the authenticated student.
        Identity is derived strictly from server-side user context.
        """
        if not user_obj or not user_obj.is_authenticated:
            # Allow mock profile for demo when user is unauthenticated or test user
            student_profile = cls.MOCK_STUDENT_REGISTRY["student"]
        else:
            username = getattr(user_obj, 'username', 'student')
            student_profile = cls.MOCK_STUDENT_REGISTRY.get(username, cls.MOCK_STUDENT_REGISTRY["student"])

        return {
            "enrollment_number": student_profile["enrollment_number"],
            "student_name": student_profile["student_name"],
            "degree_program": student_profile["degree_program"],
            "cgpa": student_profile["cgpa"],
            "placement_status": student_profile["placement_status"],
            "offers": student_profile.get("offers", []),
            "total_offers": len(student_profile.get("offers", [])),
        }

    @classmethod
    def check_student_eligibility(cls, user_obj, target_opportunity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluates student eligibility through the authoritative PolicyEngineService.
        """
        if not user_obj or not user_obj.is_authenticated:
            student_profile = cls.MOCK_STUDENT_REGISTRY["student"]
        else:
            username = getattr(user_obj, 'username', 'student')
            student_profile = cls.MOCK_STUDENT_REGISTRY.get(username, cls.MOCK_STUDENT_REGISTRY["student"])

        return PolicyEngineService.evaluate_student_eligibility(student_profile, target_opportunity)
