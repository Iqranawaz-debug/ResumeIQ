"""Conservative line-oriented employment and project extraction."""
import re
from utils.employment_dates import split_date, interval

BULLET = re.compile(r'^\s*[•●▪*\-]\s+')
ROLE = re.compile(r'\b(intern|assistant|engineer|developer|manager|analyst|consultant|specialist|director|officer|coordinator|teacher|professor|nurse|physician|accountant|designer|technician|clerk|supervisor|associate|researcher|freelance|contractor|apprentice|chef|lawyer|administrator|representative|role)\b', re.I)
ORG = re.compile(r'\b(inc|ltd|llc|company|corp|corporation|university|college|hospital|school|agency|services|foundation|institute|authority)\b', re.I)
ACTION = re.compile(r'^(built|developed|managed|led|mentored|supported|assisted|worked|created|implemented|automated|used|designed|delivered|responsible|performed|provided|taught|maintained|improved|collaborated)\b', re.I)


def header(text):
    return bool(text and len(text.split()) <= 16 and not BULLET.match(text)
                and not ACTION.match(re.sub(r'^I\s+', '', text, flags=re.I))
                and not re.search(r'[;!?]|\.$', text.rstrip('. ') if ORG.search(text) else text))


def role(text):
    return header(text) and bool(ROLE.search(text))


def organization(text):
    return header(text) and bool(ORG.search(text)) and not role(text)


def details(lines):
    result = []
    for line in lines:
        if not line:
            continue
        bullet = bool(BULLET.match(line))
        value = BULLET.sub('', line)
        if result and not bullet and value[0].islower() and not re.search(r'[.!?]$', result[-1]):
            result[-1] += ' ' + value
        else:
            result.append(value)
    return result


def employment(lines):
    # Rejoin only explicit range continuations; never pair two lone dates.
    unwrapped = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if index + 1 < len(lines) and re.search(r'[-–—−]$', line):
            remainder, end = split_date(lines[index + 1])
            if end and not remainder:
                line += ' ' + lines[index + 1]
                index += 1
        elif index + 2 < len(lines) and lines[index + 1] in ('-', '–', '—', '−'):
            remainder, start = split_date(line)
            end_text, end = split_date(lines[index + 2])
            if start and not remainder and end and not end_text:
                line += ' ' + lines[index + 1] + ' ' + lines[index + 2]
                index += 2
        unwrapped.append(line)
        index += 1
    lines = unwrapped
    entries, current = [], None
    following, next_nonempty = [''] * len(lines), ''
    for index in range(len(lines) - 1, -1, -1):
        following[index] = next_nonempty
        if lines[index]:
            next_nonempty = lines[index]

    def new():
        entry = {'title': None, 'organization': None, 'duration': None, 'details': []}
        entries.append(entry)
        return entry

    for index, line in enumerate(lines):
        if not line:
            continue
        text, duration = split_date(line)
        is_header = header(text) or not text
        # Bullets and prose containing dates stay descriptions.
        if not is_header:
            if current is None:
                current = new()
            current['details'].append(line)
            continue
        parts = [p.strip() for p in re.split(r'\s+[|–—]\s+|\s+at\s+|,\s*', text) if p.strip()]
        roles = [p for p in parts if role(p)]
        orgs = [p for p in parts if organization(p)]
        next_line = following[index]
        next_text, next_date = split_date(next_line)
        begins = bool(roles or orgs or duration or (header(text) and next_date and not next_text))
        if not begins and role(next_text) and header(text) and not current:
            current = new()
            current['header_lines'] = [text]
            continue
        if begins:
            # A header can continue only until a date or descriptions close it.
            if current is None or current['details'] or current['duration'] or (roles and current['title']) or (orgs and current['organization']):
                current = new()
            if roles:
                current['title'] = ' '.join(roles)
                # Common wrapped title prefixes are explicit modifiers, not employers.
                prefix = current.get('header_lines', [])
                if len(prefix) == 1 and re.fullmatch(r'(?:Senior|Junior|Lead|Principal|Staff|Part-time|Full-time)(?: Software)?', prefix[0], re.I):
                    current['title'] = prefix[0] + ' ' + current['title']
                    del current['header_lines']
                remaining = [p for p in parts if p not in roles]
                if remaining:
                    current['organization'] = ', '.join(remaining)
            elif orgs:
                current['organization'] = text
            elif text and current['title']:
                current.setdefault('header_lines', []).append(text)
            elif text:
                # Unknown dated headings remain verbatim, with no guessed organization.
                current['title'] = text
            if duration:
                current['duration'] = duration
                current['date_status'] = interval(duration)[1]
        elif current and not current['duration'] and not current['details'] and current['title']:
            # Unlabelled employer is ambiguous: preserve it as header text.
            current.setdefault('header_lines', []).append(text)
        else:
            if current is None:
                current = new()
            current['details'].append(line)
    for entry in entries:
        entry['details'] = details(entry['details'])
    return entries


def projects(lines):
    entries, current = [], None
    for line in lines:
        if not line:
            current = None
            continue
        # A standalone date describes the current project, not another project.
        remainder, duration = split_date(line)
        if current is not None and duration and not remainder:
            current['details'].append(line)
            continue
        if current is None or (header(line) and not BULLET.match(line)):
            current = {'title': line if header(line) else None, 'details': []}
            entries.append(current)
            if current['title']:
                continue
        current['details'].append(line)
    for entry in entries:
        entry['details'] = details(entry['details'])
    return entries
