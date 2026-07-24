from parser.docx_parser import extract_text_from_docx
from parser.pdf_parser import extract_text_from_pdf


def parse_resume(filename: str, file_bytes: bytes) -> str:
    """Convert a resume file (PDF or DOCX) into plain text."""
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension == "pdf":
        return extract_text_from_pdf(file_bytes)
    if extension == "docx":
        return extract_text_from_docx(file_bytes)

    raise ValueError(f"Unsupported file type: {extension}")
