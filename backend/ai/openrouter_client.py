"""OpenAI-compatible AI client. OpenRouter by default; any compatible provider
(for example Google Gemini's OpenAI endpoint) via AI_BASE_URL.

Configuration (all optional; without a key, AI features fall back to local rules):
  AI_API_KEY        provider key (OPENROUTER_API_KEY is still accepted)
  AI_BASE_URL       provider endpoint, default https://openrouter.ai/api/v1
  AI_MODEL          model ID for that provider (OPENROUTER_MODEL is still accepted)
"""
import os
from urllib.parse import urlparse

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"
def configured_model() -> str:
    return (os.environ.get("AI_MODEL", "").strip() or os.environ.get("OPENROUTER_MODEL", "").strip()
            or DEFAULT_MODEL)


MODEL = configured_model()
REQUEST_TIMEOUT_SECONDS = 20.0
KNOWN_PROVIDERS = {"openrouter.ai": "OpenRouter", "generativelanguage.googleapis.com": "Google Gemini",
                   "api.openai.com": "OpenAI"}


class AIConfigurationError(KeyError):
    """Missing key or unusable provider settings (reported as "not configured")."""


def base_url() -> str:
    return os.environ.get("AI_BASE_URL", "").strip() or OPENROUTER_BASE_URL


def api_key() -> str:
    return (os.environ.get("AI_API_KEY", "").strip()
            or os.environ.get("OPENROUTER_API_KEY", "").strip())


def is_configured() -> bool:
    return bool(api_key())


def provider_name() -> str:
    """Human-readable provider for privacy notices (no key or path details)."""
    host = (urlparse(base_url()).hostname or "").lower()
    return KNOWN_PROVIDERS.get(host, host or "the configured AI provider")


def get_client() -> OpenAI:
    """Build a client for the configured provider. Raises KeyError when no key
    is set, so callers relying on the rule-based fallback see a clean failure.

    A capped timeout keeps a congested provider queue from stalling the
    analyze request for a long time — a slow call fails fast and falls back to
    the rule-based path instead."""
    key = api_key()
    if not key:
        # An empty value is "not configured", not a provider outage.
        raise AIConfigurationError("AI_API_KEY")
    endpoint = base_url()
    if urlparse(endpoint).scheme != "https":
        # Resume details must not travel to a provider in clear text.
        raise AIConfigurationError("AI_BASE_URL must use https")
    return OpenAI(
        base_url=endpoint,
        api_key=key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
