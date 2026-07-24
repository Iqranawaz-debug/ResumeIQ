import os

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "openai/gpt-oss-20b:free"


def get_client() -> OpenAI:
    """Build an OpenRouter client. Raises if OPENROUTER_API_KEY isn't set,
    so callers relying on the rule-based fallback see a clean failure."""
    api_key = os.environ["OPENROUTER_API_KEY"]
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)
