"""Minimize provider payloads; best-effort redaction is not anonymization."""
import re


def redact_text(text, candidate=None):
    for field in ("name", "email", "phone"):
        value = (candidate or {}).get(field)
        if value:
            text = re.sub(re.escape(value), "[redacted]", text, flags=re.I)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
    text = re.sub(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)", "[phone]", text)
    return text


def candidate_payload(candidate):
    def clean(value):
        if isinstance(value, str):
            return redact_text(value, candidate)
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k in {"title", "duration", "details"}}
        return value
    return {key: clean(candidate.get(key) or []) for key in ("skills", "education", "experience")}
