"""Normalization for short user-entered text (recruiter notes and tags).

Stored as plain text; the frontend escapes on render. Cleaning removes control
and bidirectional-override characters (which can disguise content), normalizes
Unicode compatibility forms and trims whitespace. Length checks happen after
cleaning, so invisible characters cannot pad past a limit.
"""
import re
import unicodedata

# C0/C1 controls except tab/newline, zero-width and bidi override/isolate marks.
UNSAFE = re.compile('[\x00-\x08\x0b-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]')
TAG_PATTERN = re.compile(r"[\w][\w +#.&'-]*", re.UNICODE)


def clean_note(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).replace('\r\n', '\n').replace('\r', '\n').replace('\t', ' ')
    value = UNSAFE.sub('', value)
    lines = [' '.join(line.split()) for line in value.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def clean_tag(value: str) -> str:
    value = UNSAFE.sub('', unicodedata.normalize('NFKC', value))
    return ' '.join(value.split())


def valid_tag(value: str) -> bool:
    """Letters, digits, spaces and + # . & ' - _ ; must start with a letter or digit.
    No slash, so a tag is always safe as a single URL path segment."""
    return bool(TAG_PATTERN.fullmatch(value)) and not value.startswith('_')
