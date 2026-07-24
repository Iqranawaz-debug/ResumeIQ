from parser.docx_parser import extract_text_from_docx
from parser.pdf_parser import extract_text_from_pdf


def parse_document(filename: str, file_bytes: bytes) -> str:
    """Convert a PDF, DOCX, or plain text file into plain text.

    Used for freeform documents (like a job description) that aren't
    necessarily a resume, so plain .txt is also accepted.
    """
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension == "pdf":
        return extract_text_from_pdf(file_bytes)
    if extension == "docx":
        return extract_text_from_docx(file_bytes)
    if extension == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {extension}")
