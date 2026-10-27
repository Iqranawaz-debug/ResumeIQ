from io import BytesIO

from docx import Document
from docx.oxml.ns import qn
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


def _part_text(part):
    return " ".join(node.text or "" for node in part._element.iter(qn("w:t"))).strip()


def extract_text_from_docx(file_bytes: bytes, stats: dict | None = None) -> str:
    """Extract body text; optionally record content this parser does not read."""
    validate_format("docx", file_bytes)
    document = Document(BytesIO(file_bytes))
    if sum(1 for _ in document.element.iter()) > limits.XML_NODES:
        raise limits.DocumentLimitError("DOCX structure exceeds the configured limit.")

    lines = list(_iter_blocks(document, document.element.body))

    if stats is not None:
        # Headers, footers and text boxes are not part of the extracted body text.
        hidden = []
        for section in document.sections:
            for part in (section.header, section.footer, section.first_page_header, section.first_page_footer):
                if not part.is_linked_to_previous:
                    text = _part_text(part)
                    if text and text not in hidden:
                        hidden.append(text)
        body = document.element.body
        stats.update(format="docx", tables=sum(1 for _ in body.iter(qn("w:tbl"))),
                     text_boxes=sum(1 for _ in body.iter(qn("w:txbxContent"))),
                     header_footer_text=" ".join(hidden)[:2000])

    return limits.bound_text("\n".join(lines).strip())
