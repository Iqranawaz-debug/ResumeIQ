import os

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b:free"
MODEL = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
REQUEST_TIMEOUT_SECONDS = 20.0


def get_client() -> OpenAI:
    """Build an OpenRouter client. Raises if OPENROUTER_API_KEY isn't set,
    so callers relying on the rule-based fallback see a clean failure.

    A capped timeout keeps a congested free-tier queue from stalling the
    upload/analyze request for a long time — a slow call fails fast and
    falls back to the rule-based path instead."""
    api_key = os.environ["OPENROUTER_API_KEY"].strip()
    if not api_key:
        # An empty value is "not configured", not a provider outage.
        raise KeyError("OPENROUTER_API_KEY")
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,
    )
