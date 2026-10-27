from io import BytesIO
from pypdf import PdfReader
from utils import limits
from utils.upload import validate_format


def extract_text_from_pdf(file_bytes: bytes) -> str:
    validate_format("pdf", file_bytes)
    reader = PdfReader(BytesIO(file_bytes))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are unsupported.")
    if len(reader.pages) > limits.PDF_PAGES:
        raise limits.DocumentLimitError("PDF page count exceeds the configured limit.")
    parts, length = [], 0
    for page in reader.pages:
        text = page.extract_text() or ""
        length += len(text) + 1
        if length > limits.TEXT_CHARS:
            raise limits.DocumentLimitError("Document text exceeds the configured limit.")
        parts.append(text)
    return "\n".join(parts).strip()
