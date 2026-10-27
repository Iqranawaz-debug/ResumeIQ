"""Additional synthetic browser fixtures, written only to ignored QA output."""
from pathlib import Path
from docx import Document
from browser_fixtures import fixtures, TEXT

if __name__ == '__main__':
    fixtures()
    dest = Path(__file__).resolve().parents[2] / 'test-results' / 'phase6'
    dest.mkdir(parents=True, exist_ok=True)
    for index in range(1, 6):
        doc = Document()
        surname = ['One', 'Two', 'Three', 'Four', 'Five'][index - 1]
        text = TEXT.replace('Alex Example', f'Morgan Example {surname}').replace('alex@example.invalid', f'morgan{index}@example.invalid')
        for line in text.splitlines(): doc.add_paragraph(line)
        doc.save(dest / f'candidate-{index}.docx')
