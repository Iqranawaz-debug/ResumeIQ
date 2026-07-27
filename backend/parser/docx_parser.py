from io import BytesIO

from docx import Document


def _iter_table_text(table):
    """Yield paragraph text from every cell, recursing into nested tables —
    python-docx's own `document.paragraphs` skips table content entirely,
    which breaks table-based (e.g. two-column) resume layouts."""
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                if paragraph.text:
                    yield paragraph.text
            for nested_table in cell.tables:
                yield from _iter_table_text(nested_table)


def extract_text_from_docx(file_bytes: bytes) -> str:
    document = Document(BytesIO(file_bytes))

    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
    for table in document.tables:
        lines.extend(_iter_table_text(table))

    return "\n".join(lines).strip()
