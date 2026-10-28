"""How ResumeIQ read the document: deterministic, unscored readability findings.

Findings describe this parser's view of the file. Applicant tracking systems
differ, so nothing here is a compatibility guarantee.
"""
import re

from utils.employment_dates import interval

NOTE = ('These checks describe how ResumeIQ read this file. Applicant tracking systems '
        'differ, so they indicate possible risks, not guaranteed compatibility.')
CORE_SECTIONS = {'experience': 'Experience', 'education': 'Education', 'skills': 'Skills'}
EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE = re.compile(r'\+?\d[\d\-\s()]{7,}\d')
PRIVATE_USE = re.compile('[-]')


def _finding(code, severity, title, detail, fix):
    return {'id': code, 'severity': severity, 'title': title, 'detail': detail, 'fix': fix}


def document_checks(stats, text, candidate):
    stats = stats or {}
    findings, passed = [], []
    fmt = stats.get('format')
    pages = stats.get('pages')
    chars = len((text or '').strip())

    image_pages = stats.get('image_only_pages') or 0
    if image_pages:
        findings.append(_finding('image_pages', 'warning', f'{image_pages} page(s) appear to be images',
            'These pages contain images but almost no extractable text, so their content was not read.',
            'Export the resume from your editor as a text-based PDF rather than scanning or printing to image.'))
    elif fmt == 'pdf':
        passed.append('Text was extracted from every page.')

    if pages and chars / pages < 400:
        findings.append(_finding('low_text', 'warning', 'Little text was extracted',
            f'About {chars // max(pages, 1)} characters per page were read, which is unusually low for a resume.',
            'Check that the text is real text (selectable in a PDF viewer), not graphics or outlined fonts.'))

    hidden = stats.get('header_footer_text') or ''
    if hidden:
        missing_contact = [label for label, key, pattern in (('email', 'email', EMAIL), ('phone number', 'phone', PHONE))
                           if pattern.search(hidden) and not candidate.get(key)]
        if missing_contact:
            findings.append(_finding('contact_in_header', 'warning', 'Contact details appear to be in the header or footer',
                f'Your {" and ".join(missing_contact)} seem to be in a page header/footer, which ResumeIQ does not read; some ATS parsers skip them too.',
                'Move your name and contact details into the main body at the top of the page.'))
        else:
            findings.append(_finding('header_footer', 'info', 'Header or footer text was not read',
                'Text placed in page headers or footers is excluded from extraction.',
                'Keep important information in the main body of the document.'))

    if stats.get('text_boxes'):
        findings.append(_finding('text_boxes', 'warning', f'{stats["text_boxes"]} text box(es) found',
            'Text inside text boxes or shapes is not read by ResumeIQ and is often skipped by ATS parsers.',
            'Move that content into normal paragraphs.'))
    if stats.get('tables'):
        findings.append(_finding('tables', 'info', f'{stats["tables"]} table(s) used',
            'Table content was read cell by cell. Some parsers flatten tables in a different order, which can mix up columns.',
            'For maximum portability, prefer a single-column layout without tables.'))

    glyphs = len(PRIVATE_USE.findall(text or ''))
    if glyphs >= 3:
        findings.append(_finding('icon_glyphs', 'info', 'Icon or symbol characters were extracted',
            f'{glyphs} unreadable symbol characters were found, usually from icon fonts beside contact details.',
            'Replace icons with plain-text labels such as "Email:" and "Phone:".'))

    lines = [line.strip() for line in (text or '').splitlines() if line.strip()]
    if len(lines) >= 30 and sum(len(line.split()) <= 2 for line in lines) / len(lines) > 0.55:
        findings.append(_finding('fragmented', 'info', 'Text may have been read out of order',
            'Many extracted lines are one or two words long, which often happens with multi-column layouts.',
            'A single-column layout is read more predictably.'))

    absent = [label for label, key in (('email', 'email'), ('phone number', 'phone')) if not candidate.get(key)]
    if absent:
        findings.append(_finding('missing_contact', 'warning', 'Contact details not found',
            f'No {" or ".join(absent)} was found in the extracted text.',
            'Add contact details as plain text near the top of the resume.'))
    else:
        passed.append('Email and phone number were found.')

    detected = set(candidate.get('detected_sections') or [])
    unrecognized = [label for key, label in CORE_SECTIONS.items() if key not in detected]
    if unrecognized:
        findings.append(_finding('headings', 'warning', 'Standard section headings not recognized',
            f'No heading was recognized for: {", ".join(unrecognized)}. Content under unusual headings may not be categorized.',
            'Use conventional headings such as "Experience", "Education" and "Skills".'))
    else:
        passed.append('Standard Experience, Education and Skills headings were recognized.')

    entries = candidate.get('experience') or []
    unclear = sum(interval(entry.get('duration'))[0] is None for entry in entries)
    if unclear:
        findings.append(_finding('dates', 'info', f'{unclear} employment date range(s) could not be read',
            'Missing, single or mixed-format dates prevent calculating experience length.',
            'Use a consistent range format such as "Jan 2021 – Mar 2023" or "2021 – Present".'))
    elif entries:
        passed.append('All employment date ranges were readable.')

    if pages and pages > 3:
        findings.append(_finding('length', 'info', f'{pages} pages',
            'Longer resumes are fine for some roles, but reviewers often skim.',
            'Consider whether every section is relevant to the roles you target.'))

    order = {'warning': 0, 'info': 1}
    findings.sort(key=lambda item: order[item['severity']])
    return {'version': 1, 'note': NOTE, 'format': fmt, 'pages': pages, 'characters': chars,
            'findings': findings, 'passed': passed}
