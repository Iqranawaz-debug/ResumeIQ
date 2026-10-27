"""Recognize written dates; quantify only ranges with compatible precision."""
import re
from datetime import date

MONTH = r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
YEAR = r'(?:19|20)\d{2}'
POINT = rf'(?:{MONTH}\.?\s+{YEAR}|\d{{1,2}}/{YEAR}|{YEAR})'
DATE_PATTERN = re.compile(rf'(?<!\w)(?:{POINT}\s*[-–—−]\s*(?:{POINT}|Present|Current)|(?:Fall|Autumn|Spring|Summer|Winter)\s+{YEAR}|{POINT})(?!\w)', re.I)
MONTHS = {name: i for i, name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'), 1)}


def split_date(text):
    match = DATE_PATTERN.search(text)
    if not match:
        return text, None
    # Dates embedded in prose are not header anchors.
    return (text[:match.start()] + text[match.end():]).strip(' ()|,–—-'), match.group()


def interval(duration, today=None):
    """Return month coordinates and status. Year ranges retain year precision.

    Endpoints are elapsed-time boundaries, not inclusive months. Seasons,
    single dates and mixed precision cannot establish a reliable duration.
    """
    today = today or date.today()
    parts = re.split(r'\s*[-–—−]\s*', duration or '')
    if len(parts) != 2:
        return None, 'uncertain'

    def point(value):
        if re.fullmatch(YEAR, value):
            return int(value) * 12, 'year'
        match = re.fullmatch(rf'({MONTH})\.?\s+({YEAR})', value, re.I)
        if match:
            return int(match[2]) * 12 + MONTHS[match[1][:3].lower()] - 1, 'month'
        match = re.fullmatch(rf'(\d{{1,2}})/({YEAR})', value)
        if match and 1 <= int(match[1]) <= 12:
            return int(match[2]) * 12 + int(match[1]) - 1, 'month'
        return None, None

    start, precision = point(parts[0])
    if parts[1].lower() in ('present', 'current'):
        end, end_precision = today.year * 12 + (today.month - 1 if precision == 'month' else 0), precision
    else:
        end, end_precision = point(parts[1])
    if start is None or end is None:
        return None, 'invalid'
    if end < start:
        return None, 'invalid'
    if precision != end_precision:
        return None, 'uncertain'
    return (start, end), 'year' if precision == 'year' else 'month'
