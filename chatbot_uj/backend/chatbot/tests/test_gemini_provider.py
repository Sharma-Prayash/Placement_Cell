from django.test import TestCase
from unittest.mock import patch, MagicMock
from chatbot.gemini_provider import GeminiProvider


class GeminiProviderTestCase(TestCase):
    """Verifies Gemini provider configuration, mock generation, and fallback."""

    def test_provider_disabled_or_missing_key(self):
        provider = GeminiProvider(api_key="", model="gemini-2.5-flash")
        self.assertFalse(provider.is_available())
        response = provider.generate_response("test", [], "sys")
        self.assertIsNone(response)

    @patch('google.genai.Client')
    def test_mock_successful_generation(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is a grounded mock explanation."
        mock_client.models.generate_content.return_value = mock_response

        provider = GeminiProvider(api_key="valid-dummy-key", model="gemini-2.5-flash")
        provider._client = mock_client

        context = [{"company": "Google", "topic": "QUIC", "question": "Q", "answer": "A", "provenance": "reported"}]
        result = provider.generate_response("Explain QUIC", context)
        self.assertEqual(result, "This is a grounded mock explanation.")

    @patch('google.genai.Client')
    def test_resilient_error_handling(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("Quota Exceeded (HTTP 429)")

        provider = GeminiProvider(api_key="valid-dummy-key", model="gemini-2.5-flash")
        provider._client = mock_client

        # Should catch error gracefully and return None (triggering deterministic fallback)
        result = provider.generate_response("Explain QUIC", [])
        self.assertIsNone(result)
