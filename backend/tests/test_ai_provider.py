"""Configurable OpenAI-compatible provider (OpenRouter default, Gemini direct).
No network: the OpenAI client class is replaced with a mock."""
import os
from unittest.mock import patch

from ai import openrouter_client as client
from evaluator.analyzer import analyze_resume_for_job
from network_guard import OfflineTestCase

GEMINI = 'https://generativelanguage.googleapis.com/v1beta/openai/'
CLEAN = {'AI_API_KEY': '', 'OPENROUTER_API_KEY': '', 'AI_BASE_URL': '', 'AI_MODEL': '', 'OPENROUTER_MODEL': ''}


class ProviderConfigTests(OfflineTestCase):
    def env(self, **values):
        return patch.dict(os.environ, CLEAN | values)

    def test_defaults_to_openrouter_and_local_fallback(self):
        with self.env():
            self.assertEqual(client.base_url(), client.OPENROUTER_BASE_URL)
            self.assertEqual(client.configured_model(), client.DEFAULT_MODEL)
            self.assertFalse(client.is_configured())
            with self.assertRaises(KeyError):  # Existing fallback paths catch KeyError.
                client.get_client()

    def test_new_key_takes_precedence_and_old_names_still_work(self):
        with self.env(OPENROUTER_API_KEY='old-key', OPENROUTER_MODEL='old/model'):
            self.assertEqual((client.api_key(), client.configured_model()), ('old-key', 'old/model'))
        with self.env(AI_API_KEY='new-key', OPENROUTER_API_KEY='old-key', AI_MODEL='new-model', OPENROUTER_MODEL='old/model'):
            self.assertEqual((client.api_key(), client.configured_model()), ('new-key', 'new-model'))
        with self.env(AI_API_KEY='   '):
            self.assertFalse(client.is_configured())

    def test_gemini_endpoint_is_used_directly(self):
        with self.env(AI_API_KEY='gemini-key', AI_BASE_URL=GEMINI), patch.object(client, 'OpenAI') as openai:
            client.get_client()
        kwargs = openai.call_args.kwargs
        self.assertEqual((kwargs['base_url'], kwargs['api_key'], kwargs['max_retries']), (GEMINI, 'gemini-key', 0))
        with self.env(AI_BASE_URL=GEMINI):
            self.assertEqual(client.provider_name(), 'Google Gemini')

    def test_provider_names(self):
        for url, name in ((client.OPENROUTER_BASE_URL, 'OpenRouter'), ('https://api.openai.com/v1', 'OpenAI'),
                          ('https://llm.example.test/v1', 'llm.example.test')):
            with self.subTest(url=url), self.env(AI_BASE_URL=url):
                self.assertEqual(client.provider_name(), name)

    def test_plain_http_endpoints_are_refused(self):
        with self.env(AI_API_KEY='key', AI_BASE_URL='http://llm.example.test/v1'), patch.object(client, 'OpenAI') as openai:
            with self.assertRaises(client.AIConfigurationError):
                client.get_client()
        openai.assert_not_called()

    def test_misconfiguration_falls_back_with_a_clear_note(self):
        candidate = {'skills': ['Python'], 'experience': [], 'education': []}
        with self.env(AI_API_KEY='key', AI_BASE_URL='http://llm.example.test/v1'):
            result = analyze_resume_for_job(candidate, 'Python, Docker')
        self.assertEqual((result['ai_status'], result['job_fit_method']), ('fallback', 'rule-based'))
        self.assertIn('invalid AI_BASE_URL', result['processing_note'])
