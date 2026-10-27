from io import BytesIO

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from utils import limits
from utils.upload import validate_format


def _iter_blocks(parent, element):
    """Keep paragraphs and tables in source order, including blank boundaries."""
    for child in element:
        if child.tag.endswith('}p'):
            yield Paragraph(child, parent).text
        elif child.tag.endswith('}tbl'):
            table = Table(child, parent)
            seen = set()
            for row in table.rows:
                for cell in row.cells:
                    if cell._tc not in seen:
                        seen.add(cell._tc)
                        yield from _iter_blocks(cell, cell._tc)


def extract_text_from_docx(file_bytes: bytes) -> str:
    validate_format("docx", file_bytes)
    document = Document(BytesIO(file_bytes))
    if sum(1 for _ in document.element.iter()) > limits.XML_NODES:
        raise limits.DocumentLimitError("DOCX structure exceeds the configured limit.")

    lines = list(_iter_blocks(document, document.element.body))

    return limits.bound_text("\n".join(lines).strip())
