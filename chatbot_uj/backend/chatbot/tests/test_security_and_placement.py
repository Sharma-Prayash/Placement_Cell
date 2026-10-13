from django.test import TestCase
from django.core.management import call_command
from rest_framework.test import APIClient
from rest_framework import status
from chatbot.policy_engine import PolicyEngineService
from chatbot.orchestrator import ChatbotOrchestrator


class SecurityAndPlacementTestCase(TestCase):
    """Verifies security controls, policy engine, and API integration."""

    def setUp(self):
        call_command('ingest_knowledge')
        self.client = APIClient()
        self.orchestrator = ChatbotOrchestrator()

    def test_policy_engine_allow(self):
        profile = {
            "student_name": "Test Student",
            "enrollment_number": "NFSU/TEST/001",
            "cgpa": 8.5,
            "attendance_pct": 90.0,
            "active_backlogs": 0,
            "disciplinary_flag": False,
            "existing_offer_ctc": None
        }
        res = PolicyEngineService.evaluate_student_eligibility(profile)
        self.assertEqual(res['decision'], PolicyEngineService.OUTCOME_ALLOW)

    def test_policy_engine_block_on_backlog(self):
        profile = {
            "student_name": "Backlog Student",
            "enrollment_number": "NFSU/TEST/002",
            "cgpa": 8.0,
            "attendance_pct": 85.0,
            "active_backlogs": 2,
            "disciplinary_flag": False
        }
        res = PolicyEngineService.evaluate_student_eligibility(profile)
        self.assertEqual(res['decision'], PolicyEngineService.OUTCOME_BLOCK)
        self.assertTrue(any("backlog" in r.lower() for r in res['reasons']))

    def test_policy_engine_block_on_attendance(self):
        profile = {
            "student_name": "Low Attendance",
            "enrollment_number": "NFSU/TEST/003",
            "cgpa": 8.5,
            "attendance_pct": 68.0,
            "active_backlogs": 0,
            "disciplinary_flag": False
        }
        res = PolicyEngineService.evaluate_student_eligibility(profile)
        self.assertEqual(res['decision'], PolicyEngineService.OUTCOME_BLOCK)

    def test_policy_engine_manual_review_for_upgrade(self):
        profile = {
            "student_name": "Existing Offer Student",
            "enrollment_number": "NFSU/TEST/004",
            "cgpa": 8.9,
            "attendance_pct": 92.0,
            "active_backlogs": 0,
            "disciplinary_flag": False,
            "existing_offer_ctc": 10.0
        }
        # Applying for a 16 LPA dream company (> 1.5x)
        opp = {"min_cgpa": 7.0, "ctc_lpa": 16.0, "company_name": "SuperDream Corp"}
        res = PolicyEngineService.evaluate_student_eligibility(profile, opp)
        self.assertEqual(res['decision'], PolicyEngineService.OUTCOME_MANUAL_REVIEW)

    def test_api_message_endpoint_success(self):
        response = self.client.post('/api/chatbot/message/', {
            "message": "What is the placement process at NFSU?"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], 'answered')
        self.assertEqual(data['intent'], 'general_placement_info')
        self.assertTrue(len(data['answer']) > 0)

    def test_api_message_endpoint_interview_prep(self):
        response = self.client.post('/api/chatbot/message/', {
            "message": "Give me Amazon graph topological sort questions"
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], 'answered')
        self.assertEqual(data['intent'], 'interview_preparation')
        self.assertTrue(len(data['sources']) > 0)

    def test_api_oversized_message_rejection(self):
        long_message = "A" * 1005
        response = self.client.post('/api/chatbot/message/', {
            "message": long_message
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_info_endpoint(self):
        response = self.client.get('/api/chatbot/info/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['status'], 'operational')
        self.assertGreaterEqual(data['total_knowledge_entries'], 40)
