"""
Chatbot Orchestrator for NFSU Placement Management System.
Routes user requests, validates input, manages intent classification,
coordinates retrieval, delegates to LLM when available, and enforces deterministic fallback.
"""

import time
import re
from typing import Dict, Any, Optional, List
from django.conf import settings

from chatbot.retrieval import KnowledgeRetrievalService
from chatbot.placement_tools import PlacementTools
from chatbot.policy_engine import PolicyEngineService
from chatbot.gemini_provider import GeminiProvider
from chatbot.models import ConversationSession, ChatLog


class ChatbotOrchestrator:
    """
    Central orchestration engine for the NFSU placement chatbot.
    """

    MAX_MESSAGE_LENGTH = 1000

    INTENT_INTERVIEW_PREP = "interview_preparation"
    INTENT_GENERAL_PLACEMENT = "general_placement_info"
    INTENT_PERSONAL_PLACEMENT = "personal_placement_assistance"

    def __init__(self, retrieval_service=None, llm_provider=None):
        self.retrieval_service = retrieval_service or KnowledgeRetrievalService()
        self.llm_provider = llm_provider or GeminiProvider()

    def classify_intent(self, query: str) -> str:
        """Classifies student message into one of three primary intents."""
        q = query.lower()

        # Personal Placement Assistance intent indicators
        personal_patterns = [
            r'\bmy\b.*(status|eligibility|offer|package|cgpa|application|record)',
            r'\bam i eligible\b',
            r'\bcan i apply\b',
            r'\bmy placement\b',
            r'\bcheck my\b',
            r'\bview my\b',
            r'\bmy recorded offers\b',
            r'\bwhy (was i|am i) (blocked|not eligible)\b'
        ]
        if any(re.search(pat, q) for pat in personal_patterns):
            return self.INTENT_PERSONAL_PLACEMENT

        # General Placement Information indicators
        general_patterns = [
            r'\bplacement (process|procedure|stages|rules|policy|schedule)\b',
            r'\b(highest|average|median) (package|ctc|salary)\b',
            r'\bplacement (stats|statistics|percentage|rate)\b',
            r'\b(who|which recruiters|what companies) (visit|hire|participate)\b',
            r'\brequired documents\b',
            r'\bcdc registration\b',
            r'\bone student one job\b'
        ]
        if any(re.search(pat, q) for pat in general_patterns):
            return self.INTENT_GENERAL_PLACEMENT

        # Default to interview preparation
        return self.INTENT_INTERVIEW_PREP

    def process_message(
        self,
        user_message: str,
        user_obj=None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a user message end-to-end.
        """
        start_time = time.time()

        # 1. Validation
        cleaned_msg = user_message.strip() if user_message else ""
        if not cleaned_msg:
            return {
                "answer": "Please enter a question regarding NFSU placements or interview preparation.",
                "intent": "unknown",
                "sources": [],
                "status": "unavailable",
                "generation_mode": "validation_error"
            }

        if len(cleaned_msg) > self.MAX_MESSAGE_LENGTH:
            return {
                "answer": f"Message exceeds maximum allowed length of {self.MAX_MESSAGE_LENGTH} characters.",
                "intent": "unknown",
                "sources": [],
                "status": "unavailable",
                "generation_mode": "validation_error"
            }

        intent = self.classify_intent(cleaned_msg)

        # 2. Dispatch based on intent
        if intent == self.INTENT_PERSONAL_PLACEMENT:
            result = self._handle_personal_placement(cleaned_msg, user_obj)
        elif intent == self.INTENT_GENERAL_PLACEMENT:
            result = self._handle_general_placement(cleaned_msg)
        else:
            result = self._handle_interview_preparation(cleaned_msg)

        # 3. Privacy-conscious audit log
        latency_ms = int((time.time() - start_time) * 1000)
        self._record_log(cleaned_msg, result, latency_ms, session_id)

        return result

    def _handle_personal_placement(self, query: str, user_obj) -> Dict[str, Any]:
        """Handles student placement status & policy engine eligibility verification."""
        q = query.lower()

        # If asking about eligibility specifically
        if any(w in q for w in ['eligible', 'eligibility', 'apply', 'blocked', 'why']):
            decision_data = PlacementTools.check_student_eligibility(user_obj)
            outcome = decision_data['decision']
            student = decision_data['student_summary']
            reasons_formatted = "\n• " + "\n• ".join(decision_data['reasons'])

            if outcome == PolicyEngineService.OUTCOME_ALLOW:
                answer = (
                    f"✅ **Placement Eligibility: APPROVED (ALLOW)**\n\n"
                    f"Student: **{student['student_name']}** ({student['enrollment_number']})\n"
                    f"Program: {student['degree_program']} | CGPA: {student['cgpa']:.2f}\n"
                    f"Attendance: {student['attendance_pct']:.1f}% | Active Backlogs: {student['active_backlogs']}\n\n"
                    f"**Policy Verification:**{reasons_formatted}\n\n"
                    f"You are cleared to apply for upcoming placement drives via the CDC portal."
                )
            elif outcome == PolicyEngineService.OUTCOME_BLOCK:
                answer = (
                    f"⛔ **Placement Eligibility: BLOCKED (BLOCK)**\n\n"
                    f"Student: **{student['student_name']}** ({student['enrollment_number']})\n"
                    f"**Reasons for ineligibility:**{reasons_formatted}\n\n"
                    f"Please contact the Career Development Centre (CDC) if you believe this is an error."
                )
            else:
                answer = (
                    f"⚠️ **Placement Eligibility: MANUAL REVIEW REQUIRED**\n\n"
                    f"Student: **{student['student_name']}** ({student['enrollment_number']})\n"
                    f"**Review Notes:**{reasons_formatted}\n\n"
                    f"Your application requires approval from the CDC Placement Committee under institutional policy."
                )

            return {
                "answer": answer,
                "intent": self.INTENT_PERSONAL_PLACEMENT,
                "sources": [
                    {
                        "id": "policy-engine-v1",
                        "title": "NFSU Authoritative Policy Engine",
                        "provenance": "official",
                        "status": outcome,
                        "source_url": "https://www.nfsu.ac.in/placements"
                    }
                ],
                "status": "answered",
                "generation_mode": "policy_engine"
            }

        # Otherwise, return student placement status and recorded offers
        status_data = PlacementTools.get_student_status(user_obj)
        offers_text = ""
        if status_data['offers']:
            offers_text = "\n**Recorded Offers:**\n"
            for off in status_data['offers']:
                offers_text += f"• **{off['company']}** — {off['role']} ({off['ctc_lpa']} LPA) [{off['status']}]\n"
        else:
            offers_text = "\n**Recorded Offers:** No offers recorded yet."

        answer = (
            f"📋 **Personal Placement Record**\n\n"
            f"• Student: **{status_data['student_name']}** ({status_data['enrollment_number']})\n"
            f"• Program: {status_data['degree_program']}\n"
            f"• Current CGPA: {status_data['cgpa']:.2f}\n"
            f"• Placement Status: **{status_data['placement_status']}**\n"
            f"{offers_text}"
        )

        return {
            "answer": answer,
            "intent": self.INTENT_PERSONAL_PLACEMENT,
            "sources": [
                {
                    "id": "student-registry-v1",
                    "title": "NFSU Student Career Development Record",
                    "provenance": "official",
                    "source_url": "https://www.nfsu.ac.in/placements"
                }
            ],
            "status": "answered",
            "generation_mode": "student_records"
        }

    def _handle_general_placement(self, query: str) -> Dict[str, Any]:
        """Handles general procedures, recruiter lists, and aggregated statistics."""
        data = PlacementTools.get_general_placement_info(query)
        return {
            "answer": data["text"],
            "intent": self.INTENT_GENERAL_PLACEMENT,
            "sources": [
                {
                    "id": "cdc-general-info",
                    "title": data["title"],
                    "provenance": "official",
                    "source_url": "https://www.nfsu.ac.in/placements"
                }
            ],
            "status": "answered",
            "generation_mode": "placement_tools"
        }

    def _handle_interview_preparation(self, query: str) -> Dict[str, Any]:
        """Searches question bank and grounds with Gemini or deterministic fallback."""
        retrieved = self.retrieval_service.search(query, top_k=3)

        if not retrieved:
            return {
                "answer": (
                    "I do not have sufficient verified information in the NFSU knowledge base for this specific query.\n\n"
                    "💡 **Try asking about:**\n"
                    "• Company interviews: JPMorgan Chase, Amazon, Microsoft, Google, Deloitte, Accenture\n"
                    "• Technical topics: Cybersecurity, OWASP Top 10, SOC/SIEM, Cryptography, DSA, DBMS, Linux, AI/ML\n"
                    "• Placement procedures: 'How does the placement process work?' or 'What is my eligibility?'"
                ),
                "intent": self.INTENT_INTERVIEW_PREP,
                "sources": [],
                "status": "insufficient_evidence",
                "generation_mode": "deterministic_fallback"
            }

        # Build source citation references
        sources = []
        for r in retrieved:
            sources.append({
                "id": r["entry_id"],
                "title": f"{r['company'] or r['domain']} - {r['topic']}",
                "company": r["company"],
                "domain": r["domain"],
                "topic": r["topic"],
                "subtopic": r["subtopic"],
                "difficulty": r["difficulty"],
                "provenance": r["provenance"],
                "source_title": r["source_title"],
                "source_url": r["source_url"],
                "pdf_document": r["pdf_document"]
            })

        # Attempt grounded Gemini generation if available
        llm_response = None
        if self.llm_provider and self.llm_provider.is_available():
            llm_response = self.llm_provider.generate_response(query, retrieved, None)

        if llm_response:
            return {
                "answer": llm_response,
                "intent": self.INTENT_INTERVIEW_PREP,
                "sources": sources,
                "status": "answered",
                "generation_mode": "grounded_llm"
            }

        # Deterministic Grounded Fallback: Format top retrieved model answers cleanly
        formatted_answers = []
        for idx, item in enumerate(retrieved, 1):
            target = item["company"] or item["domain"]
            prov_label = item["provenance"].upper()
            formatted_answers.append(
                f"### {idx}. [{prov_label}] {target} — {item['topic']}\n"
                f"**Question:** {item['question']}\n\n"
                f"**Model Answer:**\n{item['answer']}\n\n"
                f"*Difficulty:* `{item['difficulty'].capitalize()}` | *Verified Source:* [{item['source_title']}]({item['source_url']})"
            )

        answer_text = "\n\n---\n\n".join(formatted_answers)
        return {
            "answer": answer_text,
            "intent": self.INTENT_INTERVIEW_PREP,
            "sources": sources,
            "status": "answered",
            "generation_mode": "deterministic_fallback"
        }

    def _record_log(self, user_msg: str, result: Dict[str, Any], latency_ms: int, session_id: Optional[str]):
        """Saves privacy-conscious log without blocking."""
        try:
            # Simple sanitization
            sanitized_msg = user_msg[:500]
            ChatLog.objects.create(
                user_message=sanitized_msg,
                bot_response=result.get("answer", "")[:1000],
                intent=result.get("intent", "unknown"),
                status=result.get("status", "unknown"),
                generation_mode=result.get("generation_mode", "unknown"),
                sources_cited=result.get("sources", []),
                latency_ms=latency_ms
            )
        except Exception:
            pass
