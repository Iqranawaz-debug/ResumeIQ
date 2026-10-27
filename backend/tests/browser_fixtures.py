"""Generate fictional documents into ignored test-results; no new packages."""
from pathlib import Path
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

DEST = Path(__file__).resolve().parents[2] / 'test-results' / 'phase51'
TEXT = '''Alex Example
alex@example.invalid
+1 202 555 0100
Skills
Python, SQL, React.js, sklearn, NLP, NodeJS, REST APIs, dotnet, C++, C#
Experience
Software Developer | Example Labs
Jan 2020 - Dec 2021
Utilized Python in order to prepare reports.
I maintained FastAPI services.
Experience
Data Analyst | Fictional Systems
Jan 2023 - Dec 2023
I helped with SQL testing.
Built reports using SQL.
Projects
Portfolio Dashboard
Jan 2024 - Dec 2024
Utilized React for charts.
Research Tool
Built a Python demonstration.
Education
BSc Computer Science, Example University, 2019
'''


def fixtures():
    DEST.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for line in TEXT.splitlines():
        doc.add_paragraph(line)
    doc.save(DEST / 'synthetic.docx')
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    lines = ['BT /F1 10 Tf 40 750 Td 14 TL']
    for line in TEXT.splitlines():
        escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        lines.append(f'({escaped}) Tj T*')
    lines.append('ET')
    stream.set_data('\n'.join(lines).encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(DEST / 'synthetic.pdf')


if __name__ == '__main__':
    fixtures()
