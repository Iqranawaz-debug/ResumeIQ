from io import BytesIO
from pypdf import PdfReader
from utils import limits
from utils.upload import validate_format


def _has_images(page):
    try:
        objects = page["/Resources"].get_object().get("/XObject")
        objects = objects.get_object() if objects is not None else {}
        return any(objects[name].get_object().get("/Subtype") == "/Image" for name in objects)
    except Exception:
        return False


def extract_text_from_pdf(file_bytes: bytes, stats: dict | None = None) -> str:
    """Extract text; optionally record per-page layout stats for document checks."""
    validate_format("pdf", file_bytes)
    reader = PdfReader(BytesIO(file_bytes))
    if reader.is_encrypted:
        raise limits.UnreadableDocument("Encrypted (password-protected) PDFs are not supported. Remove the password and upload it again.")
    if len(reader.pages) > limits.PDF_PAGES:
        raise limits.DocumentLimitError("PDF page count exceeds the configured limit.")
    parts, length, page_chars, image_pages = [], 0, [], 0
    for page in reader.pages:
        text = page.extract_text() or ""
        length += len(text) + 1
        if length > limits.TEXT_CHARS:
            raise limits.DocumentLimitError("Document text exceeds the configured limit.")
        parts.append(text)
        page_chars.append(len(text.strip()))
        if stats is not None and len(text.strip()) < 30 and _has_images(page):
            image_pages += 1
    if stats is not None:
        stats.update(format="pdf", pages=len(reader.pages), page_chars=page_chars, image_only_pages=image_pages)
    return "\n".join(parts).strip()
