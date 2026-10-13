from django.test import TestCase
from django.core.management import call_command
from chatbot.retrieval import KnowledgeRetrievalService
from chatbot.models import QABankEntry


class KnowledgeRetrievalTestCase(TestCase):
    """Verifies search, ranking, filtering, and insufficient evidence handling."""

    def setUp(self):
        call_command('ingest_knowledge')
        self.retrieval = KnowledgeRetrievalService()

    def test_company_search_jpmorgan(self):
        results = self.retrieval.search("JPMorgan cybersecurity interview questions", top_k=3)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertEqual(top['company'], "JPMorgan Chase")
        self.assertIn("entry_id", top)
        self.assertIn("provenance", top)

    def test_domain_search_dsa(self):
        results = self.retrieval.search("dynamic programming knapsack", top_k=3)
        self.assertTrue(len(results) > 0)
        self.assertTrue(any("knapsack" in r['question'].lower() or "knapsack" in r['answer'].lower() for r in results))

    def test_revoked_entries_never_returned(self):
        # Create a revoked entry matching a unique term
        QABankEntry.objects.create(
            entry_id="TEST-REV-999",
            domain="Cybersecurity",
            topic="Revoked Topic",
            question="What is QuantumX999 protocol?",
            answer="QuantumX999 model answer.",
            provenance="reported",
            verification_status="revoked",
            is_active=True
        )

        results = self.retrieval.search("QuantumX999", top_k=3)
        # Should not be returned because verification_status == 'revoked'
        revoked_ids = [r['entry_id'] for r in results]
        self.assertNotIn("TEST-REV-999", revoked_ids)

    def test_insufficient_evidence_handling(self):
        # Searching for something completely unrelated with high min_score should return empty
        results = self.retrieval.search("xyzzqwerty completely unrelated Martian biology query", top_k=3, min_score=10)
        self.assertEqual(len(results), 0)
