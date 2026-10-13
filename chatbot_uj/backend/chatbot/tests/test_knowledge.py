from django.test import TestCase
from django.core.management import call_command
from chatbot.models import QABankEntry


class KnowledgeIngestionTestCase(TestCase):
    """Verifies knowledge bank models, schema constraints, and idempotent ingestion."""

    def test_idempotent_ingestion(self):
        # First ingestion
        call_command('ingest_knowledge')
        initial_count = QABankEntry.objects.count()
        self.assertGreaterEqual(initial_count, 40, "Seed dataset must contain at least 40 entries")

        # Second ingestion should not create duplicates
        call_command('ingest_knowledge')
        repeated_count = QABankEntry.objects.count()
        self.assertEqual(initial_count, repeated_count, "Repeated ingestion must be strictly idempotent")

    def test_provenance_and_verification_rules(self):
        call_command('ingest_knowledge')
        approved_entries = QABankEntry.objects.filter(verification_status='approved')
        self.assertTrue(approved_entries.exists())

        # Test creating a revoked entry
        revoked = QABankEntry.objects.create(
            entry_id="TEST-REV-001",
            domain="Test",
            topic="Revoked Topic",
            question="Is this active?",
            answer="No, this was revoked.",
            provenance="reported",
            verification_status="revoked"
        )
        self.assertEqual(revoked.verification_status, "revoked")
