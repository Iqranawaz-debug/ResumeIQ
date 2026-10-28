"""Resource limits, read once at startup. Invalid configuration fails fast."""
import os


def positive_int(name, default):
    value = int(os.environ.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


RESUME_BYTES = positive_int("MAX_RESUME_BYTES", 10 * 1024**2)
JD_BYTES = positive_int("MAX_JD_BYTES", 2 * 1024**2)
REQUEST_BYTES = positive_int("MAX_REQUEST_BYTES", max(RESUME_BYTES, JD_BYTES) + 1024**2)
TEXT_CHARS = positive_int("MAX_TEXT_CHARS", 100_000)
PDF_PAGES = positive_int("MAX_PDF_PAGES", 50)
ZIP_ENTRIES = positive_int("MAX_DOCX_ENTRIES", 1000)
ZIP_BYTES = positive_int("MAX_DOCX_EXPANDED_BYTES", 20 * 1024**2)
XML_NODES = positive_int("MAX_DOCX_NODES", 50_000)


class DocumentLimitError(ValueError):
    pass


class UnreadableDocument(ValueError):
    """A document problem whose message is safe and useful to show the user."""


def bound_text(text):
    if len(text) > TEXT_CHARS:
        raise DocumentLimitError("Document text exceeds the configured limit.")
    return text
